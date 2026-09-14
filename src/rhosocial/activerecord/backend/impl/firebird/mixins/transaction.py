# src/rhosocial/activerecord/backend/impl/firebird/mixins/transaction.py
"""Firebird transaction management mixin."""

from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.transaction import (
        BeginTransactionExpression,
        SetTransactionExpression,
    )


class FirebirdTransactionMixin:

    def _format_begin_sql(self, isolation_level=None, mode=None, wait=True, lock_timeout=None):
        parts = ["SET TRANSACTION"]

        if isolation_level:
            level_map = {
                'READ UNCOMMITTED': 'READ COMMITTED',
                'READ COMMITTED': 'READ COMMITTED',
                'REPEATABLE READ': 'SNAPSHOT',
                'SERIALIZABLE': 'SNAPSHOT TABLE STABILITY',
            }
            fb_level = level_map.get(
                isolation_level.upper() if isinstance(isolation_level, str) else isolation_level,
                isolation_level,
            )
            parts.append(f"ISOLATION LEVEL {fb_level}")

        if mode:
            parts.append(mode.upper())

        if wait:
            parts.append("WAIT")
        else:
            parts.append("NO WAIT")

        if lock_timeout is not None:
            parts.append(f"LOCK TIMEOUT {lock_timeout}")

        return " ".join(parts)

    def supports_transaction_mode(self) -> bool:
        return True

    def supports_isolation_level_in_begin(self) -> bool:
        return True

    def supports_read_only_transaction(self) -> bool:
        return True

    def supports_deferrable_transaction(self) -> bool:
        return False

    def supports_savepoint(self) -> bool:
        return True

    def format_begin_transaction(self, expr: "BeginTransactionExpression") -> Tuple[str, tuple]:
        from rhosocial.activerecord.backend.transaction import IsolationLevel
        level_map = {
            IsolationLevel.READ_UNCOMMITTED: "READ COMMITTED",
            IsolationLevel.READ_COMMITTED: "READ COMMITTED",
            IsolationLevel.REPEATABLE_READ: "SNAPSHOT",
            IsolationLevel.SERIALIZABLE: "SNAPSHOT TABLE STABILITY",
        }

        parts = ["SET TRANSACTION"]
        if expr._isolation_level is not None:
            fb_level = level_map.get(expr._isolation_level, "READ COMMITTED")
            parts.append(f"ISOLATION LEVEL {fb_level}")

        from rhosocial.activerecord.backend.transaction import TransactionMode
        if expr._mode == TransactionMode.READ_ONLY:
            parts.append("READ ONLY")
        elif expr._mode == TransactionMode.READ_WRITE:
            parts.append("READ WRITE")
        else:
            parts.append("READ WRITE")

        parts.append("WAIT")
        return " ".join(parts), ()

    def format_set_transaction(self, expr: "SetTransactionExpression") -> Tuple[str, tuple]:
        from rhosocial.activerecord.backend.transaction import IsolationLevel, TransactionMode

        parts = ["SET TRANSACTION"]
        if expr._isolation_level is not None:
            level_map = {
                IsolationLevel.READ_UNCOMMITTED: "READ COMMITTED",
                IsolationLevel.READ_COMMITTED: "READ COMMITTED",
                IsolationLevel.REPEATABLE_READ: "SNAPSHOT",
                IsolationLevel.SERIALIZABLE: "SNAPSHOT TABLE STABILITY",
            }
            fb_level = level_map.get(expr._isolation_level, "READ COMMITTED")
            parts.append(f"ISOLATION LEVEL {fb_level}")
        if expr._mode == TransactionMode.READ_ONLY:
            parts.append("READ ONLY")
        elif expr._mode == TransactionMode.READ_WRITE:
            parts.append("READ WRITE")
        return " ".join(parts), ()