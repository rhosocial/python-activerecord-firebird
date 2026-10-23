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
        # Stored under the declared parameter's own name: get_params() reads
        # a parameter from the attribute of that name, so a private spelling
        # would leave the node unreadable and unwritable in one breath.
        self.generator_name = generator_name
        self.step = step

    @property
    def format_method(self) -> str:
        return "format_gen_id_expression"

    def __repr__(self) -> str:
        return f"GenIdExpression({self.generator_name}, step={self.step})"


class NextValueForExpression(BaseExpression):
    """Expression for NEXT VALUE FOR sequence_name."""

    def __init__(self, dialect: "SQLDialectBase", sequence_name: str):
        super().__init__(dialect)
        self.sequence_name = sequence_name

    @property
    def format_method(self) -> str:
        return "format_next_value_for_expression"

    def __repr__(self) -> str:
        return f"NextValueForExpression({self.sequence_name})"


__all__ = ["GenIdExpression", "NextValueForExpression"]
