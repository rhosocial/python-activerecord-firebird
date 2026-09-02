# tests/rhosocial/activerecord_firebird_test/feature/backend/cli/test_cli_introspect.py
"""Offline black-box tests for the ``firebird introspect`` CLI subcommand.

``handle()`` runs against a fake backend whose introspector returns fixed
payloads; every INTROSPECT_TYPES value is exercised through capsys, and
ConnectionError/QueryError paths must exit non-zero.
"""
import argparse
import asyncio

import pytest

from rhosocial.activerecord.backend.errors import ConnectionError, QueryError
from rhosocial.activerecord.backend.impl.firebird.cli import introspect as introspect_mod
from rhosocial.activerecord.backend.impl.firebird.cli.introspect import INTROSPECT_TYPES


def parse_introspect_args(argv):
    parser = argparse.ArgumentParser(prog="firebird")
    subparsers = parser.add_subparsers(dest="command")
    introspect_mod.create_parser(subparsers)
    return parser.parse_args(argv)


class TableInfo:
    def __init__(self, columns=None, indexes=None, foreign_keys=None):
        self.columns = columns if columns is not None else [{"name": "ID", "type": "INTEGER"}]
        self.indexes = indexes if indexes is not None else [{"name": "RDB$PRIMARY"}]
        self.foreign_keys = foreign_keys if foreign_keys is not None else [{"name": "FK_ORDERS"}]


class FakeIntrospector:
    def __init__(self):
        self.calls = []

    def list_tables(self, schema=None, include_system=False):
        self.calls.append(("list_tables", schema, include_system))
        return ["USERS", "ORDERS"]

    def list_views(self, schema=None):
        self.calls.append(("list_views", schema))
        return ["ACTIVE_USERS"]

    def get_table_info(self, name, schema=None):
        self.calls.append(("get_table_info", name, schema))
        return TableInfo() if name == "USERS" else None

    def list_columns(self, name, schema=None):
        self.calls.append(("list_columns", name, schema))
        return [{"name": "ID", "type": "INTEGER"}, {"name": "NAME", "type": "VARCHAR"}]

    def list_indexes(self, name, schema=None):
        self.calls.append(("list_indexes", name, schema))
        return [{"name": "IDX_USERS_NAME"}]

    def list_foreign_keys(self, name, schema=None):
        self.calls.append(("list_foreign_keys", name, schema))
        return [{"name": "FK_USERS_ROLE"}]

    def list_triggers(self, table=None, schema=None):
        self.calls.append(("list_triggers", table_name, schema))
        return [{"name": "TRG_AUDIT"}]

    def get_database_info(self):
        self.calls.append(("get_database_info",))
        return {"name": "/tmp/x.fdb", "page_size": 8192}


class RaisingIntrospector(FakeIntrospector):
    def __init__(self, exc):
        super().__init__()
        self._exc = exc

    def list_tables(self, schema=None, include_system=False):
        raise self._exc


def make_async_introspector(exc=None):
    if exc is not None:
        async def list_tables(schema=None, include_system=False):
            raise exc

        return type("AI", (), {"list_tables": staticmethod(list_tables)})()

    base = FakeIntrospector()

    class AsyncFakeIntrospector:
        def __getattr__(self, name):
            attr = getattr(base, name)

            async def runner(*args, **kwargs):
                return attr(*args, **kwargs)

            return runner

        def track(self, name):
            return name

    return AsyncFakeIntrospector()


class FakeBackend:
    last_instance = None

    def __init__(self, connection_config=None):
        self.connection_config = connection_config
        self._connection = None
        self.disconnect_calls = 0
        self.introspector = FakeIntrospector()
        FakeBackend.last_instance = self

    def connect(self):
        self._connection = object()

    def disconnect(self):
        self.disconnect_calls += 1
        self._connection = None


@pytest.fixture(autouse=True)
def clean_fb_env(monkeypatch):
    for name in ("FIREBIRD_HOST", "FIREBIRD_PORT", "FIREBIRD_DATABASE",
                 "FIREBIRD_USER", "FIREBIRD_PASSWORD", "FIREBIRD_ROLE"):
        monkeypatch.delenv(name, raising=False)


