# src/rhosocial/activerecord/backend/impl/firebird/transaction.py
"""Firebird transaction manager.

Firebird transaction model:
- SET TRANSACTION must be first statement in transaction
- Isolation levels: READ COMMITTED, SNAPSHOT, SNAPSHOT TABLE STABILITY
- WAIT/NO WAIT and LOCK TIMEOUT configuration
- READ ONLY / READ WRITE modes
"""

from typing import Optional

from rhosocial.activerecord.backend.transaction import (
    TransactionManager, IsolationLevel, TransactionMode
)
from .mixins import FirebirdTransactionMixin


class FirebirdTransactionManager(FirebirdTransactionMixin, TransactionManager):
    """Firebird-specific transaction manager.

    Firebird uses SET TRANSACTION instead of START TRANSACTION.
    The SET TRANSACTION must be the first SQL statement in the transaction.
    """

    def _do_begin(self, isolation_level: Optional[IsolationLevel] = None,
                  mode: Optional[TransactionMode] = None,
                  wait: bool = True,
                  lock_timeout: Optional[int] = None) -> None:
        """Begin a new transaction using Firebird SET TRANSACTION syntax.

        Maps standard isolation levels to Firebird equivalents:
        - READ UNCOMMITTED -> READ COMMITTED (Firebird's lowest level)
        - READ COMMITTED -> READ COMMITTED
        - REPEATABLE READ -> SNAPSHOT
        - SERIALIZABLE -> SNAPSHOT TABLE STABILITY

        Args:
            isolation_level: Standard isolation level to map
            mode: READ ONLY or READ WRITE
            wait: True for WAIT, False for NO WAIT
            lock_timeout: Lock timeout in seconds
        """
        fb_mode = None
        fb_isolation = None

        if mode is not None:
            if mode == TransactionMode.READ_ONLY:
                fb_mode = 'READ ONLY'
            elif mode == TransactionMode.READ_WRITE:
                fb_mode = 'READ WRITE'

        if isolation_level is not None:
            level_map = {
                IsolationLevel.READ_UNCOMMITTED: 'READ COMMITTED',
                IsolationLevel.READ_COMMITTED: 'READ COMMITTED',
                IsolationLevel.REPEATABLE_READ: 'SNAPSHOT',
                IsolationLevel.SERIALIZABLE: 'SNAPSHOT TABLE STABILITY',
            }
            fb_isolation = level_map.get(isolation_level, 'READ COMMITTED')

        sql = self._format_begin_sql(
            isolation_level=fb_isolation,
            mode=fb_mode,
            wait=wait,
            lock_timeout=lock_timeout,
        )

        self._connection.execute_direct(sql)

    def _do_commit(self) -> None:
        """Commit the current transaction."""
        self._connection.commit()

    def _do_rollback(self) -> None:
        """Rollback the current transaction."""
        self._connection.rollback()

    def _do_create_savepoint(self, name: str) -> None:
        """Create a savepoint within the current transaction.

        Args:
            name: Savepoint name
        """
        self._connection.execute_direct(f"SAVEPOINT {name}")

    def _do_release_savepoint(self, name: str) -> None:
        """Release a savepoint.

        Args:
            name: Savepoint name
        """
        self._connection.execute_direct(f"RELEASE SAVEPOINT {name}")

    def _do_rollback_savepoint(self, name: str) -> None:
        """Roll back to a savepoint.

        Args:
            name: Savepoint name
        """
        self._connection.execute_direct(f"ROLLBACK TO SAVEPOINT {name}")

    def supports_savepoint(self) -> bool:
        """Firebird supports savepoints."""
        return True