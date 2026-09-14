# src/rhosocial/activerecord/backend/impl/firebird/mixins/blob.py
"""Firebird BLOB handling mixin."""

from typing import Optional, Tuple


class FirebirdBlobMixin:

    def format_blob_column(
        self,
        expr_or_column_name,
        sub_type: int = 0,
        segment_size: int = 65536,
        character_set: Optional[str] = None,
    ) -> Tuple[str, tuple]:
        from rhosocial.activerecord.backend.impl.firebird.expression.blob import (
            BlobColumnExpression,
        )

        if isinstance(expr_or_column_name, BlobColumnExpression):
            expr = expr_or_column_name
            column_name = expr._column_name
            sub_type = expr._sub_type
            segment_size = expr._segment_size
            character_set = expr._character_set
        else:
            column_name = expr_or_column_name

        parts = [f"{self.format_identifier(column_name)} BLOB SUB_TYPE {sub_type}"]
        if sub_type == 1 and character_set:
            parts.append(f"CHARACTER SET {character_set}")
        parts.append(f"SEGMENT SIZE {segment_size}")
        return ' '.join(parts), ()

    def supports_blob(self) -> bool:
        return True

    def supports_blob_sub_type(self, sub_type: int) -> bool:
        return sub_type in (0, 1, 2, 3, 4, 5)

    def format_blob_literal(self, value_or_expr, sub_type: int = 0) -> Tuple[str, tuple]:
        from rhosocial.activerecord.backend.impl.firebird.expression.blob import (
            BlobLiteralExpression,
        )

        if isinstance(value_or_expr, BlobLiteralExpression):
            expr = value_or_expr
            value = expr._value
        else:
            value = value_or_expr

        escaped = value.hex()
        return f"X'{escaped}'", ()