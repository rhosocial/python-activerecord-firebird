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

INTROSPECT_TYPES = [
    "tables",
    "views",
    "table",
    "columns",
    "indexes",
    "foreign-keys",
    "triggers",
    "database",
    "generators",
    "domains",
]


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
        help=(
            "Introspection type: tables, views, table, columns, indexes, "
            "foreign-keys, triggers, database, generators, domains"
        ),
    )
    parser.add_argument(
        "name",
        nargs="?",
        default=None,
        help="Table/view/generator/domain name (required for some types)",
    )
    parser.add_argument(
        "--include-system",
        action="store_true",
        help="Include system tables in output",
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

        introspector = backend.introspector

        if args.type == "tables":
            tables = introspector.list_tables(schema=None, include_system=args.include_system)
            data = _serialize_for_output(tables)
            provider.display_results(data, title="Tables")

        elif args.type == "views":
            views = introspector.list_views(schema=None)
            data = _serialize_for_output(views)
            provider.display_results(data, title="Views")

        elif args.type == "table":
            if not args.name:
                print("Error: Table name is required for 'table' introspection", file=sys.stderr)
                sys.exit(1)
            info = introspector.get_table_info(args.name, schema=None)
            if info:
                provider.display_results(_serialize_for_output(info.columns), title=f"Columns of {args.name}")
                if info.indexes:
                    provider.display_results(_serialize_for_output(info.indexes), title=f"Indexes of {args.name}")
                if info.foreign_keys:
                    provider.display_results(
                        _serialize_for_output(info.foreign_keys), title=f"Foreign Keys of {args.name}"
                    )
            else:
                print(f"Error: Table '{args.name}' not found", file=sys.stderr)
                sys.exit(1)

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
                provider.display_results(_serialize_for_output(domains), title="Domains")

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

        introspector = backend.introspector

        if args.type == "tables":
            tables = await introspector.list_tables(schema=None, include_system=args.include_system)
            data = _serialize_for_output(tables)
            provider.display_results(data, title="Tables")

        elif args.type == "views":
            views = await introspector.list_views(schema=None)
            data = _serialize_for_output(views)
            provider.display_results(data, title="Views")

        elif args.type == "table":
            if not args.name:
                print("Error: Table name is required for 'table' introspection", file=sys.stderr)
                sys.exit(1)
            info = await introspector.get_table_info(args.name, schema=None)
            if info:
                provider.display_results(_serialize_for_output(info.columns), title=f"Columns of {args.name}")
                if info.indexes:
                    provider.display_results(_serialize_for_output(info.indexes), title=f"Indexes of {args.name}")
                if info.foreign_keys:
                    provider.display_results(
                        _serialize_for_output(info.foreign_keys), title=f"Foreign Keys of {args.name}"
                    )
            else:
                print(f"Error: Table '{args.name}' not found", file=sys.stderr)
                sys.exit(1)

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
