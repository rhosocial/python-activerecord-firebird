# src/rhosocial/activerecord/backend/impl/firebird/mixins/transaction.py
"""Firebird transaction management mixin."""

from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.transaction import (
        BeginTransactionExpression,
        SetTransactionExpression,
    )


class FirebirdTransactionMixin:

    def supports_transaction_wait(self) -> bool:
        """Firebird's ``SET TRANSACTION`` grammar accepts ``WAIT`` and ``NO WAIT``.

        Measured on 5.0.4 and 6.0.0: ``SET TRANSACTION WAIT``, ``SET
        TRANSACTION NO WAIT``, and both spellings after an ``ISOLATION LEVEL``
        clause prepare successfully, while ``DEFERRABLE`` in the same position
        is answered with ``Token unknown - DEFERRABLE`` -- so the measurement
        distinguishes acceptance from a parse failure. The parameters ``wait``
        and ``no_wait`` select the spelling; neither set renders nothing.
        """
        return True

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

        # DEFERRABLE / NOT DEFERRABLE is a two-spelling option with one
        # parameter per spelling. Firebird's SET TRANSACTION grammar has
        # neither (measured on 5.0.4 and 6.0.0: ``Token unknown -
        # DEFERRABLE`` / ``- NOT``), so a requested spelling is refused by
        # name rather than dropped.
        if expr._deferrable or expr._not_deferrable:
            if not self.supports_deferrable_transaction():
                raise UnsupportedFeatureError(
                    self.name, "DEFERRABLE transaction",
                    f"{self.name} does not support [NOT] DEFERRABLE transactions.",
                )

        # WAIT / NO WAIT is the same shape. Firebird's grammar accepts both
        # spellings (measured), so each parameter renders its own word; a
        # dialect that declines the pair refuses by name instead of dropping.
        if expr._wait or expr._no_wait:
            if not self.supports_transaction_wait():
                feature = "WAIT" if expr._wait else "NO WAIT"
                raise UnsupportedFeatureError(
                    self.name, f"transaction {feature}",
                    f"{self.name} does not support the {feature} transaction clause.",
                )
            parts.append("WAIT" if expr._wait else "NO WAIT")

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

        # Same pair as BEGIN: Firebird's grammar has neither spelling.
        if expr._deferrable or expr._not_deferrable:
            if not self.supports_deferrable_transaction():
                raise UnsupportedFeatureError(
                    self.name, "DEFERRABLE transaction",
                    f"{self.name} does not support [NOT] DEFERRABLE transactions.",
                )

        # WAIT / NO WAIT, one parameter per spelling; see BEGIN above.
        if expr._wait or expr._no_wait:
            if not self.supports_transaction_wait():
                feature = "WAIT" if expr._wait else "NO WAIT"
                raise UnsupportedFeatureError(
                    self.name, f"transaction {feature}",
                    f"{self.name} does not support the {feature} transaction clause.",
                )
            parts.append("WAIT" if expr._wait else "NO WAIT")

        return " ".join(parts), ()