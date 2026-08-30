# src/rhosocial/activerecord/backend/impl/firebird/cli/named_procedure_graph.py
"""named-procedure-graph subcommand - Adapter for shared CLI helper.

named-procedure-graph requires connection arguments, output arguments, and --rich-ascii.

Usage:
    $ python -m rhosocial.activerecord.backend.impl.firebird named-procedure-graph run \\
        myapp.npg.monthly_report \\
        --host localhost --database mydb \\
        --params '{"month": "2026-04"}'

    $ python -m rhosocial.activerecord.backend.impl.firebird named-procedure-graph list \\
        myapp.npg

    $ python -m rhosocial.activerecord.backend.impl.firebird named-procedure-graph validate \\
        myapp.npg.monthly_report
"""

from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend, AsyncFirebirdBackend

from .connection import create_connection_parent_parser, resolve_connection_config_from_args
from .output import create_provider


def create_parser(subparsers):
    """Create the named-procedure-graph subcommand parser.

    Reuses the shared create_named_procedure_graph_parser, passing a parent parser
    containing only connection and output arguments.
    """
    from rhosocial.activerecord.backend.named_expression.cli_procedure_graph import (
        create_named_procedure_graph_parser,
    )

    local_parent = create_connection_parent_parser()
    return create_named_procedure_graph_parser(subparsers, local_parent)


def handle(args):
    """Handle the named-procedure-graph subcommand."""
    from rhosocial.activerecord.backend.named_expression.cli_procedure_graph import (
        handle_named_procedure_graph as handle_npg,
    )

    provider = create_provider(args.output, ascii_borders=args.rich_ascii)

    backend = None

    def backend_factory():
        nonlocal backend
        config = resolve_connection_config_from_args(args)
        backend = FirebirdBackend(connection_config=config)
        backend.connect()
        backend.introspect_and_adapt()
        return backend

    def disconnect():
        if backend and backend._connection:
            backend.disconnect()

    is_async = getattr(args, "is_async", False)
    if is_async:
        async_backend = None

        def backend_async_factory():
            nonlocal async_backend
            config = resolve_connection_config_from_args(args)
            async_backend = AsyncFirebirdBackend(connection_config=config)
            return async_backend

        async def disconnect_async():
            if async_backend and async_backend._connection:
                await async_backend.disconnect()

        handle_npg(
            args,
            provider,
            backend_factory=backend_factory,
            disconnect=disconnect,
            backend_async_factory=backend_async_factory,
            disconnect_async=disconnect_async,
        )
        return

    handle_npg(
        args,
        provider,
        backend_factory=backend_factory,
        disconnect=disconnect,
    )
