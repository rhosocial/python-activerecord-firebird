# tests/rhosocial/activerecord_firebird_test/feature/backend/construct/errors/test_driver_error_mapping.py
"""Firebird driver exceptions map to the shared semantic error taxonomy.

Every case builds a firebird-driver ``DatabaseError`` (or a tiny double that
only exposes ``sqlstate``/``code``) and calls the backend mapping function
directly. No database connection is opened, so the module runs offline; if the
driver is not installed the whole module is skipped.
"""

import pytest

pytest.importorskip("firebird.driver")

from firebird.driver import DatabaseError as FirebirdDriverError  # noqa: E402

from rhosocial.activerecord.backend.errors import (  # noqa: E402
    ConcurrencyError,
    ConnectionError,
    DataError,
    DatabaseError,
    DeadlockError,
    InfrastructureError,
    IntegrityError,
    LockError,
    OperationalError,
    QueryError,
)
from rhosocial.activerecord.backend.impl.firebird.backend.backend import (  # noqa: E402
    FirebirdBackend,
)


@pytest.fixture
def backend():
    """Backend constructed without a connection."""
    return FirebirdBackend(database="taxonomy.fdb")


def translate(backend, error):
    """Return the translated error while checking the original cause."""
    with pytest.raises(DatabaseError) as info:
        backend._handle_error(error)
    assert info.value.__cause__ is error
    return info.value


def test_unique_sqlstate_maps_to_integrity(backend):
    error = FirebirdDriverError(
        "violation of PRIMARY KEY constraint",
        sqlstate="23000",
        sqlcode=-803,
        gds_codes=(335544665,),
    )
    translated = translate(backend, error)
    assert isinstance(translated, IntegrityError)
    assert isinstance(translated, DataError)
    assert translated.sqlstate == "23000"
    assert translated.driver_code == -803
    assert translated.backend == "firebird"
    assert translated.operation == "execute"
    assert translated.transient is False
    assert translated.retryable is False


def test_unique_sqlstate_23505_maps_to_integrity(backend):
    error = FirebirdDriverError("duplicate key value", sqlstate="23505", sqlcode=-803)
    translated = translate(backend, error)
    assert isinstance(translated, IntegrityError)
    assert translated.sqlstate == "23505"
    assert translated.driver_code == -803


def test_not_null_sqlstate_maps_to_integrity(backend):
    error = FirebirdDriverError(
        "validation error for column NAME, value *** null ***",
        sqlstate="22004",
        sqlcode=-625,
    )
    translated = translate(backend, error)
    assert isinstance(translated, IntegrityError)
    assert translated.sqlstate == "22004"
    assert translated.driver_code == -625
    assert translated.transient is False


def test_not_null_code_only_maps_to_integrity(backend):
    error = FirebirdDriverError(
        "validation error for column NAME, value *** null ***", sqlcode=-625
    )
    translated = translate(backend, error)
    assert isinstance(translated, IntegrityError)
    assert translated.driver_code == -625


def test_foreign_key_code_maps_to_integrity(backend):
    error = FirebirdDriverError("foreign key constraint violation", sqlcode=-530)
    translated = translate(backend, error)
    assert isinstance(translated, IntegrityError)
    assert translated.driver_code == -530


def test_update_conflict_sqlstate_maps_to_deadlock(backend):
    error = FirebirdDriverError(
        "update conflicts with concurrent update", sqlstate="40001", sqlcode=-901
    )
    translated = translate(backend, error)
    assert isinstance(translated, DeadlockError)
    assert isinstance(translated, LockError)
    assert isinstance(translated, ConcurrencyError)
    assert translated.transient is True
    assert translated.retryable is True


def test_lock_conflict_901_maps_to_lock_error(backend):
    error = FirebirdDriverError("lock conflict on no wait transaction", sqlcode=-901)
    translated = translate(backend, error)
    assert isinstance(translated, LockError)
    assert not isinstance(translated, DeadlockError)
    assert translated.driver_code == -901
    assert translated.transient is True
    assert translated.retryable is True


def test_lock_conflict_902_maps_to_lock_error(backend):
    error = FirebirdDriverError("lock conflict", sqlcode=-902)
    translated = translate(backend, error)
    assert isinstance(translated, LockError)
    assert not isinstance(translated, DeadlockError)
    assert translated.driver_code == -902
    assert translated.transient is True


def test_deadlock_code_maps_to_deadlock_error(backend):
    error = FirebirdDriverError("deadlock detected", sqlcode=-913)
    translated = translate(backend, error)
    assert isinstance(translated, DeadlockError)
    assert translated.driver_code == -913
    assert translated.transient is True


def test_message_fallback_lock_conflict(backend):
    error = FirebirdDriverError("lock conflict on no wait transaction")
    translated = translate(backend, error)
    assert isinstance(translated, LockError)
    assert translated.transient is True


def test_connection_failure_sqlstate_is_transient(backend):
    error = FirebirdDriverError("connection failure", sqlstate="08006", sqlcode=-904)
    translated = translate(backend, error)
    assert isinstance(translated, OperationalError)
    assert isinstance(translated, InfrastructureError)
    assert translated.transient is True
    assert translated.retryable is True


def test_connection_failed_sqlstate_is_transient(backend):
    error = FirebirdDriverError("unable to establish connection", sqlstate="08001")
    translated = translate(backend, error)
    assert isinstance(translated, ConnectionError)
    assert translated.sqlstate == "08001"
    assert translated.transient is True
    assert translated.retryable is True


def test_connection_code_is_transient(backend):
    error = FirebirdDriverError("connection lost", sqlcode=-904)
    translated = translate(backend, error)
    assert isinstance(translated, ConnectionError)
    assert translated.driver_code == -904
    assert translated.transient is True


