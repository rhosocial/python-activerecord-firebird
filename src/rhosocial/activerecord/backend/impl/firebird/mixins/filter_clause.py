# src/rhosocial/activerecord/backend/impl/firebird/mixins/filter_clause.py
"""Firebird filter clause mixin."""


class FirebirdFilterClauseMixin:

    def supports_filter_clause(self) -> bool:
        return self.version_at_least((3, 0, 0))
