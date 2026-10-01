# src/rhosocial/activerecord/backend/impl/firebird/mixins/json.py
"""Firebird JSON path functions.

Firebird 4.0 added ``JSON_VALUE``, which returns a SQL scalar as text, and 5.0
added ``JSON_QUERY``, which returns a document. So the two operators split
across versions rather than sitting together: ``->>`` works from 4.0 and ``->``
only from 5.0.

There are no arrow operators, and no ``JSON_UNQUOTE`` — which is what the
core default emits for ``->>``, so a path here used to produce SQL no Firebird
server accepts.
"""

# src/rhosocial/activerecord/backend/impl/firebird/mixins/json.py
from typing import Tuple


class FirebirdJSONMixin:
    """JSON path rendering, version-gated on which functions exist."""

    #: JSON_QUERY arrived in Firebird 5; JSON_VALUE in 4.
    QUERY_VERSION = (5, 0, 0)
    VALUE_VERSION = (4, 0, 0)

    def supports_json_type(self) -> bool:
        """Whether this server has any JSON path function at all."""
        return self.version >= self.VALUE_VERSION

    def supports_json_document_path(self) -> bool:
        """Whether a path can return a document rather than text.

        Split out because it is the one capability that moved: a caller asking
        for a document on Firebird 4 needs to be told no, while ``->>`` works.
        """
        return self.version >= self.QUERY_VERSION

    def format_json_function_expression(self, expr) -> Tuple[str, tuple]:
        """Render a JSON path with JSON_VALUE or JSON_QUERY.

        Declared in a mixin that sits before the core JSONMixin, since a
        formatter written after it in the MRO is dead code.
        """
        from ....dialect.exceptions import UnsupportedFeatureError
        from ....expression import bases

        if expr.operation != "->>" and not self.supports_json_document_path():
            raise UnsupportedFeatureError(
                dialect_name=type(self).__name__,
                feature_name="a JSON path that returns a document (->)",
                suggestion=(
                    "JSON_QUERY arrived in Firebird 5. Use ->> for text on "
                    "Firebird 4, or upgrade."
                ),
            )

        if isinstance(expr.column, bases.BaseExpression):
            col_sql, col_params = expr.column.to_sql()
        else:
            col_sql, col_params = self.format_identifier(str(expr.column)), ()

        path = self.format_literal(str(expr.path or "").strip() or "$")
        if expr.operation == "->>":
            sql = f"JSON_VALUE({col_sql}, {path})"
        else:
            sql = f"JSON_QUERY({col_sql}, {path})"

        if expr.alias:
            sql = f"{sql} AS {self.format_identifier(expr.alias)}"
        return sql, col_params

    def format_json_arrow_expression(self, expr) -> Tuple[str, tuple]:
        """Firebird has no ``->`` operator, so ARROW mode is refused."""
        from ....dialect.exceptions import UnsupportedFeatureError

        raise UnsupportedFeatureError(
            dialect_name=type(self).__name__,
            feature_name="the -> and ->> JSON operators",
            suggestion=(
                "Firebird has no arrow operators for JSON. Use "
                "JSONPathMode.FUNCTION, or AUTO."
            ),
        )
