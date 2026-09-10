# src/rhosocial/activerecord/backend/impl/firebird/expression/generator.py
"""Firebird GENERATOR/SEQUENCE expressions."""

from typing import TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class GenIdExpression(BaseExpression):
    """Expression for GEN_ID(generator_name, step)."""

    def __init__(self, dialect: "SQLDialectBase", generator_name: str, step: int = 1):
        super().__init__(dialect)
        self._generator_name = generator_name
        self._step = step

    @property
    def format_method(self) -> str:
        return "format_gen_id"

    def __repr__(self) -> str:
        return f"GenIdExpression({self._generator_name}, step={self._step})"


class NextValueForExpression(BaseExpression):
    """Expression for NEXT VALUE FOR sequence_name."""

    def __init__(self, dialect: "SQLDialectBase", sequence_name: str):
        super().__init__(dialect)
        self._sequence_name = sequence_name

    @property
    def format_method(self) -> str:
        return "format_next_value_for"

    def __repr__(self) -> str:
        return f"NextValueForExpression({self._sequence_name})"


__all__ = ["GenIdExpression", "NextValueForExpression"]
