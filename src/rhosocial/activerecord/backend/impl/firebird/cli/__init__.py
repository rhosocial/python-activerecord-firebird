# src/rhosocial/activerecord/backend/impl/firebird/cli/__init__.py
"""Firebird CLI subcommand registration."""

COMMAND_NAMES = [
    "connection", "info", "introspect",
    "named-connection", "named-migration", "named-procedure", "named-query",
    "query", "status",
]


def register_commands(subparsers):
    """Register all CLI subcommands.

    Args:
        subparsers: argparse subparsers object
    """
    from .connection import register as register_connection
    from .info import register as register_info
    from .introspect import register as register_introspect
    from .named_connection import register as register_named_connection
    from .named_migration import create_parser as register_named_migration
    from .named_procedure import register as register_named_procedure
    from .named_query import register as register_named_query
    from .query import register as register_query
    from .status import register as register_status

    register_connection(subparsers)
    register_info(subparsers)
    register_introspect(subparsers)
    register_named_connection(subparsers)
    register_named_migration(subparsers)
    register_named_procedure(subparsers)
    register_named_query(subparsers)
    register_query(subparsers)
    register_status(subparsers)


def get_handler(command_name: str):
    """Get handler function for a command.

    Args:
        command_name: Command name

    Returns:
        Handler function
    """
    handlers = {
        "connection": _import_handler("connection", "handle_connection"),
        "info": _import_handler("info", "handle_info"),
        "introspect": _import_handler("introspect", "handle_introspect"),
        "named-connection": _import_handler("named_connection", "handle_named_connection"),
        "named-migration": _import_handler("named_migration", "handle"),
        "named-procedure": _import_handler("named_procedure", "handle_named_procedure"),
        "named-query": _import_handler("named_query", "handle_named_query"),
        "query": _import_handler("query", "handle_query"),
        "status": _import_handler("status", "handle_status"),
    }
    return handlers.get(command_name)


def _import_handler(module_name: str, func_name: str):
    import importlib
    module = importlib.import_module(f".{module_name}", package="rhosocial.activerecord.backend.impl.firebird.cli")
    return getattr(module, func_name)