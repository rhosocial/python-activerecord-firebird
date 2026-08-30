# src/rhosocial/activerecord/backend/impl/firebird/mixins/user.py
"""Firebird USER management statement formatting mixin.

SQL user management (``CREATE USER`` / ``ALTER USER`` / ``DROP USER``) was
introduced in Firebird 3.0; all three statements are gated at ``(3, 0, 0)``.
"""

from typing import Tuple

from .version_boundaries import _norm_version
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


class FirebirdUserMixin:

    def supports_create_user(self) -> bool:
        return _norm_version(self.version) >= (3, 0, 0)

    def supports_alter_user(self) -> bool:
        return _norm_version(self.version) >= (3, 0, 0)

    def supports_drop_user(self) -> bool:
        return _norm_version(self.version) >= (3, 0, 0)

    def format_create_user_statement(self, expr) -> Tuple[str, tuple]:
        """Format CREATE USER name PASSWORD '...' [FIRSTNAME ...] [MIDDLENAME ...]
        [LASTNAME ...] [GRANT ADMIN ROLE]."""
        self._check_user_version("CREATE USER")

        parts = [
            "CREATE USER",
            self.format_identifier(expr.username),
            "PASSWORD",
            self._quote_literal(expr.password),
        ]
        if expr.first_name is not None:
            parts += ["FIRSTNAME", self._quote_literal(expr.first_name)]
        if expr.middle_name is not None:
            parts += ["MIDDLENAME", self._quote_literal(expr.middle_name)]
        if expr.last_name is not None:
            parts += ["LASTNAME", self._quote_literal(expr.last_name)]
        if expr.grant_admin_role:
            parts.append("GRANT ADMIN ROLE")
        return " ".join(parts), ()

    def format_alter_user_statement(self, expr) -> Tuple[str, tuple]:
        """Format ALTER USER name [PASSWORD ...] [FIRSTNAME ...] [MIDDLENAME ...]
        [LASTNAME ...] [GRANT ADMIN ROLE] [REVOKE ADMIN ROLE]."""
        self._check_user_version("ALTER USER")

        parts = ["ALTER USER", self.format_identifier(expr.username)]
        if expr.password is not None:
            parts += ["PASSWORD", self._quote_literal(expr.password)]
        if expr.first_name is not None:
            parts += ["FIRSTNAME", self._quote_literal(expr.first_name)]
        if expr.middle_name is not None:
            parts += ["MIDDLENAME", self._quote_literal(expr.middle_name)]
        if expr.last_name is not None:
            parts += ["LASTNAME", self._quote_literal(expr.last_name)]
        if expr.grant_admin_role:
            parts.append("GRANT ADMIN ROLE")
        if expr.revoke_admin_role:
            parts.append("REVOKE ADMIN ROLE")
        return " ".join(parts), ()

    def format_drop_user_statement(self, expr) -> Tuple[str, tuple]:
        """Format DROP USER name."""
        self._check_user_version("DROP USER")
        return f"DROP USER {self.format_identifier(expr.username)}", ()

    def _quote_literal(self, value: str) -> str:
        """Inline a string literal with Firebird single-quote escaping."""
        return f"'{value.replace(chr(39), chr(39) * 2)}'"

    def _check_user_version(self, feature: str) -> None:
        version = getattr(self, 'version', (3, 0, 0))
        if _norm_version(version) < (3, 0, 0):
            raise UnsupportedFeatureError(
                self.name,
                feature,
                "Firebird 3.0 or later is required for SQL user management statements.",
            )