def test_authentication_sqlstate_is_not_transient(backend):
    error = FirebirdDriverError(
        "Your user name and password are not defined", sqlstate="28000", sqlcode=-804
    )
    translated = translate(backend, error)
    assert isinstance(translated, ConnectionError)
    assert translated.transient is False
    assert translated.retryable is False


def test_authentication_message_fallback_is_not_transient(backend):
    error = FirebirdDriverError("Your user name and password are not defined")
    translated = translate(backend, error)
    assert isinstance(translated, ConnectionError)
    assert translated.transient is False
    assert translated.retryable is False


def test_unknown_table_maps_to_query_error(backend):
    error = FirebirdDriverError(
        "Dynamic SQL Error: Table unknown - USERS", sqlstate="42S02", sqlcode=-204
    )
    translated = translate(backend, error)
    assert isinstance(translated, QueryError)
    assert translated.sqlstate == "42S02"
    assert translated.driver_code == -204


def test_unknown_column_maps_to_query_error(backend):
    error = FirebirdDriverError("Column unknown - NAME", sqlstate="42S22", sqlcode=-206)
    translated = translate(backend, error)
    assert isinstance(translated, QueryError)
    assert translated.driver_code == -206


def test_syntax_error_maps_to_query_error(backend):
    error = FirebirdDriverError("Token unknown - line 1, column 8", sqlstate="42000")
    translated = translate(backend, error)
    assert isinstance(translated, QueryError)
    assert translated.sqlstate == "42000"


def test_syntax_message_fallback_maps_to_query_error(backend):
    error = FirebirdDriverError("Token unknown - line 1, column 8")
    translated = translate(backend, error)
    assert isinstance(translated, QueryError)


def test_sqlstate_wins_over_code_and_message(backend):
    """A stable SQLSTATE must outrank a misleading code or message."""
    error = FirebirdDriverError("deadlock lock conflict", sqlstate="23000", sqlcode=-901)
    translated = translate(backend, error)
    assert isinstance(translated, IntegrityError)
    assert not isinstance(translated, LockError)


def test_code_wins_over_message(backend):
    error = FirebirdDriverError("lock conflict on no wait transaction", sqlcode=-803)
    translated = translate(backend, error)
    assert isinstance(translated, IntegrityError)
    assert translated.driver_code == -803


def test_plain_code_attribute_is_recognized(backend):
    class FakeDriverError(Exception):
        def __init__(self, message, code):
            super().__init__(message)
            self.sqlstate = None
            self.code = code

    error = FakeDriverError("duplicate key value", code=-803)
    translated = translate(backend, error)
    assert isinstance(translated, IntegrityError)
    assert translated.driver_code == -803


def test_unrecognized_error_falls_back_to_database_error(backend):
    error = FirebirdDriverError("some unexpected storage engine failure")
    translated = translate(backend, error)
    assert isinstance(translated, DatabaseError)
    assert not isinstance(
        translated,
        (IntegrityError, QueryError, LockError, ConnectionError, OperationalError),
    )
    assert translated.transient is False


class FakeDriverError(Exception):
    """Minimal driver error exposing only the attributes the mapper inspects."""

    def __init__(self, message, *, sqlstate=None, sqlcode=None, code=None, gds_codes=None):
        super().__init__(message)
        self.sqlstate = sqlstate
        if sqlcode is not None:
            self.sqlcode = sqlcode
        if code is not None:
            self.code = code
        if gds_codes is not None:
            self.gds_codes = gds_codes


def test_empty_sqlstate_list_falls_back_to_code(backend):
    """An empty SQLSTATE list carries no information; codes still classify."""
    error = FakeDriverError("unique key violation", sqlstate=[], sqlcode=-803)
    translated = translate(backend, error)
    assert isinstance(translated, IntegrityError)
    assert translated.sqlstate is None
    assert translated.driver_code == -803


def test_sqlstate_list_uses_first_entry(backend):
    """Legacy driver builds report SQLSTATE as a sequence."""
    error = FakeDriverError("duplicate key value", sqlstate=["23505"], sqlcode=-803)
    translated = translate(backend, error)
    assert isinstance(translated, IntegrityError)
    assert translated.sqlstate == "23505"


def test_scalar_gds_code_is_classified(backend):
    """A single GDS code is accepted alongside the usual sequence form."""
    error = FakeDriverError("constraint failure", gds_codes=530)
    translated = translate(backend, error)
    assert isinstance(translated, IntegrityError)
    assert translated.driver_code == 530


def test_non_numeric_code_is_ignored(backend):
    """Codes that are not integers are skipped instead of misfiring."""
    error = FakeDriverError("foreign key constraint violation", code="not-a-number")
    translated = translate(backend, error)
    assert isinstance(translated, IntegrityError)
    assert translated.driver_code is None


def test_connection_message_fallback_is_transient(backend):
    error = FakeDriverError("network error while talking to the server")
    translated = translate(backend, error)
    assert isinstance(translated, ConnectionError)
    assert translated.transient is True
    assert translated.retryable is True


def test_deadlock_message_fallback_maps_to_deadlock(backend):
    error = FakeDriverError("deadlock detected, transaction aborted")
    translated = translate(backend, error)
    assert isinstance(translated, DeadlockError)
    assert translated.transient is True


def test_integrity_message_fallback_maps_to_integrity(backend):
    error = FakeDriverError("foreign key constraint violation on insert")
    translated = translate(backend, error)
    assert isinstance(translated, IntegrityError)
    assert translated.transient is False


def test_framework_error_is_re_raised_unchanged(backend):
    """An already translated framework error keeps its type and identity."""
    error = DatabaseError("already translated")
    with pytest.raises(DatabaseError) as info:
        backend._handle_error(error)
    assert info.value is error

