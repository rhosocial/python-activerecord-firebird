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
    name = "firebird_decimal"


class FirebirdFloatType(FloatType):
    """Firebird FLOAT type."""
    name = "firebird_float"


class FirebirdDoubleType(FloatType):
    """Firebird DOUBLE PRECISION type."""
    name = "firebird_double"


class FirebirdBlobSubType(IntegerType):
    """Firebird BLOB SUB_TYPE type."""
    name = "firebird_blob_subtype"


class FirebirdTimeStampTzType(TimestampTzType):
    """Firebird TIMESTAMP WITH TIME ZONE type (Firebird 4.0+)."""
    name = "firebird_timestamptz"


class FirebirdTimeTzType(TimeTzType):
    """Firebird TIME WITH TIME ZONE type (Firebird 4.0+)."""
    name = "firebird_timetz"


class FirebirdDecFloatType(DataType):
    """Firebird DECFLOAT(16|34) type (Firebird 4.0+).

    Firebird 4.0 introduced the decimal floating-point type with a
    precision of either 16 or 34 decimal digits.
    """

    name = "firebird_decfloat"

    def __init__(self, dialect=None, precision: int = 16,
                 dialect_options=None):
        super().__init__(dialect, dialect_options=dialect_options)
        if precision not in (16, 34):
            raise ValueError(f"DECFLOAT precision must be 16 or 34, got {precision}")
        self.precision: int = precision

    def _type_params(self) -> Tuple[int]:
        return (self.precision,)


class FirebirdInt128Type(DataType):
    """Firebird INT128 type (Firebird 4.0+).

    Firebird 4.0 introduced the INT128 fixed-point integer type holding
    values from -2**127 to 2**127 - 1.
    """

    name = "firebird_int128"


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
