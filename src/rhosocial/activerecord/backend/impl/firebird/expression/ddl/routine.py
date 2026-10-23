# src/rhosocial/activerecord/backend/impl/firebird/expression/ddl/routine.py
"""Firebird PSQL PROCEDURE / FUNCTION statement expressions.

Firebird stored routines are written in PSQL (BEGIN ... END blocks).
Procedures exist since Firebird 1.0 and are gated at ``(2, 5, 0)``; stored
functions were introduced in Firebird 3.0.  Each expression delegates SQL
generation to the dialect's ``format_*_routine_statement`` methods,
following the Expression-Dialect separation pattern.
"""

from enum import Enum
from typing import TYPE_CHECKING, Any, List, Optional, Union

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class FirebirdRoutineMode(str, Enum):
    #: A member *is* the word it carries: ``__str__ = str.__str__`` keeps the
    #: artifact's spelling the bare word, because the Enum ``__str__`` that
    #: would otherwise win writes ``ClassName.MEMBER`` (§11.3).
    __str__ = str.__str__

    """Firebird routine DDL variant."""

    CREATE = "CREATE"
    CREATE_OR_ALTER = "CREATE OR ALTER"
    RECREATE = "RECREATE"
    DROP = "DROP"


def _normalize_routine_mode(mode: FirebirdRoutineMode) -> FirebirdRoutineMode:
    """The mode as the enum member, whatever spelling arrived.

    The artifact carries the plain word (a string enum *is* a JSON string), so
    the constructor accepts the word back and normalizes it.  Anything else is
    refused here, by name, rather than at render time.
    """
    if isinstance(mode, FirebirdRoutineMode):
        return mode
    if isinstance(mode, str):
        try:
            return FirebirdRoutineMode(mode)
        except ValueError as exc:
            raise ValueError(f"unsupported routine DDL mode: {mode!r}") from exc
    raise TypeError(
        f"mode must be a FirebirdRoutineMode (or its word), "
        f"got {type(mode).__name__}"
    )


RoutineParam = Union[tuple, dict]


class FirebirdCreateProcedureStatement(BaseExpression):
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
        self.mode: FirebirdRoutineMode = _normalize_routine_mode(mode)

    @property
    def format_method(self) -> str:
        return "format_create_procedure_statement"


class FirebirdCreateFunctionStatement(BaseExpression):
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
        self.mode: FirebirdRoutineMode = _normalize_routine_mode(mode)

    @property
    def format_method(self) -> str:
        return "format_create_function_statement"


class FirebirdDropRoutineStatement(BaseExpression):
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
        self.mode: FirebirdRoutineMode = _normalize_routine_mode(mode)
        self.params: List[RoutineParam] = params or []
        self.returns: Any = returns
        self.body: str = body

    @property
    def format_method(self) -> str:
        return "format_drop_routine_statement"


__all__ = [
    "FirebirdRoutineMode",
    "FirebirdCreateProcedureStatement",
    "FirebirdCreateFunctionStatement",
    "FirebirdDropRoutineStatement",
]
