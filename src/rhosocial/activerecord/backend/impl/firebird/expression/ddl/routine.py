# src/rhosocial/activerecord/backend/impl/firebird/expression/ddl/routine.py
"""Firebird PSQL PROCEDURE / FUNCTION statement expressions.

Firebird stored routines are written in PSQL (BEGIN ... END blocks).
Procedures exist since Firebird 1.0 and are gated at ``(2, 5, 0)``; stored
functions were introduced in Firebird 3.0.  Each expression delegates SQL
generation to the dialect's ``format_*_routine_statement`` methods,
following the Expression-Dialect separation pattern.
"""

from enum import Enum
from typing import TYPE_CHECKING, Any, List, Optional, Tuple, Union

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class FirebirdRoutineMode(Enum):
    """Firebird routine DDL variant."""

    CREATE = "CREATE"
    CREATE_OR_ALTER = "CREATE OR ALTER"
    RECREATE = "RECREATE"
    DROP = "DROP"


RoutineParam = Union[Tuple[str, str], dict]


class FirebirdCreateProcedureExpression(BaseExpression):
    """CREATE [OR ALTER | RECREATE] PROCEDURE name (params) RETURNS (...) AS <body>."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        procedure_name: str,
        params: Optional[List[RoutineParam]] = None,
        returns: Optional[List[RoutineParam]] = None,
        body: str = "",
        mode: FirebirdRoutineMode = FirebirdRoutineMode.CREATE,
    ):
        super().__init__(dialect)
        self.procedure_name: str = procedure_name
        self.params: List[RoutineParam] = params or []
        self.returns: List[RoutineParam] = returns or []
        self.body: str = body
        self.mode: FirebirdRoutineMode = mode

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_create_procedure_statement(self)


class FirebirdCreateFunctionExpression(BaseExpression):
    """CREATE [OR ALTER | RECREATE] FUNCTION name (params) RETURNS type AS <body>.

    Stored functions require Firebird 3.0 or later.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        function_name: str,
        params: Optional[List[RoutineParam]] = None,
        returns: Any = None,
        body: str = "",
        mode: FirebirdRoutineMode = FirebirdRoutineMode.CREATE,
    ):
        super().__init__(dialect)
        self.function_name: str = function_name
        self.params: List[RoutineParam] = params or []
        self.returns: Any = returns
        self.body: str = body
        self.mode: FirebirdRoutineMode = mode

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_create_function_statement(self)


class FirebirdDropRoutineExpression(BaseExpression):
    """DROP / CREATE OR ALTER / RECREATE for a PROCEDURE or FUNCTION.

    ``routine_type`` selects the object kind and ``mode`` the DDL variant.
    For the ``DROP`` mode only the routine name is required; the other
    modes reuse the CREATE header fields.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        routine_name: str,
        routine_type: str = "PROCEDURE",
        mode: FirebirdRoutineMode = FirebirdRoutineMode.DROP,
        params: Optional[List[RoutineParam]] = None,
        returns: Any = None,
        body: str = "",
    ):
        super().__init__(dialect)
        self.routine_name: str = routine_name
        self.routine_type: str = routine_type.upper()
        self.mode: FirebirdRoutineMode = mode
        self.params: List[RoutineParam] = params or []
        self.returns: Any = returns
        self.body: str = body

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_drop_routine_statement(self)


__all__ = [
    "FirebirdRoutineMode",
    "FirebirdCreateProcedureExpression",
    "FirebirdCreateFunctionExpression",
    "FirebirdDropRoutineExpression",
]
