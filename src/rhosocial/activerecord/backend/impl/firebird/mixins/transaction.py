# src/rhosocial/activerecord/backend/impl/firebird/mixins/transaction.py
"""Firebird transaction management mixin."""


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