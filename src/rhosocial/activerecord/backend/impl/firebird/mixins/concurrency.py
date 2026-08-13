# src/rhosocial/activerecord/backend/impl/firebird/mixins/concurrency.py
"""Firebird concurrency mixin."""

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
        max_connections = self._query_max_connections()
        pool_size = getattr(self.config, "pool_size", None) or None

        if max_connections and max_connections > 0:
            if pool_size:
                limit = min(max_connections, pool_size)
                reason = (
                    f"min(mon_max_connections={max_connections}, "
                    f"pool_size={pool_size})"
                )
            else:
                limit = max_connections
                reason = f"mon_max_connections={max_connections}"
            self._concurrency_hint = ConcurrencyHint(
                max_concurrency=limit,
                reason=reason,
            )
        elif pool_size:
            self._concurrency_hint = ConcurrencyHint(
                max_concurrency=pool_size,
                reason=f"pool_size={pool_size}",
            )
        else:
            self._concurrency_hint = None

    def _query_max_connections(self) -> Optional[int]:
        """Query the configured maximum number of connections.

        The ``MON$MAX_CONNECTIONS`` column exists on Firebird 3/4 but was
        removed from the ``MON$DATABASE`` virtual table in Firebird 5+.
        Return ``None`` when the limit cannot be discovered so that the
        caller falls back to the configured pool size (or no constraint).
        """
        try:
            cursor = self._connection.cursor()
            cursor.execute("SELECT MON$MAX_CONNECTIONS FROM MON$DATABASE")
            row = cursor.fetchone()
            cursor.close()
            if row and row[0] is not None:
                return int(row[0])
        except Exception:
            pass
        return None

    def get_concurrency_hint(self) -> Optional[ConcurrencyHint]:
        return self._concurrency_hint