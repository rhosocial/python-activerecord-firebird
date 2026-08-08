# src/rhosocial/activerecord/backend/impl/firebird/expression/ddl/external_function.py
"""Firebird EXTERNAL FUNCTION (UDF) declaration expressions.

External functions (UDFs) are declared with ``DECLARE EXTERNAL FUNCTION``.
The feature is ancient (available since Firebird 1.0) and gated here at
``(2, 5, 0)``; Firebird 4.0 deprecates UDFs in favour of UDRs
(``CREATE FUNCTION ... EXTERNAL``).  Each expression delegates SQL generation
to the dialect's ``format_*_external_function_statement`` methods, following
the Expression-Dialect separation pattern.
"""

from typing import TYPE_CHECKING, List, Optional, Tuple

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class FirebirdCreateExternalFunctionExpression(BaseExpression):
    """DECLARE EXTERNAL FUNCTION name [(params)] RETURNS type [BY VALUE]
    [FREE_IT] ENTRY_POINT 'entry' MODULE_NAME 'module'."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        function_name: str,
        params: Optional[List[str]] = None,
        returns: str = "INT",
        by_value: bool = False,
        entry_point: str = "",
        module_name: str = "",
        free_it: bool = False,
    ):
        super().__init__(dialect)
        self.function_name: str = function_name
        self.params: List[str] = params or []
        self.returns: str = returns
        self.by_value: bool = by_value
        self.entry_point: str = entry_point
        self.module_name: str = module_name
        self.free_it: bool = free_it

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_create_external_function_statement(self)


class FirebirdAlterExternalFunctionExpression(BaseExpression):
    """ALTER EXTERNAL FUNCTION name [ENTRY_POINT 'entry'] [MODULE_NAME 'module']."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        function_name: str,
        entry_point: Optional[str] = None,
        module_name: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.function_name: str = function_name
        self.entry_point: Optional[str] = entry_point
        self.module_name: Optional[str] = module_name

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_alter_external_function_statement(self)


class FirebirdDropExternalFunctionExpression(BaseExpression):
    """DROP EXTERNAL FUNCTION name."""

    def __init__(self, dialect: "SQLDialectBase", function_name: str):
        super().__init__(dialect)
        self.function_name: str = function_name

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_drop_external_function_statement(self)


__all__ = [
    "FirebirdCreateExternalFunctionExpression",
    "FirebirdAlterExternalFunctionExpression",
    "FirebirdDropExternalFunctionExpression",
]
