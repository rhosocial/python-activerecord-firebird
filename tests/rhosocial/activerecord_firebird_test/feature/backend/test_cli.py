# tests/rhosocial/activerecord_firebird_test/feature/backend/test_cli.py
"""Tests for the Firebird backend CLI argument parsing.

Tests the ``_build_parser`` argument parser without connecting to a
database, verifying command registration and subcommand arguments.
"""

import sys

from unittest.mock import patch

from rhosocial.activerecord.backend.impl.firebird.__main__ import _build_parser
from rhosocial.activerecord.backend.impl.firebird.cli import COMMAND_NAMES


class TestFirebirdCLICommandRegistration:
    """Test that all CLI subcommands are registered."""

    def test_all_commands_registered(self):
        parser = _build_parser()
        subparsers_actions = [
            action for action in parser._actions
            if isinstance(action, type(parser._actions[-1]))
            and getattr(action, "choices", None)
        ]
        registered = set()
        for action in subparsers_actions:
            registered.update(action.choices or {})
        for command in COMMAND_NAMES:
            assert command in registered, f"CLI command {command} not registered"

    def test_get_handler_for_each_command(self):
        from rhosocial.activerecord.backend.impl.firebird.cli import get_handler

        for command in COMMAND_NAMES:
            assert get_handler(command) is not None, (
                f"No handler for CLI command {command}"
            )


class TestFirebirdCLIQuery:
    """Test the query subcommand argument parsing."""

    def test_query_sql_argument(self):
        with patch.object(sys, "argv", ["firebird", "query", "SELECT 1 FROM RDB$DATABASE"]):
            args = _build_parser().parse_args()
        assert args.command == "query"
        assert args.sql == "SELECT 1 FROM RDB$DATABASE"
        assert args.output == "table"

    def test_query_output_format(self):
        with patch.object(sys, "argv", ["firebird", "query", "-o", "json", "SELECT 1"]):
            args = _build_parser().parse_args()
        assert args.command == "query"
        assert args.output == "json"

    def test_query_file_option(self):
        with patch.object(sys, "argv", ["firebird", "query", "-f", "query.sql"]):
            args = _build_parser().parse_args()
        assert args.command == "query"
        assert args.file == "query.sql"
        assert args.sql is None

    def test_query_log_level(self):
        with patch.object(sys, "argv", ["firebird", "query", "--log-level", "DEBUG", "SELECT 1"]):
            args = _build_parser().parse_args()
        assert args.command == "query"
        assert args.log_level == "DEBUG"

    def test_query_rich_ascii_flag(self):
        with patch.object(sys, "argv", ["firebird", "query", "--rich-ascii", "SELECT 1"]):
            args = _build_parser().parse_args()
        assert args.command == "query"
        assert args.rich_ascii is True

    def test_query_connection_defaults(self):
        with patch.object(sys, "argv", ["firebird", "query", "SELECT 1"]):
            args = _build_parser().parse_args()
        assert isinstance(args.host, str) and args.host
        assert isinstance(args.port, int) and args.port > 0


class TestFirebirdCLIIntrospect:
    """Test the introspect subcommand argument parsing."""

    def test_introspect_tables(self):
        with patch.object(sys, "argv", ["firebird", "introspect", "tables"]):
            args = _build_parser().parse_args()
        assert args.command == "introspect"
        assert args.type == "tables"

    def test_introspect_table_with_name(self):
        with patch.object(sys, "argv", ["firebird", "introspect", "table", "users"]):
            args = _build_parser().parse_args()
        assert args.command == "introspect"
        assert args.type == "table"
        assert args.name == "users"

    def test_introspect_all_valid_types(self):
        from rhosocial.activerecord.backend.impl.firebird.cli.introspect import INTROSPECT_TYPES

        for introspect_type in INTROSPECT_TYPES:
            with patch.object(sys, "argv", ["firebird", "introspect", introspect_type]):
                args = _build_parser().parse_args()
                assert args.type == introspect_type

    def test_introspect_include_system(self):
        with patch.object(
            sys, "argv", ["firebird", "introspect", "tables", "--include-system"]
        ):
            args = _build_parser().parse_args()
        assert args.command == "introspect"
        assert args.include_system is True

    def test_introspect_output_json(self):
        with patch.object(sys, "argv", ["firebird", "introspect", "tables", "-o", "json"]):
            args = _build_parser().parse_args()
        assert args.command == "introspect"
        assert args.output == "json"

    def test_introspect_schema_option(self):
        with patch.object(
            sys, "argv", ["firebird", "introspect", "tables", "--schema", "PUBLIC"]
        ):
            args = _build_parser().parse_args()
        assert args.command == "introspect"
        assert args.schema == "PUBLIC"


class TestFirebirdCLIInfo:
    """Test the info subcommand argument parsing."""

    def test_info_command(self):
        with patch.object(sys, "argv", ["firebird", "info"]):
            args = _build_parser().parse_args()
        assert args.command == "info"

    def test_info_verbose(self):
        with patch.object(sys, "argv", ["firebird", "info", "-v"]):
            args = _build_parser().parse_args()
        assert args.verbose == 1