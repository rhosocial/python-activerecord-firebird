# src/rhosocial/activerecord/backend/impl/firebird/cli/named_connection.py
"""CLI named-connection subcommand."""


def register(subparsers):
    """Register the named-connection subcommand."""
    parser = subparsers.add_parser("named-connection", help="Manage named connections")
    parser.add_argument("action", choices=["list", "show", "set", "delete"], help="Action")
    parser.add_argument("name", nargs="?", help="Connection name")


def handle_named_connection(args):
    """Handle named-connection subcommand."""
    print(f"Named connection: {args.action}")
    if args.name:
        print(f"  Name: {args.name}")