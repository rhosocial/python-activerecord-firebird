# src/rhosocial/activerecord/backend/impl/firebird/mixins/blob.py
"""Firebird BLOB handling mixin."""

from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ..expression.blob import FirebirdBlobColumnExpression, FirebirdBlobLiteralExpression


class FirebirdBlobMixin:

    def format_blob_column_expression(self, expr: "FirebirdBlobColumnExpression") -> Tuple[str, tuple]:
        column_name = expr.column_name
        sub_type = expr.sub_type
        segment_size = expr.segment_size
        character_set = expr.character_set

        parts = [f"{self.format_identifier(column_name)} BLOB SUB_TYPE {sub_type}"]
        if sub_type == 1 and character_set:
            parts.append(f"CHARACTER SET {character_set}")
        parts.append(f"SEGMENT SIZE {segment_size}")
        return ' '.join(parts), ()

    def supports_blob(self) -> bool:
        return True

    # Firebird addresses a BLOB by sub-type number: 0 is binary and 1 is text.
    # Those are the two kinds the closed switch vocabulary names; this backend
    # has always accepted 0 through 5, so both named kinds answer True.
    def supports_blob_sub_type_binary(self) -> bool:
        """Whether ``BLOB SUB_TYPE 0`` (binary) is supported."""
        return True

    def supports_blob_sub_type_text(self) -> bool:
        """Whether ``BLOB SUB_TYPE 1`` (text) is supported."""
        return True

    def format_blob_literal_expression(self, expr: "FirebirdBlobLiteralExpression") -> Tuple[str, tuple]:
        escaped = expr.value.hex()
        return f"X'{escaped}'", ()
