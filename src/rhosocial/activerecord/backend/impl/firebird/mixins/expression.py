# src/rhosocial/activerecord/backend/impl/firebird/mixins/expression.py
"""Firebird expression formatting mixin."""

from typing import Any, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.types import DataType

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.advanced_functions import CaseExpression
    from rhosocial.activerecord.backend.expression.operators import ArithmeticOperation


class FirebirdExpressionMixin:

    _PY_TYPE_TO_FIREBIRD_SQL = {
        int: "INTEGER",
        float: "DOUBLE PRECISION",
        bool: "SMALLINT",
        str: "VARCHAR(255)",
        bytes: "BLOB",
    }

    def _python_type_to_firebird_sql(self, value: Any) -> Optional[DataType]:
        """Map a Python value to the Firebird type an explicit CAST should name.

        Returns a DataType rather than a type name, because cast() refuses a
        string: the type position cannot take a bound parameter, so whatever
        lands there is rendered into the statement and a name is code, not data.
        The dialect renders the type, so the spelling stays Firebird's.

        Returns None for values that need no explicit cast (e.g. None).
        """
        if value is None:
            return None
        import datetime
        import decimal

        from rhosocial.activerecord.backend.expression.types import (
            BlobType,
            DateTimeType,
            DateType,
            DecimalType,
            DoubleType,
            IntegerType,
            SmallIntType,
            VarCharType,
        )

        # bool before int: bool is an int subclass, and Firebird has no boolean
        if isinstance(value, bool):
            return SmallIntType(self)
        if isinstance(value, int):
            return IntegerType(self)
        if isinstance(value, float):
            return DoubleType(self)
        if isinstance(value, str):
            return VarCharType(self, 255)
        if isinstance(value, bytes):
            return BlobType(self)
        if isinstance(value, datetime.datetime):
            return DateTimeType(self)
        if isinstance(value, datetime.date):
            return DateType(self)
        if isinstance(value, decimal.Decimal):
            return DecimalType(self, 18, 4)
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

        value = expr.value
        cases = expr.cases
        else_result = expr.else_result
        alias = expr.alias

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

    def format_arithmetic_operation(self, expr: "ArithmeticOperation") -> Tuple[str, tuple]:
        """Format an arithmetic operation with typed phantom parameters.

        Firebird cannot infer the type of a ``?`` parameter used inside an
        arithmetic expression (e.g. ``col + ?`` raises -804 Data type unknown).
        Wrap literal ``?`` operands in an explicit CAST based on the bound value.

        The entry point itself is the core's current name (``cf7972d9``):
        the node declares ``format_arithmetic_operation``, and this method
        carried the older ``format_binary_arithmetic_expression`` spelling,
        which nothing dispatched to -- the operand wrapping below never
        reached the server through it.
        """
        from rhosocial.activerecord.backend.expression.operators import ArithmeticOperation

        left = self._maybe_cast_operand(expr.left)
        right = self._maybe_cast_operand(expr.right)

        # Rebuild with the wrapped operands; the alias rides along because
        # the base renderer reads it off the node it is handed.
        wrapped = ArithmeticOperation(self, expr.op, left, right)
        wrapped.alias = expr.alias
        return super().format_arithmetic_operation(wrapped)

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

    # No ``format_function_call`` override: the entry point now serves
    # user-defined functions alone (core ``c5210245``), and the two remaps
    # this method used to carry live on the classed entry points instead --
    # ``format_char_length_function`` spells the length functions Firebird
    # actually has, and ``format_sum_function`` / ``format_avg_function``
    # pin the DECIMAL(18,2) result type. Both are on FirebirdFunctionMixin,
    # so what reaches the core's generic call renderer is a UDF whose name
    # is the user's own and none of this backend's business.
