# src/rhosocial/activerecord/backend/impl/firebird/mixins/unsupported.py
"""Firebird overrides that reject SQL features the engine does not support.

These formatters intentionally raise instead of rendering the generic
cross-vendor syntax, which would otherwise emit SQL that Firebird rejects.
"""

from typing import Any, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.expression import bases
    from rhosocial.activerecord.backend.expression.query_parts import QualifyClause

_SUGGESTION_ARRAY = "Firebird does not support array types. Use separate tables or BLOB."
_SUGGESTION_GRAPH_MATCH = "Firebird does not support graph MATCH clause."
_SUGGESTION_ORDERED_SET_AGG = "Firebird does not support ordered-set aggregate functions (WITHIN GROUP)."
_SUGGESTION_QUALIFY = "Firebird does not support QUALIFY clause. Use subquery or CTE."


class FirebirdUnsupportedFeaturesMixin:

    def format_array_expression(self, _expr: "bases.BaseExpression") -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(self.name, "Array operations", _SUGGESTION_ARRAY)

    def format_match_clause(self, _clause: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(self.name, "graph MATCH clause", _SUGGESTION_GRAPH_MATCH)

    def format_ordered_set_aggregation(self, _aggregation: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(self.name, "ordered-set aggregate functions", _SUGGESTION_ORDERED_SET_AGG)

    def format_qualify_clause(self, clause: "QualifyClause") -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(self.name, "QUALIFY clause", _SUGGESTION_QUALIFY)
