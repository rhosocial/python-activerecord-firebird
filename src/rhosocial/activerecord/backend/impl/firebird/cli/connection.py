# src/rhosocial/activerecord/backend/impl/firebird/cli/connection.py
"""CLI connection subcommand and shared connection helpers."""

import argparse
import os


def add_connection_args(parser):
    """Add Firebird connection arguments to a subcommand parser."""
    parser.add_argument(
        "--host",
        default=os.getenv("FIREBIRD_HOST", "localhost"),
        help="Firebird host (env: FIREBIRD_HOST, default: localhost)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("FIREBIRD_PORT", "3050")),
        help="Firebird port (env: FIREBIRD_PORT, default: 3050)",
    )
    parser.add_argument(
        "--database", "-d",
        default=os.getenv("FIREBIRD_DATABASE"),
        help="Database path (env: FIREBIRD_DATABASE)",
    )
    parser.add_argument(
        "--user", "-u",
        default=os.getenv("FIREBIRD_USER"),
        help="Username (env: FIREBIRD_USER)",
    )
    parser.add_argument(
        "--password", "-p",
        default=os.getenv("FIREBIRD_PASSWORD"),
        help="Password (env: FIREBIRD_PASSWORD)",
    )
    parser.add_argument(
        "--charset",
        default=os.getenv("FIREBIRD_CHARSET", "UTF8"),
        help="Connection charset (env: FIREBIRD_CHARSET, default: UTF8)",
    )
    parser.add_argument(
        "--role",
        default=os.getenv("FIREBIRD_ROLE"),
        help="SQL role name (env: FIREBIRD_ROLE)",
    )
    parser.add_argument(
        "--ssl",
        choices=["auto", "require", "verify-ca", "verify-full", "disabled"],
        default="auto",
        help="SSL mode (env: FIREBIRD_SSL, default: auto)",
    )
    parser.add_argument(
        "--async",
        action="store_true",
        dest="is_async",
        help="Use asynchronous backend",
    )
    parser.add_argument(
        "--named-connection",
        dest="named_connection",
        metavar="QUALIFIED_NAME",
        help="Named connection from Python module (e.g., myapp.connections.prod_db). "
        "The --host/--port/--database options can override fields in this connection.",
    )
    parser.add_argument(
        "--conn-param",
        action="append",
        metavar="KEY=VALUE",
        default=[],
        dest="connection_params",
        help="Connection parameter override for named connection. Can be specified multiple times.",
    )


def create_connection_parent_parser():
    """Create a parent parser with connection and output arguments only.

    Used by named-expression/named-procedure shared CLI helpers which
    require a parent_parser argument.
    """
    parser = argparse.ArgumentParser(add_help=False)
    add_connection_args(parser)
    parser.add_argument(
        "-o",
        "--output",
        choices=["table", "json", "csv", "tsv"],
        default="table",
        help='Output format. Defaults to "table" if rich is installed.',
    )
    parser.add_argument(
        "--rich-ascii",
        action="store_true",
        help="Use ASCII characters for rich table borders.",
    )
    return parser


def warn_if_async_requested(args) -> None:
    """Refuse execution when --async is requested.

    The official ``firebird-driver`` has no asynchronous support.  The
    ``--async`` flag is kept for CLI surface parity with the other backends,
    but Firebird commands reject it outright rather than silently degrading
    to synchronous execution (which would mislead the caller).
    """
    if getattr(args, "is_async", False):
        import sys

        print(
            "[ERROR] Firebird official driver (firebird-driver) does not support "
            "asynchronous execution. Remove --async to run synchronously.",
            file=sys.stderr,
        )
        sys.exit(1)


def add_version_arg(parser):
    """Add --version argument (used only by info subcommand)."""
    parser.add_argument(
        "--version",
        type=str,
        default=None,
        help='Firebird version to simulate (e.g., "4.0.0", "3.0.0"). Default: 4.0.0.',
    )


def resolve_connection_config_from_args(args):
    """Resolve Firebird connection config from parsed args.

    Priority order:
        1. --named-connection + --conn-param
        2. Explicit connection parameters (--host, --port, etc.)
        3. Default values
    """
    from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig
    from rhosocial.activerecord.backend.named_connection.cli import parse_params
    from rhosocial.activerecord.backend.named_connection import NamedConnectionResolver

    named_conn = getattr(args, "named_connection", None)
    conn_params = getattr(args, "connection_params", [])

    if conn_params:
        conn_params = parse_params(conn_params)
    else:
        conn_params = {}

    if named_conn:
        resolver = NamedConnectionResolver(named_conn).load()
        if conn_params:
            return resolver.resolve(conn_params)
        return resolver.resolve({})

    return FirebirdConnectionConfig(
        host=args.host,
        port=args.port,
        database=args.database,
        username=args.user,
        password=args.password or "",
        charset=getattr(args, 'charset', "UTF8"),
        role=getattr(args, 'role', None),
    )