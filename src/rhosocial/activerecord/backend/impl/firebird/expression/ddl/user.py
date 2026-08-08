# src/rhosocial/activerecord/backend/impl/firebird/expression/ddl/user.py
"""Firebird USER management statement expressions.

SQL user management (``CREATE USER`` / ``ALTER USER`` / ``DROP USER``) was
introduced in Firebird 3.0, replacing the older isql ``CREATE USER`` command.
Each expression delegates SQL generation to the dialect's
``format_*_user_statement`` methods, following the Expression-Dialect
separation pattern.
"""

from typing import TYPE_CHECKING, Optional, Tuple

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class FirebirdCreateUserExpression(BaseExpression):
    """CREATE USER name PASSWORD '...' [FIRSTNAME ...] [MIDDLENAME ...]
    [LASTNAME ...] [GRANT ADMIN ROLE]."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        username: str,
        password: str,
        first_name: Optional[str] = None,
        middle_name: Optional[str] = None,
        last_name: Optional[str] = None,
        grant_admin_role: bool = False,
    ):
        super().__init__(dialect)
        self.username: str = username
        self.password: str = password
        self.first_name: Optional[str] = first_name
        self.middle_name: Optional[str] = middle_name
        self.last_name: Optional[str] = last_name
        self.grant_admin_role: bool = grant_admin_role

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_create_user_statement(self)


class FirebirdAlterUserExpression(BaseExpression):
    """ALTER USER name [PASSWORD ...] [FIRSTNAME ...] [MIDDLENAME ...]
    [LASTNAME ...] [GRANT ADMIN ROLE] [REVOKE ADMIN ROLE]."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        username: str,
        password: Optional[str] = None,
        first_name: Optional[str] = None,
        middle_name: Optional[str] = None,
        last_name: Optional[str] = None,
        grant_admin_role: bool = False,
        revoke_admin_role: bool = False,
    ):
        super().__init__(dialect)
        self.username: str = username
        self.password: Optional[str] = password
        self.first_name: Optional[str] = first_name
        self.middle_name: Optional[str] = middle_name
        self.last_name: Optional[str] = last_name
        self.grant_admin_role: bool = grant_admin_role
        self.revoke_admin_role: bool = revoke_admin_role

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_alter_user_statement(self)


class FirebirdDropUserExpression(BaseExpression):
    """DROP USER name."""

    def __init__(self, dialect: "SQLDialectBase", username: str):
        super().__init__(dialect)
        self.username: str = username

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_drop_user_statement(self)


__all__ = [
    "FirebirdCreateUserExpression",
    "FirebirdAlterUserExpression",
    "FirebirdDropUserExpression",
]
