# src/rhosocial/activerecord/backend/impl/firebird/mixins/generated_column.py
"""Firebird generated column mixin."""

from .version_boundaries import _norm_version


class FirebirdGeneratedColumnMixin:

    def supports_generated_always(self) -> bool:
        return True

    def supports_identity_columns(self) -> bool:
        return _norm_version(self.version) >= (3, 0, 0)

    def supports_auto_increment(self) -> bool:
        return _norm_version(self.version) >= (3, 0, 0)
