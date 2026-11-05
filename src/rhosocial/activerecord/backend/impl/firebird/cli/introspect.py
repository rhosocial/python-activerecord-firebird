# src/rhosocial/activerecord/backend/impl/firebird/cli/introspect.py
"""introspect subcommand - Database introspection.

There is no namespace flag here, and that is deliberate. Firebird has a
single unnamed namespace: every object lives in the one database the
connection opens, and Firebird never qualifies a name with anything above
it. An earlier version accepted ``--schema``, which named something that
does not exist here; it is gone rather than aliased, so a caller cannot
ask for a level the engine cannot express.

**The families beyond the catalogue.** Beside the schema structure this
backend answers two more kinds of question, and each is a type here:

* the *operational* families -- how the server is behaving rather than
  what it contains (unused indexes, usage counters, runtime metrics);
* the *row* families -- what the data holds rather than what the
  declaration promises (a column's profile, its most frequent values,
  how much two columns' value domains overlap).

Firebird answers the row families from the table itself: it keeps no
per-column statistics catalogue, so a profile is one aggregate over the
rows and a value listing is one grouped read. Both are exact and both are
paid for in time. The operational families Firebird *declines* -- its
catalogue describes objects, not a statistics collector, and there is no
``RDB$`` relation answering for any of them. Those types are offered
anyway and gated: the capability switch they name answers ``False`` on
this dialect, so a run is refused with "this server cannot answer that"
rather than reaching a statement the engine has no formatter for. That
distinction is the whole point of the mapping below -- an offered type
with an unanswered switch is a contract the CLI keeps by refusing, not by
producing an empty row that reads like an answer of zero.
"""

import argparse
import asyncio
import sys
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from rhosocial.activerecord.backend.impl.firebird.backend import FirebirdBackend
from rhosocial.activerecord.backend.impl.firebird.backend.async_backend import AsyncFirebirdBackend
from rhosocial.activerecord.backend.errors import ConnectionError, QueryError

from .connection import add_connection_args, resolve_connection_config_from_args, warn_if_async_requested
from .output import create_provider

OUTPUT_CHOICES = ["table", "json", "csv", "tsv"]

#: CLI type -> the dialect capability switch that answers for it.
#:
#: The advertised list is derived from this mapping, so adding a family to one
#: place and forgetting it in the other cannot happen. A type whose switch is
#: False on the *connected* server is refused when handled, rather than run and
#: answered with an empty list -- "this server has no publications" and "this
#: database has none" are different answers.
#:
#: One entry per item the catalogue reports independently: a family Firebird
#: answers as its own row set gets its own type, and no type covers two of them.
#: Procedure parameters and function arguments are separate relations from the
#: routines they belong to, so they are separate dimensions too.
_TYPE_CAPABILITIES = {
    "tables": "supports_table_introspection",
    "views": "supports_view_introspection",
    "columns": "supports_column_introspection",
    "indexes": "supports_index_introspection",
    "foreign-keys": "supports_foreign_key_introspection",
    "triggers": "supports_trigger_introspection",
    "database": "supports_database_info",
    "generators": "supports_generator_introspection",
    "domains": "supports_domain_introspection",
    "exceptions": "supports_exception_introspection",
    "procedures": "supports_procedure_introspection",
    "procedure-parameters": "supports_procedure_introspection",
    "functions": "supports_function_introspection",
    "function-arguments": "supports_function_introspection",
    "constraints": "supports_constraint_introspection",
    "roles": "supports_role_introspection",
    "privileges": "supports_privilege_introspection",
    "charsets": "supports_charset_introspection",
    "collations": "supports_collation_introspection",
    "dependencies": "supports_dependency_introspection",
    "view-relations": "supports_view_relation_introspection",
    "publications": "supports_publication_introspection",
    # ---- the four operational families ------------------------------
    # Read from a statistics collector rather than the catalogue: how the
    # server is behaving, not what it contains. Firebird has no collector
    # and no ``RDB$`` relation standing in for one, so each switch answers
    # False and the gate refuses the type. They are offered rather than
    # omitted because the dialect's answer is "this engine cannot tell
    # you", which is a fact worth letting a caller ask for and be told.
    "unused-indexes": "supports_unused_indexes_detection",
    "table-stats": "supports_table_stats",
    "runtime": "supports_runtime_stats",
    "index-stats": "supports_index_stats",
    # ---- the one-object families ------------------------------------
    # ``ddl`` uses ``supports_ddl_extraction``, the switch every backend
    # answers for "can you rebuild this object's text"; it is False here
    # because Firebird retrieves a source body from ``RDB$`` rather than
    # assembling a full ``CREATE`` statement, and an assembled fragment
    # would read as authoritative. ``dependencies`` above already names
    # the dependency family -- answered from ``RDB$DEPENDENCIES`` -- so it
    # is not repeated under the common switch.
    "ddl": "supports_ddl_extraction",
    # ---- the row families -------------------------------------------
    # What the data holds rather than what the column declares. All three
    # answer True here: they read the table itself, and the cost is a
    # scan, which is time rather than money on this engine.
    "column-profiles": "supports_column_data_profile",
    "value-samples": "supports_column_value_sample",
    "join-coverage": "supports_join_coverage",
}

