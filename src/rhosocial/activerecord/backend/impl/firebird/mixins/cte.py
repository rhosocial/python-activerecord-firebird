# src/rhosocial/activerecord/backend/impl/firebird/mixins/cte.py
"""Firebird CTE mixin."""

from .version_boundaries import _norm_version


class FirebirdCTEMixin:

    def supports_basic_cte(self) -> bool:
        return _norm_version(self.version) >= (3, 0, 0)

    def supports_recursive_cte(self) -> bool:
        return _norm_version(self.version) >= (3, 0, 0)
