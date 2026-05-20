from typing import Optional

from rhosocial.activerecord.backend.transaction import (
    TransactionManager, IsolationLevel, TransactionMode
)
from .mixins import FirebirdTransactionMixin


class FirebirdTransactionManager(FirebirdTransactionMixin, TransactionManager):
    """Firebird-specific transaction manager.

    Uses firebird-driver's native transaction API (connection.begin/commit/rollback).
    """

    def _do_begin(self, isolation_level: Optional[IsolationLevel] = None,
                  mode: Optional[TransactionMode] = None,
                  wait: bool = True,
                  lock_timeout: Optional[int] = None) -> None:
        conn = self._backend._connection
        conn.begin()

    def _do_commit(self) -> None:
        self._backend._connection.commit()

    def _do_rollback(self) -> None:
        self._backend._connection.rollback()

    def _do_create_savepoint(self, name: str) -> None:
        self._backend._connection.savepoint(name)

    def _do_release_savepoint(self, name: str) -> None:
        pass

    def _do_rollback_savepoint(self, name: str) -> None:
        self._backend._connection.rollback(savepoint=name)

    def supports_savepoint(self) -> bool:
        return True

    def __enter__(self):
        self.begin()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback()
        else:
            try:
                self.commit()
            except Exception:
                self.rollback()
                raise
