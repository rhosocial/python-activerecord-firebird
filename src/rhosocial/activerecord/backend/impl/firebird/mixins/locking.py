# src/rhosocial/activerecord/backend/impl/firebird/mixins/locking.py
"""Firebird locking mixin.

Wired into the core ``LockingSupport`` protocol: the query path
(``DQLMixin.format_query_statement``) checks ``supports_for_update()`` and
then calls ``format_for_update_clause()``, so both names must match the
protocol exactly or SELECT ... FOR UPDATE silently degrades to the empty
Protocol stub.
"""

from typing import Tuple, TYPE_CHECKING

from .version_boundaries import _norm_version

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.query_parts import ForUpdateClause


class FirebirdLockingMixin:

    def supports_for_update(self) -> bool:
        """Row-level FOR UPDATE locking requires Firebird 3.0+."""
        return _norm_version(getattr(self, 'version', (3, 0, 0))) >= (3, 0, 0)

    def format_for_update_clause(self, clause: "ForUpdateClause") -> Tuple[str, tuple]:
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
        from rhosocial.activerecord.backend.expression import LockStrength

        if clause.strength != LockStrength.UPDATE:
            raise UnsupportedFeatureError(
                self.name, f"{clause.strength.value} (unsupported lock strength)"
            )

        parts = ["FOR UPDATE"]
        params: Tuple = ()

        of_columns = clause.of_columns
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
        if clause.nowait:
            parts.append("WITH LOCK")
        if clause.skip_locked and self.supports_skip_locked():
            # Single source of truth for the threshold lives on the dialect
            # (see FirebirdDialect.supports_skip_locked); this mixin only
            # delegates so the gate cannot drift between the two sites.
            parts.append("SKIP LOCKED")

        return ' '.join(parts), params

    def supports_for_update_with_lock(self) -> bool:
        return self.supports_for_update()

    def supports_for_update_skip_locked(self) -> bool:
        return self.supports_skip_locked()

    def supports_lateral_join(self) -> bool:
        """Firebird 4.0 introduced joins with LATERAL derived tables."""
        return _norm_version(getattr(self, 'version', (4, 0, 0))) >= (4, 0, 0)
