# src/rhosocial/activerecord/backend/impl/firebird/cli/status.py
"""status subcommand - Display Firebird server status overview."""

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend, AsyncFirebirdBackend
from rhosocial.activerecord.backend.errors import ConnectionError, QueryError

from .connection import add_connection_args, resolve_connection_config_from_args
from .output import create_provider

OUTPUT_CHOICES = ["table", "json", "csv", "tsv"]

STATUS_TYPES = ["all", "config", "performance", "connections", "storage", "databases", "users"]


def create_parser(subparsers):
    """Create the status subcommand parser."""
    parser = subparsers.add_parser(
        "status",
        help="Display server status overview",
        epilog="""Examples:
  # Show complete status overview
  %(prog)s all --database /path/to/test_db

  # Show configuration parameters only
  %(prog)s config --database /path/to/test_db

  # Show performance metrics only
  %(prog)s performance --database /path/to/test_db

  # Show connection information
  %(prog)s connections --database /path/to/test_db

  # Output as JSON
  %(prog)s all --database /path/to/test_db -o json

  # Using environment variables for connection
  export FIREBIRD_HOST=localhost FIREBIRD_DATABASE=/path/to/test_db FIREBIRD_USER=root FIREBIRD_PASSWORD=secret
  %(prog)s all
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

    # Verbosity
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity for additional columns.",
    )

    # Rich display options
    parser.add_argument(
        "--rich-ascii",
        action="store_true",
        help="Use ASCII characters for rich table borders.",
    )

    # status-specific arguments
    parser.add_argument(
        "type",
        nargs="?",
        default="all",
        choices=STATUS_TYPES,
        help="Status type: all (default), config, performance, connections, storage, databases, users",
    )

    return parser


def handle(args):
    """Handle the status subcommand."""
    provider = create_provider(args.output, ascii_borders=args.rich_ascii)

    if not getattr(args, "database", None):
        print("Error: --database is required for status", file=sys.stderr)
        sys.exit(1)

    config = resolve_connection_config_from_args(args)

    if getattr(args, "use_async", False):
        backend = AsyncFirebirdBackend(connection_config=config)
        asyncio.run(_handle_status_async(args, backend, provider))
    else:
        backend = FirebirdBackend(connection_config=config)
        _handle_status_sync(args, backend, provider)


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


def _format_size(size_bytes) -> str:
    """Format byte size to human-readable string."""
    if size_bytes is None:
        return "N/A"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    for unit in units:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def _handle_status_sync(args, backend: FirebirdBackend, provider):
    """Handle status subcommand synchronously."""
    from rhosocial.activerecord.backend.introspection.status import StatusCategory

    try:
        backend.connect()
        backend.introspect_and_adapt()

        status_introspector = backend.introspector.status
        status_type = args.type

        if status_type == "all":
            status = status_introspector.get_overview()
            # 'all' type outputs nested structure; csv/tsv not suitable, fall back to json
            effective_output = args.output
            if effective_output in ("csv", "tsv"):
                effective_output = "json"

            if effective_output == "json":
                print(json.dumps(_serialize_for_output(status.to_dict()), indent=2))
            else:
                _display_status_rich(status, args.verbose)
        elif status_type == "config":
            config_items = status_introspector.list_configuration(StatusCategory.CONFIGURATION)
            data = _serialize_for_output(config_items)
            provider.display_results(data, title="Configuration")
        elif status_type == "performance":
            perf_items = status_introspector.list_performance_metrics(StatusCategory.PERFORMANCE)
            data = _serialize_for_output(perf_items)
            provider.display_results(data, title="Performance")
        elif status_type == "connections":
            conn_info = status_introspector.get_connection_info()
            data = _serialize_for_output(conn_info)
            provider.display_results([data], title="Connections")
        elif status_type == "storage":
            storage_info = status_introspector.get_storage_info()
            data = _serialize_for_output(storage_info)
            provider.display_results([data], title="Storage")
        elif status_type == "databases":
            databases = status_introspector.list_databases()
            data = _serialize_for_output(databases)
            provider.display_results(data, title="Databases")
        elif status_type == "users":
            users = status_introspector.list_users()
            data = _serialize_for_output(users)
            provider.display_results(data, title="Users")

    except ConnectionError as e:
        provider.display_connection_error(e)
        sys.exit(1)
    except QueryError as e:
        provider.display_query_error(e)
        sys.exit(1)
    except Exception as e:
        print(f"Error during status retrieval: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if backend._connection:  # type: ignore
            backend.disconnect()


async def _handle_status_async(args, backend: AsyncFirebirdBackend, provider):
    """Handle status subcommand asynchronously."""
    from rhosocial.activerecord.backend.introspection.status import StatusCategory

    try:
        await backend.connect()
        await backend.introspect_and_adapt()

        status_introspector = backend.introspector.status
        status_type = args.type

        if status_type == "all":
            status = await status_introspector.get_overview()
            effective_output = args.output
            if effective_output in ("csv", "tsv"):
                effective_output = "json"

            if effective_output == "json":
                print(json.dumps(_serialize_for_output(status.to_dict()), indent=2))
            else:
                _display_status_rich(status, args.verbose)
        elif status_type == "config":
            config_items = await status_introspector.list_configuration(StatusCategory.CONFIGURATION)
            data = _serialize_for_output(config_items)
            provider.display_results(data, title="Configuration")
        elif status_type == "performance":
            perf_items = await status_introspector.list_performance_metrics(StatusCategory.PERFORMANCE)
            data = _serialize_for_output(perf_items)
            provider.display_results(data, title="Performance")
        elif status_type == "connections":
            conn_info = await status_introspector.get_connection_info()
            data = _serialize_for_output(conn_info)
            provider.display_results([data], title="Connections")
        elif status_type == "storage":
            storage_info = await status_introspector.get_storage_info()
            data = _serialize_for_output(storage_info)
            provider.display_results([data], title="Storage")
        elif status_type == "databases":
            databases = await status_introspector.list_databases()
            data = _serialize_for_output(databases)
            provider.display_results(data, title="Databases")
        elif status_type == "users":
            users = await status_introspector.list_users()
            data = _serialize_for_output(users)
            provider.display_results(data, title="Users")

    except ConnectionError as e:
        provider.display_connection_error(e)
        sys.exit(1)
    except QueryError as e:
        provider.display_query_error(e)
        sys.exit(1)
    except Exception as e:
        print(f"Error during status retrieval: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if backend._connection:  # type: ignore
            await backend.disconnect()


def _display_status_rich(status, verbose: int = 0):
    """Display status using rich console."""
    from rich.console import Console
    from rich.table import Table

    console = Console(force_terminal=True)

    # Header
    console.print("\n[bold cyan]Firebird Server Status[/bold cyan]\n")
    console.print(f"[bold]Version:[/bold] {status.server_version}")
    console.print(f"[bold]Vendor:[/bold] {status.server_vendor}")

    # Session info
    if hasattr(status, "session") and status.session:
        session = status.session
        console.print()
        console.print("[bold green]Session[/bold green]")
        if session.user:
            console.print(f"  [bold]User:[/bold] {session.user}")
        if session.database:
            console.print(f"  [bold]Database:[/bold] {session.database}")

    # Connection info
    if hasattr(status, "connections") and status.connections:
        conn = status.connections
        if conn.active_count is not None:
            console.print(f"[bold]Active Connections:[/bold] {conn.active_count}")

    console.print()

    # Configuration section
    config_items = status.configuration
    if config_items:
        console.print("[bold green]Configuration[/bold green]")
        config_table = Table(show_header=True, header_style="bold")
        config_table.add_column("Parameter")
        config_table.add_column("Value")
        if verbose >= 1:
            config_table.add_column("Description")

        for item in config_items:
            row = [item.name, str(item.value)]
            if verbose >= 1:
                row.append(item.description or "")
            config_table.add_row(*row)

        console.print(config_table)
        console.print()

    # Performance section
    perf_items = status.performance
    if perf_items:
        console.print("[bold green]Performance[/bold green]")
        perf_table = Table(show_header=True, header_style="bold")
        perf_table.add_column("Parameter")
        perf_table.add_column("Value")

        for item in perf_items:
            perf_table.add_row(item.name, str(item.value))

        console.print(perf_table)
        console.print()

    # Storage section
    if hasattr(status, "storage") and status.storage:
        storage = status.storage
        console.print("[bold green]Storage[/bold green]")
        storage_table = Table(show_header=True, header_style="bold")
        storage_table.add_column("Metric")
        storage_table.add_column("Value")
        storage_table.add_row("Total size", _format_size(storage.total_size_bytes))
        storage_table.add_row("Free space", _format_size(storage.free_space_bytes))
        console.print(storage_table)
        console.print()

    # Databases section
    if status.databases:
        console.print("[bold green]Databases[/bold green]")
        db_table = Table(show_header=True, header_style="bold")
        db_table.add_column("Name")

        for db in status.databases:
            db_table.add_row(db.name)

        console.print(db_table)
        console.print()

    # Users section
    if status.users:
        console.print("[bold green]Users[/bold green]")
        user_table = Table(show_header=True, header_style="bold")
        user_table.add_column("Name")

        for user in status.users:
            user_table.add_row(user.name)

        console.print(user_table)
        console.print()
