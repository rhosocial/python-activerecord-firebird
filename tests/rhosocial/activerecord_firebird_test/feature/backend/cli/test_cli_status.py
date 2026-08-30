# tests/rhosocial/activerecord_firebird_test/feature/backend/cli/test_cli_status.py
"""Offline black-box tests for the ``firebird status`` CLI subcommand.

The FirebirdBackend construction point is replaced with a fake backend so
``handle()`` runs end-to-end without a server: fixed QueryResult-like
introspector payloads are asserted through capsys, every STATUS_TYPES value
is exercised, and ConnectionError/QueryError paths must produce a non-zero
exit code.
"""
import argparse
import asyncio
import json
from enum import Enum

import pytest

from rhosocial.activerecord.backend.errors import ConnectionError, QueryError
from rhosocial.activerecord.backend.impl.firebird.cli import status as status_mod
from rhosocial.activerecord.backend.impl.firebird.cli.status import STATUS_TYPES


def parse_status_args(argv):
    parser = argparse.ArgumentParser(prog="firebird")
    subparsers = parser.add_subparsers(dest="command")
    status_mod.create_parser(subparsers)
    return parser.parse_args(argv)


class FakeOverview:
    def to_dict(self):
        return {
            "server_version": "WI-V5.0.0",
            "server_vendor": "Firebird Project",
            "configuration": [{"name": "MaxBuffers", "value": "1024"}],
            "performance": [{"name": "Reads", "value": 42}],
        }


class FakeStatusIntrospector:
    def __init__(self):
        self.calls = []

    def get_overview(self):
        self.calls.append("overview")
        return FakeOverview()

    def list_configuration(self, category):
        self.calls.append("configuration")
        return [{"name": "MaxBuffers", "value": 1024}]

    def list_performance_metrics(self, category):
        self.calls.append("performance")
        return [{"name": "Reads", "value": 42}]

    def get_connection_info(self):
        self.calls.append("connection_info")
        return {"user": "SYSDBA", "active_count": 3}

    def get_storage_info(self):
        self.calls.append("storage_info")
        return {"total_size_bytes": 2048, "free_space_bytes": 512}

    def list_databases(self):
        self.calls.append("databases")
        return ["employees.fdb"]

    def list_users(self):
        self.calls.append("users")
        return ["SYSDBA"]


class RaisingStatusIntrospector(FakeStatusIntrospector):
    def __init__(self, exc):
        super().__init__()
        self._exc = exc

    def get_overview(self):
        raise self._exc

    def list_configuration(self, category):
        raise self._exc


class AsyncRaisingStatusIntrospector(RaisingStatusIntrospector):
    async def get_overview(self):
        raise self._exc

    async def list_configuration(self, category):
        raise self._exc


class FakeBackend:
    last_instance = None

    def __init__(self, connection_config=None):
        self.connection_config = connection_config
        self._connection = None
        self.connect_calls = 0
        self.disconnect_calls = 0
        self.introspector = type("I", (), {"status": FakeStatusIntrospector()})()
        FakeBackend.last_instance = self

    def connect(self):
        self.connect_calls += 1
        self._connection = object()

    def introspect_and_adapt(self):
        pass

    def disconnect(self):
        self.disconnect_calls += 1
        self._connection = None


class ExplodingConnectBackend(FakeBackend):
    def __init__(self, connection_config=None, exc=None):
        super().__init__(connection_config)
        self._exc = exc

    def connect(self):
        raise self._exc


class FakeAsyncBackend(FakeBackend):
    async def connect(self):
        self.connect_calls += 1
        self._connection = object()

    async def introspect_and_adapt(self):
        pass

    async def disconnect(self):
        self.disconnect_calls += 1
        self._connection = None


