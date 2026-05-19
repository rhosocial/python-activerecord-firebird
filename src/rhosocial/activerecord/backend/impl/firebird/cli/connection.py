# src/rhosocial/activerecord/backend/impl/firebird/cli/connection.py
"""CLI connection subcommand."""


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