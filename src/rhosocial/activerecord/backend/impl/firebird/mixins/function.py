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
        if expr.unit == "octet":
            return self._format_scalar_function("OCTET_LENGTH", expr)
        if expr.unit == "bit":
            return self._format_scalar_function("BIT_LENGTH", expr)
        return self._format_scalar_function("CHAR_LENGTH", expr)

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
