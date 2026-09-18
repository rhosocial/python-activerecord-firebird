# src/rhosocial/activerecord/backend/impl/firebird/mixins/dql.py
"""Firebird DQL formatting mixin."""

from typing import Any, Optional, Tuple, TYPE_CHECKING

from .version_boundaries import _norm_version

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.query_parts import LimitOffsetClause


class FirebirdDQLMixin:

    def supports_fetch_with_ties(self) -> bool:
        """Firebird does not support FETCH ... WITH TIES."""
        return False

    def supports_nulls_first_last(self) -> bool:
        """Firebird supports explicit NULLS FIRST / NULLS LAST ordering."""
        return True

    def format_query_statement(self, expr: Any) -> Tuple[str, tuple]:
        """Format a SELECT statement, qualifying a bare wildcard when mixed with columns.

        Firebird rejects ``SELECT *, extra_col ...`` (Token unknown, error -104) and
        requires an explicit column list or a table-qualified wildcard such as
        ``SELECT "T".*, extra_col ...`` when additional expressions are selected.
        """
        from rhosocial.activerecord.backend.expression import WildcardExpression

        if len(expr.select) > 1:
            table_name = None
            for e in expr.select:
                if isinstance(e, WildcardExpression) and e.table is None and e.schema_name is None:
                    if getattr(expr, "from_", None) is not None:
                        src = expr.from_
                        if isinstance(src, list) and len(src) == 1:
                            src = src[0]
                        if hasattr(src, 'alias') or hasattr(src, 'name'):
                            table_name = getattr(src, 'alias', None) or getattr(src, 'name', None)
                    if table_name:
                        e.table = table_name
        return super().format_query_statement(expr)

    def format_limit_offset(self, limit: Optional[int] = None,
                             offset: Optional[int] = None) -> Tuple[str, tuple]:
        """Format LIMIT/OFFSET for Firebird.

        Firebird 2.5+: ROWS m TO n
        Firebird 3.0+: OFFSET m ROWS FETCH NEXT n ROWS ONLY
        """
        if limit is None and offset is None:
            return "", ()

        if _norm_version(self.version) >= (3, 0, 0):
            parts = []
            if offset is not None and offset > 0:
                parts.append(f"OFFSET {offset} ROWS")
            if limit is not None:
                parts.append(f"FETCH NEXT {limit} ROWS ONLY")
            return " ".join(parts), ()
        else:
            if limit is not None:
                if offset is not None and offset > 0:
                    return f"ROWS {offset + 1} TO {offset + limit}", ()
                return f"ROWS 1 TO {limit}", ()
            if offset is not None and offset > 0:
                return f"ROWS {offset + 1} TO {999999999}", ()
            return "", ()

    def format_limit_offset_clause(self, clause: "LimitOffsetClause") -> Tuple[str, tuple]:
        """Format LIMIT/OFFSET clause for Firebird using ROWS/FETCH syntax."""
        all_params = []
        if clause.limit is None and clause.offset is None:
            return "", ()

        if getattr(clause, "with_ties", False):
            from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

            raise UnsupportedFeatureError(
                self.name,
                "FETCH ... WITH TIES",
                "Firebird does not support FETCH ... WITH TIES.",
            )

        if _norm_version(self.version) >= (3, 0, 0):
            parts = []
            if clause.offset is not None:
                parts.append(f"OFFSET {clause.offset} ROWS")
            if clause.limit is not None:
                parts.append(f"FETCH NEXT {clause.limit} ROWS ONLY")
            return " ".join(parts), tuple(all_params)
        else:
            limit = clause.limit or 999999999
            if clause.offset is not None and clause.offset > 0:
                return f"ROWS {clause.offset + 1} TO {clause.offset + limit}", tuple(all_params)
            return f"ROWS 1 TO {limit}", tuple(all_params)
