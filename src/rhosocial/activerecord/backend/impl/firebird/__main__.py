# src/rhosocial/activerecord/backend/impl/firebird/__main__.py
"""Firebird backend command-line interface.

Provides SQL execution and database introspection capabilities.
"""

import argparse
import sys


def _build_parser():
    parser = argparse.ArgumentParser(
        description="Execute SQL queries against a Firebird backend.",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    subparsers = parser.add_subparsers(
        dest="command", help="Available commands"
    )

    try:
        from .cli import register_commands, COMMAND_NAMES
        register_commands(subparsers)
    except ImportError:
        pass

    return parser


def main():
    parser = _build_parser()
    args = parser.parse_args()

    if args.command is None:
        print("Error: Please specify a command.", file=sys.stderr)
        print("Use --help for more information.", file=sys.stderr)
        sys.exit(1)

    try:
        from .cli import get_handler, COMMAND_NAMES
        handler = get_handler(args.command)
        handler(args)
    except ImportError:
        print("CLI commands not available.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()