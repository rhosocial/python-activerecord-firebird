# src/rhosocial/activerecord/backend/impl/firebird/cli/named_procedure.py
"""CLI named-procedure subcommand."""


def register(subparsers):
    """Register the named-procedure subcommand."""
    parser = subparsers.add_parser("named-procedure", help="Execute named procedures")
    parser.add_argument("name", help="Procedure name")
    parser.add_argument("params", nargs="*", help="Procedure parameters")


def handle_named_procedure(args):
    """Handle named-procedure subcommand."""
    print(f"Procedure: {args.name}")
    if args.params:
        print(f"  Params: {args.params}")