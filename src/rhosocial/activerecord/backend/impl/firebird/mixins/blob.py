# src/rhosocial/activerecord/backend/impl/firebird/mixins/blob.py
"""Firebird BLOB handling mixin."""

from typing import Optional, Tuple


class FirebirdBlobMixin:

    def format_blob_column(
        self,
        column_name: str,
        sub_type: int = 0,
        segment_size: int = 65536,
        character_set: Optional[str] = None,
    ) -> str:
        parts = [f"{self.format_identifier(column_name)} BLOB SUB_TYPE {sub_type}"]
        if sub_type == 1 and character_set:
            parts.append(f"CHARACTER SET {character_set}")
        parts.append(f"SEGMENT SIZE {segment_size}")
        return ' '.join(parts)

    def supports_blob(self) -> bool:
        return True

    def supports_blob_sub_type(self, sub_type: int) -> bool:
        return sub_type in (0, 1, 2, 3, 4, 5)

    def format_blob_literal(self, value: bytes, sub_type: int = 0) -> Tuple[str, tuple]:
        escaped = value.hex()
        return f"X'{escaped}'", ()