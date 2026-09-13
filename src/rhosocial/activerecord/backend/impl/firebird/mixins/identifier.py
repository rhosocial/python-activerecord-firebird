# src/rhosocial/activerecord/backend/impl/firebird/mixins/identifier.py
"""Firebird identifier formatting mixin."""


class FirebirdIdentifierMixin:

    def format_identifier(self, identifier: str, need_quote: bool = True) -> str:
        """Format identifier using Firebird's double-quote quoting.

        Firebird by default folds identifiers to uppercase unless quoted.
        This uppercases the identifier so that quoted and unquoted references
        are consistent with Firebird's default behavior.
        """
        if not need_quote:
            if self.is_reserved_word(identifier):
                import warnings
                from rhosocial.activerecord.backend.warnings import IdentifierQuotingWarning
                warnings.warn(
                    f"Identifier '{identifier}' is a reserved word in {self.name} "
                    f"and may cause SQL errors without quoting.",
                    IdentifierQuotingWarning,
                    stacklevel=2,
                )
            return identifier
        escaped = identifier.upper().replace('"', '""')
        return f'"{escaped}"'
