# src/rhosocial/activerecord/backend/impl/firebird/mixins/domain.py
"""Firebird DOMAIN statement formatting mixin.

DOMAIN is an ancient Firebird feature (available in every supported
version, gated here at ``(2, 5, 0)``) that packages a data type with a
default value, a NOT NULL flag and optional CHECK constraints for reuse
across table columns.
"""

from typing import Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

from ..expression.ddl.domain import FirebirdDomainAlterMode


class FirebirdDomainMixin:

    def supports_domain(self) -> bool:
        return self.version >= (2, 5, 0)

    def supports_create_domain(self) -> bool:
        return self.version >= (2, 5, 0)

    def supports_alter_domain(self) -> bool:
        return self.version >= (2, 5, 0)

    def supports_drop_domain(self) -> bool:
        return self.version >= (2, 5, 0)

    def format_create_domain_statement(self, expr) -> Tuple[str, tuple]:
        """Format CREATE DOMAIN name [AS] datatype [DEFAULT ...] [NOT NULL] [CHECK (...)]."""
        self._check_domain_version("CREATE DOMAIN")

        type_sql, _ = self.format_data_type(expr.data_type)
        parts = [
            "CREATE DOMAIN",
            self.format_identifier(expr.domain_name),
            "AS",
            type_sql,
        ]

        if getattr(expr, "default", None) is not None:
            parts.append(f"DEFAULT {self._format_ddl_literal(expr.default)}")

        if getattr(expr, "not_null", False):
            parts.append("NOT NULL")

        if getattr(expr, "check", None):
            parts.append(f"CHECK ({expr.check})")

        return " ".join(parts), ()

    def format_alter_domain_statement(self, expr) -> Tuple[str, tuple]:
        """Format ALTER DOMAIN name <clause> per the requested mode."""
        self._check_domain_version("ALTER DOMAIN")

        domain = self.format_identifier(expr.domain_name)
        mode = expr.mode

        if mode == FirebirdDomainAlterMode.SET_DEFAULT:
            return f"ALTER DOMAIN {domain} SET DEFAULT {self._format_ddl_literal(expr.value)}", ()
        if mode == FirebirdDomainAlterMode.DROP_DEFAULT:
            return f"ALTER DOMAIN {domain} DROP DEFAULT", ()
        if mode == FirebirdDomainAlterMode.SET_NOT_NULL:
            return f"ALTER DOMAIN {domain} SET NOT NULL", ()
        if mode == FirebirdDomainAlterMode.DROP_NOT_NULL:
            return f"ALTER DOMAIN {domain} DROP NOT NULL", ()
        if mode == FirebirdDomainAlterMode.ADD_CONSTRAINT:
            constraint = f"CONSTRAINT {self.format_identifier(expr.constraint_name)} " if expr.constraint_name else ""
            return (
                f"ALTER DOMAIN {domain} ADD {constraint}CHECK ({expr.constraint_sql})",
                (),
            )
        if mode == FirebirdDomainAlterMode.DROP_CONSTRAINT:
            return (
                f"ALTER DOMAIN {domain} DROP CONSTRAINT "
                f"{self.format_identifier(expr.constraint_name)}",
                (),
            )
        if mode == FirebirdDomainAlterMode.SET_TYPE:
            type_sql, _ = self.format_data_type(expr.data_type)
            return f"ALTER DOMAIN {domain} TYPE {type_sql}", ()

        raise UnsupportedFeatureError(
            self.name,
            f"ALTER DOMAIN mode {mode}",
            "Unsupported ALTER DOMAIN clause.",
        )

    def format_drop_domain_statement(self, expr) -> Tuple[str, tuple]:
        """Format DROP DOMAIN name."""
        self._check_domain_version("DROP DOMAIN")
        return f"DROP DOMAIN {self.format_identifier(expr.domain_name)}", ()

    def _format_ddl_literal(self, value) -> str:
        """Render a DDL default value as an inline literal."""
        if isinstance(value, str):
            return self._quote_literal(value)
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        return str(value)

    def _quote_literal(self, value: str) -> str:
        """Inline a string literal with Firebird single-quote escaping."""
        return f"'{value.replace(chr(39), chr(39) * 2)}'"

    def _check_domain_version(self, feature: str) -> None:
        version = getattr(self, 'version', (2, 5, 0))
        if version < (2, 5, 0):
            raise UnsupportedFeatureError(
                self.name,
                feature,
                "Firebird 2.5 or later is required for DOMAIN statements.",
            )
