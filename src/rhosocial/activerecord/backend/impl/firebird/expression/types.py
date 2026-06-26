# src/rhosocial/activerecord/backend/impl/firebird/expression/types.py
"""Firebird-specific DDL DataType subclasses."""

from rhosocial.activerecord.backend.expression.types import DecimalType, FloatType, IntegerType


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


__all__ = [
    "FirebirdDecimalType",
    "FirebirdFloatType",
    "FirebirdDoubleType",
    "FirebirdBlobSubType",
]