# src/rhosocial/activerecord/backend/impl/firebird/mixins/truncate.py
"""Firebird TRUNCATE mixin."""


class FirebirdTruncateMixin:

    def supports_truncate(self) -> bool:
        """Firebird has no ``TRUNCATE`` statement.

        Measured on 5.0.4 and 6.0.0: ``TRUNCATE TABLE t`` is answered with
        ``Token unknown - TRUNCATE`` on both, including the ``RESTART
        IDENTITY`` / ``CASCADE`` / ``RESTRICT`` variants. The core TRUNCATE
        formatter refuses the statement by name rather than emitting a token
        the parser rejects; ``DELETE FROM`` is the replacement.
        """
        return False

    def supports_truncate_table_keyword(self) -> bool:
        return False

    def supports_truncate_restart_identity(self) -> bool:
        return False

    def supports_truncate_cascade(self) -> bool:
        return False
