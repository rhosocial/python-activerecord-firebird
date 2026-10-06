# src/rhosocial/activerecord/backend/impl/firebird/mixins/routine.py
"""Firebird PSQL PROCEDURE / FUNCTION statement formatting mixin.

Procedures exist since Firebird 1.0 and are gated here at ``(2, 5, 0)``;
stored functions were introduced in Firebird 3.0.  The PSQL body is
received as a string; when it does not already start with ``BEGIN`` it is
wrapped in a ``BEGIN ... END`` block (mirroring
``FirebirdDMLOperationMixin.format_execute_block``).
"""

from typing import Any, List, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.objects import Function, Procedure

from ..expression.ddl.routine import FirebirdRoutineMode

if TYPE_CHECKING:
    from ..expression.ddl.routine import (
        FirebirdCreateProcedureExpression,
        FirebirdCreateFunctionExpression,
        FirebirdDropRoutineExpression,
    )


class FirebirdRoutineMixin:

    def format_create_procedure_statement(self, expr: "FirebirdCreateProcedureExpression") -> Tuple[str, tuple]:
        """Format CREATE [OR ALTER | RECREATE] PROCEDURE ... AS <body>."""
        self._check_routine_version("CREATE PROCEDURE", (2, 5, 0))

        parts = [expr.mode.value, "PROCEDURE", Procedure(self, expr.procedure_name).to_sql()[0]]
        if expr.params:
            parts.append(f"({self._format_routine_params(expr.params)})")
        if expr.returns:
            parts.append(f"RETURNS ({self._format_routine_params(expr.returns)})")
        parts.append("AS")
        parts.append(self._format_psql_body(expr.body))
        return " ".join(parts), ()

    def format_create_function_statement(self, expr: "FirebirdCreateFunctionExpression") -> Tuple[str, tuple]:
        """Format CREATE [OR ALTER | RECREATE] FUNCTION ... RETURNS type AS <body>.

        Overrides the core ``FunctionMixin`` renderer so the Firebird PSQL
        function syntax (``AS`` + raw body, no ``LANGUAGE``/``$$``) is
        produced.  Stored functions require Firebird 3.0 or later.
        """
        self._check_routine_version("CREATE FUNCTION", (3, 0, 0))

        parts = [expr.mode.value, "FUNCTION", Function(self, expr.function_name).to_sql()[0]]
        if expr.params:
            parts.append(f"({self._format_routine_params(expr.params)})")
        if getattr(expr, "returns", None):
            parts.append(f"RETURNS {self._format_routine_return_type(expr.returns)}")
        parts.append("AS")
        parts.append(self._format_psql_body(expr.body))
        return " ".join(parts), ()

    def format_drop_routine_statement(self, expr: "FirebirdDropRoutineExpression") -> Tuple[str, tuple]:
        """Format DROP / CREATE OR ALTER / RECREATE for a PROCEDURE or FUNCTION."""
        minimum = (3, 0, 0) if expr.routine_type == "FUNCTION" else (2, 5, 0)
        self._check_routine_version(f"{expr.routine_type} routine DDL", minimum)

        # The statement knows which kind it is; name the object accordingly so
        # the object says PROCEDURE rather than "some routine".
        name_renderer = self._routine_name_renderer(expr.routine_type)

        if expr.mode == FirebirdRoutineMode.DROP:
            return f"DROP {expr.routine_type} {name_renderer(expr.routine_name)}", ()

        if expr.routine_type == "FUNCTION":
            parts = [expr.mode.value, "FUNCTION", name_renderer(expr.routine_name)]
            if expr.params:
                parts.append(f"({self._format_routine_params(expr.params)})")
            if getattr(expr, "returns", None):
                parts.append(f"RETURNS {self._format_routine_return_type(expr.returns)}")
        else:
            parts = [expr.mode.value, "PROCEDURE", name_renderer(expr.routine_name)]
            if expr.params:
                parts.append(f"({self._format_routine_params(expr.params)})")
            if expr.returns:
                parts.append(f"RETURNS ({self._format_routine_params(expr.returns)})")
        parts.append("AS")
        parts.append(self._format_psql_body(expr.body))
        return " ".join(parts), ()

    def _routine_name_renderer(self, routine_type: str):
        """The renderer for a routine name, chosen by the kind the caller named.

        Firebird spells a procedure and a function the same way, but the object
        still says which it is, so a caller reading a rendered name back out of
        a statement cannot mistake one for the other.
        """
        kind = Function if routine_type == "FUNCTION" else Procedure
        return lambda name: kind(self, name).to_sql()[0]

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
