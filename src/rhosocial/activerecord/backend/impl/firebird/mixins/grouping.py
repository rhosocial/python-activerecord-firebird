# src/rhosocial/activerecord/backend/impl/firebird/mixins/grouping.py
"""Firebird grouping mixin."""


class FirebirdGroupingMixin:

    def supports_rollup(self) -> bool:
        return True
