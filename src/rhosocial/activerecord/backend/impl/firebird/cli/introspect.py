# src/rhosocial/activerecord/backend/impl/firebird/cli/introspect.py
"""introspect subcommand - Database introspection.

There is no namespace flag here, and that is deliberate. Firebird has a
single unnamed namespace: every object lives in the one database the
connection opens, and Firebird never qualifies a name with anything above
it. An earlier version accepted ``--schema``, which named something that
does not exist here; it is gone rather than aliased, so a caller cannot
ask for a level the engine cannot express.
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

        introspector = backend.introspector

        if args.type == "tables":
            tables = introspector.list_tables(schema=None, include_system=args.include_system)
            data = _serialize_for_output(tables)
            provider.display_results(data, title="Tables")

        elif args.type == "views":
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

        introspector = backend.introspector

        if args.type == "tables":
            tables = await introspector.list_tables(schema=None, include_system=args.include_system)
            data = _serialize_for_output(tables)
            provider.display_results(data, title="Tables")

        elif args.type == "views":
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
