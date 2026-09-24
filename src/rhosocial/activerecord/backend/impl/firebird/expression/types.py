# src/rhosocial/activerecord/backend/impl/firebird/expression/types.py
"""Firebird-specific DDL DataType subclasses."""

import re
from typing import Tuple

from rhosocial.activerecord.backend.expression.serialization import ExpressionRegistry
from rhosocial.activerecord.backend.expression.types import (
    BigIntType,
    BinaryType,
    BooleanType,
    CharType,
    CustomType,
    DataType,
    DateType,
    DecimalType,
    DoubleType,
    FloatType,
    IntegerType,
    SmallIntType,
    TextType,
    TimeType,
    TimeTzType,
    TimestampType,
    TimestampTzType,
    VarBinaryType,
    VarCharType,
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


class FirebirdCharType(CharType):
    """Firebird CHAR type with an explicit UTF8 character set."""
    name = "firebird_char"


class FirebirdVarCharType(VarCharType):
    """Firebird VARCHAR type with an explicit UTF8 character set."""
    name = "firebird_varchar"


class FirebirdTimeStampTzType(TimestampTzType):
    """Firebird TIMESTAMP WITH TIME ZONE type (Firebird 4.0+)."""
    name = "firebird_timestamptz"


class FirebirdTimeTzType(TimeTzType):
    """Firebird TIME WITH TIME ZONE type (Firebird 4.0+)."""
    name = "firebird_timetz"


class FirebirdTimeWithoutTimeZoneType(TimeType):
    """Firebird TIME WITHOUT TIME ZONE type (Firebird 4.0+)."""
    name = "firebird_time_without_time_zone"


class FirebirdDecFloatType(DataType):
    """Firebird DECFLOAT(16|34) type (Firebird 4.0+).

    Firebird 4.0 introduced the decimal floating-point type with a
    precision of either 16 or 34 decimal digits.
    """

    name = "firebird_decfloat"

    def __init__(self, dialect=None, precision: int = 16):
        super().__init__(dialect)
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


_DATA_TYPE_TEXT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_$.,() \t]*")
_QUALIFIED_IDENTIFIER_RE = re.compile(
    r"[A-Za-z_][A-Za-z0-9_$]*(?:\.[A-Za-z_][A-Za-z0-9_$]*)?"
)
_INTEGER_RE = re.compile(r"INTEGER|INT|BIGINT|SMALLINT", re.IGNORECASE)
_FLOAT_RE = re.compile(r"FLOAT(?:\s*\(\s*(\d+)\s*\))?", re.IGNORECASE)
_REAL_RE = re.compile(r"REAL", re.IGNORECASE)
_DOUBLE_RE = re.compile(r"DOUBLE\s+PRECISION", re.IGNORECASE)
_DECIMAL_RE = re.compile(
    r"(?:DECIMAL|NUMERIC)(?:\s*\(\s*(\d+)\s*(?:,\s*(\d+)\s*)?\))?",
    re.IGNORECASE,
)
_VARCHAR_RE = re.compile(
    r"(?:VARCHAR|CHARACTER\s+VARYING|CHAR\s+VARYING)"
    r"(?:\s*\(\s*(\d+)\s*\))?",
    re.IGNORECASE,
)
_CHAR_RE = re.compile(
    r"(?:CHAR|CHARACTER)(?:\s*\(\s*(\d+)\s*\))?",
    re.IGNORECASE,
)
_BINARY_VARCHAR_RE = re.compile(
    r"(?:VARCHAR|CHARACTER\s+VARYING|CHAR\s+VARYING)"
    r"\s*\(\s*(\d+)\s*\)\s+CHARACTER\s+SET\s+OCTETS",
    re.IGNORECASE,
)
_BINARY_CHAR_RE = re.compile(
    r"(?:CHAR|CHARACTER)\s*\(\s*(\d+)\s*\)\s+CHARACTER\s+SET\s+OCTETS",
    re.IGNORECASE,
)
_UTF8_VARCHAR_RE = re.compile(
    r"(?:VARCHAR|CHARACTER\s+VARYING|CHAR\s+VARYING)"
    r"\s*\(\s*(\d+)\s*\)\s+CHARACTER\s+SET\s+UTF8",
    re.IGNORECASE,
)
_UTF8_CHAR_RE = re.compile(
    r"(?:CHAR|CHARACTER)\s*\(\s*(\d+)\s*\)\s+CHARACTER\s+SET\s+UTF8",
    re.IGNORECASE,
)
_BLOB_TEXT_RE = re.compile(r"BLOB\s+SUB_TYPE\s+TEXT", re.IGNORECASE)
_BLOB_BINARY_RE = re.compile(
    r"BLOB(?:\s+SUB_TYPE\s+BINARY|\s+CHARACTER\s+SET\s+OCTETS)?",
    re.IGNORECASE,
)
_DATE_RE = re.compile(r"DATE", re.IGNORECASE)
_TIME_RE = re.compile(r"TIME", re.IGNORECASE)
_TIMESTAMP_RE = re.compile(r"TIMESTAMP", re.IGNORECASE)
_BOOLEAN_RE = re.compile(r"BOOLEAN", re.IGNORECASE)
_DECFLOAT_RE = re.compile(
    r"DECFLOAT(?:\s*\(\s*(16|34)\s*\))?",
    re.IGNORECASE,
)
_INT128_RE = re.compile(r"INT128", re.IGNORECASE)
_TIMESTAMP_WITH_TIME_ZONE_RE = re.compile(
    r"TIMESTAMP(?:\s*\(\s*(\d+)\s*\))?\s+WITH\s+TIME\s+ZONE",
    re.IGNORECASE,
)
_TIME_WITH_TIME_ZONE_RE = re.compile(
    r"TIME(?:\s*\(\s*(\d+)\s*\))?\s+WITH\s+TIME\s+ZONE",
    re.IGNORECASE,
)
_TIME_WITHOUT_TIME_ZONE_RE = re.compile(
    r"TIME(?:\s*\(\s*(\d+)\s*\))?\s+WITHOUT\s+TIME\s+ZONE",
    re.IGNORECASE,
)
_ACTION_WORDS = {
    "ADD",
    "ALTER",
    "CHECK",
    "COLLATE",
    "CONSTRAINT",
    "CREATE",
    "DEFAULT",
    "DROP",
    "NOT",
    "NULL",
    "SET",
    "TO",
    "WITHOUT",
}


