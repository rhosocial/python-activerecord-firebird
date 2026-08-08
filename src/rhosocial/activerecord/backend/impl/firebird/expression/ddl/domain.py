# src/rhosocial/activerecord/backend/impl/firebird/expression/ddl/domain.py
"""Firebird DOMAIN statement expressions.

DOMAIN is a reusable column type (data type + DEFAULT + NOT NULL + CHECK
constraint) available since Firebird 2.5.  Each expression delegates SQL
generation to the dialect's ``format_*_domain_statement`` method, following
the Expression-Dialect separation pattern.
"""

from enum import Enum
from typing import TYPE_CHECKING, Any, Optional, Tuple

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase
    from rhosocial.activerecord.backend.expression.types import DataType


class FirebirdDomainAlterMode(Enum):
    """ALTER DOMAIN clause selector."""

    SET_DEFAULT = "SET DEFAULT"
    DROP_DEFAULT = "DROP DEFAULT"
    SET_NOT_NULL = "SET NOT NULL"
    DROP_NOT_NULL = "DROP NOT NULL"
    ADD_CONSTRAINT = "ADD CONSTRAINT"
    DROP_CONSTRAINT = "DROP CONSTRAINT"
    SET_TYPE = "TYPE"


class FirebirdCreateDomainExpression(BaseExpression):
    """CREATE DOMAIN name [AS] datatype [DEFAULT ...] [NOT NULL] [CHECK (...)]."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        domain_name: str,
        data_type: "DataType",
        default: Any = None,
        not_null: bool = False,
        check: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.domain_name: str = domain_name
        self.data_type: "DataType" = data_type
        self.default: Any = default
        self.not_null: bool = not_null
        self.check: Optional[str] = check

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_create_domain_statement(self)


class FirebirdAlterDomainExpression(BaseExpression):
    """ALTER DOMAIN name { SET DEFAULT | DROP DEFAULT | SET/DROP NOT NULL |
    ADD/DROP CONSTRAINT | TYPE }."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        domain_name: str,
        mode: FirebirdDomainAlterMode,
        value: Any = None,
        data_type: Optional["DataType"] = None,
        constraint_name: Optional[str] = None,
        constraint_sql: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.domain_name: str = domain_name
        self.mode: FirebirdDomainAlterMode = mode
        self.value: Any = value
        self.data_type: Optional["DataType"] = data_type
        self.constraint_name: Optional[str] = constraint_name
        self.constraint_sql: Optional[str] = constraint_sql

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_alter_domain_statement(self)


class FirebirdDropDomainExpression(BaseExpression):
    """DROP DOMAIN name."""

    def __init__(self, dialect: "SQLDialectBase", domain_name: str):
        super().__init__(dialect)
        self.domain_name: str = domain_name

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_drop_domain_statement(self)


__all__ = [
    "FirebirdDomainAlterMode",
    "FirebirdCreateDomainExpression",
    "FirebirdAlterDomainExpression",
    "FirebirdDropDomainExpression",
]
