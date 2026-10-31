# src/rhosocial/activerecord/backend/impl/firebird/expression/ddl/role.py
"""Firebird ROLE statement expressions.

Roles group privileges for convenient grant management.  ``CREATE ROLE`` and
``DROP ROLE`` exist since early Firebird and are gated here at ``(2, 5, 0)``;
``ALTER ROLE`` (SET/DROP SYSTEM PRIVILEGES, SET/DROP AUTO ADMIN MAPPING) was
added in Firebird 3.0.  Each expression delegates SQL generation to the
dialect's ``format_*_role_statement`` methods, following the Expression-Dialect
separation pattern.
"""

from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class FirebirdRoleAlterClause(str, Enum):
    #: A member *is* the word it carries: ``__str__ = str.__str__`` keeps the
    #: artifact's spelling the bare word, because the Enum ``__str__`` that
    #: would otherwise win writes ``ClassName.MEMBER`` (§11.3).
    __str__ = str.__str__

    """ALTER ROLE clause selector (Firebird 3.0+).

    Per the Firebird 5.0 Language Reference, ``ALTER ROLE`` supports only:
    ``SET SYSTEM PRIVILEGES TO <list>``, ``DROP SYSTEM PRIVILEGES`` and
    ``{SET | DROP} AUTO ADMIN MAPPING``.
    """

    SET_SYSTEM_PRIVILEGES = "SET SYSTEM PRIVILEGES TO"
    DROP_SYSTEM_PRIVILEGES = "DROP SYSTEM PRIVILEGES"
    SET_AUTO_ADMIN_MAPPING = "SET AUTO ADMIN MAPPING"
    DROP_AUTO_ADMIN_MAPPING = "DROP AUTO ADMIN MAPPING"


def _normalize_role_clause(clause: FirebirdRoleAlterClause) -> FirebirdRoleAlterClause:
    """The clause as the enum member, whatever spelling arrived.

    The artifact carries the plain word (a string enum *is* a JSON string), so
    the constructor accepts the word back and normalizes it.  Anything else is
    refused here, by name, rather than at render time.
    """
    if isinstance(clause, FirebirdRoleAlterClause):
        return clause
    if isinstance(clause, str):
        try:
            return FirebirdRoleAlterClause(clause)
        except ValueError as exc:
            raise ValueError(f"unsupported ALTER ROLE clause: {clause!r}") from exc
    raise TypeError(
        f"clause must be a FirebirdRoleAlterClause (or its word), "
        f"got {type(clause).__name__}"
    )


class FirebirdCreateRoleStatement(BaseExpression):
    """CREATE ROLE name."""

    def __init__(self, dialect: "SQLDialectBase", role_name: str):
        super().__init__(dialect)
        self.role_name: str = role_name

    @property
    def format_method(self) -> str:
        return "format_create_role_statement"


class FirebirdAlterRoleStatement(BaseExpression):
    """ALTER ROLE name {SET SYSTEM PRIVILEGES TO ... | DROP SYSTEM
    PRIVILEGES | SET/DROP AUTO ADMIN MAPPING} (Firebird 3.0+)."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        role_name: str,
        clause: FirebirdRoleAlterClause = FirebirdRoleAlterClause.SET_AUTO_ADMIN_MAPPING,
        system_privileges: Optional[List[str]] = None,
    ):
        super().__init__(dialect)
        self.role_name: str = role_name
        self.clause: FirebirdRoleAlterClause = _normalize_role_clause(clause)
        self.system_privileges: Optional[List[str]] = system_privileges

    @property
    def format_method(self) -> str:
        return "format_alter_role_statement"


class FirebirdDropRoleStatement(BaseExpression):
    """DROP ROLE name."""

    def __init__(self, dialect: "SQLDialectBase", role_name: str):
        super().__init__(dialect)
        self.role_name: str = role_name

    @property
    def format_method(self) -> str:
        return "format_drop_role_statement"


__all__ = [
    "FirebirdRoleAlterClause",
    "FirebirdCreateRoleStatement",
    "FirebirdAlterRoleStatement",
    "FirebirdDropRoleStatement",
]
