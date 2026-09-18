# src/rhosocial/activerecord/backend/impl/firebird/mixins/truncate.py
"""Firebird TRUNCATE mixin."""


class FirebirdTruncateMixin:

    def supports_truncate(self) -> bool:
        return False

    def supports_truncate_table_keyword(self) -> bool:
        return False

    def supports_truncate_restart_identity(self) -> bool:
        return False

    def supports_truncate_cascade(self) -> bool:
        return False
