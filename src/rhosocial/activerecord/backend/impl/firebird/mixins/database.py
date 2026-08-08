# src/rhosocial/activerecord/backend/impl/firebird/mixins/database.py
"""Firebird CREATE / DROP DATABASE statement formatting mixin.

Database creation/removal is operational DDL with a Firebird-specific option
set (PAGE_SIZE, DEFAULT CHARACTER SET, COLLATION, DIALECT, FORCE WRITE,
SQL SECURITY).  Both statements are gated at ``(2, 5, 0)``.
"""

from typing import Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


class FirebirdDatabaseMixin:

    def supports_create_database(self) -> bool:
        return self.version >= (2, 5, 0)

    def supports_drop_database(self) -> bool:
        return self.version >= (2, 5, 0)

    def format_create_database_statement(self, expr) -> Tuple[str, tuple]:
        """Format CREATE DATABASE 'file' with the configured options."""
        self._check_database_version("CREATE DATABASE")

        parts = ["CREATE DATABASE", self._quote_literal(expr.file_path)]
        if expr.user is not None:
            parts.append(f"USER {self._quote_literal(expr.user)}")
        if expr.password is not None:
            parts.append(f"PASSWORD {self._quote_literal(expr.password)}")
        if expr.page_size is not None:
            parts.append(f"PAGE_SIZE {expr.page_size}")
        if expr.default_character_set is not None:
            parts.append(f"DEFAULT CHARACTER SET {expr.default_character_set}")
        if expr.collation is not None:
            parts.append(f"COLLATION {self._quote_literal(expr.collation)}")
        if expr.sql_dialect is not None:
            parts.append(f"DIALECT {expr.sql_dialect}")
        if getattr(expr, "force_write", False):
            parts.append("FORCE WRITE")
        if expr.sql_security is not None:
            mode = getattr(expr.sql_security, "value", expr.sql_security)
            parts.append(f"SQL SECURITY {mode}")
        return " ".join(parts), ()

    def format_drop_database_statement(self, expr) -> Tuple[str, tuple]:
        """Format DROP DATABASE."""
        self._check_database_version("DROP DATABASE")
        return "DROP DATABASE", ()

    def _quote_literal(self, value: str) -> str:
        """Inline a string literal with Firebird single-quote escaping."""
        return f"'{value.replace(chr(39), chr(39) * 2)}'"

    def _check_database_version(self, feature: str) -> None:
        version = getattr(self, 'version', (2, 5, 0))
        if version < (2, 5, 0):
            raise UnsupportedFeatureError(
                self.name,
                feature,
                "Firebird 2.5 or later is required for DATABASE statements.",
            )