INTROSPECT_TYPES = list(_TYPE_CAPABILITIES)


def _require_capability(backend, args) -> None:
    """Refuse a type the connected server cannot answer.

    The dialect is adapted before this runs, so the switches answer for the
    server in front of us rather than for the newest release this backend
    knows.
    """
    switch = _TYPE_CAPABILITIES.get(args.type)
    if switch is None:
        return
    dialect = getattr(backend, "dialect", None)
    if dialect is None:
        # A stub standing in for the backend (the offline CLI tests) has no
        # dialect to ask; a real one always does.
        return
    supported = getattr(dialect, switch, None)
    if supported is None or supported():
        return
    print(
        f"Error: {args.type} introspection is not supported by this server",
        file=sys.stderr,
    )
    sys.exit(2)


def _refuse_name(args: argparse.Namespace, hint: str) -> None:
    """Refuse a ``NAME`` the type has no question for.

    The operational families describe the database as a whole: dropping the
    name instead would print the family listing under a one-object
    question, which is a different answer than the one asked for.
    """
    print(f"Error: '{args.type}' does not take an object name; {hint}", file=sys.stderr)
    sys.exit(2)


def _display_ddl(provider, statement, args) -> None:
    """Show a DDL statement in the form that stays readable.

    A ``CREATE TABLE`` is text: a one-row table folds it into a cell that
    wraps at the terminal width and interleaves with the other columns.
    Table output therefore prints the statement itself, while the
    structured formats keep the whole row so JSON and CSV still carry
    ``object_type`` and ``native`` beside the text.
    """
    if args.output == "table":
        print(statement.ddl or "")
        return
    data = _serialize_for_output([statement])
    provider.display_results(data, title=f"DDL of {statement.object_name}")


def _refuse_unused_arguments(args: argparse.Namespace) -> None:
    """Refuse a flag the chosen type has no question for.

    The same defect as a silently dropped name, one flag over: ``--column``
    beside ``introspect tables`` would be ignored and the listing printed as
    if the column had been part of the question. Only the two families whose
    probe takes a column read ``--column``, and only ``join-coverage`` reads
    the two right-hand names, so only they may be given them.

    Read with ``getattr`` because the handler is also driven with hand-built
    namespaces (the offline tests), which carry no flags at all -- an absent
    attribute is "not given", not an error.
    """
    column = getattr(args, "column", None)
    right_table = getattr(args, "right_table", None)
    right_column = getattr(args, "right_column", None)

    if column is not None and args.type not in ("value-samples", "join-coverage"):
        print(
            f"Error: '{args.type}' does not take --column; "
            "use 'value-samples' or 'join-coverage'",
            file=sys.stderr,
        )
        sys.exit(2)
    if (right_table is not None or right_column is not None) and args.type != "join-coverage":
        print(
            f"Error: '{args.type}' does not take --right-table or --right-column; "
            "use 'join-coverage'",
            file=sys.stderr,
        )
        sys.exit(2)


def _note_unmeasured_profiles(profiles, table_name: str) -> None:
    """Say which figures the engine declined to compute, on stderr.

    Firebird refuses ``MIN``, ``MAX`` and ``COUNT(DISTINCT ...)`` on a
    ``BLOB`` at prepare time, so a BLOB column's profile carries its null
    count and the table's row count and *nothing else*: those three slots
    arrive as ``None``, which means "this engine will not measure that
    about this type" rather than "it measured it as nothing". The row is
    kept and the figures are shown as they are; hiding the column would
    delete the one signal this family exists to deliver, and erroring
    would fail a run whose remaining figures are correct.

    The note goes to stderr so the machine formats stay parseable, exactly
    as the profile listing's own row does on stdout.
    """
    blind = [
        profile.column_name
        for profile in profiles
        if profile is not None
        and getattr(profile, "distinct_count", None) is None
        and getattr(profile, "min_value", None) is None
        and getattr(profile, "max_value", None) is None
    ]
    if not blind:
        return
    print(
        f"Note: {len(blind)} column(s) of {table_name} report no distinct "
        "count and no bounds -- Firebird refuses those aggregates on a type "
        "it cannot compare (BLOB), so the figures are not measured rather "
        f"than measured as empty: {', '.join(blind)}",
        file=sys.stderr,
    )


