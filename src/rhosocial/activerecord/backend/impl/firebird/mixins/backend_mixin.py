# src/rhosocial/activerecord/backend/impl/firebird/mixins/backend_mixin.py
"""Firebird shared non-I/O backend mixin."""

import threading
from typing import Dict, Tuple, Type

from rhosocial.activerecord.backend import errors as exc

from .version_boundaries import _norm_version
from rhosocial.activerecord.backend.type_adapter import SQLTypeAdapter

from ..adapters import firebird_adapters

_live_connections_lock = threading.Lock()
_live_connections = set()


def track_firebird_connection(connection) -> None:
    """Keep a strong reference to a firebird-driver connection.

    firebird-driver connections are not safe to close from the garbage
    collector: libfbclient is not thread-safe, and when ``__del__`` runs
    during an unrelated GC pass (e.g. while a query is being executed and
    logged) it can corrupt the library and crash the process with a
    segmentation fault. Holding every live connection here means the
    garbage collector never collects one that has not been closed
    explicitly, so ``__del__`` never runs at an unlucky moment. Backends
    must call :func:`untrack_firebird_connection` before closing.
    """
    with _live_connections_lock:
        _live_connections.add(connection)


def untrack_firebird_connection(connection) -> None:
    with _live_connections_lock:
        _live_connections.discard(connection)


def track_firebird_backend(backend) -> None:
    """Keep a strong reference to a backend while its connection is live.

    A backend owns its firebird-driver ``Connection`` and ``Cursor``. As long
    as the backend is referenced here, the garbage collector cannot reclaim
    those driver objects, so their ``__del__`` (which calls into the
    non-thread-safe libfbclient) never runs at a GC-driven moment. Backends
    must call :func:`untrack_firebird_backend` after ``disconnect()`` has
    explicitly closed the underlying objects.
    """
    with _live_connections_lock:
        _live_connections.add(backend)


def untrack_firebird_backend(backend) -> None:
    with _live_connections_lock:
        _live_connections.discard(backend)


