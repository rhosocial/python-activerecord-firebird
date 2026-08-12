# src/rhosocial/activerecord/backend/impl/firebird/cli/connection.py
"""CLI connection subcommand and shared connection helpers."""

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
        "--use-async",
        action="store_true",
        help="Use asynchronous backend",
    )


def add_version_arg(parser):
    """Add --version argument (used only by info subcommand)."""
    parser.add_argument(
        "--version",
        type=str,
        default=None,
        help='Firebird version to simulate (e.g., "4.0.0", "3.0.0"). Default: 4.0.0.',
    )


def resolve_connection_config_from_args(args):
    """Resolve Firebird connection config from parsed args."""
    from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

    return FirebirdConnectionConfig(
        host=args.host,
        port=args.port,
        database=args.database,
        username=args.user,
        password=args.password or "",
        charset=getattr(args, 'charset', "UTF8"),
        role=getattr(args, 'role', None),
    )


def register(subparsers):
    """Register the connection subcommand."""
    parser = subparsers.add_parser("connection", help="Manage database connections")
    parser.add_argument("action", choices=["test", "list", "details"], help="Action to perform")
    parser.add_argument("--name", "-n", help="Connection name")
    parser.add_argument("--host", default="localhost", help="Firebird host")
    parser.add_argument("--port", type=int, default=3050, help="Firebird port")
    parser.add_argument("--database", "-d", help="Database path")
    parser.add_argument("--user", "-u", help="Username")
    parser.add_argument("--password", "-p", help="Password")


def handle_connection(args):
    """Handle connection subcommand."""
    print(f"Connection action: {args.action}")
    print(f"  Host: {args.host}:{args.port}")
    print(f"  Database: {args.database or '(not specified)'}")
    print(f"  User: {args.user or '(not specified)'}")