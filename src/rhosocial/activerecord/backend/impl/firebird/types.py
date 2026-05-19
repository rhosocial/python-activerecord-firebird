# src/rhosocial/activerecord/backend/impl/firebird/types.py
"""Firebird-specific type definitions and helpers."""

from typing import Optional


class FirebirdBlobType:
    """Firebird BLOB type helper.

    Firebird BLOB types:
    - SUB_TYPE 0: BINARY (unstructured binary)
    - SUB_TYPE 1: TEXT (text with character set)
    - SUB_TYPE 2: BLR (binary language representation)
    - SUB_TYPE 3: ACL (access control list)
    - SUB_TYPE 4: RANGES (delta ranges)
    - SUB_TYPE 5: FORMATTED_TEXT (formatted text)

    Example usage:
        blob_text = FirebirdBlobType(sub_type=1, segment_size=16384, character_set='UTF8')
    """

    def __init__(self, sub_type: int = 0, segment_size: int = 65536,
                 character_set: Optional[str] = None, collation: Optional[str] = None):
        self.sub_type = sub_type
        self.segment_size = segment_size
        self.character_set = character_set
        self.collation = collation

    def to_sql(self) -> str:
        """Generate SQL type definition string."""
        parts = [f"BLOB SUB_TYPE {self.sub_type}"]
        parts.append(f"SEGMENT SIZE {self.segment_size}")
        if self.character_set:
            parts.append(f"CHARACTER SET {self.character_set}")
        if self.collation:
            parts.append(f"COLLATE {self.collation}")
        return ' '.join(parts)

    def __repr__(self) -> str:
        return f"FirebirdBlobType(sub_type={self.sub_type})"


class FirebirdArrayType:
    """Firebird array type helper.

    Firebird supports multi-dimensional arrays of scalar types.

    Example:
        arr = FirebirdArrayType(base_type='INTEGER', dimensions=[5])
        arr = FirebirdArrayType('VARCHAR(30)', dimensions=[3, 4])
    """

    def __init__(self, base_type: str, dimensions: list):
        self.base_type = base_type
        self.dimensions = dimensions

    def to_sql(self) -> str:
        dim_strs = []
        for dim in self.dimensions:
            if isinstance(dim, tuple):
                dim_strs.append(f"{dim[0]}:{dim[1]}")
            else:
                dim_strs.append(str(dim))
        return f"{self.base_type}[{' AND '.join(dim_strs)}]"

    def __repr__(self) -> str:
        return f"FirebirdArrayType(base={self.base_type}, dims={self.dimensions})"


class FirebirdDomainType:
    """Firebird DOMAIN type helper for CREATE DOMAIN statements.

    Example:
        domain = FirebirdDomainType('VARCHAR(100)', not_null=True, default="''")
    """

    def __init__(self, base_type: str, not_null: bool = False,
                 default: Optional[str] = None, check: Optional[str] = None,
                 collation: Optional[str] = None, character_set: Optional[str] = None):
        self.base_type = base_type
        self.not_null = not_null
        self.default = default
        self.check = check
        self.collation = collation
        self.character_set = character_set

    def to_sql(self) -> str:
        parts = [self.base_type]
        if self.character_set:
            parts.append(f"CHARACTER SET {self.character_set}")
        if self.collation:
            parts.append(f"COLLATE {self.collation}")
        if self.default is not None:
            parts.append(f"DEFAULT {self.default}")
        if self.not_null:
            parts.append("NOT NULL")
        if self.check:
            parts.append(f"CHECK ({self.check})")
        return ' '.join(parts)


__all__ = [
    "FirebirdBlobType",
    "FirebirdArrayType",
    "FirebirdDomainType",
]