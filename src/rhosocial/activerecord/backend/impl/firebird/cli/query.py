# src/rhosocial/activerecord/backend/impl/firebird/cli/query.py
"""query subcommand - Execute SQL queries.

query requires connection arguments, output arguments, and --log-level.
"""

import argparse
import asyncio
import logging
import sys

from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend, AsyncFirebirdBackend
from rhosocial.activerecord.backend.errors import ConnectionError, QueryError

from .connection import add_connection_args, resolve_connection_config_from_args, warn_if_async_requested
from .output import create_provider

OUTPUT_CHOICES = ["table", "json", "csv", "tsv"]


def create_parser(subparsers):
    """Create the query subcommand parser."""
    parser = subparsers.add_parser(
        "query",
        help="Execute SQL query",
        epilog="""Examples:
  # Query a database
  %(prog)s --host localhost --database /path/to/test_db "SELECT * FROM users"

  # Execute SQL from file
  %(prog)s --host localhost --database /path/to/test_db -f query.sql

  # Using environment variables for connection
  export FIREBIRD_HOST=localhost FIREBIRD_DATABASE=/path/to/test_db FIREBIRD_USER=root FIREBIRD_PASSWORD=secret
  %(prog)s "SELECT 1"
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

    # Log level (query only)
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Set logging level (e.g., DEBUG, INFO)",
    )

    # Rich display options
    parser.add_argument(
        "--rich-ascii",
        action="store_true",
        help="Use ASCII characters for rich table borders.",
    )

    # query-specific arguments
    parser.add_argument(
        "sql",
        nargs="?",
        default=None,
        help="SQL query to execute. If not provided, reads from --file or stdin.",
    )
    parser.add_argument(
        "-f",
        "--file",
        default=None,
        help="Path to a file containing SQL to execute.",
    )

    return parser


def handle(args):

    warn_if_async_requested(args)

    """Handle the query subcommand."""
    # Set log level (query only)
    numeric_level = getattr(logging, args.log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {args.log_level}")

    provider = create_provider(args.output, ascii_borders=args.rich_ascii)

    try:
        from rhosocial.activerecord.backend.output_rich import RichOutputProvider

        if isinstance(provider, RichOutputProvider):
            from rich.console import Console
            from rich.logging import RichHandler

            handler = RichHandler(rich_tracebacks=True, show_path=False, console=Console(stderr=True))
            logging.basicConfig(level=numeric_level, format="%(message)s", datefmt="[%X]", handlers=[handler])
        else:
            logging.basicConfig(
                level=numeric_level, format="%(asctime)s - %(levelname)s - %(message)s", stream=sys.stderr
            )
    except ImportError:
        logging.basicConfig(level=numeric_level, format="%(asctime)s - %(levelname)s - %(message)s", stream=sys.stderr)

    provider.display_greeting()

    # Determine SQL source
    sql_source = None
    if args.sql:
        sql_source = args.sql
    elif args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                sql_source = f.read()
        except FileNotFoundError:
            logging.error(f"Error: File not found at {args.file}")
            sys.exit(1)
    elif not sys.stdin.isatty():
        sql_source = sys.stdin.read()

    if not sql_source:
        msg = "Error: No SQL query provided. Use SQL argument, --file, or stdin."
        print(msg, file=sys.stderr)
        sys.exit(1)

    # Ensure only one statement is provided
    if ";" in sql_source.strip().rstrip(";"):
        logging.error("Error: Multiple SQL statements are not supported.")
        sys.exit(1)

    config = resolve_connection_config_from_args(args)
    kwargs = {"use_ascii": args.rich_ascii}

    if getattr(args, "is_async", False):
        backend = AsyncFirebirdBackend(connection_config=config)
        asyncio.run(_execute_query_async(sql_source, backend, provider, **kwargs))
    else:
        backend = FirebirdBackend(connection_config=config)
        _execute_query_sync(sql_source, backend, provider, **kwargs)


# ---------------------------------------------------------------------------
# Internal helper functions
# ---------------------------------------------------------------------------


def _execute_query_sync(sql_query: str, backend: FirebirdBackend, provider, **kwargs):
    """Execute a SQL query synchronously."""
    try:
        backend.connect()
        provider.display_query(sql_query, is_async=False)
        result = backend.execute(sql_query)

        if not result:
            provider.display_no_result_object()
        else:
            provider.display_success(result.affected_rows, result.duration)
            if result.data:
                provider.display_results(result.data, **kwargs)
            else:
                provider.display_no_data()

    except ConnectionError as e:
        provider.display_connection_error(e)
        sys.exit(1)
    except QueryError as e:
        provider.display_query_error(e)
        sys.exit(1)
    except Exception as e:
        provider.display_unexpected_error(e, is_async=False)
        sys.exit(1)
    finally:
        if backend._connection:  # type: ignore
            backend.disconnect()
            provider.display_disconnect(is_async=False)


async def _execute_query_async(sql_query: str, backend: AsyncFirebirdBackend, provider, **kwargs):
    """Execute a SQL query asynchronously."""
    try:
        await backend.connect()
        provider.display_query(sql_query, is_async=True)
        result = await backend.execute(sql_query)

        if not result:
            provider.display_no_result_object()
        else:
            provider.display_success(result.affected_rows, result.duration)
            if result.data:
                provider.display_results(result.data, **kwargs)
            else:
                provider.display_no_data()

    except ConnectionError as e:
        provider.display_connection_error(e)
        sys.exit(1)
    except QueryError as e:
        provider.display_query_error(e)
        sys.exit(1)
    except Exception as e:
        provider.display_unexpected_error(e, is_async=True)
        sys.exit(1)
    finally:
        if backend._connection:  # type: ignore
            await backend.disconnect()
            provider.display_disconnect(is_async=True)
