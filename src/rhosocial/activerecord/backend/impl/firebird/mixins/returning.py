# src/rhosocial/activerecord/backend/impl/firebird/mixins/returning.py
"""Firebird RETURNING clause mixin."""


class FirebirdReturningMixin:

    def supports_returning_insert(self) -> bool:
        return True

    def supports_returning_update(self) -> bool:
        return True

    def supports_returning_delete(self) -> bool:
        return True

    def supports_returning_alias(self) -> bool:
        """Firebird RETURNING does not support a clause-level alias."""
        return False

    def supports_returning_single_row(self) -> bool:
        """Firebird RETURNING is inherently single-row."""
        return True
