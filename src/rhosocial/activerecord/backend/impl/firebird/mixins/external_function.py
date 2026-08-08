# src/rhosocial/activerecord/backend/impl/firebird/mixins/external_function.py
"""Firebird EXTERNAL FUNCTION (UDF) statement formatting mixin.

UDFs are an ancient Firebird feature (available in every supported version,
gated here at ``(2, 5, 0)``).  Firebird 4.0 deprecates UDFs in favour of
UDRs (``CREATE FUNCTION ... EXTERNAL``); the DECLARE ALTER/DROP statements
below remain accepted for backwards compatibility.
"""

from typing import Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


class FirebirdExternalFunctionMixin:

    def format_create_external_function_statement(self, expr) -> Tuple[str, tuple]:
        """Format DECLARE EXTERNAL FUNCTION name [(params)] RETURNS type
        [BY VALUE] [FREE_IT] ENTRY_POINT 'entry' MODULE_NAME 'module'."""
        self._check_external_function_version("DECLARE EXTERNAL FUNCTION")

        parts = [
            "DECLARE EXTERNAL FUNCTION",
            self.format_identifier(expr.function_name),
        ]
        if expr.params:
            parts.append(f"({', '.join(expr.params)})")
        returns = expr.returns
        if getattr(expr, "by_value", False):
            returns = f"{returns} BY VALUE"
        parts.append(f"RETURNS {returns}")
        if getattr(expr, "free_it", False):
            parts.append("FREE_IT")
        parts.append(f"ENTRY_POINT {self._quote_literal(expr.entry_point)}")
        parts.append(f"MODULE_NAME {self._quote_literal(expr.module_name)}")
        return " ".join(parts), ()

    def format_alter_external_function_statement(self, expr) -> Tuple[str, tuple]:
        """Format ALTER EXTERNAL FUNCTION name [ENTRY_POINT ...] [MODULE_NAME ...]."""
        self._check_external_function_version("ALTER EXTERNAL FUNCTION")

        parts = ["ALTER EXTERNAL FUNCTION", self.format_identifier(expr.function_name)]
        if expr.entry_point is not None:
            parts.append(f"ENTRY_POINT {self._quote_literal(expr.entry_point)}")
        if expr.module_name is not None:
            parts.append(f"MODULE_NAME {self._quote_literal(expr.module_name)}")
        return " ".join(parts), ()

    def format_drop_external_function_statement(self, expr) -> Tuple[str, tuple]:
        """Format DROP EXTERNAL FUNCTION name."""
        self._check_external_function_version("DROP EXTERNAL FUNCTION")
        return f"DROP EXTERNAL FUNCTION {self.format_identifier(expr.function_name)}", ()

    def _quote_literal(self, value: str) -> str:
        """Inline a string literal with Firebird single-quote escaping."""
        return f"'{value.replace(chr(39), chr(39) * 2)}'"

    def _check_external_function_version(self, feature: str) -> None:
        version = getattr(self, 'version', (2, 5, 0))
        if version < (2, 5, 0):
            raise UnsupportedFeatureError(
                self.name,
                feature,
                "Firebird 2.5 or later is required for EXTERNAL FUNCTION statements.",
            )
