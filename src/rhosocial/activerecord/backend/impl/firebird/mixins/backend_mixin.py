# src/rhosocial/activerecord/backend/impl/firebird/mixins/backend_mixin.py
"""Firebird shared non-I/O backend mixin."""

from typing import Any, Dict, Optional, Tuple, Type

from rhosocial.activerecord.backend import errors as exc
from rhosocial.activerecord.backend.type_adapter import SQLTypeAdapter

from ..adapters import firebird_adapters


class FirebirdBackendMixin:

    CONNECTION_ERROR_CODES = {
        -902: "Unable to connect to database",
        -904: "Connection lost",
        -909: "Database shutdown",
        -916: "Database is not started",
        -917: "Database already in use",
        -923: "Connection not established",
    }

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

    def _is_connection_error(self, error: Exception) -> bool:
        error_code = getattr(error, 'sqlcode', None)
        if error_code is not None and error_code in self.CONNECTION_ERROR_CODES:
            return True

        error_msg = str(error).lower()
        connection_keywords = [
            'unable to connect', 'connection lost', 'connection not established',
            'database shutdown', 'broken pipe', 'connection reset',
            'network error', 'connection refused', 'database already in use',
        ]
        return any(kw in error_msg for kw in connection_keywords)

    def _handle_error(self, error: Exception) -> None:
        error_msg = str(error)
        error_code = getattr(error, 'sqlcode', None)
        gds_code = getattr(error, 'gds_codes', None)

        if self._is_connection_error(error):
            raise exc.ConnectionError(error_msg) from error

        if gds_code:
            for code in gds_code if isinstance(gds_code, (list, tuple)) else [gds_code]:
                if abs(code) in (803, 804, 805):
                    raise exc.IntegrityError(error_msg) from error
                if abs(code) in (901,):
                    raise exc.LockError(error_msg) from error
                if abs(code) in (902,):
                    raise exc.DeadlockError(error_msg) from error

        if error_code:
            if error_code in (-803, -804, -805):
                raise exc.IntegrityError(error_msg) from error
            if error_code == -901:
                raise exc.DeadlockError(error_msg) from error
            if error_code in (-902, -904, -909, -916, -917, -923):
                raise exc.ConnectionError(error_msg) from error
            if error_code in (-530, -531):
                raise exc.IntegrityError(error_msg) from error
            if error_code in (-104, -206, -207):
                raise exc.QueryError(error_msg) from error
            if error_code in (-204,):
                raise exc.DatabaseError(error_msg) from error

        raise exc.DatabaseError(error_msg) from error

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
        if version is not None and version < (3, 0, 0):
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