def make_async_introspector(exc=None):
    if exc is None:
        async def get_overview():
            return FakeOverview()

        async def list_configuration(category):
            return [{"name": "MaxBuffers", "value": 1024}]

        return type("AI", (), {
            "get_overview": staticmethod(get_overview),
            "list_configuration": staticmethod(list_configuration),
        })()
    return AsyncRaisingStatusIntrospector(exc)


@pytest.fixture(autouse=True)
def clean_fb_env(monkeypatch):
    for name in ("FIREBIRD_HOST", "FIREBIRD_PORT", "FIREBIRD_DATABASE",
                 "FIREBIRD_USER", "FIREBIRD_PASSWORD", "FIREBIRD_ROLE"):
        monkeypatch.delenv(name, raising=False)


class TestStatusParserContract:
    def test_connection_arguments_are_parsed(self):
        args = parse_status_args([
            "status", "--host", "fb.internal", "--port", "3051",
            "--database", "/data/app.fdb", "--user", "appuser",
            "--password", "s3cret", "--role", "APPROLE",
        ])
        assert args.command == "status"
        assert args.host == "fb.internal"
        assert args.port == 3051
        assert args.database == "/data/app.fdb"
        assert args.user == "appuser"
        assert args.password == "s3cret"
        assert args.role == "APPROLE"

    def test_defaults_without_environment(self):
        args = parse_status_args(["status"])
        assert args.host == "localhost"
        assert args.port == 3050
        assert args.database is None
        assert args.user is None
        assert args.password is None
        assert args.role is None
        assert args.charset == "UTF8"
        assert args.output == "table"
        assert args.type == "all"

    def test_environment_variables_feed_defaults(self, monkeypatch):
        monkeypatch.setenv("FIREBIRD_HOST", "envhost")
        monkeypatch.setenv("FIREBIRD_PORT", "3052")
        monkeypatch.setenv("FIREBIRD_DATABASE", "/env/db.fdb")
        monkeypatch.setenv("FIREBIRD_USER", "envuser")
        monkeypatch.setenv("FIREBIRD_PASSWORD", "envpass")
        monkeypatch.setenv("FIREBIRD_ROLE", "envrole")
        args = parse_status_args(["status"])
        assert args.host == "envhost"
        assert args.port == 3052
        assert args.database == "/env/db.fdb"
        assert args.user == "envuser"
        assert args.password == "envpass"
        assert args.role == "envrole"

    def test_output_choices(self):
        for fmt in ("table", "json", "csv", "tsv"):
            assert parse_status_args(["status", "-o", fmt]).output == fmt
        with pytest.raises(SystemExit) as excinfo:
            parse_status_args(["status", "-o", "yaml"])
        assert excinfo.value.code == 2

    def test_no_dsn_form_exists(self):
        with pytest.raises(SystemExit) as excinfo:
            parse_status_args(["status", "--dsn", "inet://h/db"])
        assert excinfo.value.code == 2

    def test_status_types_constant_fully_accepted(self):
        assert "all" in STATUS_TYPES
        for status_type in STATUS_TYPES:
            args = parse_status_args(["status", status_type] if status_type != "all" else ["status"])
            assert args.type == status_type

    def test_invalid_type_rejected(self):
        with pytest.raises(SystemExit) as excinfo:
            parse_status_args(["status", "bogus"])
        assert excinfo.value.code == 2


