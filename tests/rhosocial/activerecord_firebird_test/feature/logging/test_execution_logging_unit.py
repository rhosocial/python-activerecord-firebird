# tests/rhosocial/activerecord_firebird_test/feature/logging/test_execution_logging_unit.py
"""DB-free unit tests for the Firebird execution logging changes.

Every test here uses fake connections and cursors, so the module runs without a
live Firebird server or the optional firebird-driver.  The sync and async
classes exercise the same methods with the same names.
"""

import argparse
import logging

import pytest

from rhosocial.activerecord.backend.errors import DatabaseError
from rhosocial.activerecord.backend.impl.firebird.backend import (
    AsyncFirebirdBackend,
    FirebirdBackend,
)
from rhosocial.activerecord.backend.impl.firebird.backend import (
    async_backend as async_backend_module,
)
from rhosocial.activerecord.backend.impl.firebird.backend import (
    backend as backend_module,
)
from rhosocial.activerecord.backend.impl.firebird.cli import info as cli_info
from rhosocial.activerecord.backend.impl.firebird.cli import query as cli_query
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig
from rhosocial.activerecord.backend.options import (
    BulkInsertOptions,
    ExecutionOptions,
    InsertOptions,
    LogContext,
)
from rhosocial.activerecord.backend.result import QueryResult
from rhosocial.activerecord.backend.schema import StatementType

CANONICAL_LOGGER = "rhosocial.activerecord.backend.firebird"
CLI_QUERY_LOGGER = "rhosocial.activerecord.backend.firebird.cli.query"


class _FakeCursor:
    """Minimal DB-API cursor double with an optional error injection."""

    def __init__(self, *, rowcount: int = -1, rows=None, error=None):
        self.rowcount = rowcount
        self.description = None
        self._rows = rows or []
        self._error = error
        self.executed = []
        self.executemany_calls = []

    def execute(self, sql, params=None):
        if self._error is not None:
            raise self._error
        self.executed.append((sql, params))
        return self

    def executemany(self, sql, params_list):
        if self._error is not None:
            raise self._error
        self.executemany_calls.append((sql, params_list))
        return self

    def fetchall(self):
        if self._error is not None:
            raise self._error
        return self._rows

    def close(self):
        pass


class _FakeAsyncCursor(_FakeCursor):
    """Cursor double whose ``executemany`` is awaitable for the async pipeline."""

    async def executemany(self, sql, params_list):
        if self._error is not None:
            raise self._error
        self.executemany_calls.append((sql, params_list))
        return self


class _FakeConnection:
    """Connection double that records commits and hands out the fake cursor."""

    def __init__(self, cursor):
        self._cursor = cursor
        self.commit_calls = 0
        self.closed = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.commit_calls += 1

    def close(self):
        self.closed = True

    def is_closed(self):
        return self.closed


def _sync_backend() -> FirebirdBackend:
    return FirebirdBackend(
        connection_config=FirebirdConnectionConfig(database="unit-test.fdb")
    )


def _async_backend() -> AsyncFirebirdBackend:
    return AsyncFirebirdBackend(
        connection_config=FirebirdConnectionConfig(database="unit-test.fdb")
    )


def _wire_backend(backend, cursor):
    """Install a fake connection/cursor so execution never touches a real DB."""
    connection = _FakeConnection(cursor)
    backend._connection = connection
    backend._cursor = cursor
    backend._is_connected = True
    return connection


