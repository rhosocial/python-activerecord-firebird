# src/rhosocial/activerecord/backend/impl/firebird/expression/blob.py
"""Firebird BLOB column and literal expressions.

``BlobColumnExpression`` generates a ``BLOB SUB_TYPE …`` column definition
suitable for DDL.  ``BlobLiteralExpression`` renders an inline hex literal
for DML (``X'…'``).
"""

from typing import TYPE_CHECKING, Optional

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class BlobColumnExpression(BaseExpression):
    """Expression for ``BLOB SUB_TYPE n [SEGMENT SIZE n] [CHARACTER SET …]``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        column_name: str,
        sub_type: int = 0,
        segment_size: int = 65536,
        character_set: Optional[str] = None,
    ):
        super().__init__(dialect)
        # Each constructor argument is stored under its own name: the
        # artifact contract reads a parameter by the name it was declared
        # with, so a private spelling would make the node unwritable and
        # unreadable in the same breath.
        self.column_name = column_name
        self.sub_type = sub_type
        self.segment_size = segment_size
        self.character_set = character_set

    @property
    def format_method(self) -> str:
        return "format_blob_column"


class BlobLiteralExpression(BaseExpression):
    """Expression for ``X'…'`` hex-literal BLOB value."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        value: bytes,
        sub_type: int = 0,
    ):
        super().__init__(dialect)
        self.value = value
        self.sub_type = sub_type

    @property
    def format_method(self) -> str:
        return "format_blob_literal"


__all__ = ["BlobColumnExpression", "BlobLiteralExpression"]
