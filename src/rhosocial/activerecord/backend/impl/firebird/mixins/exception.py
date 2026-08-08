# src/rhosocial/activerecord/backend/impl/firebird/mixins/exception.py
"""Firebird EXCEPTION statement formatting mixin.

EXCEPTION is a user-defined error message available since Firebird 1.0;
the formatting here is gated at ``(2, 5, 0)`` to match the oldest
supported server version.
"""

from typing import Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


class FirebirdExceptionMixin:

    def format_create_exception_statement(self, expr) -> Tuple[str, tuple]:
        """Format CREATE EXCEPTION name 'message'."""
        self._check_exception_version("CREATE EXCEPTION")
        return (
            f"CREATE EXCEPTION {self.format_identifier(expr.exception_name)} "
            f"'{expr.message.replace(chr(39), chr(39) * 2)}'",
            (),
        )

    def format_alter_exception_statement(self, expr) -> Tuple[str, tuple]:
        """Format ALTER EXCEPTION name 'message'."""
        self._check_exception_version("ALTER EXCEPTION")
        return (
            f"ALTER EXCEPTION {self.format_identifier(expr.exception_name)} "
            f"'{expr.message.replace(chr(39), chr(39) * 2)}'",
            (),
        )

    def format_drop_exception_statement(self, expr) -> Tuple[str, tuple]:
        """Format DROP EXCEPTION name."""
        self._check_exception_version("DROP EXCEPTION")
        return f"DROP EXCEPTION {self.format_identifier(expr.exception_name)}", ()

    def _check_exception_version(self, feature: str) -> None:
        version = getattr(self, 'version', (2, 5, 0))
        if version < (2, 5, 0):
            raise UnsupportedFeatureError(
                self.name,
                feature,
                "Firebird 2.5 or later is required for EXCEPTION statements.",
            )
