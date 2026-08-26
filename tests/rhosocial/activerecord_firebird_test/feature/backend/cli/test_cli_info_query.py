# tests/rhosocial/activerecord_firebird_test/feature/backend/cli/test_cli_info_query.py
"""Offline black-box tests for the ``firebird info`` and ``firebird query``
CLI subcommands.

``info`` runs against a simulated dialect (or a fake backend when
``--database`` is given); ``query`` runs against a fake backend returning a
fixed QueryResult. Output formats, exit codes and connection-argument
resolution are asserted through capsys.
"""
import argparse
import asyncio
import io
import json
import sys

import pytest

from rhosocial.activerecord.backend.errors import ConnectionError, QueryError
from rhosocial.activerecord.backend.impl import firebird as firebird_impl_pkg
from rhosocial.activerecord.backend.impl.firebird.cli import info as info_mod
from rhosocial.activerecord.backend.impl.firebird.cli import query as query_mod
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.result import QueryResult


def parse_args(module, argv):
    parser = argparse.ArgumentParser(prog="firebird")
    subparsers = parser.add_subparsers(dest="command")
    module.create_parser(subparsers)
    return parser.parse_args(argv)


@pytest.fixture(autouse=True)
def clean_fb_env(monkeypatch):
    for name in ("FIREBIRD_HOST", "FIREBIRD_PORT", "FIREBIRD_DATABASE",
                 "FIREBIRD_USER", "FIREBIRD_PASSWORD", "FIREBIRD_ROLE"):
        monkeypatch.delenv(name, raising=False)


class FakeInfoBackend:
    last_instance = None

    def __init__(self, connection_config=None):
        self.connection_config = connection_config
        self.dialect = FirebirdDialect((5, 0, 0))
        self.disconnect_calls = 0
        FakeInfoBackend.last_instance = self

    def connect(self):
        pass

    def introspect_and_adapt(self):
        pass

    def get_server_version(self):
        return (5, 0, 2)

    def disconnect(self):
        self.disconnect_calls += 1


def install_query_fake(monkeypatch, result="DEFAULT", connect_exc=None, execute_exc=None):
    created = []

    class FakeQueryBackend:
        last_instance = None

        def __init__(self, connection_config=None):
            self.connection_config = connection_config
            self._connection = None
            self.executed = []
            self.disconnect_calls = 0
            self._connect_exc = connect_exc
            self._execute_exc = execute_exc
            self._result = QueryResult(data=None) if result == "DEFAULT" else result
            type(self).last_instance = self
            created.append(self)

        def connect(self):
            if self._connect_exc is not None:
                raise self._connect_exc
            self._connection = object()

        def execute(self, sql):
            self.executed.append(sql)
            if self._execute_exc is not None:
                raise self._execute_exc
            return self._result

        def disconnect(self):
            self.disconnect_calls += 1
            self._connection = None

    monkeypatch.setattr(query_mod, "FirebirdBackend", FakeQueryBackend)
    return created


class TestInfoParserContract:
    def test_defaults(self):
        args = parse_args(info_mod, ["info"])
        assert args.command == "info"
        assert args.output == "table"
        assert args.verbose == 0
        assert args.version is None
        assert args.database is None
        assert args.host == "localhost"

    def test_connection_arguments_optional(self):
        args = parse_args(info_mod, [
            "info", "--host", "h", "--port", "3054", "--database", "/d.fdb",
            "--user", "u", "--password", "p", "--role", "r",
        ])
        assert args.host == "h"
        assert args.port == 3054
        assert args.database == "/d.fdb"
        assert args.user == "u"
        assert args.password == "p"
        assert args.role == "r"

    def test_output_limited_to_table_and_json(self):
        for fmt in ("table", "json"):
            assert parse_args(info_mod, ["info", "-o", fmt]).output == fmt
        with pytest.raises(SystemExit) as excinfo:
            parse_args(info_mod, ["info", "-o", "csv"])
        assert excinfo.value.code == 2

    def test_verbose_counts(self):
        assert parse_args(info_mod, ["info"]).verbose == 0
        assert parse_args(info_mod, ["info", "-v"]).verbose == 1
        assert parse_args(info_mod, ["info", "-vv"]).verbose == 2