def create_parser(subparsers):
    """Create the introspect subcommand parser."""
    parser = subparsers.add_parser(
        "introspect",
        help="Database introspection",
        epilog="""Examples:
  # List all tables in database
  %(prog)s tables --database /path/to/test_db

  # List all views
  %(prog)s views --database /path/to/test_db

  # Get detailed table info (columns, indexes, foreign keys)
  %(prog)s table users --database /path/to/test_db

  # Get column details for a table
  %(prog)s columns users --database /path/to/test_db

  # List generators (sequences) with their current values, or one of them
  %(prog)s generators --database /path/to/test_db
  %(prog)s generators MY_GENERATOR --database /path/to/test_db

  # List domains, or one of them
  %(prog)s domains --database /path/to/test_db
  %(prog)s domains POSITIVE_INT --database /path/to/test_db

  # The operational families this engine declines -- refused, not empty
  %(prog)s unused-indexes --database /path/to/test_db
  %(prog)s table-stats --database /path/to/test_db
  %(prog)s runtime --database /path/to/test_db
  %(prog)s index-stats --database /path/to/test_db

  # What the rows hold, not what the columns declare
  %(prog)s column-profiles orders --database /path/to/test_db
  %(prog)s value-samples orders --column status --database /path/to/test_db
  %(prog)s ddl orders --database /path/to/test_db
  %(prog)s join-coverage orders --column customer_id --right-table customers \\
    --right-column id --database /path/to/test_db

  # Output as JSON
  %(prog)s tables --database /path/to/test_db -o json

  # Using environment variables for connection
  export FIREBIRD_HOST=localhost FIREBIRD_DATABASE=/path/to/test_db FIREBIRD_USER=root FIREBIRD_PASSWORD=secret
  %(prog)s tables
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Output format
    parser.add_argument(
        "-o",
        "--output",
        choices=OUTPUT_CHOICES,
        default="table",
        help="Output format (default: table)",
    )

    # Connection arguments
    add_connection_args(parser)

    # Rich display options
    parser.add_argument(
        "--rich-ascii",
        action="store_true",
        help="Use ASCII characters for rich table borders.",
    )

    # introspect-specific arguments
    parser.add_argument(
        "type",
        choices=INTROSPECT_TYPES,
        help="Introspection type: " + ", ".join(INTROSPECT_TYPES),
    )
    parser.add_argument(
        "name",
        nargs="?",
        default=None,
        help="Object name (required for some types, optional for most lists)",
    )
    # The flags the row families read. They stay flags rather than more
    # positionals because ``name`` already means "the table" everywhere
    # else, and ``value-samples orders.email`` would read as a dotted
    # object name. A type that reads none of them refuses them (see
    # :func:`_refuse_unused_arguments`) rather than parsing and dropping.
    parser.add_argument(
        "--column",
        default=None,
        help="Column name: the column to sample for value-samples, and the "
        "left column for join-coverage",
    )
    parser.add_argument(
        "--right-table",
        dest="right_table",
        default=None,
        help="Right-hand table for the join-coverage type",
    )
    parser.add_argument(
        "--right-column",
        dest="right_column",
        default=None,
        help="Right-hand column for the join-coverage type",
    )
    parser.add_argument(
        "--include-system",
        action="store_true",
        help="Include the objects Firebird itself owns",
    )
    parser.add_argument(
        "--object",
        default=None,
        metavar="NAME",
        help="Restrict grants to one object (privileges)",
    )
    parser.add_argument(
        "--grantee",
        default=None,
        metavar="NAME",
        help="Restrict grants to one grantee (privileges)",
    )
    parser.add_argument(
        "--constraint-type",
        dest="constraint_type",
        default=None,
        metavar="TYPE",
        help='Restrict constraints to one kind, e.g. "PRIMARY KEY" (constraints)',
    )

    return parser


def handle(args):

    warn_if_async_requested(args)

    """Handle the introspect subcommand."""
    provider = create_provider(args.output, ascii_borders=args.rich_ascii)

    if not getattr(args, "database", None):
        print("Error: --database is required for introspection", file=sys.stderr)
        sys.exit(1)

    config = resolve_connection_config_from_args(args)

    if getattr(args, "is_async", False):
        backend = AsyncFirebirdBackend(connection_config=config)
        asyncio.run(_handle_introspect_async(args, backend, provider))
    else:
        backend = FirebirdBackend(connection_config=config)
        _handle_introspect_sync(args, backend, provider)


# ---------------------------------------------------------------------------
# Internal helper functions
# ---------------------------------------------------------------------------


def _serialize_for_output(obj: Any) -> Any:
    """Serialize object for JSON output, handling non-serializable types."""
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        try:
            result = obj.model_dump(mode="json")
            return _serialize_for_output(result)
        except TypeError:
            result = obj.model_dump()
            return _serialize_for_output(result)
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _serialize_for_output(v) for k, v in asdict(obj).items()}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {k: _serialize_for_output(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize_for_output(item) for item in obj]
    if isinstance(obj, (str, int, float, bool)):
        return obj
    return str(obj)


def _handle_introspect_sync(args, backend: FirebirdBackend, provider):
    """Handle introspect subcommand synchronously."""
    try:
        backend.connect()
        # Adapting is part of answering, not setup: several formatters read the
        # dialect's version (and refuse to render on an unadapted one). Doing it
        # once here is what lets every branch below stay a plain question;
        # without it `table` and `database` raised DialectNotAdaptedException
        # while the other families happened to work.
        backend.introspect_and_adapt()
        _require_capability(backend, args)
        _refuse_unused_arguments(args)

        introspector = backend.introspector

        if args.type == "tables":
            tables = introspector.list_tables(schema=None, include_system=args.include_system)
            data = _serialize_for_output(tables)
            provider.display_results(data, title="Tables")

        elif args.type == "views":
            if args.name:
                view = introspector.get_view_info(args.name)
                if view is None:
                    print(f"Error: View '{args.name}' not found", file=sys.stderr)
                    sys.exit(1)
                provider.display_results(_serialize_for_output([view]), title=f"View {args.name}")
            else:
                views = introspector.list_views(schema=None)
                data = _serialize_for_output(views)
                provider.display_results(data, title="Views")

        elif args.type == "columns":
            if not args.name:
                print("Error: Table name is required for 'columns' introspection", file=sys.stderr)
                sys.exit(1)
            columns = introspector.list_columns(args.name, schema=None)
            data = _serialize_for_output(columns)
            provider.display_results(data, title=f"Columns of {args.name}")

        elif args.type == "indexes":
            if not args.name:
                print("Error: Table name is required for 'indexes' introspection", file=sys.stderr)
                sys.exit(1)
            indexes = introspector.list_indexes(args.name, schema=None)
            data = _serialize_for_output(indexes)
            provider.display_results(data, title=f"Indexes of {args.name}")

        elif args.type == "foreign-keys":
            if not args.name:
                print("Error: Table name is required for 'foreign-keys' introspection", file=sys.stderr)
                sys.exit(1)
            fks = introspector.list_foreign_keys(args.name, schema=None)
            data = _serialize_for_output(fks)
            provider.display_results(data, title=f"Foreign Keys of {args.name}")

        elif args.type == "triggers":
            triggers = introspector.list_triggers(table_name=args.name, schema=None)
            data = _serialize_for_output(triggers)
            provider.display_results(data, title="Triggers")

        elif args.type == "database":
            info = introspector.get_database_info()
            data = _serialize_for_output(info)
            provider.display_results([data], title="Database Info")

        elif args.type == "generators":
            if args.name:
                generator = introspector.get_generator_info(args.name)
                if generator is None:
                    print(f"Error: Generator '{args.name}' not found", file=sys.stderr)
                    sys.exit(1)
                provider.display_results(
                    [_serialize_for_output(generator)],
                    title=f"Generator {generator.name}",
                )
            else:
                generators = introspector.list_generators()
                provider.display_results(_serialize_for_output(generators), title="Generators")

        elif args.type == "domains":
            if args.name:
                domain = introspector.get_domain_info(args.name)
                if domain is None:
                    print(f"Error: Domain '{args.name}' not found", file=sys.stderr)
                    sys.exit(1)
                provider.display_results(
                    [_serialize_for_output(domain)], title=f"Domain {domain.name}"
                )
            else:
                domains = introspector.list_domains()
                provider.display_results(
                    _serialize_for_output(domains), title="Domains"
                )

        elif args.type == "exceptions":
            if args.name:
                found = introspector.get_exception_info(args.name)
                if found is None:
                    print(f"Error: Exception '{args.name}' not found", file=sys.stderr)
                    sys.exit(1)
                provider.display_results(
                    [_serialize_for_output(found)], title=f"Exception {found.name}"
                )
            else:
                provider.display_results(
                    _serialize_for_output(
                        introspector.list_exceptions(args.include_system)
                    ),
                    title="Exceptions",
                )

        elif args.type == "procedures":
            if args.name:
                found = introspector.get_procedure_info(args.name)
                if found is None:
                    print(f"Error: Procedure '{args.name}' not found", file=sys.stderr)
                    sys.exit(1)
                provider.display_results(
                    [_serialize_for_output(found)], title=f"Procedure {found.name}"
                )
            else:
                provider.display_results(
                    _serialize_for_output(
                        introspector.list_procedures(args.include_system)
                    ),
                    title="Procedures",
                )

        elif args.type == "procedure-parameters":
            if not args.name:
                print(
                    "Error: Procedure name is required for 'procedure-parameters'",
                    file=sys.stderr,
                )
                sys.exit(1)
            provider.display_results(
                _serialize_for_output(
                    introspector.list_procedure_parameters(args.name)
                ),
                title=f"Parameters of {args.name}",
            )

        elif args.type == "functions":
            if args.name:
                found = introspector.get_function_info(args.name)
                if found is None:
                    print(f"Error: Function '{args.name}' not found", file=sys.stderr)
                    sys.exit(1)
                provider.display_results(
                    [_serialize_for_output(found)], title=f"Function {found.name}"
                )
            else:
                provider.display_results(
                    _serialize_for_output(
                        introspector.list_functions(args.include_system)
                    ),
                    title="Functions",
                )

        elif args.type == "function-arguments":
            if not args.name:
                print(
                    "Error: Function name is required for 'function-arguments'",
                    file=sys.stderr,
                )
                sys.exit(1)
            provider.display_results(
                _serialize_for_output(introspector.list_function_arguments(args.name)),
                title=f"Arguments of {args.name}",
            )

        elif args.type == "constraints":
            provider.display_results(
                _serialize_for_output(
                    introspector.list_constraints(
                        args.name, args.constraint_type, args.include_system
                    )
                ),
                title="Constraints",
            )

        elif args.type == "roles":
            provider.display_results(
                _serialize_for_output(introspector.list_roles(args.include_system)),
                title="Roles",
            )

        elif args.type == "privileges":
            provider.display_results(
                _serialize_for_output(
                    introspector.list_privileges(
                        args.object, args.grantee, args.include_system
                    )
                ),
                title="Privileges",
            )

        elif args.type == "charsets":
            provider.display_results(
                _serialize_for_output(introspector.list_charsets()),
                title="Character sets",
            )

        elif args.type == "collations":
            provider.display_results(
                _serialize_for_output(introspector.list_collations(args.name)),
                title="Collations",
            )

        elif args.type == "dependencies":
            provider.display_results(
                _serialize_for_output(introspector.list_dependencies(args.name)),
                title="Dependencies",
            )

        elif args.type == "view-relations":
            provider.display_results(
                _serialize_for_output(introspector.list_view_relations(args.name)),
                title="View relations",
            )

        elif args.type == "publications":
            provider.display_results(
                _serialize_for_output(
                    introspector.list_publications(args.include_system)
                ),
                title="Publications",
            )

        # ---- the four operational families ----------------------------
        # They describe the database as a whole, not one object, so none
        # takes a name: ``unused-indexes`` asks which indexes the engine
        # reports as never having served a query, and the three counter
        # listings ask how much the rest have been used. All four are
        # refused by the gate on this backend, so these branches are the
        # contract rather than a path a real run reaches -- and they exist
        # so the refusal is a capability answer rather than an
        # NotImplementedError from a formatter the dialect does not have.

        elif args.type == "unused-indexes":
            if args.name:
                _refuse_name(args, "it describes every index in the database")
            indexes = introspector.list_unused_indexes(schema=None)
            data = _serialize_for_output(indexes)
            provider.display_results(data, title="Indexes with no recorded use")

        elif args.type == "table-stats":
            if args.name:
                _refuse_name(args, "it describes every table in the database")
            stats = introspector.list_table_usage_stats(schema=None)
            data = _serialize_for_output(stats)
            provider.display_results(data, title="Table usage counters")

        elif args.type == "runtime":
            if args.name:
                _refuse_name(args, "it describes the server, not one object")
            metrics = introspector.list_runtime_metrics(schema=None)
            data = _serialize_for_output(metrics)
            provider.display_results(data, title="Runtime metrics")

        elif args.type == "index-stats":
            if args.name:
                _refuse_name(args, "it describes every index in the database")
            stats = introspector.list_index_usage_stats(schema=None)
            data = _serialize_for_output(stats)
            provider.display_results(data, title="Index usage counters")

        # ---- the one-object families ----------------------------------
        # The DDL that recreates one table, and the profile of one table.
        # ``name`` is the table and required; the column a value listing
        # is about is named on its own flag.

        elif args.type == "ddl":
            if not args.name:
                print("Error: Table name is required for 'ddl' introspection", file=sys.stderr)
                sys.exit(1)
            statement = introspector.get_ddl_statement(args.name, object_type=None, schema=None)
            if statement is None:
                # Not "no such table": the object exists, and this engine
                # answers with no text rather than an assembled fragment
                # that would read as authoritative. The two are worth
                # telling apart, so this exits without printing an empty
                # row.
                print(
                    f"Error: no DDL available for '{args.name}' "
                    "(Firebird records a source body, not a rebuildable statement)",
                    file=sys.stderr,
                )
                sys.exit(1)
            _display_ddl(provider, statement, args)

        elif args.type == "column-profiles":
            if not args.name:
                print(
                    "Error: Table name is required for 'column-profiles' introspection",
                    file=sys.stderr,
                )
                sys.exit(1)
            profiles = introspector.list_column_data_profiles(args.name, schema=None)
            # Which figures this engine refused, said on stderr so the
            # rows on stdout stay parseable. A BLOB's distinct count and
            # bounds are ``None`` in the rows themselves; the note names
            # them rather than letting a reader mistake the nulls for
            # zeroes the engine measured.
            _note_unmeasured_profiles(profiles, args.name)
            data = _serialize_for_output(profiles)
            provider.display_results(data, title=f"Column profiles of {args.name}")

        elif args.type == "value-samples":
            if not args.name:
                print(
                    "Error: Table name is required for 'value-samples' introspection",
                    file=sys.stderr,
                )
                sys.exit(1)
            if not args.column:
                print(
                    "Error: --column is required for 'value-samples' introspection",
                    file=sys.stderr,
                )
                sys.exit(1)
            samples = introspector.sample_column_values(args.name, args.column, schema=None)
            data = _serialize_for_output(samples)
            provider.display_results(data, title=f"Values of {args.name}.{args.column}")

        elif args.type == "join-coverage":
            if not args.name:
                print(
                    "Error: Left table name is required for 'join-coverage' introspection",
                    file=sys.stderr,
                )
                sys.exit(1)
            if not args.column:
                print(
                    "Error: --column is required for 'join-coverage' introspection",
                    file=sys.stderr,
                )
                sys.exit(1)
            if not args.right_table or not args.right_column:
                print(
                    "Error: --right-table and --right-column are required for "
                    "'join-coverage' introspection",
                    file=sys.stderr,
                )
                sys.exit(1)
            coverage = introspector.estimate_join_coverage(
                args.name, args.column, args.right_table, args.right_column, schema=None
            )
            if coverage is None:
                # A column with nothing to match answers "no measurement",
                # which is not zero overlap; printing a row of nulls would
                # read as a measured zero.
                print(
                    f"Error: no coverage could be measured for {args.name}.{args.column} "
                    f"and {args.right_table}.{args.right_column}",
                    file=sys.stderr,
                )
                sys.exit(1)
            data = _serialize_for_output([coverage])
            provider.display_results(data, title="Join Coverage")

    except ConnectionError as e:
        provider.display_connection_error(e)
        sys.exit(1)
    except QueryError as e:
        provider.display_query_error(e)
        sys.exit(1)
    except Exception as e:
        print(f"Error during introspection: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if backend._connection:  # type: ignore
            backend.disconnect()


async def _handle_introspect_async(args, backend: AsyncFirebirdBackend, provider):
    """Handle introspect subcommand asynchronously."""
    try:
        await backend.connect()
        # Same reason as the sync handler: the dialect must know the server
        # version before a formatter can render.
        await backend.introspect_and_adapt()
        _require_capability(backend, args)
        _refuse_unused_arguments(args)

        introspector = backend.introspector

        if args.type == "tables":
            tables = await introspector.list_tables(schema=None, include_system=args.include_system)
            data = _serialize_for_output(tables)
            provider.display_results(data, title="Tables")

        elif args.type == "views":
            if args.name:
                view = await introspector.get_view_info(args.name)
                if view is None:
                    print(f"Error: View '{args.name}' not found", file=sys.stderr)
                    sys.exit(1)
                provider.display_results(_serialize_for_output([view]), title=f"View {args.name}")
            else:
                views = await introspector.list_views(schema=None)
                data = _serialize_for_output(views)
                provider.display_results(data, title="Views")

        elif args.type == "columns":
            if not args.name:
                print("Error: Table name is required for 'columns' introspection", file=sys.stderr)
                sys.exit(1)
            columns = await introspector.list_columns(args.name, schema=None)
            data = _serialize_for_output(columns)
            provider.display_results(data, title=f"Columns of {args.name}")

        elif args.type == "indexes":
            if not args.name:
                print("Error: Table name is required for 'indexes' introspection", file=sys.stderr)
                sys.exit(1)
            indexes = await introspector.list_indexes(args.name, schema=None)
            data = _serialize_for_output(indexes)
            provider.display_results(data, title=f"Indexes of {args.name}")

        elif args.type == "foreign-keys":
            if not args.name:
                print("Error: Table name is required for 'foreign-keys' introspection", file=sys.stderr)
                sys.exit(1)
            fks = await introspector.list_foreign_keys(args.name, schema=None)
            data = _serialize_for_output(fks)
            provider.display_results(data, title=f"Foreign Keys of {args.name}")

        elif args.type == "triggers":
            triggers = await introspector.list_triggers(table_name=args.name, schema=None)
            data = _serialize_for_output(triggers)
            provider.display_results(data, title="Triggers")

        elif args.type == "database":
            info = await introspector.get_database_info()
            data = _serialize_for_output(info)
            provider.display_results([data], title="Database Info")

        elif args.type == "generators":
            if args.name:
                generator = await introspector.get_generator_info(args.name)
                if generator is None:
                    print(f"Error: Generator '{args.name}' not found", file=sys.stderr)
                    sys.exit(1)
                provider.display_results(
                    [_serialize_for_output(generator)],
                    title=f"Generator {generator.name}",
                )
            else:
                generators = await introspector.list_generators()
                provider.display_results(_serialize_for_output(generators), title="Generators")

        elif args.type == "domains":
            if args.name:
                domain = await introspector.get_domain_info(args.name)
                if domain is None:
                    print(f"Error: Domain '{args.name}' not found", file=sys.stderr)
                    sys.exit(1)
                provider.display_results(
                    [_serialize_for_output(domain)], title=f"Domain {domain.name}"
                )
            else:
                domains = await introspector.list_domains()
                provider.display_results(_serialize_for_output(domains), title="Domains")

        elif args.type == "exceptions":
            if args.name:
                found = await introspector.get_exception_info(args.name)
                if found is None:
                    print(f"Error: Exception '{args.name}' not found", file=sys.stderr)
                    sys.exit(1)
                provider.display_results(
                    [_serialize_for_output(found)], title=f"Exception {found.name}"
                )
            else:
                provider.display_results(
                    _serialize_for_output(
                        await introspector.list_exceptions(args.include_system)
                    ),
                    title="Exceptions",
                )

        elif args.type == "procedures":
            if args.name:
                found = await introspector.get_procedure_info(args.name)
                if found is None:
                    print(f"Error: Procedure '{args.name}' not found", file=sys.stderr)
                    sys.exit(1)
                provider.display_results(
                    [_serialize_for_output(found)], title=f"Procedure {found.name}"
                )
            else:
                provider.display_results(
                    _serialize_for_output(
                        await introspector.list_procedures(args.include_system)
                    ),
                    title="Procedures",
                )

        elif args.type == "procedure-parameters":
            if not args.name:
                print(
                    "Error: Procedure name is required for 'procedure-parameters'",
                    file=sys.stderr,
                )
                sys.exit(1)
            provider.display_results(
                _serialize_for_output(
                    await introspector.list_procedure_parameters(args.name)
                ),
                title=f"Parameters of {args.name}",
            )

        elif args.type == "functions":
            if args.name:
                found = await introspector.get_function_info(args.name)
                if found is None:
                    print(f"Error: Function '{args.name}' not found", file=sys.stderr)
                    sys.exit(1)
                provider.display_results(
                    [_serialize_for_output(found)], title=f"Function {found.name}"
                )
            else:
                provider.display_results(
                    _serialize_for_output(
                        await introspector.list_functions(args.include_system)
                    ),
                    title="Functions",
                )

        elif args.type == "function-arguments":
            if not args.name:
                print(
                    "Error: Function name is required for 'function-arguments'",
                    file=sys.stderr,
                )
                sys.exit(1)
            provider.display_results(
                _serialize_for_output(
                    await introspector.list_function_arguments(args.name)
                ),
                title=f"Arguments of {args.name}",
            )

        elif args.type == "constraints":
            provider.display_results(
                _serialize_for_output(
                    await introspector.list_constraints(
                        args.name, args.constraint_type, args.include_system
                    )
                ),
                title="Constraints",
            )

        elif args.type == "roles":
            provider.display_results(
                _serialize_for_output(
                    await introspector.list_roles(args.include_system)
                ),
                title="Roles",
            )

        elif args.type == "privileges":
            provider.display_results(
                _serialize_for_output(
                    await introspector.list_privileges(
                        args.object, args.grantee, args.include_system
                    )
                ),
                title="Privileges",
            )

        elif args.type == "charsets":
            provider.display_results(
                _serialize_for_output(await introspector.list_charsets()),
                title="Character sets",
            )

        elif args.type == "collations":
            provider.display_results(
                _serialize_for_output(
                    await introspector.list_collations(args.name)
                ),
                title="Collations",
            )

        elif args.type == "dependencies":
            provider.display_results(
                _serialize_for_output(
                    await introspector.list_dependencies(args.name)
                ),
                title="Dependencies",
            )

        elif args.type == "view-relations":
            provider.display_results(
                _serialize_for_output(
                    await introspector.list_view_relations(args.name)
                ),
                title="View relations",
            )

        elif args.type == "publications":
            provider.display_results(
                _serialize_for_output(
                    await introspector.list_publications(args.include_system)
                ),
                title="Publications",
            )

        # The async twins of the nine branches above: same method, same
        # argument and same title, awaited. They are written out rather than
        # shared with the sync chain because the executor is the only thing
        # that differs, and a shared body would have to carry an ``await``
        # flag that reads worse than the duplicate.

        elif args.type == "unused-indexes":
            if args.name:
                _refuse_name(args, "it describes every index in the database")
            indexes = await introspector.list_unused_indexes(schema=None)
            data = _serialize_for_output(indexes)
            provider.display_results(data, title="Indexes with no recorded use")

        elif args.type == "table-stats":
            if args.name:
                _refuse_name(args, "it describes every table in the database")
            stats = await introspector.list_table_usage_stats(schema=None)
            data = _serialize_for_output(stats)
            provider.display_results(data, title="Table usage counters")

        elif args.type == "runtime":
            if args.name:
                _refuse_name(args, "it describes the server, not one object")
            metrics = await introspector.list_runtime_metrics(schema=None)
            data = _serialize_for_output(metrics)
            provider.display_results(data, title="Runtime metrics")

        elif args.type == "index-stats":
            if args.name:
                _refuse_name(args, "it describes every index in the database")
            stats = await introspector.list_index_usage_stats(schema=None)
            data = _serialize_for_output(stats)
            provider.display_results(data, title="Index usage counters")

        elif args.type == "ddl":
            if not args.name:
                print("Error: Table name is required for 'ddl' introspection", file=sys.stderr)
                sys.exit(1)
            statement = await introspector.get_ddl_statement(
                args.name, object_type=None, schema=None
            )
            if statement is None:
                print(
                    f"Error: no DDL available for '{args.name}' "
                    "(Firebird records a source body, not a rebuildable statement)",
                    file=sys.stderr,
                )
                sys.exit(1)
            _display_ddl(provider, statement, args)

        elif args.type == "column-profiles":
            if not args.name:
                print(
                    "Error: Table name is required for 'column-profiles' introspection",
                    file=sys.stderr,
                )
                sys.exit(1)
            profiles = await introspector.list_column_data_profiles(args.name, schema=None)
            _note_unmeasured_profiles(profiles, args.name)
            data = _serialize_for_output(profiles)
            provider.display_results(data, title=f"Column profiles of {args.name}")

        elif args.type == "value-samples":
            if not args.name:
                print(
                    "Error: Table name is required for 'value-samples' introspection",
                    file=sys.stderr,
                )
                sys.exit(1)
            if not args.column:
                print(
                    "Error: --column is required for 'value-samples' introspection",
                    file=sys.stderr,
                )
                sys.exit(1)
            samples = await introspector.sample_column_values(
                args.name, args.column, schema=None
            )
            data = _serialize_for_output(samples)
            provider.display_results(data, title=f"Values of {args.name}.{args.column}")

        elif args.type == "join-coverage":
            if not args.name:
                print(
                    "Error: Left table name is required for 'join-coverage' introspection",
                    file=sys.stderr,
                )
                sys.exit(1)
            if not args.column:
                print(
                    "Error: --column is required for 'join-coverage' introspection",
                    file=sys.stderr,
                )
                sys.exit(1)
            if not args.right_table or not args.right_column:
                print(
                    "Error: --right-table and --right-column are required for "
                    "'join-coverage' introspection",
                    file=sys.stderr,
                )
                sys.exit(1)
            coverage = await introspector.estimate_join_coverage(
                args.name, args.column, args.right_table, args.right_column, schema=None
            )
            if coverage is None:
                print(
                    f"Error: no coverage could be measured for {args.name}.{args.column} "
                    f"and {args.right_table}.{args.right_column}",
                    file=sys.stderr,
                )
                sys.exit(1)
            data = _serialize_for_output([coverage])
            provider.display_results(data, title="Join Coverage")

    except ConnectionError as e:
        provider.display_connection_error(e)
        sys.exit(1)
    except QueryError as e:
        provider.display_query_error(e)
        sys.exit(1)
    except Exception as e:
        print(f"Error during introspection: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if backend._connection:  # type: ignore
            await backend.disconnect()
