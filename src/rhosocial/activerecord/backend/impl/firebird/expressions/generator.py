# src/rhosocial/activerecord/backend/impl/firebird/expressions/generator.py
"""Firebird GENERATOR/SEQUENCE expressions."""

from typing import Any, Optional, Tuple

from rhosocial.activerecord.backend.expression.bases import BaseExpression


class GenIdExpression(BaseExpression):
    """Expression for GEN_ID(generator_name, step).

    Used to get the next value from a Firebird generator/sequence.
    """

    def __init__(self, generator_name: str, step: int = 1):
        super().__init__()
        self._generator_name = generator_name
        self._step = step

    def to_sql(self) -> Tuple[str, tuple]:
        escaped = self._generator_name.replace('"', '""')
        return f'GEN_ID("{escaped}", {self._step})', ()

    def __repr__(self) -> str:
        return f"GenIdExpression({self._generator_name}, step={self._step})"


class NextValueForExpression(BaseExpression):
    """Expression for NEXT VALUE FOR sequence_name.

    SQL standard sequence access (Firebird 3.0+).
    """

    def __init__(self, sequence_name: str):
        super().__init__()
        self._sequence_name = sequence_name

    def to_sql(self) -> Tuple[str, tuple]:
        escaped = self._sequence_name.replace('"', '""')
        return f'NEXT VALUE FOR "{escaped}"', ()

    def __repr__(self) -> str:
        return f"NextValueForExpression({self._sequence_name})"


__all__ = ["GenIdExpression", "NextValueForExpression"]