class TestExecutionLogging:
    """Synchronous execution logging branches."""

    def test_backends_import_and_share_canonical_logger(self):
        sync_backend = _sync_backend()
        async_backend = _async_backend()

        assert backend_module.FirebirdBackend is FirebirdBackend
        assert async_backend_module.AsyncFirebirdBackend is AsyncFirebirdBackend
        assert sync_backend.logger.name == CANONICAL_LOGGER
        assert async_backend.logger.name == CANONICAL_LOGGER

    def test_execute_many_does_not_log_values(self, caplog):
        backend = _sync_backend()
        cursor = _FakeCursor(rowcount=-1)
        _wire_backend(backend, cursor)

        options = ExecutionOptions(
            stmt_type=StatementType.DML,
            log_context=LogContext(operation="insert", object_name="items"),
        )
        with caplog.at_level(logging.DEBUG, logger=CANONICAL_LOGGER):
            result = backend.execute_many(
                "INSERT INTO items (name) VALUES (?)",
                [("secret-one",), ("secret-two",)],
                options=options,
            )

        assert result.affected_rows == 2
        assert len(cursor.executemany_calls) == 1
        assert "secret-one" not in caplog.text
        assert "secret-two" not in caplog.text

    def test_executescript_logs_debug_and_info(self, caplog):
        backend = _sync_backend()
        cursor = _FakeCursor(rowcount=7)
        _wire_backend(backend, cursor)

        with caplog.at_level(logging.DEBUG, logger=CANONICAL_LOGGER):
            result = backend.executescript("UPDATE items SET flag = 1")

        assert result.affected_rows == 7
        assert "Executing SQL script." in caplog.text
        assert "SQL script executed successfully" in caplog.text

    def test_executescript_error_is_debug_and_reraised(self, caplog):
        backend = _sync_backend()
        cursor = _FakeCursor(error=RuntimeError("script boom"))
        _wire_backend(backend, cursor)

        with caplog.at_level(logging.DEBUG, logger=CANONICAL_LOGGER):
            with pytest.raises(DatabaseError):
                backend.executescript("BROKEN SCRIPT")

        assert "Error executing SQL script" in caplog.text

    def test_process_result_set_error_is_debug_and_reraised(self, caplog):
        backend = _sync_backend()
        cursor = _FakeCursor(error=RuntimeError("fetch failed"))

        with caplog.at_level(logging.DEBUG, logger=CANONICAL_LOGGER):
            with pytest.raises(RuntimeError):
                backend._process_result_set(cursor, True)

        assert "Error processing result set" in caplog.text

    def test_insert_builds_insert_log_context(self, monkeypatch):
        backend = _sync_backend()
        captured = []

        def fake_execute(sql, params=None, *, options=None):
            captured.append(options)
            return QueryResult(data=[], affected_rows=1)

        monkeypatch.setattr(backend, "execute", fake_execute)
        result = backend.insert("items", values={"name": "unit"})

        assert result.affected_rows == 1
        assert captured[0].log_context.operation == "insert"
        assert captured[0].log_context.object_name == "items"

    def test_insert_options_receive_explicit_log_context(self, monkeypatch):
        backend = _sync_backend()
        captured = []

        def fake_execute(sql, params=None, *, options=None):
            captured.append(options)
            return QueryResult(data=[], affected_rows=1)

        monkeypatch.setattr(backend, "execute", fake_execute)
        options = InsertOptions(table="items", data={"name": "unit"})
        context = LogContext(operation="bulk_insert", object_name="items")
        backend.insert(options, log_context=context)

        assert options.log_context is not None
        assert options.log_context.operation == "bulk_insert"
        assert captured[0].log_context.operation == "bulk_insert"

    def test_update_raw_sql_builds_update_log_context(self, monkeypatch):
        backend = _sync_backend()
        captured = []

        def fake_execute(sql, params=None, *, options=None):
            captured.append(options)
            return QueryResult(data=[], affected_rows=1)

        monkeypatch.setattr(backend, "execute", fake_execute)
        backend.update(
            "items",
            values={"name": "unit"},
            where_clause=("id = ?", (1,)),
        )

        assert captured[0].log_context.operation == "update"
        assert captured[0].log_context.object_name == "items"

    def test_update_returning_keeps_log_context(self, monkeypatch):
        backend = _sync_backend()
        captured = []

        def fake_execute(sql, params=None, *, options=None):
            captured.append(options)
            return QueryResult(data=[{"ID": 1}], affected_rows=1)

        monkeypatch.setattr(backend, "execute", fake_execute)
        backend.update(
            "items",
            values={"name": "unit"},
            where_clause=("id = ?", (1,)),
            returning_columns=["id"],
        )

        assert captured[0].process_result_set is True
        assert captured[0].log_context.operation == "update"

    def test_delete_raw_sql_builds_delete_log_context(self, monkeypatch):
        backend = _sync_backend()
        captured = []

        def fake_execute(sql, params=None, *, options=None):
            captured.append(options)
            return QueryResult(data=[], affected_rows=1)

        monkeypatch.setattr(backend, "execute", fake_execute)
        backend.delete("items", where_clause=("id = ?", (1,)))

        assert captured[0].log_context.operation == "delete"
        assert captured[0].log_context.object_name == "items"

    def test_delete_returning_keeps_log_context(self, monkeypatch):
        backend = _sync_backend()
        captured = []

        def fake_execute(sql, params=None, *, options=None):
            captured.append(options)
            return QueryResult(data=[{"ID": 1}], affected_rows=1)

        monkeypatch.setattr(backend, "execute", fake_execute)
        backend.delete("items", where_clause=("id = ?", (1,)), returning_columns=["id"])

        assert captured[0].process_result_set is True
        assert captured[0].log_context.operation == "delete"

    def test_bulk_insert_propagates_bulk_log_context(self, monkeypatch):
        backend = _sync_backend()
        captured = []

        def fake_insert(table_name, values=None, returning_columns=None, log_context=None):
            captured.append((table_name, values, returning_columns, log_context))
            return QueryResult(data=[], affected_rows=1)

        monkeypatch.setattr(backend, "insert", fake_insert)
        options = BulkInsertOptions(
            table="items",
            columns=["name"],
            rows=[("first",), ("second",)],
        )
        result = backend.bulk_insert(options)

        assert result.affected_rows == 2
        assert len(captured) == 2
        for _, _, _, log_context in captured:
            assert log_context.operation == "bulk_insert"
            assert log_context.object_name == "items"

    def test_bulk_insert_with_returning_uses_insert_log_context(self, monkeypatch):
        backend = _sync_backend()
        captured = []

        def fake_insert(table_name, values=None, returning_columns=None, log_context=None):
            captured.append((table_name, values, returning_columns, log_context))
            return QueryResult(data=[{"ID": len(captured)}], affected_rows=1)

        monkeypatch.setattr(backend, "insert", fake_insert)
        options = BulkInsertOptions(
            table="items",
            columns=["name"],
            rows=[("first",), ("second",)],
            returning_columns=["id"],
        )
        result = backend.bulk_insert(options)

        assert result.affected_rows == 2
        assert len(result.data) == 2
        assert captured[0][2] == ["id"]
        assert captured[0][3].operation == "bulk_insert"