class FirebirdBackendMixin:

    # firebird-driver 2.x exposes the legacy signed SQLCODE on ``DatabaseError``
    # (``sqlcode``) plus raw GDS status codes (``gds_codes``). Codes are
    # compared on ``abs()`` because both signed and unsigned forms occur.
    INTEGRITY_SQLCODES = frozenset({530, 531, 625, 803, 804, 805})
    LOCK_SQLCODES = frozenset({901, 902})
    DEADLOCK_SQLCODES = frozenset({913})
    QUERY_SQLCODES = frozenset({104, 204, 206, 207})

    # SQLSTATE is checked before driver codes: it is stable across Firebird
    # versions and driver builds.
    SQLSTATE_INTEGRITY = ("23000", "23505")
    SQLSTATE_NOT_NULL = ("22004", "22000")
    SQLSTATE_DEADLOCK = ("40001",)
    SQLSTATE_CONNECTION_LOST = ("08006",)
    SQLSTATE_CONNECTION_FAILED = ("08001",)
    SQLSTATE_AUTHENTICATION = ("28000",)
    SQLSTATE_QUERY = ("42000", "42S02", "42S22")

    CONNECTION_ERROR_CODES = {
        -904: "Connection lost",
        -909: "Database shutdown",
        -916: "Database is not started",
        -917: "Database already in use",
        -923: "Connection not established",
    }

    # Message fragments are the last resort, used only when neither SQLSTATE
    # nor a driver code identifies the failure.
    AUTHENTICATION_KEYWORDS = (
        "user name and password are not defined",
        "login failed",
        "invalid user name",
        "invalid username",
        "authentication failed",
    )
    CONNECTION_KEYWORDS = (
        "unable to connect",
        "connection lost",
        "connection not established",
        "database shutdown",
        "broken pipe",
        "connection reset",
        "network error",
        "connection refused",
        "database already in use",
        "server closed",
    )
    DEADLOCK_KEYWORDS = ("deadlock",)
    LOCK_KEYWORDS = (
        "lock conflict",
        "update conflict",
        "concurrent update",
        "lock timeout",
        "lock time-out",
    )
    INTEGRITY_KEYWORDS = (
        "unique key",
        "duplicate key",
        "duplicate value",
        "violation of primary key",
        "foreign key",
        "referential integrity",
        "not null",
        "null value",
        "validation error for column",
    )
    QUERY_KEYWORDS = (
        "syntax error",
        "token unknown",
        "unknown table",
        "table unknown",
        "unknown column",
        "column unknown",
        "no such table",
        "unsuccessful metadata update",
    )

    _dialect = None
    _default_suggestions_cache = None

    @property
    def dialect(self):
        if self._dialect is None:
            from ..dialect import FirebirdDialect
            self._dialect = FirebirdDialect()
            if hasattr(self, 'config') and self.config.version:
                self._dialect.version = self.config.version
        return self._dialect

    @dialect.setter
    def dialect(self, value):
        self._dialect = value

    @property
    def threadsafety(self) -> int:
        return 2

    def _register_firebird_adapters(self):
        registry = self.adapter_registry
        for adapter_class, py_type, db_type in firebird_adapters:
            adapter = adapter_class()
            if isinstance(py_type, tuple):
                for pt in py_type:
                    registry.register(adapter, pt, db_type, allow_override=True)
            else:
                registry.register(adapter, py_type, db_type, allow_override=True)

    @property
    def requires_manual_commit(self) -> bool:
        return True

    @staticmethod
    def _error_sqlstate(error: Exception):
        """Return a normalized SQLSTATE string, or ``None`` when absent."""
        sqlstate = getattr(error, 'sqlstate', None)
        if sqlstate is None:
            return None
        if isinstance(sqlstate, (list, tuple)):
            if not sqlstate:
                return None
            sqlstate = sqlstate[0]
        text = str(sqlstate).strip().upper()
        return text or None

    @staticmethod
    def _raw_driver_codes(error: Exception):
        """Return the raw Firebird codes carried by a driver error.

        ``firebird-driver`` sets ``sqlcode`` and ``gds_codes``; some driver
        wrappers and test doubles expose a plain ``code`` instead. Zero is
        treated as "not reported" by the driver.
        """
        values = []
        for attr in ('sqlcode', 'code'):
            value = getattr(error, attr, None)
            if value is not None:
                values.append(value)
        gds_codes = getattr(error, 'gds_codes', None)
        if gds_codes is not None:
            if isinstance(gds_codes, (list, tuple, set)):
                values.extend(gds_codes)
            else:
                values.append(gds_codes)

        codes = []
        for value in values:
            try:
                code = int(value)
            except (TypeError, ValueError):
                continue
            if code != 0:
                codes.append(code)
        return codes

    @classmethod
    def _driver_error_codes(cls, error: Exception):
        """Return deduplicated absolute Firebird codes for classification."""
        codes = []
        for raw in cls._raw_driver_codes(error):
            code = abs(raw)
            if code not in codes:
                codes.append(code)
        return codes

    @classmethod
    def _report_driver_code(cls, error: Exception, matched_code):
        """Pick the driver code to attach as diagnostics."""
        raw_codes = cls._raw_driver_codes(error)
        if matched_code is not None:
            for raw in raw_codes:
                if abs(raw) == matched_code:
                    return raw
        return raw_codes[0] if raw_codes else None

    def _classify_error(self, error: Exception):
        """Classify a driver error as ``(error_class, transient, code)``.

        Recognition order follows the backend mapping contract: SQLSTATE
        first, then the Firebird SQLCODE/GDS code, then message text.
        """
        sqlstate = self._error_sqlstate(error)
        codes = self._driver_error_codes(error)
        message = str(error).lower()

        if sqlstate:
            if sqlstate.startswith(self.SQLSTATE_INTEGRITY):
                # Unique/primary-key violation.
                return exc.IntegrityError, False, None
            if sqlstate.startswith(self.SQLSTATE_NOT_NULL):
                return exc.IntegrityError, False, None
            if sqlstate.startswith(self.SQLSTATE_DEADLOCK):
                # Serialization failure or update conflict: another writer won
                # the race, so a retry after re-reading may succeed.
                return exc.DeadlockError, True, None
            if sqlstate.startswith(self.SQLSTATE_CONNECTION_LOST):
                return exc.OperationalError, True, None
            if sqlstate.startswith(self.SQLSTATE_CONNECTION_FAILED):
                return exc.ConnectionError, True, None
            if sqlstate.startswith(self.SQLSTATE_AUTHENTICATION):
                # Bad credentials do not improve on retry.
                return exc.ConnectionError, False, None
            if sqlstate.startswith(self.SQLSTATE_QUERY):
                return exc.QueryError, False, None

        connection_codes = {abs(code) for code in self.CONNECTION_ERROR_CODES}
        for code in codes:
            if code in self.LOCK_SQLCODES:
                return exc.LockError, True, code
            if code in self.DEADLOCK_SQLCODES:
                return exc.DeadlockError, True, code
            if code in self.INTEGRITY_SQLCODES:
                return exc.IntegrityError, False, code
            if code in connection_codes:
                return exc.ConnectionError, True, code
            if code in self.QUERY_SQLCODES:
                return exc.QueryError, False, code

        if any(keyword in message for keyword in self.AUTHENTICATION_KEYWORDS):
            return exc.ConnectionError, False, None
        if any(keyword in message for keyword in self.CONNECTION_KEYWORDS):
            return exc.ConnectionError, True, None
        if any(keyword in message for keyword in self.DEADLOCK_KEYWORDS):
            return exc.DeadlockError, True, None
        if any(keyword in message for keyword in self.LOCK_KEYWORDS):
            return exc.LockError, True, None
        if any(keyword in message for keyword in self.INTEGRITY_KEYWORDS):
            return exc.IntegrityError, False, None
        if any(keyword in message for keyword in self.QUERY_KEYWORDS):
            return exc.QueryError, False, None
        return exc.DatabaseError, False, None

    def _handle_error(self, error: Exception) -> None:
        """Translate a firebird-driver error into the shared taxonomy."""
        if isinstance(error, exc.DatabaseError):
            # Already translated (e.g. the "no database specified" guard in
            # connect()); keep its type and original cause.
            raise error

        error_class, transient, matched_code = self._classify_error(error)
        raise exc.attach_diagnostics(
            error_class(str(error)),
            operation="execute",
            sqlstate=self._error_sqlstate(error),
            driver_code=self._report_driver_code(error, matched_code),
            backend="firebird",
            transient=transient,
        ) from error

    def get_default_adapter_suggestions(self) -> Dict[Type, Tuple[SQLTypeAdapter, Type]]:
        if self._default_suggestions_cache is not None:
            return self._default_suggestions_cache

        import datetime as dt
        from decimal import Decimal

        suggestions: Dict[Type, Tuple[SQLTypeAdapter, Type]] = {}
        type_mappings = [
            (int, int), (float, float), (str, str), (bytes, bytes),
            (bool, bool), (dt.datetime, dt.datetime), (dt.date, dt.date),
            (dt.time, dt.time), (Decimal, Decimal), (dict, str), (list, str),
        ]

        for py_type, db_type in type_mappings:
            adapter = self.adapter_registry.get_adapter(py_type, db_type)
            if adapter:
                suggestions[py_type] = (adapter, db_type)

        self._default_suggestions_cache = suggestions
        return suggestions

    def _check_returning_compatibility(self, returning_columns):
        version = getattr(self.dialect, 'version', None)
        if version is not None and _norm_version(version) < (3, 0, 0):
            raise exc.UnsupportedTransactionModeError(
                "RETURNING clause", "Firebird",
                "RETURNING clause requires Firebird 3.0 or later",
            )
        return True

    def _get_result_mapping(self, cursor):
        if cursor is None or cursor.description is None:
            return []
        mapping = []
        for desc in cursor.description:
            name = desc[0]
            col_type = desc[1] if len(desc) > 1 else None
            mapping.append((name, col_type, None, None, None, None, True))
        return mapping