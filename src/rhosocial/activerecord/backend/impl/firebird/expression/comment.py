# src/rhosocial/activerecord/backend/impl/firebird/expression/comment.py
"""Firebird COMMENT ON expression.

``COMMENT ON`` annotates metadata objects and is available since Firebird 2.5
(gated here at ``(2, 5, 0)``).  Firebird has no inline column comments, so
documentation must be attached via ``COMMENT ON ... IS 'text'``.  The
expression delegates SQL generation to the dialect's
``format_comment_statement`` method, following the Expression-Dialect
separation pattern.
"""

from enum import Enum
from typing import TYPE_CHECKING, Optional, Tuple

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class FirebirdCommentObjectType(Enum):
    """Object types accepted by COMMENT ON."""

    DATABASE = "DATABASE"
    TABLE = "TABLE"
    COLUMN = "COLUMN"
    VIEW = "VIEW"
    PROCEDURE = "PROCEDURE"
    FUNCTION = "FUNCTION"
    EXTERNAL_FUNCTION = "EXTERNAL FUNCTION"
    DOMAIN = "DOMAIN"
    EXCEPTION = "EXCEPTION"
    TRIGGER = "TRIGGER"
    GENERATOR = "GENERATOR"
    SEQUENCE = "SEQUENCE"
    PACKAGE = "PACKAGE"
    ROLE = "ROLE"
    INDEX = "INDEX"
    FILTER = "FILTER"
    CHARACTER_SET = "CHARACTER SET"
    COLLATION = "COLLATION"
    PARAMETER = "PARAMETER"
    USER = "USER"
    GLOBAL_MAPPING = "GLOBAL MAPPING"


class FirebirdCommentExpression(BaseExpression):
    """COMMENT ON <object> IS 'text' (or IS NULL to remove the comment)."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        object_type: FirebirdCommentObjectType,
        object_name: str,
        comment: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.object_type: FirebirdCommentObjectType = object_type
        self.object_name: str = object_name
        self.comment: Optional[str] = comment

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_comment_statement(self)


__all__ = ["FirebirdCommentObjectType", "FirebirdCommentExpression"]
