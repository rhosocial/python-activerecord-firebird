# src/rhosocial/activerecord/backend/impl/firebird/mixins/function.py
"""Firebird function support mixin."""

from typing import Dict, Tuple, TYPE_CHECKING

from .version_boundaries import _norm_version

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.expression import bases


class FirebirdFunctionMixin:

    _FIREBIRD_FUNCTION_VERSIONS = {
        "gen_uuid": ((2, 5, 0), None),
        "uuid_to_char": ((3, 0, 0), None),
        "char_to_uuid": ((3, 0, 0), None),
        "list": ((2, 5, 0), None),
        "dateadd": ((2, 5, 0), None),
        "datediff": ((2, 5, 0), None),
        "replace": ((2, 5, 0), None),
        "position": ((2, 5, 0), None),
        "iif": ((2, 5, 0), None),
        "decode": ((2, 5, 0), None),
        "lpad": ((2, 5, 0), None),
        "rpad": ((2, 5, 0), None),
    }

    def supports_functions(self) -> Dict[str, bool]:
        from rhosocial.activerecord.backend.expression.functions import __all__ as core_functions
        expression_constructors = {
            "xmlagg",
            "xmlattributes",
            "xmlcomment",
            "xmlconcat",
            "xmlelement",
            "xmlexists",
            "xmlforest",
            "xmlparse",
            "xmlpi",
            "xmlquery",
            "xmlroot",
            "xmlserialize",
            "xmltable",
        }
        result = {}
        for func_name in core_functions:
            if func_name not in expression_constructors:
                result[func_name] = True
        for func_name, (_min_ver, _max_ver) in self._FIREBIRD_FUNCTION_VERSIONS.items():
            result[func_name] = self._is_firebird_function_supported(func_name)
        return result

    def _is_firebird_function_supported(self, func_name: str) -> bool:
        version_range = self._FIREBIRD_FUNCTION_VERSIONS.get(func_name)
        if version_range is None:
            return True
        min_version, max_version = version_range
        if min_version is not None and _norm_version(self.version) < min_version:
            return False
        if max_version is not None and _norm_version(self.version) > max_version:
            return False
        return True

    def format_char_length_function(self, expr: "bases.BaseExpression") -> Tuple[str, tuple]:
        """Firebird's length spellings, by the unit the node declares.

        Firebird 5 does not expose a ``LENGTH`` scalar function (the name
        is a reserved keyword), so the core's default spelling is not an
        answer here at all. What Firebird has is one native function per
        unit the node can declare (fblangref, character functions):

        * ``char`` -- ``CHAR_LENGTH(operand)``, counted in characters;
        * ``octet`` -- ``OCTET_LENGTH(operand)``, counted in bytes;
        * ``bit`` -- ``BIT_LENGTH(operand)``, counted in bits.

        The unit is honoured rather than one spelling being picked,
        because the node records which question was asked and each of the
        three answers a different one.

        Args:
            expr: The :class:`CharLengthFunction` whose ``unit`` names the
                length semantics asked for.

        Returns:
            A ``(sql, params)`` tuple.
        """
        operand_sql, operand_params = expr.operand.to_sql()
        if expr.unit == "octet":
            sql = f"OCTET_LENGTH({operand_sql})"
        elif expr.unit == "bit":
            sql = f"BIT_LENGTH({operand_sql})"
        else:
            sql = f"CHAR_LENGTH({operand_sql})"
        if expr.alias:
            sql = f"{sql} AS {self.format_identifier(expr.alias)}"
        return sql, tuple(operand_params)

    def _format_pinned_aggregate(
        self, name: str, expr: "bases.BaseExpression"
    ) -> Tuple[str, tuple]:
        """Render ``NAME(...)`` wrapped in the DECIMAL(18,2) result pin.

        Firebird 5 / 6-snapshot fails to infer the result type of ``SUM`` /
        ``AVG`` over a ``DECIMAL`` column ("Data type unknown" at prepare
        time), so the aggregate is explicitly cast to ``DECIMAL(18,2)`` to pin
        the return type -- the precision the testsuite schemas use.

        Built here rather than by wrapping the core helper's output, because
        the alias must sit outside the ``CAST`` and the helper renders it
        inside; mutating ``expr.alias`` around a delegated call is the shape
        this replaces.
        """
        operand_sql, operand_params = expr.operand.to_sql()
        distinct = "DISTINCT " if expr.distinct else ""
        sql = f"CAST({name}({distinct}{operand_sql}) AS DECIMAL(18,2))"
        if expr.alias:
            sql = f"{sql} AS {self.format_identifier(expr.alias)}"
        return sql, tuple(operand_params)

    def format_sum_function(self, expr: "bases.BaseExpression") -> Tuple[str, tuple]:
        """``SUM`` with the result type pinned to ``DECIMAL(18,2)``.

        Measured on Firebird 5 and the 6.0 snapshot: preparing ``SUM`` over
        a ``DECIMAL`` column answers "Data type unknown" without the cast.
        """
        return self._format_pinned_aggregate("SUM", expr)

    def format_avg_function(self, expr: "bases.BaseExpression") -> Tuple[str, tuple]:
        """``AVG`` with the result type pinned to ``DECIMAL(18,2)``.

        Same measured refusal as :meth:`format_sum_function`: the cast is
        what lets the server prepare the statement at all.
        """
        return self._format_pinned_aggregate("AVG", expr)

    #: The aggregate spellings the server refuses to infer a result type
    #: for, matched on the plain :class:`FunctionCall` path below. The
    #: classed ``SumFunction`` / ``AvgFunction`` entry points above are the
    #: other route to the same measured fact.
    _PINNED_AGGREGATE_NAMES = ("SUM", "AVG")

    def format_function_call(self, expr: "bases.BaseExpression") -> Tuple[str, tuple]:
        """Pin the result type of a plain ``SUM`` / ``AVG`` call.

        The measured Firebird fact behind :meth:`format_sum_function` /
        :meth:`format_avg_function` -- the server refuses to infer the result
        type of ``SUM`` / ``AVG`` over a ``DECIMAL`` column ("Data type
        unknown" at prepare time, on Firebird 5 and the 6.0 snapshot) -- is a
        fact about the aggregate, not about which node class spelled it. A
        plain ``FunctionCall`` reaches the core's generic renderer with the
        same grammar, and that renderer spells ``SUM(args)`` bare: the
        testsuite's window tests build exactly that node -- ``FunctionCall(
        dialect, "SUM", column, window_spec=...)`` -- and the prepare of the
        rendered statement fails on the server with the same refusal.

        So the pin is applied here too: the alias is stripped for the inner
        render (the base would print it inside the call) and rides outside
        the CAST, the same outside-alias shape the classed entry points use.
        A window clause renders inside the CAST, which is where the engine
        expects the aggregate expression to end.

        Every other name passes through to the core unchanged: what remains
        on this path is a user-defined function, whose name is the user's
        own and none of this backend's business.
        """
        from rhosocial.activerecord.backend.expression.core import FunctionCall

        if (expr.func_name or "").upper() in self._PINNED_AGGREGATE_NAMES:
            inner = FunctionCall(
                expr.dialect,
                expr.func_name,
                *expr.args,
                is_distinct=expr.is_distinct,
                niladic=expr.niladic,
                filter_predicate=expr.filter_predicate,
                window_spec=expr.window_spec,
                is_aggregate=expr.is_aggregate,
            )
            sql, params = super().format_function_call(inner)
            return self._cast_sql(sql, tuple(params), "DECIMAL(18,2)", expr.alias)
        return super().format_function_call(expr)
