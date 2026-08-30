# src/rhosocial/activerecord/backend/impl/firebird/mixins/locking.py
"""Firebird locking mixin.

Wired into the core ``LockingSupport`` protocol: the query path
(``DQLMixin.format_query_statement``) checks ``supports_for_update()`` and
then calls ``format_for_update_clause()``, so both names must match the
protocol exactly or SELECT ... FOR UPDATE silently degrades to the empty
Protocol stub.
"""

from typing import Tuple

from .version_boundaries import _norm_version


class FirebirdLockingMixin:

    def supports_for_update(self) -> bool:
        """Row-level FOR UPDATE locking requires Firebird 3.0+."""
        return _norm_version(getattr(self, 'version', (3, 0, 0))) >= (3, 0, 0)

    def format_for_update_clause(self, clause) -> Tuple[str, tuple]:
        parts = ["FOR UPDATE"]
        params: Tuple = ()

        of_columns = getattr(clause, 'of_columns', None)
        if of_columns:
            of_parts = []
            all_params = []
            for col in of_columns:
                if isinstance(col, str):
                    of_parts.append(self.format_identifier(col))
                else:
                    col_sql, col_params = col.to_sql()
                    of_parts.append(col_sql)
                    all_params.extend(col_params)
            parts.append(f"OF {', '.join(of_parts)}")
            params = tuple(all_params)

        # Firebird spells row locking "WITH LOCK"; NOWAIT maps onto the same
        # immediate-lock form.
        if getattr(clause, 'with_lock', False) or getattr(clause, 'nowait', False):
            parts.append("WITH LOCK")
        if getattr(clause, 'skip_locked', False) and self.supports_skip_locked():
            # Single source of truth for the threshold lives on the dialect
            # (see FirebirdDialect.supports_skip_locked); this mixin only
            # delegates so the gate cannot drift between the two sites.
            parts.append("SKIP LOCKED")

        return ' '.join(parts), params

    def supports_for_update_with_lock(self) -> bool:
        return self.supports_for_update()