class TestStatusHandleHappyPaths:
    @pytest.mark.parametrize("status_type,marker,call", [
        ("config", "MaxBuffers", "configuration"),
        ("performance", "Reads", "performance"),
        ("connections", "SYSDBA", "connection_info"),
        ("storage", "free_space_bytes", "storage_info"),
        ("databases", "employees.fdb", "databases"),
        ("users", "SYSDBA", "users"),
    ])
    def test_each_type_json_output(self, monkeypatch, capsys, status_type, marker, call):
        monkeypatch.setattr(status_mod, "FirebirdBackend", FakeBackend)
        args = parse_status_args(["status", status_type, "--database", "/tmp/x.fdb", "-o", "json"])
        status_mod.handle(args)
        out = capsys.readouterr().out
        assert marker in out
        payload = json.loads(out)
        assert payload
        assert call in FakeBackend.last_instance.introspector.status.calls

    def test_all_type_json_snapshot(self, monkeypatch, capsys):
        monkeypatch.setattr(status_mod, "FirebirdBackend", FakeBackend)
        args = parse_status_args(["status", "all", "--database", "/tmp/x.fdb", "-o", "json"])
        status_mod.handle(args)
        payload = json.loads(capsys.readouterr().out)
        assert payload["server_version"] == "WI-V5.0.0"
        assert payload["server_vendor"] == "Firebird Project"

    @pytest.mark.parametrize("fmt", ["csv", "tsv"])
    def test_all_type_falls_back_to_json_for_flat_formats(self, monkeypatch, capsys, fmt):
        monkeypatch.setattr(status_mod, "FirebirdBackend", FakeBackend)
        args = parse_status_args(["status", "all", "--database", "/tmp/x.fdb", "-o", fmt])
        status_mod.handle(args)
        payload = json.loads(capsys.readouterr().out)
        assert payload["server_version"] == "WI-V5.0.0"

    def test_connection_config_forwarded_to_backend(self, monkeypatch):
        monkeypatch.setattr(status_mod, "FirebirdBackend", FakeBackend)
        args = parse_status_args([
            "status", "config", "--host", "h1", "--port", "3053",
            "--database", "/tmp/cfg.fdb", "--user", "u1",
            "--password", "p1", "--role", "r1", "--charset", "UTF8",
        ])
        status_mod.handle(args)
        cfg = FakeBackend.last_instance.connection_config
        assert cfg.host == "h1"
        assert cfg.port == 3053
        assert cfg.database == "/tmp/cfg.fdb"
        assert cfg.username == "u1"
        assert cfg.password == "p1"
        assert cfg.role == "r1"
        assert cfg.charset == "UTF8"
        assert FakeBackend.last_instance.disconnect_calls == 1

    def test_default_table_output_emits_rows_via_fallback_provider(self, monkeypatch, capsys):
        monkeypatch.setattr(status_mod, "FirebirdBackend", FakeBackend)
        args = parse_status_args(["status", "users", "--database", "/tmp/x.fdb"])
        status_mod.handle(args)
        assert "SYSDBA" in capsys.readouterr().out


class TestStatusAsyncPath:
    def test_async_handle_all_json(self, capsys):
        backend = FakeAsyncBackend()
        backend.introspector = type("I", (), {"status": make_async_introspector()})()
        args = parse_status_args(["status", "all", "--database", "/tmp/x.fdb", "-o", "json"])
        asyncio.run(status_mod._handle_status_async(args, backend, status_mod.create_provider("json")))
        payload = json.loads(capsys.readouterr().out)
        assert payload["server_version"] == "WI-V5.0.0"
        assert backend.disconnect_calls == 1

    def test_async_handle_connection_error_exits_nonzero(self):
        backend = FakeAsyncBackend()

        async def refused():
            raise ConnectionError("async refused")

        backend.connect = refused
        args = parse_status_args(["status", "config", "--database", "/tmp/x.fdb"])
        with pytest.raises(SystemExit) as excinfo:
            asyncio.run(
                status_mod._handle_status_async(args, backend, status_mod.create_provider("json"))
            )
        assert excinfo.value.code == 1

    def test_async_handle_query_error_exits_nonzero(self):
        backend = FakeAsyncBackend()
        backend.introspector = type(
            "I", (), {"status": make_async_introspector(exc=QueryError("bad plan"))}
        )()
        args = parse_status_args(["status", "config", "--database", "/tmp/x.fdb"])
        with pytest.raises(SystemExit) as excinfo:
            asyncio.run(
                status_mod._handle_status_async(args, backend, status_mod.create_provider("json"))
            )
        assert excinfo.value.code == 1