class TestIntrospectParserContract:
    def test_all_types_accepted(self):
        for introspect_type in INTROSPECT_TYPES:
            args = parse_introspect_args(["introspect", introspect_type])
            assert args.type == introspect_type

    def test_name_schema_and_flags(self):
        args = parse_introspect_args([
            "introspect", "columns", "users", "--schema", "MAIN",
            "--include-system",
        ])
        assert args.name == "users"
        assert args.schema == "MAIN"
        assert args.include_system is True

    def test_defaults(self):
        args = parse_introspect_args(["introspect", "tables"])
        assert args.name is None
        assert args.schema is None
        assert args.include_system is False
        assert args.output == "table"

    def test_invalid_type_rejected(self):
        with pytest.raises(SystemExit) as excinfo:
            parse_introspect_args(["introspect", "stored-procs"])
        assert excinfo.value.code == 2

    def test_no_dsn_form_exists(self):
        with pytest.raises(SystemExit) as excinfo:
            parse_introspect_args(["introspect", "--dsn", "x"])
        assert excinfo.value.code == 2


class TestIntrospectHandleHappyPaths:
    @pytest.mark.parametrize("argv,marker,call_prefix", [
        (["tables"], "ORDERS", "list_tables"),
        (["views"], "ACTIVE_USERS", "list_views"),
        (["table", "USERS"], "FK_ORDERS", "get_table_info"),
        (["columns", "USERS"], "VARCHAR", "list_columns"),
        (["indexes", "USERS"], "IDX_USERS_NAME", "list_indexes"),
        (["foreign-keys", "USERS"], "FK_USERS_ROLE", "list_foreign_keys"),
        (["triggers"], "TRG_AUDIT", "list_triggers"),
        (["database"], "page_size", "get_database_info"),
    ])
    def test_each_type_output(self, monkeypatch, capsys, argv, marker, call_prefix):
        monkeypatch.setattr(introspect_mod, "FirebirdBackend", FakeBackend)
        args = parse_introspect_args(["introspect", *argv, "--database", "/tmp/x.fdb", "-o", "json"])
        introspect_mod.handle(args)
        out = capsys.readouterr().out
        assert marker in out
        assert FakeBackend.last_instance.introspector.calls[0][0] == call_prefix
        assert FakeBackend.last_instance.disconnect_calls == 1

    def test_table_without_optional_sections_shows_only_columns(self, monkeypatch, capsys):
        monkeypatch.setattr(introspect_mod, "FirebirdBackend", FakeBackend)

        def bare_info(self, name, schema=None):
            return TableInfo(indexes=[], foreign_keys=[])

        monkeypatch.setattr(FakeIntrospector, "get_table_info", bare_info)
        args = parse_introspect_args(["introspect", "table", "USERS", "--database", "/tmp/x.fdb"])
        introspect_mod.handle(args)
        out = capsys.readouterr().out
        assert '"ID"' in out
        assert "RDB$PRIMARY" not in out
        assert "FK_ORDERS" not in out

    def test_include_system_forwarded(self, monkeypatch):
        monkeypatch.setattr(introspect_mod, "FirebirdBackend", FakeBackend)
        args = parse_introspect_args([
            "introspect", "tables", "--database", "/tmp/x.fdb", "--include-system",
        ])
        introspect_mod.handle(args)
        call = FakeBackend.last_instance.introspector.calls[0]
        assert call == ("list_tables", None, True)

    def test_schema_forwarded(self, monkeypatch):
        monkeypatch.setattr(introspect_mod, "FirebirdBackend", FakeBackend)
        args = parse_introspect_args([
            "introspect", "columns", "USERS", "--database", "/tmp/x.fdb", "--schema", "MAIN",
        ])
        introspect_mod.handle(args)
        call = FakeBackend.last_instance.introspector.calls[0]
        assert call == ("list_columns", "USERS", "MAIN")

    def test_default_table_output_emits_rows_via_fallback_provider(self, monkeypatch, capsys):
        monkeypatch.setattr(introspect_mod, "FirebirdBackend", FakeBackend)
        args = parse_introspect_args(["introspect", "tables", "--database", "/tmp/x.fdb"])
        introspect_mod.handle(args)
        assert "USERS" in capsys.readouterr().out


