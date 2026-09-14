# src/rhosocial/activerecord/backend/impl/firebird/mixins/window.py
"""Firebird window function formatting mixin."""

from typing import Any, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.advanced_functions import WindowFunctionCallExpression


class FirebirdWindowFunctionMixin:

    def format_window_function_call(self, call: "WindowFunctionCallExpression") -> Tuple[str, tuple]:
        """Format a window function call, pinning SUM/AVG result types.

        Mirrors :meth:`format_function_call`: Firebird 5/6-snapshot fails to
        infer the result type of ``SUM``/``AVG`` over a DECIMAL column inside
        a window expression, so wrap the whole ``SUM(...) OVER (...)`` call in
        an explicit ``CAST(... AS DECIMAL(18,2))``.
        """
        function_name = getattr(call, "function_name", None)
        if isinstance(function_name, str) and function_name.upper() in ("SUM", "AVG"):
            saved_alias = call.alias
            call.alias = None
            try:
                inner_sql, inner_params = super().format_window_function_call(call)
            finally:
                call.alias = saved_alias
            return self._cast_sql(inner_sql, inner_params, "DECIMAL(18,2)", saved_alias)
        return super().format_window_function_call(call)
