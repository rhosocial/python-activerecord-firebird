# tests/rhosocial/activerecord_firebird_test/feature/backend/test_execute_error_contract.py
"""Firebird execution phases follow the shared execute error contract.

Every case installs a fake connection/cursor on a backend that never
connects, so the module runs offline. It covers the phases the backend owns:
auto-commit, driver-error mapping inside ``execute_many``, framework errors
passing through untouched, and cleanup that cannot replace the original
failure.

The sync and async cases are one class each with identical method names;
``pytest.ini``-style asyncio auto mode picks up the coroutines directly.
"""

from typing import Optional

import pytest

pytest.importorskip("firebird.driver")

from firebird.driver import DatabaseError as FirebirdDriverError  # noqa: E402

from rhosocial.activerecord.backend.errors import (  # noqa: E402
    ConnectionError,
    DatabaseError,
    DeadlockError,
    QueryError,
    TransactionError,
)
from rhosocial.activerecord.backend.impl.firebird.backend.async_backend import (  # noqa: E402
    AsyncFirebirdBackend,
)
from rhosocial.activerecord.backend.impl.firebird.backend.backend import (  # noqa: E402
    FirebirdBackend,
)
from rhosocial.activerecord.backend.options import (  # noqa: E402
    ExecutionOptions,
    StatementType,
)


class _FakeCursor:
    """Cursor double that raises at the requested phase and records cleanup."""

    def __init__(
        self,
        *,
        execute_error: Optional[Exception] = None,
        executemany_error: Optional[Exception] = None,
        close_error: Optional[Exception] = None,
    ):
        self.rowcount = 1
        self.description = None
        self.close_calls = 0
        self._execute_error = execute_error
        self._executemany_error = executemany_error
        self._close_error = close_error

    def execute(self, sql, params=None):
        if self._execute_error is not None:
            raise self._execute_error
        return self

    def executemany(self, sql, params_list):
        if self._executemany_error is not None:
            raise self._executemany_error
        return self

    def fetchall(self):
        return []

    def close(self):
        self.close_calls += 1
        if self._close_error is not None:
            raise self._close_error


class _FakeConnection:
    """Connection double that records and optionally fails ``commit``."""

    def __init__(self, *, commit_error: Optional[Exception] = None):
        self.commit_calls = 0
        self._commit_error = commit_error

    def cursor(self):
        return _FakeCursor()

    def commit(self):
        self.commit_calls += 1
        if self._commit_error is not None:
            raise self._commit_error


class _RefusingBackend(FirebirdBackend):
    """Sync backend whose cursor lookup raises a framework error."""

    def __init__(self, error: Exception):
        super().__init__(database="contract.fdb")
        self._raised_error = error
        self._connection = _FakeConnection()
        self._cursor = _FakeCursor()
        self._is_connected = True

    def _get_cursor(self):
        raise self._raised_error


class _AsyncRefusingBackend(AsyncFirebirdBackend):
    """Async backend whose cursor lookup raises a framework error."""

    def __init__(self, error: Exception):
        super().__init__(database="contract.fdb")
        self._raised_error = error
        self._connection = _FakeConnection()
        self._cursor = _FakeCursor()
        self._is_connected = True

    async def _get_cursor(self):
        raise self._raised_error


def _options() -> ExecutionOptions:
    return ExecutionOptions(stmt_type=StatementType.DML)


def _sync_backend(connection, cursor) -> FirebirdBackend:
    backend = FirebirdBackend(database="contract.fdb")
    backend._connection = connection
    backend._cursor = cursor
    backend._is_connected = True
    return backend


def _async_backend(connection, cursor) -> AsyncFirebirdBackend:
    backend = AsyncFirebirdBackend(database="contract.fdb")
    backend._connection = connection
    backend._cursor = cursor
    backend._is_connected = True
    return backend


