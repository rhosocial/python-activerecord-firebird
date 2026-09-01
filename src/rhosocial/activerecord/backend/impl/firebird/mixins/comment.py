# src/rhosocial/activerecord/backend/impl/firebird/mixins/comment.py
"""Firebird COMMENT ON statement formatting mixin.

``COMMENT ON`` annotates metadata objects (tables, columns, views, routines,
domains, exceptions, triggers, generators, ...) and is available since
Firebird 2.5, gated here at ``(2, 5, 0)``.
"""

from typing import Tuple

from .version_boundaries import _norm_version
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

from ..expression.comment import FirebirdCommentObjectType


class FirebirdCommentMixin:

    def supports_comment_on(self) -> bool:
        return _norm_version(self.version) >= (2, 5, 0)

    def format_comment_statement(self, expr) -> Tuple[str, tuple]:
        """Format COMMENT ON <object> IS 'text' (or IS NULL to remove)."""
        self._check_comment_version("COMMENT ON")

        object_type = expr.object_type.value
        name = self.format_comment_object_name(expr)
        if expr.comment is None:
            return f"COMMENT ON {object_type} {name} IS NULL", ()
        return (
            f"COMMENT ON {object_type} {name} IS {self._quote_literal(expr.comment)}",
            (),
        )

    def format_comment_object_name(self, expr) -> str:
        """Quote a comment target; dotted names (COLUMN relation.field,
        PARAMETER routine.param) are quoted per part."""
        if expr.object_type in (
            FirebirdCommentObjectType.COLUMN,
            FirebirdCommentObjectType.PARAMETER,
        ):
            parts = expr.object_name.split(".")
            return ".".join(self.format_identifier(part) for part in parts)
        return self.format_identifier(expr.object_name)

    def _quote_literal(self, value: str) -> str:
        """Inline a string literal with Firebird single-quote escaping."""
        return f"'{value.replace(chr(39), chr(39) * 2)}'"

    def _check_comment_version(self, feature: str) -> None:
        version = getattr(self, 'version', (2, 5, 0))
        if _norm_version(version) < (2, 5, 0):
            raise UnsupportedFeatureError(
                self.name,
                feature,
                "Firebird 2.5 or later is required for COMMENT ON statements.",
            )
