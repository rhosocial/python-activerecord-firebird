# src/rhosocial/activerecord/backend/impl/firebird/cli/introspect.py
"""CLI introspect subcommand."""


def register(subparsers):
    """Register the introspect subcommand."""
    parser = subparsers.add_parser("introspect", help="Introspect database schema")
    parser.add_argument("table", nargs="?", help="Table name (optional)")
    parser.add_argument("--host", default="localhost", help="Firebird host")
    parser.add_argument("--port", type=int, default=3050, help="Firebird port")
    parser.add_argument("--database", "-d", required=True, help="Database path")
    parser.add_argument("--user", "-u", required=True, help="Username")
    parser.add_argument("--password", "-p", required=True, help="Password")
    parser.add_argument("--all", action="store_true", help="List all tables")


def handle_introspect(args):
    """Handle introspect subcommand."""
    print(f"Introspect database: {args.database}")
    if args.all:
        print("  (listing all tables)")
    if args.table:
        print(f"  Table: {args.table}")