class TestExecuteErrorPhases:
    """Execution phases: sync Firebird backend."""

    def test_commit_failure_raises_transaction_error_and_withholds_result(self):
        commit_error = FirebirdDriverError(
            "connection lost during commit", sqlstate="08006", sqlcode=-904
        )
        connection = _FakeConnection(commit_error=commit_error)
        backend = _sync_backend(connection, _FakeCursor())

        with pytest.raises(TransactionError) as info:
            backend.execute("UPDATE users SET name = 'x'", options=_options())

        assert info.value.__cause__ is commit_error
        assert connection.commit_calls == 1

    def test_execute_many_update_conflict_maps_to_deadlock(self):
        conflict = FirebirdDriverError(
            "update conflicts with concurrent update", sqlstate="40001", sqlcode=-901
        )
        connection = _FakeConnection()
        backend = _sync_backend(connection, _FakeCursor(executemany_error=conflict))

        with pytest.raises(DeadlockError) as info:
            backend.execute_many("UPDATE users SET name = ?", [("a",), ("b",)])

        assert info.value.__cause__ is conflict
        assert info.value.transient is True
        # The batch failed before the commit phase, so nothing was committed.
        assert connection.commit_calls == 0

    def test_execute_many_commit_is_attempted_and_failure_surfaces(self):
        commit_error = FirebirdDriverError("lock conflict on commit", sqlstate="40001")
        connection = _FakeConnection(commit_error=commit_error)
        backend = _sync_backend(connection, _FakeCursor())

        with pytest.raises(TransactionError) as info:
            backend.execute_many("UPDATE users SET name = ?", [("a",), ("b",)])

        assert connection.commit_calls == 1
        assert info.value.__cause__ is commit_error

    def test_framework_connection_error_from_get_cursor_propagates_unchanged(self):
        error = ConnectionError("Not connected to Firebird database")
        backend = _RefusingBackend(error)

        with pytest.raises(ConnectionError) as info:
            backend.execute("SELECT 1 FROM rdb$database", options=_options())

        assert info.value is error

    def test_cursor_close_failure_does_not_replace_original_error(self):
        driver_error = FirebirdDriverError("Token unknown", sqlstate="42000")
        cursor = _FakeCursor(
            execute_error=driver_error,
            close_error=RuntimeError("close failed"),
        )
        backend = _sync_backend(_FakeConnection(), cursor)

        with pytest.raises(QueryError) as info:
            backend.execute("SELECT FROM", options=_options())

        assert info.value.__cause__ is driver_error
        # The close was attempted, and its failure was discarded instead of
        # replacing the QueryError that carries the driver cause.
        assert cursor.close_calls == 1

    def test_executescript_commit_failure_raises_transaction_error(self):
        commit_error = FirebirdDriverError("connection lost", sqlstate="08006", sqlcode=-904)
        connection = _FakeConnection(commit_error=commit_error)
        backend = _sync_backend(connection, _FakeCursor())

        with pytest.raises(TransactionError) as info:
            backend.executescript("UPDATE users SET name = 'x'")

        assert info.value.__cause__ is commit_error
        assert connection.commit_calls == 1

    def test_driver_error_is_mapped_not_returned_none(self):
        driver_error = FirebirdDriverError("Token unknown", sqlstate="42000")
        backend = _sync_backend(_FakeConnection(), _FakeCursor(execute_error=driver_error))

        with pytest.raises(DatabaseError) as info:
            backend.execute("SELECT FROM", options=_options())

        assert isinstance(info.value, QueryError)
        assert info.value.__cause__ is driver_error


class TestAsyncExecuteErrorPhases:
    """Execution phases: async Firebird backend (same method names as sync)."""

    async def test_commit_failure_raises_transaction_error_and_withholds_result(self):
        commit_error = FirebirdDriverError("connection lost", sqlstate="08006", sqlcode=-904)
        connection = _FakeConnection(commit_error=commit_error)
        backend = _async_backend(connection, _FakeCursor())

        with pytest.raises(TransactionError) as info:
            await backend.execute("UPDATE users SET name = 'x'", options=_options())

        assert info.value.__cause__ is commit_error
        assert connection.commit_calls == 1

    async def test_driver_error_is_mapped_not_returned_none(self):
        driver_error = FirebirdDriverError("Token unknown", sqlstate="42000")
        backend = _async_backend(_FakeConnection(), _FakeCursor(execute_error=driver_error))

        with pytest.raises(DatabaseError) as info:
            await backend.execute("SELECT FROM", options=_options())

        assert isinstance(info.value, QueryError)
        assert info.value.__cause__ is driver_error

    async def test_framework_connection_error_from_get_cursor_propagates_unchanged(self):
        error = ConnectionError("Not connected to Firebird database")
        backend = _AsyncRefusingBackend(error)

        with pytest.raises(ConnectionError) as info:
            await backend.execute("SELECT 1 FROM rdb$database", options=_options())

        assert info.value is error

    async def test_cursor_close_failure_does_not_replace_original_error(self):
        driver_error = FirebirdDriverError("Token unknown", sqlstate="42000")
        cursor = _FakeCursor(
            execute_error=driver_error,
            close_error=RuntimeError("close failed"),
        )
        backend = _async_backend(_FakeConnection(), cursor)

        with pytest.raises(QueryError) as info:
            await backend.execute("SELECT FROM", options=_options())

        assert info.value.__cause__ is driver_error
        assert cursor.close_calls == 1
