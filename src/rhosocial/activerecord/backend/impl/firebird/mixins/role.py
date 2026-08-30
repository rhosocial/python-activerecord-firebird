# src/rhosocial/activerecord/backend/impl/firebird/mixins/role.py
"""Firebird ROLE statement formatting mixin.

Roles are an ancient Firebird feature; ``CREATE ROLE`` / ``DROP ROLE`` are
gated here at ``(2, 5, 0)`` while ``ALTER ROLE`` (SET/DROP SYSTEM PRIVILEGES,
SET/DROP AUTO ADMIN MAPPING) requires Firebird 3.0.
"""

from typing import Tuple

from .version_boundaries import _norm_version
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

from ..expression.ddl.role import FirebirdRoleAlterClause


class FirebirdRoleMixin:

    def supports_roles(self) -> bool:
        return _norm_version(self.version) >= (2, 5, 0)

    def supports_create_role(self) -> bool:
        return _norm_version(self.version) >= (2, 5, 0)

    def supports_alter_role(self) -> bool:
        return _norm_version(self.version) >= (3, 0, 0)

    def supports_drop_role(self) -> bool:
        return _norm_version(self.version) >= (2, 5, 0)

    def format_create_role_statement(self, expr) -> Tuple[str, tuple]:
        """Format CREATE ROLE name."""
        self._check_role_version("CREATE ROLE", (2, 5, 0))
        return f"CREATE ROLE {self.format_identifier(expr.role_name)}", ()

    def format_alter_role_statement(self, expr) -> Tuple[str, tuple]:
        """Format ALTER ROLE name <clause> (Firebird 3.0+).

        Firebird 5.0 ALTER ROLE supports: ``SET SYSTEM PRIVILEGES TO <list>``,
        ``DROP SYSTEM PRIVILEGES`` and ``{SET | DROP} AUTO ADMIN MAPPING``.
        """
        self._check_role_version("ALTER ROLE", (3, 0, 0))

        name = self.format_identifier(expr.role_name)
        if expr.clause == FirebirdRoleAlterClause.SET_SYSTEM_PRIVILEGES:
            privileges = expr.system_privileges or []
            if not privileges:
                raise ValueError(
                    "system_privileges are required for "
                    "FirebirdRoleAlterClause.SET_SYSTEM_PRIVILEGES"
                )
            return (
                f"ALTER ROLE {name} SET SYSTEM PRIVILEGES TO "
                f"{', '.join(str(p) for p in privileges)}",
                (),
            )
        return f"ALTER ROLE {name} {expr.clause.value}", ()

    def format_drop_role_statement(self, expr) -> Tuple[str, tuple]:
        """Format DROP ROLE name."""
        self._check_role_version("DROP ROLE", (2, 5, 0))
        return f"DROP ROLE {self.format_identifier(expr.role_name)}", ()

    def _check_role_version(self, feature: str, minimum) -> None:
        version = getattr(self, 'version', minimum)
        if _norm_version(version) < minimum:
            boundary = "Firebird 3.0" if minimum >= (3, 0, 0) else "Firebird 2.5"
            raise UnsupportedFeatureError(
                self.name,
                feature,
                f"{boundary} or later is required for {feature}.",
            )