class TestStatusErrorPaths:
    def test_missing_database_exits_with_stderr_message(self, capsys):
        args = parse_status_args(["status", "all"])
        with pytest.raises(SystemExit) as excinfo:
            status_mod.handle(args)
        assert excinfo.value.code == 1
        assert "--database is required" in capsys.readouterr().err

    def test_async_flag_is_rejected(self, monkeypatch, capsys):
        created = []

        class ShouldNotBuild(FakeBackend):
            def __init__(self, connection_config=None):
                created.append(self)

        monkeypatch.setattr(status_mod, "FirebirdBackend", ShouldNotBuild)
        args = parse_status_args(["status", "all", "--database", "/tmp/x.fdb", "--async"])
        with pytest.raises(SystemExit) as excinfo:
            status_mod.handle(args)
        assert excinfo.value.code == 1
        assert "does not support" in capsys.readouterr().err
        assert not created

    def test_connection_error_exits_nonzero(self, monkeypatch, caplog):
        monkeypatch.setattr(
            status_mod, "FirebirdBackend",
            lambda connection_config=None: ExplodingConnectBackend(exc=ConnectionError("refused")),
        )
        args = parse_status_args(["status", "config", "--database", "/tmp/x.fdb"])
        with pytest.raises(SystemExit) as excinfo:
            status_mod.handle(args)
        assert excinfo.value.code == 1

    def test_query_error_exits_nonzero(self, monkeypatch):
        monkeypatch.setattr(status_mod, "FirebirdBackend", FakeBackend)

        class QFRaising(FakeStatusIntrospector):
            def list_configuration(self, category):
                raise QueryError("bad plan")

        original_init = FakeBackend.__init__

        def patched_init(self, connection_config=None):
            original_init(self, connection_config)
            self.introspector = type("I", (), {"status": QFRaising()})()

        monkeypatch.setattr(FakeBackend, "__init__", patched_init)
        args = parse_status_args(["status", "config", "--database", "/tmp/x.fdb"])
        with pytest.raises(SystemExit) as excinfo:
            status_mod.handle(args)
        assert excinfo.value.code == 1

    def test_unexpected_error_prints_to_stderr_and_exits(self, monkeypatch, capsys):
        monkeypatch.setattr(status_mod, "FirebirdBackend", FakeBackend)

        class BrokenIntrospector(FakeStatusIntrospector):
            def list_configuration(self, category):
                raise RuntimeError("boom")

        original_init = FakeBackend.__init__

        def patched_init(self, connection_config=None):
            original_init(self, connection_config)
            self.introspector = type("I", (), {"status": BrokenIntrospector()})()

        monkeypatch.setattr(FakeBackend, "__init__", patched_init)
        args = parse_status_args(["status", "config", "--database", "/tmp/x.fdb"])
        with pytest.raises(SystemExit) as excinfo:
            status_mod.handle(args)
        assert excinfo.value.code == 1
        assert "Error during status retrieval" in capsys.readouterr().err


class TestStatusHelpers:
    def test_format_size_branches(self):
        f = status_mod._format_size
        assert f(None) == "N/A"
        assert f(512) == "512.0 B"
        assert f(2048) == "2.0 KB"
        assert f(5 * 1024 ** 2) == "5.0 MB"
        assert f(3 * 1024 ** 3) == "3.0 GB"
        assert f(2 * 1024 ** 4) == "2.0 TB"
        assert f(1.5 * 1024 ** 5) == "1.5 PB"

    def test_serialize_for_output_enum_dataclass_and_fallback(self):
        from dataclasses import dataclass

        class Color(Enum):
            RED = "red"

        @dataclass
        class Point:
            x: int
            y: int

        s = status_mod._serialize_for_output
        assert s(None) is None
        assert s(Color.RED) == "red"
        assert s(Point(1, 2)) == {"x": 1, "y": 2}
        assert s((Color.RED, 7)) == ["red", 7]
        assert s(object()) != ""
