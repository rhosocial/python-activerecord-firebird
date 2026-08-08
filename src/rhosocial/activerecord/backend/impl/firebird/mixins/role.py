# src/rhosocial/activerecord/backend/impl/firebird/mixins/role.py
"""Firebird ROLE statement formatting mixin.

Roles are an ancient Firebird feature; ``CREATE ROLE`` / ``DROP ROLE`` are
gated here at ``(2, 5, 0)`` while ``ALTER ROLE`` (SET DEFAULT/ACTIVE/
INACTIVE/AUTO_ADMIN, DROP AUTO_ADMIN, RENAME TO) requires Firebird 3.0.
"""

from typing import Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

from ..expression.ddl.role import FirebirdRoleAlterClause


class FirebirdRoleMixin:

    def supports_roles(self) -> bool:
        return self.version >= (2, 5, 0)

    def supports_create_role(self) -> bool:
        return self.version >= (2, 5, 0)

    def supports_alter_role(self) -> bool:
        return self.version >= (3, 0, 0)

    def supports_drop_role(self) -> bool:
        return self.version >= (2, 5, 0)

    def format_create_role_statement(self, expr) -> Tuple[str, tuple]:
        """Format CREATE ROLE name."""
        self._check_role_version("CREATE ROLE", (2, 5, 0))
        return f"CREATE ROLE {self.format_identifier(expr.role_name)}", ()

    def format_alter_role_statement(self, expr) -> Tuple[str, tuple]:
        """Format ALTER ROLE name <clause> (Firebird 3.0+)."""
        self._check_role_version("ALTER ROLE", (3, 0, 0))

        name = self.format_identifier(expr.role_name)
        if expr.clause == FirebirdRoleAlterClause.RENAME_TO:
            return (
                f"ALTER ROLE {name} RENAME TO {self.format_identifier(expr.new_name)}",
                (),
            )
        return f"ALTER ROLE {name} {expr.clause.value}", ()

    def format_drop_role_statement(self, expr) -> Tuple[str, tuple]:
        """Format DROP ROLE name."""
        self._check_role_version("DROP ROLE", (2, 5, 0))
        return f"DROP ROLE {self.format_identifier(expr.role_name)}", ()

    def _check_role_version(self, feature: str, minimum) -> None:
        version = getattr(self, 'version', minimum)
        if version < minimum:
            boundary = "Firebird 3.0" if minimum >= (3, 0, 0) else "Firebird 2.5"
            raise UnsupportedFeatureError(
                self.name,
                feature,
                f"{boundary} or later is required for {feature}.",
            )
