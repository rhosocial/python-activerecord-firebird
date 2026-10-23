# src/rhosocial/activerecord/backend/impl/firebird/mixins/blob.py
"""Firebird BLOB handling mixin."""

from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ..expression.blob import BlobColumnExpression, BlobLiteralExpression


class FirebirdBlobMixin:

    def format_blob_column_expression(self, expr: "BlobColumnExpression") -> Tuple[str, tuple]:
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

    def supports_blob_sub_type(self, sub_type: int) -> bool:
        return sub_type in (0, 1, 2, 3, 4, 5)

    def format_blob_literal_expression(self, expr: "BlobLiteralExpression") -> Tuple[str, tuple]:
        escaped = expr.value.hex()
        return f"X'{escaped}'", ()
