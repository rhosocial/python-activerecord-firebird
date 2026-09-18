# src/rhosocial/activerecord/backend/impl/firebird/mixins/expression.py
"""Firebird expression formatting mixin."""

from typing import Any, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression import bases
    from rhosocial.activerecord.backend.expression.advanced_functions import CaseExpression
    from rhosocial.activerecord.backend.expression.operators import BinaryArithmeticExpression


class FirebirdExpressionMixin:

    _PY_TYPE_TO_FIREBIRD_SQL = {
        int: "INTEGER",
        float: "DOUBLE PRECISION",
        bool: "SMALLINT",
        str: "VARCHAR(255)",
        bytes: "BLOB",
    }

    @staticmethod
    def _python_type_to_firebird_sql(value: Any) -> Optional[str]:
        """Map a Python value to its Firebird SQL type for explicit CAST.

        Returns None for types that don't need explicit casting (e.g. None).
        """
        if value is None:
            return None
        import datetime
        import decimal
        if isinstance(value, bool):
            return "SMALLINT"
        if isinstance(value, int):
            return "INTEGER"
        if isinstance(value, float):
            return "DOUBLE PRECISION"
        if isinstance(value, str):
            return "VARCHAR(255)"
        if isinstance(value, bytes):
            return "BLOB"
        if isinstance(value, datetime.date):
            return "DATE"
        if isinstance(value, datetime.datetime):
            return "TIMESTAMP"
        if isinstance(value, decimal.Decimal):
            return "DECIMAL(18, 4)"
        return None

    def format_case_expression(self, expr: "CaseExpression") -> Tuple[str, tuple]:
        """Format a CASE expression, wrapping result values in CAST for type inference.

        Firebird cannot infer the type of a ``?`` parameter used as a CASE
        result. When a result is a literal parameter whose Python type maps
        to a Firebird SQL type, wrap the result in ``CAST(... AS fb_type)``
        so Firebird can resolve the type.  This applies to both simple CASE
        (``CASE col WHEN val THEN …``) and searched CASE
        (``CASE WHEN cond THEN …``) expressions.
        """
        from rhosocial.activerecord.backend.expression.core import CastExpression, Literal

        value = getattr(expr, "value", None)
        cases = getattr(expr, "cases", [])
        else_result = getattr(expr, "else_result", None)
        alias = getattr(expr, "alias", None)

        wrapped_cases = []
        for condition, result in cases:
            wrapped_result = result
            res_sql, res_params = result.to_sql()
            placeholder = self.get_parameter_placeholder()
            if res_sql.strip() == placeholder and res_params:
                fb_type = self._python_type_to_firebird_sql(res_params[0])
                if fb_type:
                    literal = Literal(self, res_params[0])
                    wrapped_result = CastExpression(self, literal, fb_type)
            wrapped_cases.append((condition, wrapped_result))

        wrapped_else = else_result
        if else_result is not None:
            else_sql, else_params = else_result.to_sql()
            placeholder = self.get_parameter_placeholder()
            if else_sql.strip() == placeholder and else_params:
                fb_type = self._python_type_to_firebird_sql(else_params[0])
                if fb_type:
                    literal = Literal(self, else_params[0])
                    wrapped_else = CastExpression(self, literal, fb_type)

        from rhosocial.activerecord.backend.expression.advanced_functions import CaseExpression
        wrapped_expr = CaseExpression(self, value=value, cases=wrapped_cases, else_result=wrapped_else, alias=alias)
        return super().format_case_expression(wrapped_expr)

    def format_binary_arithmetic_expression(self, expr: "BinaryArithmeticExpression") -> Tuple[str, tuple]:
        """Format a binary arithmetic expression with typed phantom parameters.

        Firebird cannot infer the type of a ``?`` parameter used inside an
        arithmetic expression (e.g. ``col + ?`` raises -804 Data type unknown).
        Wrap literal ``?`` operands in an explicit CAST based on the bound value.
        """
        from rhosocial.activerecord.backend.expression.operators import BinaryArithmeticExpression

        left = expr.left
        right = expr.right
        op = expr.op

        # Cast literal operands that Firebird can't type-infer
        left = self._maybe_cast_operand(left)
        right = self._maybe_cast_operand(right)

        # Rebuild expression with wrapped operands
        wrapped = BinaryArithmeticExpression(self, op, left, right)
        wrapped.alias = getattr(expr, 'alias', None)
        return super().format_binary_arithmetic_expression(wrapped)

    def _maybe_cast_operand(self, operand):
        """Wrap a Literal operand in CastExpression if Firebird needs explicit typing."""
        from rhosocial.activerecord.backend.expression.core import Literal, CastExpression

        if not isinstance(operand, Literal):
            return operand
        value = operand.value
        fb_type = self._python_type_to_firebird_sql(value)
        if fb_type:
            return CastExpression(self, operand, fb_type)
        return operand

    def _cast_sql(self, inner_sql: str, inner_params: tuple,
                   target_type: str, alias: Optional[str] = None) -> Tuple[str, tuple]:
        """Wrap already-rendered SQL in a CAST expression.

        Used when the inner expression (e.g. a window function or aggregate)
        must be explicitly typed but cannot be wrapped in a CastExpression node
        before rendering (because the base formatter accesses node-specific
        attributes that CastExpression doesn't carry).
        """
        if not self._validate_data_type(target_type):
            raise ValueError(
                f"Invalid target type '{target_type}': "
                "must contain only alphanumeric characters, spaces, parentheses, and commas."
            )
        sql = f"CAST({inner_sql} AS {target_type})"
        if alias:
            sql = f"{sql} AS {self.format_identifier(alias)}"
        return sql, inner_params

    def format_function_call(self, expr: "bases.BaseExpression") -> Tuple[str, tuple]:
        """Format a function call, remapping names Firebird does not provide.

        Firebird 5 does not expose a ``LENGTH`` scalar function (the name is a
        reserved keyword); the canonical length function is ``CHAR_LENGTH`` for
        characters and ``OCTET_LENGTH`` for bytes.

        Firebird 5/6-snapshot fails to infer the result type of ``SUM``/``AVG``
        over a ``DECIMAL`` column ("Data type unknown" at prepare time), so the
        aggregate result is explicitly cast to ``DECIMAL(18,2)`` to pin the
        return type. This matches the precision used by the testsuite schemas.
        """
        func_name = getattr(expr, "func_name", None)
        if isinstance(func_name, str) and func_name.upper() == "LENGTH":
            expr.func_name = "CHAR_LENGTH"
            try:
                return super().format_function_call(expr)
            finally:
                expr.func_name = func_name
        if isinstance(func_name, str) and func_name.upper() in ("SUM", "AVG"):
            saved_alias = expr.alias
            expr.alias = None
            try:
                inner_sql, inner_params = super().format_function_call(expr)
            finally:
                expr.alias = saved_alias
            return self._cast_sql(inner_sql, inner_params, "DECIMAL(18,2)", saved_alias)
        return super().format_function_call(expr)
