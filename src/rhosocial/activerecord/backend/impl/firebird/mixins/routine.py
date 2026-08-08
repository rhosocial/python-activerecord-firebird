# src/rhosocial/activerecord/backend/impl/firebird/mixins/routine.py
"""Firebird PSQL PROCEDURE / FUNCTION statement formatting mixin.

Procedures exist since Firebird 1.0 and are gated here at ``(2, 5, 0)``;
stored functions were introduced in Firebird 3.0.  The PSQL body is
received as a string; when it does not already start with ``BEGIN`` it is
wrapped in a ``BEGIN ... END`` block (mirroring
``FirebirdDMLOperationMixin.format_execute_block``).
"""

from typing import Any, List, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

from ..expression.ddl.routine import FirebirdRoutineMode


class FirebirdRoutineMixin:

    def format_create_procedure_statement(self, expr) -> Tuple[str, tuple]:
        """Format CREATE [OR ALTER | RECREATE] PROCEDURE ... AS <body>."""
        self._check_routine_version("CREATE PROCEDURE", (2, 5, 0))

        parts = [expr.mode.value, "PROCEDURE", self.format_identifier(expr.procedure_name)]
        if expr.params:
            parts.append(f"({self._format_routine_params(expr.params)})")
        if expr.returns:
            parts.append(f"RETURNS ({self._format_routine_params(expr.returns)})")
        parts.append("AS")
        parts.append(self._format_psql_body(expr.body))
        return " ".join(parts), ()

    def format_create_function_statement(self, expr) -> Tuple[str, tuple]:
        """Format CREATE [OR ALTER | RECREATE] FUNCTION ... RETURNS type AS <body>.

        Overrides the core ``FunctionMixin`` renderer so the Firebird PSQL
        function syntax (``AS`` + raw body, no ``LANGUAGE``/``$$``) is
        produced.  Stored functions require Firebird 3.0 or later.
        """
        self._check_routine_version("CREATE FUNCTION", (3, 0, 0))

        parts = [expr.mode.value, "FUNCTION", self.format_identifier(expr.function_name)]
        if expr.params:
            parts.append(f"({self._format_routine_params(expr.params)})")
        if getattr(expr, "returns", None):
            parts.append(f"RETURNS {self._format_routine_return_type(expr.returns)}")
        parts.append("AS")
        parts.append(self._format_psql_body(expr.body))
        return " ".join(parts), ()

    def format_drop_routine_statement(self, expr) -> Tuple[str, tuple]:
        """Format DROP / CREATE OR ALTER / RECREATE for a PROCEDURE or FUNCTION."""
        minimum = (3, 0, 0) if expr.routine_type == "FUNCTION" else (2, 5, 0)
        self._check_routine_version(f"{expr.routine_type} routine DDL", minimum)

        if expr.mode == FirebirdRoutineMode.DROP:
            return f"DROP {expr.routine_type} {self.format_identifier(expr.routine_name)}", ()

        if expr.routine_type == "FUNCTION":
            parts = [expr.mode.value, "FUNCTION", self.format_identifier(expr.routine_name)]
            if expr.params:
                parts.append(f"({self._format_routine_params(expr.params)})")
            if getattr(expr, "returns", None):
                parts.append(f"RETURNS {self._format_routine_return_type(expr.returns)}")
        else:
            parts = [expr.mode.value, "PROCEDURE", self.format_identifier(expr.routine_name)]
            if expr.params:
                parts.append(f"({self._format_routine_params(expr.params)})")
            if expr.returns:
                parts.append(f"RETURNS ({self._format_routine_params(expr.returns)})")
        parts.append("AS")
        parts.append(self._format_psql_body(expr.body))
        return " ".join(parts), ()

    def _format_routine_params(self, params: List[Any]) -> str:
        """Render a parameter list as 'name type, name type'."""
        rendered = []
        for param in params:
            if isinstance(param, dict):
                rendered.append(f"{param.get('name', '')} {param.get('type', '')}".strip())
            else:
                rendered.append(" ".join(str(part) for part in param).strip())
        return ", ".join(rendered)

    def _format_routine_return_type(self, returns: Any) -> str:
        """Render a single return type (str or DataType)."""
        if hasattr(returns, "to_sql"):
            type_sql, _ = returns.to_sql()
            return type_sql
        return str(returns)

    def _format_psql_body(self, body: str) -> str:
        """Wrap a PSQL body in BEGIN ... END unless already wrapped."""
        stripped = body.strip()
        if stripped.upper().startswith("BEGIN"):
            return stripped
        return f"BEGIN\n{stripped}\nEND"

    def _check_routine_version(self, feature: str, minimum) -> None:
        version = getattr(self, 'version', minimum)
        if version < minimum:
            boundary = "Firebird 3.0" if minimum >= (3, 0, 0) else "Firebird 2.5"
            raise UnsupportedFeatureError(
                self.name,
                feature,
                f"{boundary} or later is required for {feature}.",
            )
