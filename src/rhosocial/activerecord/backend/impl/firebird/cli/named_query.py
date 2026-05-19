# src/rhosocial/activerecord/backend/impl/firebird/cli/named_query.py
"""CLI named-query subcommand."""


def register(subparsers):
    """Register the named-query subcommand."""
    parser = subparsers.add_parser("named-query", help="Execute named queries")
    parser.add_argument("name", help="Query name")
    parser.add_argument("params", nargs="*", help="Query parameters")


def handle_named_query(args):
    """Handle named-query subcommand."""
    print(f"Query: {args.name}")
    if args.params:
        print(f"  Params: {args.params}")