class TestInfoHandle:
    def test_default_run_reports_simulated_4_0(self, capsys):
        args = parse_args(info_mod, ["info"])
        info_mod.handle(args)
        payload = json.loads(capsys.readouterr().out)
        assert payload["database"]["type"] == "firebird"
        assert payload["database"]["version"] == "4.0.0"
        assert payload["database"]["version_tuple"] == [4, 0, 0]
        assert payload["database"]["connected"] is False
        assert "Firebird-specific" in payload["protocols"]

    def test_version_override(self, capsys):
        args = parse_args(info_mod, ["info", "--version", "3.0.7"])
        info_mod.handle(args)
        payload = json.loads(capsys.readouterr().out)
        assert payload["database"]["version"] == "3.0.7"
        assert payload["database"]["version_tuple"] == [3, 0, 7]

    def test_verbose_json_includes_method_details(self, capsys):
        args = parse_args(info_mod, ["info", "-vv"])
        info_mod.handle(args)
        payload = json.loads(capsys.readouterr().out)
        firebird_protocols = payload["protocols"]["Firebird-specific"]
        assert firebird_protocols
        for stats in firebird_protocols.values():
            assert set(stats) == {"supported", "total", "percentage", "methods"}

    def test_connected_run_uses_backend_dialect(self, monkeypatch, capsys):
        monkeypatch.setattr(firebird_impl_pkg, "FirebirdBackend", FakeInfoBackend)
        args = parse_args(info_mod, ["info", "--database", "/tmp/live.fdb"])
        info_mod.handle(args)
        payload = json.loads(capsys.readouterr().out)
        assert payload["database"]["connected"] is True
        assert payload["database"]["version"] == "5.0.2"
        assert FakeInfoBackend.last_instance.disconnect_calls == 1

    def test_connection_failure_falls_back_to_defaults(self, monkeypatch, capsys, caplog):
        class RefusedBackend(FakeInfoBackend):
            def connect(self):
                raise ConnectionError("no listener")

        monkeypatch.setattr(firebird_impl_pkg, "FirebirdBackend", RefusedBackend)
        args = parse_args(info_mod, ["info", "--database", "/tmp/live.fdb", "-o", "json"])
        info_mod.handle(args)
        payload = json.loads(capsys.readouterr().out)
        assert payload["database"]["connected"] is False
        assert payload["database"]["version"] == "4.0.0"


class TestInfoHelpers:
    def test_parse_version_variants(self):
        assert info_mod.parse_version("4") == (4, 0, 0)
        assert info_mod.parse_version("3.1") == (3, 1, 0)
        assert info_mod.parse_version("2.5.9") == (2, 5, 9)

    def test_get_protocol_support_methods_filters_naming_patterns(self):
        class Dummy:
            def supports_alpha(self):
                return True

            def is_beta_available(self):
                return True

            def format_gamma(self):
                return ""

        methods = info_mod.get_protocol_support_methods(Dummy)
        assert methods == ["is_beta_available", "supports_alpha"]

    def test_check_protocol_support_bool_and_parameterized(self):
        from rhosocial.activerecord.backend.impl.firebird.protocols import (
            FirebirdBlobSupport,
            FirebirdWindowFunctionSupport,
        )

        dialect = FirebirdDialect((4, 0, 0))
        blob = info_mod.check_protocol_support(dialect, FirebirdBlobSupport)
        assert blob["supports_blob"] is True
        parameterized = blob["supports_blob_sub_type"]
        assert set(parameterized) == {"supported", "total", "args"}
        assert parameterized["total"] == len(parameterized["args"]) == 2

        window = info_mod.check_protocol_support(dialect, FirebirdWindowFunctionSupport)
        assert window["supports_window_functions"] is True

    def test_calculate_protocol_stats_mixed_shapes(self):
        stats = {"yes": True, "no": False, "multi": {"supported": 2, "total": 3}}
        supported, total = info_mod._calculate_protocol_stats(stats)
        assert supported == 3
        assert total == 5