def _normalize_firebird_data_type_name(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"data_type_name must be a string, got {type(value).__name__}")
    normalized = " ".join(value.strip().split())
    if not normalized or _DATA_TYPE_TEXT_RE.fullmatch(normalized) is None:
        raise ValueError("data_type_name must be a valid Firebird data type declaration")
    return normalized


def _parse_firebird_data_type_name(value: str) -> DataType:
    normalized = _normalize_firebird_data_type_name(value)
    upper = normalized.upper()
    match = _BINARY_VARCHAR_RE.fullmatch(upper)
    if match:
        return VarBinaryType(length=int(match.group(1)))
    match = _BINARY_CHAR_RE.fullmatch(upper)
    if match:
        return BinaryType(length=int(match.group(1)))
    match = _UTF8_VARCHAR_RE.fullmatch(upper)
    if match:
        return FirebirdVarCharType(length=int(match.group(1)))
    match = _UTF8_CHAR_RE.fullmatch(upper)
    if match:
        return FirebirdCharType(length=int(match.group(1)))
    if _BLOB_TEXT_RE.fullmatch(upper):
        return TextType()
    if _BLOB_BINARY_RE.fullmatch(upper):
        return BinaryType()
    match = _TIMESTAMP_WITH_TIME_ZONE_RE.fullmatch(upper)
    if match:
        precision = int(match.group(1)) if match.group(1) else None
        return FirebirdTimeStampTzType(precision=precision)
    match = _TIME_WITH_TIME_ZONE_RE.fullmatch(upper)
    if match:
        precision = int(match.group(1)) if match.group(1) else None
        return FirebirdTimeTzType(precision=precision)
    match = _TIME_WITHOUT_TIME_ZONE_RE.fullmatch(upper)
    if match:
        precision = int(match.group(1)) if match.group(1) else None
        return FirebirdTimeWithoutTimeZoneType(precision=precision)
    match = _DECFLOAT_RE.fullmatch(upper)
    if match:
        precision = int(match.group(1)) if match.group(1) else 16
        return FirebirdDecFloatType(precision=precision)
    if upper.startswith("DECFLOAT"):
        raise ValueError("DECFLOAT precision must be 16 or 34")
    if _INT128_RE.fullmatch(upper):
        return FirebirdInt128Type()
    if _TIMESTAMP_RE.fullmatch(upper):
        return TimestampType()
    if _TIME_RE.fullmatch(upper):
        return TimeType()
    if _DATE_RE.fullmatch(upper):
        return DateType()
    if _BOOLEAN_RE.fullmatch(upper):
        return BooleanType()
    if _DOUBLE_RE.fullmatch(upper):
        return DoubleType()
    if _REAL_RE.fullmatch(upper):
        return FloatType()
    match = _FLOAT_RE.fullmatch(upper)
    if match:
        return FloatType(precision=int(match.group(1)) if match.group(1) else None)
    match = _DECIMAL_RE.fullmatch(upper)
    if match:
        return DecimalType(
            precision=int(match.group(1)) if match.group(1) else None,
            scale=int(match.group(2)) if match.group(2) else None,
        )
    match = _VARCHAR_RE.fullmatch(upper)
    if match:
        return VarCharType(length=int(match.group(1)) if match.group(1) else None)
    match = _CHAR_RE.fullmatch(upper)
    if match:
        return CharType(length=int(match.group(1)) if match.group(1) else None)
    if _INTEGER_RE.fullmatch(upper):
        if upper == "BIGINT":
            return BigIntType()
        if upper == "SMALLINT":
            return SmallIntType()
        return IntegerType()
    if _QUALIFIED_IDENTIFIER_RE.fullmatch(normalized):
        if normalized.upper() in _ACTION_WORDS:
            raise ValueError("data_type_name contains an unsupported action word")
        return CustomType(raw=normalized)
    raise ValueError("data_type_name contains unsupported Firebird type syntax")


ExpressionRegistry.register(FirebirdDecimalType)
ExpressionRegistry.register(FirebirdFloatType)
ExpressionRegistry.register(FirebirdDoubleType)
ExpressionRegistry.register(FirebirdBlobSubType)
ExpressionRegistry.register(FirebirdCharType)
ExpressionRegistry.register(FirebirdVarCharType)
ExpressionRegistry.register(FirebirdTimeStampTzType)
ExpressionRegistry.register(FirebirdTimeTzType)
ExpressionRegistry.register(FirebirdTimeWithoutTimeZoneType)
ExpressionRegistry.register(FirebirdDecFloatType)
ExpressionRegistry.register(FirebirdInt128Type)


__all__ = [
    "FirebirdDecimalType",
    "FirebirdFloatType",
    "FirebirdDoubleType",
    "FirebirdBlobSubType",
    "FirebirdCharType",
    "FirebirdVarCharType",
    "FirebirdTimeStampTzType",
    "FirebirdTimeTzType",
    "FirebirdTimeWithoutTimeZoneType",
    "FirebirdDecFloatType",
    "FirebirdInt128Type",
]
