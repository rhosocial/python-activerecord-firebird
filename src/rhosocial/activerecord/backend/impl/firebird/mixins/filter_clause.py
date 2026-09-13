# src/rhosocial/activerecord/backend/impl/firebird/mixins/filter_clause.py
"""Firebird filter clause mixin."""

from .version_boundaries import _norm_version


class FirebirdFilterClauseMixin:

    def supports_filter_clause(self) -> bool:
        return _norm_version(self.version) >= (3, 0, 0)
