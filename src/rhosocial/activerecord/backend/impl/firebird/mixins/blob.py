# src/rhosocial/activerecord/backend/impl/firebird/mixins/blob.py
"""Firebird BLOB handling mixin."""

from typing import Tuple


class FirebirdBlobMixin:

    def format_blob_column(self, expr) -> Tuple[str, tuple]:
        column_name = expr._column_name
        sub_type = expr._sub_type
        segment_size = expr._segment_size
        character_set = expr._character_set

        parts = [f"{self.format_identifier(column_name)} BLOB SUB_TYPE {sub_type}"]
        if sub_type == 1 and character_set:
            parts.append(f"CHARACTER SET {character_set}")
        parts.append(f"SEGMENT SIZE {segment_size}")
        return ' '.join(parts), ()

    def supports_blob(self) -> bool:
        return True

    def supports_blob_sub_type(self, sub_type: int) -> bool:
        return sub_type in (0, 1, 2, 3, 4, 5)

    def format_blob_literal(self, expr) -> Tuple[str, tuple]:
        escaped = expr._value.hex()
        return f"X'{escaped}'", ()
