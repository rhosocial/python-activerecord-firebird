# src/rhosocial/activerecord/backend/impl/firebird/mixins/backend_mixin.py
"""Firebird shared non-I/O backend mixin."""

import threading
from typing import Dict, List, Tuple

from rhosocial.activerecord.backend import errors as exc
from rhosocial.activerecord.backend.suggestion.definitions import (
    DataAdapterSuggestion,
    ExtraDataAdapterSuggestion,
)

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
            py_types = py_type if isinstance(py_type, tuple) else (py_type,)
            db_types = db_type if isinstance(db_type, tuple) else (db_type,)
            for pt in py_types:
                for dt in db_types:
                    registry.register(adapter, pt, dt, allow_override=True)

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

    # SQLDataType.BLOB and its text sub-type, as reported by the driver's
    # prepared-statement input metadata. Firebird's unbounded character type
    # (``BLOB SUB_TYPE TEXT``) is what :class:`TextType` renders to.
    _FB_BLOB_DATATYPE = 520
    _FB_BLOB_TEXT_SUBTYPE = 1

    def _coerce_blob_text_params(self, cursor, sql: str, params):
        """Stringify values bound to ``BLOB SUB_TYPE TEXT`` parameters.

        The firebird driver auto-converts non-string values to text only for
        ``TEXT``/``VARYING`` parameters. A ``BLOB`` parameter takes its own
        binding path whose packer calls ``len(value)`` directly, so binding an
        ``int``, ``bool``, ``Decimal``, etc. to a text BLOB raises ``TypeError``
        (surfaced as a ``DatabaseError``).

        Fields declared with a text storage type can still carry a non-string
        Python value -- a ``Union[str, int]`` field's ``0`` default is the
        concrete case. Every other backend's driver coerces that to text at the
        binding boundary; Firebird needs the same courtesy here. The parameter
        types come from the driver's own prepared-statement metadata, so this
        is exact: no SQL sniffing and no guessing which placeholders are text.
        """
        if not params:
            return params
        try:
            statement = cursor.prepare(sql)
        except Exception:
            # Preparing for metadata is best-effort; execute() prepares the
            # statement itself and will surface any real SQL problem.
            return params
        try:
            meta = getattr(statement, "_in_meta", None)
            count = getattr(statement, "_in_cnt", 0)
            if meta is None or not count:
                return params
            coerced = None
            for index in range(min(count, len(params))):
                value = params[index]
                if value is None or isinstance(value, (str, bytes, bytearray)):
                    continue
                try:
                    is_text_blob = (
                        meta.get_type(index) == self._FB_BLOB_DATATYPE
                        and meta.get_subtype(index) == self._FB_BLOB_TEXT_SUBTYPE
                    )
                except Exception:
                    continue
                if is_text_blob:
                    if coerced is None:
                        coerced = list(params)
                    coerced[index] = str(value)
            return tuple(coerced) if coerced is not None else params
        finally:
            try:
                statement.free()
            except Exception:
                pass

    def suggest_data_adapters(self) -> DataAdapterSuggestion:
        """Provide type adapter suggestions for Firebird.

        The portable baseline supplies the framework's common pairs; Firebird's
        own pairs are merged on top (its driver accepts the temporal and decimal
        values natively, so those targets stay identity-shaped), including the
        neutral families it carries as VARCHAR / BLOB text.
        """
        if self._default_suggestions_cache is not None:
            return DataAdapterSuggestion(table=self._default_suggestions_cache)

        import datetime as dt
        from decimal import Decimal

        from rhosocial.activerecord.backend.adapters import (
            BitString,
            Geometry,
            MacAddress,
            Multirange,
            Range,
            Vector,
        )
        from rhosocial.activerecord.backend.adapters.portable import PORTABLE_TYPE_MAPPINGS
        from rhosocial.activerecord.backend.base.type_adaption import (
            merge_adapter_suggestions,
        )

        type_mappings = [
            (int, int), (float, float), (str, str), (bytes, bytes),
            (bool, bool), (dt.datetime, dt.datetime), (dt.date, dt.date),
            (dt.time, dt.time), (Decimal, Decimal), (dict, str), (list, str),
            # Neutral families: Firebird carries them as VARCHAR / BLOB text.
            (Geometry, str), (Vector, str), (BitString, str),
            (Range, str), (Multirange, str), (MacAddress, str),
        ]

        suggestions = merge_adapter_suggestions(
            {}, list(PORTABLE_TYPE_MAPPINGS) + type_mappings, self.adapter_registry
        )

        self._default_suggestions_cache = suggestions
        return DataAdapterSuggestion(table=suggestions)

    def suggest_extra_data_adapters(self) -> ExtraDataAdapterSuggestion:
        """No backend-owned extra adapter types."""
        return ExtraDataAdapterSuggestion(table={})

    def get_type_adapters(self) -> List["SQLTypeAdapter"]:
        """Return the adapter instances this backend provides.

        This is a plain inventory: it says which adapters exist for this backend.
        It carries no suggestion/default/priority semantics; the caller decides.
        """
        registered = self.adapter_registry.get_all_adapters().values()
        unique: Dict[Tuple[str, str], "SQLTypeAdapter"] = {}
        for adapter in registered:
            adapter_class = type(adapter)
            key = (adapter_class.__module__, adapter_class.__qualname__)
            unique.setdefault(key, adapter)
        return [unique[key] for key in sorted(unique)]

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