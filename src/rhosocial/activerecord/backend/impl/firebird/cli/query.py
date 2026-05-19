# src/rhosocial/activerecord/backend/impl/firebird/cli/query.py
"""CLI query subcommand."""


def register(subparsers):
    """Register the query subcommand."""
    parser = subparsers.add_parser("query", help="Execute SQL query")
    parser.add_argument("sql", help="SQL query to execute")
    parser.add_argument("--host", default="localhost", help="Firebird host")
    parser.add_argument("--port", type=int, default=3050, help="Firebird port")
    parser.add_argument("--database", "-d", required=True, help="Database path")
    parser.add_argument("--user", "-u", required=True, help="Username")
    parser.add_argument("--password", "-p", required=True, help="Password")
    parser.add_argument("--format", choices=["table", "json", "csv"], default="table",
                       help="Output format")


def handle_query(args):
    """Handle query subcommand."""
    print(f"SQL: {args.sql}")
    print(f"  Format: {args.format}")
    print(f"  Database: {args.database}")