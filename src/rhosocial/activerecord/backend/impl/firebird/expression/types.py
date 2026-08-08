# src/rhosocial/activerecord/backend/impl/firebird/expression/types.py
"""Firebird-specific DDL DataType subclasses."""

from typing import Optional, Tuple

from rhosocial.activerecord.backend.expression.types import (
    DataType,
    DecimalType,
    FloatType,
    IntegerType,
    TimeTzType,
    TimestampTzType,
)


class FirebirdDecimalType(DecimalType):
    """Firebird DECIMAL type."""
    pass


class FirebirdFloatType(FloatType):
    """Firebird FLOAT type."""
    pass


class FirebirdDoubleType(FloatType):
    """Firebird DOUBLE PRECISION type."""
    pass


class FirebirdBlobSubType(IntegerType):
    """Firebird BLOB SUB_TYPE type."""
    pass


class FirebirdTimeStampTzType(TimestampTzType):
    """Firebird TIMESTAMP WITH TIME ZONE type (Firebird 4.0+)."""
    pass


class FirebirdTimeTzType(TimeTzType):
    """Firebird TIME WITH TIME ZONE type (Firebird 4.0+)."""
    pass


class FirebirdDecFloatType(DataType):
    """Firebird DECFLOAT(16|34) type (Firebird 4.0+).

    Firebird 4.0 introduced the decimal floating-point type with a
    precision of either 16 or 34 decimal digits.
    """

    def __init__(self, precision: int = 16, dialect: Optional[object] = None):
        super().__init__(dialect)
        if precision not in (16, 34):
            raise ValueError(f"DECFLOAT precision must be 16 or 34, got {precision}")
        self.precision: int = precision

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return self.precision == other.precision

    def __hash__(self) -> int:
        return hash((type(self), self.precision))

    def _type_params(self) -> Tuple[int]:
        return (self.precision,)


class FirebirdInt128Type(DataType):
    """Firebird INT128 type (Firebird 4.0+).

    Firebird 4.0 introduced the INT128 fixed-point integer type holding
    values from -2**127 to 2**127 - 1.
    """
    pass


__all__ = [
    "FirebirdDecimalType",
    "FirebirdFloatType",
    "FirebirdDoubleType",
    "FirebirdBlobSubType",
    "FirebirdTimeStampTzType",
    "FirebirdTimeTzType",
    "FirebirdDecFloatType",
    "FirebirdInt128Type",
]
