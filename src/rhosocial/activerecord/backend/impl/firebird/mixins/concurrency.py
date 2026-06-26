# src/rhosocial/activerecord/backend/impl/firebird/mixins/concurrency.py
"""Firebird concurrency mixin."""

import logging
from typing import Optional

from rhosocial.activerecord.backend.protocols import ConcurrencyHint


class FirebirdConcurrencyMixin:
    _concurrency_hint: Optional[ConcurrencyHint] = None

    @property
    def threadsafety(self) -> int:
        return 2

    def connect(self):
        super().connect()
        self._fetch_concurrency_hint()

    def _fetch_concurrency_hint(self) -> None:
        try:
            cursor = self._connection.cursor()
            cursor.execute(
                "SELECT MON$MAX_CONNECTIONS FROM MON$DATABASE"
            )
            row = cursor.fetchone()
            cursor.close()

            if row and row[0] is not None:
                max_connections = int(row[0])
                pool_size = getattr(self.config, "pool_size", 5) or 5
                limit = min(max_connections, pool_size)
                self._concurrency_hint = ConcurrencyHint(
                    max_concurrency=limit,
                    reason=f"min(mon_max_connections={max_connections}, pool_size={pool_size})",
                )
        except Exception as e:
            pool_size = getattr(self.config, "pool_size", None)
            if pool_size:
                self._concurrency_hint = ConcurrencyHint(
                    max_concurrency=pool_size,
                    reason=f"pool_size={pool_size}",
                )
            else:
                self._concurrency_hint = None

    def get_concurrency_hint(self) -> Optional[ConcurrencyHint]:
        return self._concurrency_hint