# src/rhosocial/activerecord/backend/impl/firebird/mixins/cte.py
"""Firebird CTE mixin."""

from .version_boundaries import _norm_version


class FirebirdCTEMixin:

    def supports_basic_cte(self) -> bool:
        return _norm_version(self.version) >= (3, 0, 0)

    def supports_recursive_cte(self) -> bool:
        return _norm_version(self.version) >= (3, 0, 0)

    def supports_materialized_cte(self) -> bool:
        """Firebird has no ``MATERIALIZED`` / ``NOT MATERIALIZED`` CTE hint.

        Measured on 5.0.4 and 6.0.0: ``WITH c AS MATERIALIZED (SELECT ...)``
        and ``WITH c AS NOT MATERIALIZED (SELECT ...)`` are both answered with
        ``Token unknown - MATERIALIZED`` / ``Token unknown - NOT``, while the
        same CTE without the hint runs. The core CTE formatter refuses a
        requested hint by name rather than emitting a hint the parser rejects.
        """
        return False