class TestQueryBuilderContract:
    def test_sql_positional_argument(self):
        args = parse_args(query_mod, ["query", "SELECT 1 FROM RDB$DATABASE"])
        assert args.sql == "SELECT 1 FROM RDB$DATABASE"
        assert args.file is None
        assert args.log_level == "INFO"

    def test_file_option(self):
        args = parse_args(query_mod, ["query", "-f", "script.sql"])
        assert args.file == "script.sql"
        assert args.sql is None

    def test_log_level_option(self):
        assert parse_args(query_mod, ["query", "--log-level", "DEBUG", "SELECT 1"]).log_level == "DEBUG"

    def test_connection_arguments(self):
        args = parse_args(query_mod, [
            "query", "--host", "qhost", "--port", "3055", "--database", "/q.fdb",
            "--user", "qu", "--password", "qp", "--role", "qr",
        ])
        assert (args.host, args.port, args.database) == ("qhost", 3055, "/q.fdb")
        assert (args.user, args.password, args.role) == ("qu", "qp", "qr")

    def test_invalid_log_level_raises_value_error(self):
        args = parse_args(query_mod, ["query", "--log-level", "LOUD", "SELECT 1"])
        with pytest.raises(ValueError) as excinfo:
            query_mod.handle(args)
        assert "Invalid log level" in str(excinfo.value)


class TestQueryHandle:
    def test_successful_select_prints_rows(self, monkeypatch, capsys):
        install_query_fake(monkeypatch, QueryResult(data=[{"A": 1}, {"A": 2}], affected_rows=2))
        args = parse_args(query_mod, ["query", "SELECT A FROM T", "--database", "/tmp/q.fdb"])
        query_mod.handle(args)
        out = capsys.readouterr().out
        payload = json.loads(out)
        assert payload == [{"A": 1}, {"A": 2}]
        backend = query_mod.FirebirdBackend.last_instance
        assert backend.executed == ["SELECT A FROM T"]

    def test_connection_parameters_forwarded(self, monkeypatch):
        install_query_fake(monkeypatch, QueryResult(data=[]))
        args = parse_args(query_mod, [
            "query", "SELECT 1", "--host", "qh", "--port", "3056",
            "--database", "/q2.fdb", "--user", "qn", "--password", "qw",
            "--role", "qro",
        ])
        query_mod.handle(args)
        cfg = query_mod.FirebirdBackend.last_instance.connection_config
        assert cfg.host == "qh"
        assert cfg.port == 3056
        assert cfg.database == "/q2.fdb"
        assert cfg.username == "qn"
        assert cfg.password == "qw"
        assert cfg.role == "qro"

    def test_empty_result_writes_empty_json_array(self, monkeypatch, capsys):
        install_query_fake(monkeypatch, QueryResult(data=[], affected_rows=0))
        args = parse_args(query_mod, ["query", "SELECT 1", "--database", "/tmp/q.fdb"])
        query_mod.handle(args)
        assert capsys.readouterr().out == "[]\n"

    def test_none_result_is_reported_without_crash(self, monkeypatch, capsys):
        install_query_fake(monkeypatch, result=None)
        args = parse_args(query_mod, ["query", "UPDATE T SET A = 1", "--database", "/tmp/q.fdb"])
        query_mod.handle(args)
        assert query_mod.FirebirdBackend.last_instance.executed == ["UPDATE T SET A = 1"]

    def test_disconnect_called_when_connected(self, monkeypatch):
        install_query_fake(monkeypatch, QueryResult(data=[{"A": 1}]))
        args = parse_args(query_mod, ["query", "SELECT 1", "--database", "/tmp/q.fdb"])
        query_mod.handle(args)
        assert query_mod.FirebirdBackend.last_instance.disconnect_calls == 1

    def test_sql_from_file(self, monkeypatch, capsys, tmp_path):
        script = tmp_path / "s.sql"
        script.write_text("SELECT 99 FROM RDB$DATABASE", encoding="utf-8")
        install_query_fake(monkeypatch, QueryResult(data=[{"CONSTANT": 99}]))
        args = parse_args(query_mod, ["query", "-f", str(script), "--database", "/tmp/q.fdb"])
        query_mod.handle(args)
        assert json.loads(capsys.readouterr().out) == [{"CONSTANT": 99}]
        assert query_mod.FirebirdBackend.last_instance.executed == ["SELECT 99 FROM RDB$DATABASE"]

    def test_sql_from_stdin(self, monkeypatch, capsys):
        install_query_fake(monkeypatch, QueryResult(data=[{"SEVEN": 7}]))
        fake_stdin = io.StringIO("SELECT 7 FROM RDB$DATABASE")
        fake_stdin.isatty = lambda: False
        monkeypatch.setattr(sys, "stdin", fake_stdin)
        args = parse_args(query_mod, ["query", "--database", "/tmp/q.fdb"])
        query_mod.handle(args)
        assert json.loads(capsys.readouterr().out) == [{"SEVEN": 7}]
        assert query_mod.FirebirdBackend.last_instance.executed == ["SELECT 7 FROM RDB$DATABASE"]

    def test_no_sql_source_exits_nonzero(self, monkeypatch, capsys):
        install_query_fake(monkeypatch)
        fake_stdin = io.StringIO("")
        fake_stdin.isatty = lambda: False
        monkeypatch.setattr(sys, "stdin", fake_stdin)
        args = parse_args(query_mod, ["query", "--database", "/tmp/q.fdb"])
        with pytest.raises(SystemExit) as excinfo:
            query_mod.handle(args)
        assert excinfo.value.code == 1
        assert "No SQL query provided" in capsys.readouterr().err

    def test_multiple_statements_rejected(self, monkeypatch, capsys):
        install_query_fake(monkeypatch)
        args = parse_args(query_mod, [
            "query", "SELECT 1; SELECT 2", "--database", "/tmp/q.fdb",
        ])
        with pytest.raises(SystemExit) as excinfo:
            query_mod.handle(args)
        assert excinfo.value.code == 1

    def test_missing_file_exits_nonzero(self, monkeypatch):
        install_query_fake(monkeypatch)
        args = parse_args(query_mod, ["query", "-f", "/nonexistent/x.sql", "--database", "/tmp/q.fdb"])
        with pytest.raises(SystemExit) as excinfo:
            query_mod.handle(args)
        assert excinfo.value.code == 1


