# src/rhosocial/activerecord/backend/impl/firebird/mixins/generated_column.py
"""Firebird generated column mixin."""


class FirebirdGeneratedColumnMixin:

    def supports_generated_always(self) -> bool:
        return True

    def supports_generated_columns(self) -> bool:
        """Firebird supports COMPUTED BY columns."""
        return True

    def supports_stored_generated_columns(self) -> bool:
        """Firebird COMPUTED BY columns are virtual (not stored)."""
        return False

    def supports_virtual_generated_columns(self) -> bool:
        """Firebird COMPUTED BY columns behave as virtual columns."""
        return True
