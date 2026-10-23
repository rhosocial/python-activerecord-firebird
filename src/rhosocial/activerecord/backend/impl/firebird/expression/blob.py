# src/rhosocial/activerecord/backend/impl/firebird/expression/blob.py
"""Firebird BLOB column and literal expressions.

``BlobColumnExpression`` generates a ``BLOB SUB_TYPE …`` column definition
suitable for DDL.  ``BlobLiteralExpression`` renders an inline hex literal
for DML (``X'…'``).
"""

import base64
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
        return "format_blob_column_expression"


class BlobLiteralExpression(BaseExpression):
    """Expression for ``X'…'`` hex-literal BLOB value."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        value: bytes,
        sub_type: int = 0,
    ):
        super().__init__(dialect)
        # The artifact writes bytes as base64 text -- the binary_value
        # spelling -- so the constructor accepts that spelling back and
        # normalizes it: wide at the entry, one host type in storage.  A str
        # that is not valid base64 fails here, by name, instead of at render
        # time inside the formatter.
        if isinstance(value, str):
            # binascii.Error is a ValueError, so one except covers both.
            try:
                value = base64.b64decode(value, validate=True)
            except ValueError as exc:
                raise ValueError(
                    f"blob value arrives as base64 text in an artifact; "
                    f"{value[:8]!r}... is not decodable base64"
                ) from exc
        elif isinstance(value, (bytearray, memoryview)):
            value = bytes(value)
        if not isinstance(value, bytes):
            raise TypeError(
                f"blob value must be bytes (or the base64 spelling an "
                f"artifact carries), got {type(value).__name__}"
            )
        self.value = value
        self.sub_type = sub_type

    @property
    def format_method(self) -> str:
        return "format_blob_literal_expression"


__all__ = ["BlobColumnExpression", "BlobLiteralExpression"]
