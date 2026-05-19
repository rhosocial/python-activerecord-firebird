# src/rhosocial/activerecord/backend/impl/firebird/cli/info.py
"""CLI info subcommand."""


def register(subparsers):
    """Register the info subcommand."""
    parser = subparsers.add_parser("info", help="Show Firebird database information")
    parser.add_argument("--host", default="localhost", help="Firebird host")
    parser.add_argument("--port", type=int, default=3050, help="Firebird port")
    parser.add_argument("--database", "-d", help="Database path")
    parser.add_argument("--user", "-u", help="Username")
    parser.add_argument("--password", "-p", help="Password")


def handle_info(args):
    """Handle info subcommand."""
    print(f"Firebird database info")
    print(f"  Host: {args.host}:{args.port}")
    print(f"  Database: {args.database or '(not specified)'}")