class TestIntrospectArgumentValidation:
    @pytest.mark.parametrize("introspect_type", ["table", "columns", "indexes", "foreign-keys"])
    def test_missing_name_exits_nonzero(self, monkeypatch, capsys, introspect_type):
        monkeypatch.setattr(introspect_mod, "FirebirdBackend", FakeBackend)
        args = parse_introspect_args(["introspect", introspect_type, "--database", "/tmp/x.fdb"])
        with pytest.raises(SystemExit) as excinfo:
            introspect_mod.handle(args)
        assert excinfo.value.code == 1
        assert "Table name is required" in capsys.readouterr().err

    def test_unknown_table_exits_nonzero(self, monkeypatch, capsys):
        monkeypatch.setattr(introspect_mod, "FirebirdBackend", FakeBackend)
        args = parse_introspect_args(["introspect", "table", "GHOST", "--database", "/tmp/x.fdb"])
        with pytest.raises(SystemExit) as excinfo:
            introspect_mod.handle(args)
        assert excinfo.value.code == 1
        assert "Table 'GHOST' not found" in capsys.readouterr().err


class TestIntrospectAsyncPath:
    def test_async_tables_json(self, capsys):
        class AsyncBackend(FakeBackend):
            async def connect(self):
                self._connection = object()

            async def disconnect(self):
                self.disconnect_calls += 1
                self._connection = None

        backend = AsyncBackend()
        backend.introspector = make_async_introspector()
        args = parse_introspect_args(["introspect", "tables", "--database", "/tmp/x.fdb", "-o", "json"])
        asyncio.run(
            introspect_mod._handle_introspect_async(args, backend, introspect_mod.create_provider("json"))
        )
        assert "ORDERS" in capsys.readouterr().out
        assert backend.disconnect_calls == 1

    def test_async_query_error_exits_nonzero(self):
        class AsyncBackend(FakeBackend):
            async def connect(self):
                self._connection = object()

            async def disconnect(self):
                self._connection = None

        backend = AsyncBackend()
        backend.introspector = make_async_introspector(exc=QueryError("no such table"))
        args = parse_introspect_args(["introspect", "tables", "--database", "/tmp/x.fdb"])
        with pytest.raises(SystemExit) as excinfo:
            asyncio.run(
                introspect_mod._handle_introspect_async(args, backend, introspect_mod.create_provider("json"))
            )
        assert excinfo.value.code == 1


class TestIntrospectErrorPaths:
    def test_missing_database_exits_with_stderr_message(self, capsys):
        args = parse_introspect_args(["introspect", "tables"])
        with pytest.raises(SystemExit) as excinfo:
            introspect_mod.handle(args)
        assert excinfo.value.code == 1
        assert "--database is required" in capsys.readouterr().err

    def test_connection_error_exits_nonzero(self, monkeypatch):
        class RefusedBackend(FakeBackend):
            def connect(self):
                raise ConnectionError("unavailable")

        monkeypatch.setattr(introspect_mod, "FirebirdBackend", RefusedBackend)
        args = parse_introspect_args(["introspect", "tables", "--database", "/tmp/x.fdb"])
        with pytest.raises(SystemExit) as excinfo:
            introspect_mod.handle(args)
        assert excinfo.value.code == 1

    def test_query_error_exits_nonzero(self, monkeypatch):
        monkeypatch.setattr(introspect_mod, "FirebirdBackend", FakeBackend)
        original_init = FakeBackend.__init__

        def patched_init(self, connection_config=None):
            original_init(self, connection_config)
            self.introspector = RaisingIntrospector(QueryError("malformed"))

        monkeypatch.setattr(FakeBackend, "__init__", patched_init)
        args = parse_introspect_args(["introspect", "tables", "--database", "/tmp/x.fdb"])
        with pytest.raises(SystemExit) as excinfo:
            introspect_mod.handle(args)
        assert excinfo.value.code == 1

    def test_unexpected_error_prints_to_stderr_and_exits(self, monkeypatch, capsys):
        monkeypatch.setattr(introspect_mod, "FirebirdBackend", FakeBackend)

        class BrokenIntrospector(FakeIntrospector):
            def list_tables(self, schema=None, include_system=False):
                raise RuntimeError("boom")

        original_init = FakeBackend.__init__

        def patched_init(self, connection_config=None):
            original_init(self, connection_config)
            self.introspector = BrokenIntrospector()

        monkeypatch.setattr(FakeBackend, "__init__", patched_init)
        args = parse_introspect_args(["introspect", "tables", "--database", "/tmp/x.fdb"])
        with pytest.raises(SystemExit) as excinfo:
            introspect_mod.handle(args)
        assert excinfo.value.code == 1
        assert "Error during introspection" in capsys.readouterr().err
