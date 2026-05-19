# src/rhosocial/activerecord/backend/impl/firebird/cli/status.py
"""CLI status subcommand."""


def register(subparsers):
    """Register the status subcommand."""
    parser = subparsers.add_parser("status", help="Show Firebird server status")
    parser.add_argument("--host", default="localhost", help="Firebird host")
    parser.add_argument("--port", type=int, default=3050, help="Firebird port")
    parser.add_argument("--database", "-d", help="Database path")
    parser.add_argument("--user", "-u", help="Username")
    parser.add_argument("--password", "-p", help="Password")


def handle_status(args):
    """Handle status subcommand."""
    print(f"Firebird server status")
    print(f"  Host: {args.host}:{args.port}")
    print(f"  Database: {args.database or '(not specified)'}")