class TestAsyncExecutionLogging:
    """Asynchronous counterparts of the sync execution logging branches."""

    async def test_backends_import_and_share_canonical_logger(self):
        sync_backend = _sync_backend()
        async_backend = _async_backend()

        assert backend_module.FirebirdBackend is FirebirdBackend
        assert async_backend_module.AsyncFirebirdBackend is AsyncFirebirdBackend
        assert sync_backend.logger.name == CANONICAL_LOGGER
        assert async_backend.logger.name == CANONICAL_LOGGER

    async def test_execute_many_does_not_log_values(self, caplog):
        backend = _async_backend()
        cursor = _FakeAsyncCursor(rowcount=2)
        _wire_backend(backend, cursor)

        options = ExecutionOptions(
            stmt_type=StatementType.DML,
            log_context=LogContext(operation="insert", object_name="items"),
        )
        with caplog.at_level(logging.DEBUG, logger=CANONICAL_LOGGER):
            result = await backend.execute_many(
                "INSERT INTO items (name) VALUES (?)",
                [("secret-one",), ("secret-two",)],
                options=options,
            )

        assert result.affected_rows == 2
        assert len(cursor.executemany_calls) == 1
        assert "secret-one" not in caplog.text
        assert "secret-two" not in caplog.text

    async def test_executescript_logs_debug_and_info(self, caplog):
        backend = _async_backend()
        cursor = _FakeAsyncCursor(rowcount=7)
        _wire_backend(backend, cursor)

        with caplog.at_level(logging.DEBUG, logger=CANONICAL_LOGGER):
            await backend.executescript("UPDATE items SET flag = 1")

        assert backend._connection.commit_calls == 1
        assert "Executing SQL script asynchronously." in caplog.text
        assert "Async SQL script executed successfully" in caplog.text

    async def test_executescript_error_is_debug_and_reraised(self, caplog):
        backend = _async_backend()
        cursor = _FakeAsyncCursor(error=RuntimeError("script boom"))
        _wire_backend(backend, cursor)

        with caplog.at_level(logging.DEBUG, logger=CANONICAL_LOGGER):
            with pytest.raises(DatabaseError):
                await backend.executescript("BROKEN SCRIPT")

        assert "Error executing async SQL script" in caplog.text

    async def test_process_result_set_error_is_debug_and_reraised(self, caplog):
        backend = _async_backend()
        cursor = _FakeAsyncCursor(error=RuntimeError("fetch failed"))

        with caplog.at_level(logging.DEBUG, logger=CANONICAL_LOGGER):
            with pytest.raises(RuntimeError):
                await backend._process_result_set(cursor, True)

        assert "Error processing result set" in caplog.text

    async def test_insert_builds_insert_log_context(self, monkeypatch):
        backend = _async_backend()
        captured = []

        async def fake_execute(sql, params=None, *, options=None):
            captured.append(options)
            return QueryResult(data=[], affected_rows=1)

        monkeypatch.setattr(backend, "execute", fake_execute)
        result = await backend.insert("items", values={"name": "unit"})

        assert result.affected_rows == 1
        assert captured[0].log_context.operation == "insert"
        assert captured[0].log_context.object_name == "items"

    async def test_insert_options_receive_explicit_log_context(self, monkeypatch):
        backend = _async_backend()
        captured = []

        async def fake_execute(sql, params=None, *, options=None):
            captured.append(options)
            return QueryResult(data=[], affected_rows=1)

        monkeypatch.setattr(backend, "execute", fake_execute)
        options = InsertOptions(table="items", data={"name": "unit"})
        context = LogContext(operation="bulk_insert", object_name="items")
        await backend.insert(options, log_context=context)

        assert options.log_context is not None
        assert options.log_context.operation == "bulk_insert"
        assert captured[0].log_context.operation == "bulk_insert"

    async def test_update_raw_sql_builds_update_log_context(self, monkeypatch):
        backend = _async_backend()
        captured = []

        async def fake_execute(sql, params=None, *, options=None):
            captured.append(options)
            return QueryResult(data=[], affected_rows=1)

        monkeypatch.setattr(backend, "execute", fake_execute)
        await backend.update(
            "items",
            values={"name": "unit"},
            where_clause=("id = ?", (1,)),
        )

        assert captured[0].log_context.operation == "update"
        assert captured[0].log_context.object_name == "items"

    async def test_update_returning_keeps_log_context(self, monkeypatch):
        backend = _async_backend()
        captured = []

        async def fake_execute(sql, params=None, *, options=None):
            captured.append(options)
            return QueryResult(data=[{"ID": 1}], affected_rows=1)

        monkeypatch.setattr(backend, "execute", fake_execute)
        await backend.update(
            "items",
            values={"name": "unit"},
            where_clause=("id = ?", (1,)),
            returning_columns=["id"],
        )

        assert captured[0].process_result_set is True
        assert captured[0].log_context.operation == "update"

    async def test_delete_raw_sql_builds_delete_log_context(self, monkeypatch):
        backend = _async_backend()
        captured = []

        async def fake_execute(sql, params=None, *, options=None):
            captured.append(options)
            return QueryResult(data=[], affected_rows=1)

        monkeypatch.setattr(backend, "execute", fake_execute)
        await backend.delete("items", where_clause=("id = ?", (1,)))

        assert captured[0].log_context.operation == "delete"
        assert captured[0].log_context.object_name == "items"

    async def test_delete_returning_keeps_log_context(self, monkeypatch):
        backend = _async_backend()
        captured = []

        async def fake_execute(sql, params=None, *, options=None):
            captured.append(options)
            return QueryResult(data=[{"ID": 1}], affected_rows=1)

        monkeypatch.setattr(backend, "execute", fake_execute)
        await backend.delete("items", where_clause=("id = ?", (1,)), returning_columns=["id"])

        assert captured[0].process_result_set is True
        assert captured[0].log_context.operation == "delete"

    async def test_bulk_insert_propagates_bulk_log_context(self, monkeypatch):
        backend = _async_backend()
        captured = []

        async def fake_insert(table_name, values=None, returning_columns=None, log_context=None):
            captured.append((table_name, values, returning_columns, log_context))
            return QueryResult(data=[], affected_rows=1)

        monkeypatch.setattr(backend, "insert", fake_insert)
        options = BulkInsertOptions(
            table="items",
            columns=["name"],
            rows=[("first",), ("second",)],
        )
        result = await backend.bulk_insert(options)

        assert result.affected_rows == 2
        assert len(captured) == 2
        for _, _, _, log_context in captured:
            assert log_context.operation == "bulk_insert"
            assert log_context.object_name == "items"

    async def test_bulk_insert_with_returning_uses_insert_log_context(self, monkeypatch):
        backend = _async_backend()
        captured = []

        async def fake_insert(table_name, values=None, returning_columns=None, log_context=None):
            captured.append((table_name, values, returning_columns, log_context))
            return QueryResult(data=[{"ID": len(captured)}], affected_rows=1)

        monkeypatch.setattr(backend, "insert", fake_insert)
        options = BulkInsertOptions(
            table="items",
            columns=["name"],
            rows=[("first",), ("second",)],
            returning_columns=["id"],
        )
        result = await backend.bulk_insert(options)

        assert result.affected_rows == 2
        assert len(result.data) == 2
        assert captured[0][2] == ["id"]
        assert captured[0][3].operation == "bulk_insert"


