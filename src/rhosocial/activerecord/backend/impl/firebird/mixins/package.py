# src/rhosocial/activerecord/backend/impl/firebird/mixins/package.py
"""Firebird PACKAGE statement formatting mixin.

Packages were introduced in Firebird 3.0; both the header
(``CREATE PACKAGE``) and the implementation body (``CREATE PACKAGE BODY``)
are gated at ``(3, 0, 0)``.
"""

from typing import Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


class FirebirdPackageMixin:

    def format_create_package_statement(self, expr) -> Tuple[str, tuple]:
        """Format CREATE PACKAGE name AS <declarations>."""
        self._check_package_version("CREATE PACKAGE")
        parts = ["CREATE PACKAGE", self.format_identifier(expr.package_name)]
        if getattr(expr, "body", None):
            parts.append(f"AS {expr.body}")
        return " ".join(parts), ()

    def format_create_package_body_statement(self, expr) -> Tuple[str, tuple]:
        """Format CREATE PACKAGE BODY name AS <implementations>."""
        self._check_package_version("CREATE PACKAGE BODY")
        parts = ["CREATE PACKAGE BODY", self.format_identifier(expr.package_name)]
        if getattr(expr, "body", None):
            parts.append(f"AS {expr.body}")
        return " ".join(parts), ()

    def format_drop_package_statement(self, expr) -> Tuple[str, tuple]:
        """Format DROP PACKAGE [BODY] name."""
        self._check_package_version("DROP PACKAGE")
        if getattr(expr, "body", False):
            return (
                f"DROP PACKAGE BODY {self.format_identifier(expr.package_name)}",
                (),
            )
        return f"DROP PACKAGE {self.format_identifier(expr.package_name)}", ()

    def _check_package_version(self, feature: str) -> None:
        version = getattr(self, 'version', (3, 0, 0))
        if version < (3, 0, 0):
            raise UnsupportedFeatureError(
                self.name,
                feature,
                "Firebird 3.0 or later is required for PACKAGE statements.",
            )