class TestQueryAsyncPath:
    def _run_async(self, backend, sql="SELECT 1"):
        asyncio.run(
            query_mod._execute_query_async(sql, backend, query_mod.create_provider("json"))
        )

    def test_async_success(self, capsys):
        class AsyncBackend:
            def __init__(self):
                self._connection = object()
                self.disconnect_calls = 0
                self.executed = []

            async def connect(self):
                pass

            async def execute(self, sql):
                self.executed.append(sql)
                return QueryResult(data=[{"A": 1}])

            async def disconnect(self):
                self.disconnect_calls += 1

        backend = AsyncBackend()
        self._run_async(backend)
        assert json.loads(capsys.readouterr().out) == [{"A": 1}]
        assert backend.disconnect_calls == 1

    def test_async_connection_error_exits_nonzero(self):
        class AsyncBackend:
            def __init__(self):
                self._connection = None

            async def connect(self):
                raise ConnectionError("refused")

            async def disconnect(self):
                pass

        with pytest.raises(SystemExit) as excinfo:
            self._run_async(AsyncBackend())
        assert excinfo.value.code == 1

    def test_async_query_error_exits_nonzero(self):
        class AsyncBackend:
            def __init__(self):
                self._connection = None

            async def connect(self):
                self._connection = object()

            async def execute(self, sql):
                raise QueryError("syntax")

            async def disconnect(self):
                pass

        with pytest.raises(SystemExit) as excinfo:
            self._run_async(AsyncBackend())
        assert excinfo.value.code == 1


class TestQueryErrorPaths:
    def test_connection_error_exits_nonzero(self, monkeypatch):
        install_query_fake(monkeypatch, connect_exc=ConnectionError("down"))
        args = parse_args(query_mod, ["query", "SELECT 1", "--database", "/tmp/q.fdb"])
        with pytest.raises(SystemExit) as excinfo:
            query_mod.handle(args)
        assert excinfo.value.code == 1

    def test_query_error_exits_nonzero(self, monkeypatch):
        install_query_fake(monkeypatch, execute_exc=QueryError("bad syntax"))
        args = parse_args(query_mod, ["query", "SELECT 1", "--database", "/tmp/q.fdb"])
        with pytest.raises(SystemExit) as excinfo:
            query_mod.handle(args)
        assert excinfo.value.code == 1

    def test_unexpected_error_exits_nonzero(self, monkeypatch):
        install_query_fake(monkeypatch, execute_exc=RuntimeError("boom"))
        args = parse_args(query_mod, ["query", "SELECT 1", "--database", "/tmp/q.fdb"])
        with pytest.raises(SystemExit) as excinfo:
            query_mod.handle(args)
        assert excinfo.value.code == 1