class _FakeProvider:
    """Output provider double that only records the greeting call."""

    def __init__(self):
        self.greeted = False

    def display_greeting(self):
        self.greeted = True


def _query_args(**overrides):
    values = {
        "log_level": "INFO",
        "output": "json",
        "rich_ascii": False,
        "sql": None,
        "file": None,
        "is_async": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class TestCliLogging:
    """CLI modules import and log through the framework namespace."""

    def test_cli_loggers_use_framework_namespace(self):
        assert cli_info.logger.name == "rhosocial.activerecord.backend.firebird.cli.info"
        assert cli_query.logger.name == CLI_QUERY_LOGGER

    def test_query_reports_missing_file(self, monkeypatch, tmp_path, caplog):
        provider = _FakeProvider()
        monkeypatch.setattr(cli_query, "create_provider", lambda *a, **k: provider)
        monkeypatch.setattr(cli_query.logging, "basicConfig", lambda **kwargs: None)
        args = _query_args(file=str(tmp_path / "missing.sql"))

        with caplog.at_level(logging.ERROR, logger=CLI_QUERY_LOGGER):
            with pytest.raises(SystemExit):
                cli_query.handle(args)

        assert provider.greeted is True
        assert "Error: File not found at" in caplog.text

    def test_query_reports_multiple_statements(self, monkeypatch, caplog):
        provider = _FakeProvider()
        monkeypatch.setattr(cli_query, "create_provider", lambda *a, **k: provider)
        monkeypatch.setattr(cli_query.logging, "basicConfig", lambda **kwargs: None)
        args = _query_args(sql="SELECT 1; SELECT 2")

        with caplog.at_level(logging.ERROR, logger=CLI_QUERY_LOGGER):
            with pytest.raises(SystemExit):
                cli_query.handle(args)

        assert provider.greeted is True
        assert "Multiple SQL statements are not supported." in caplog.text
