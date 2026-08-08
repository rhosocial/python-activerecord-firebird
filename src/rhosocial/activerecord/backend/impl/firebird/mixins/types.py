# src/rhosocial/activerecord/backend/impl/firebird/mixins/types.py
"""Firebird DataType formatting mixin.

Covers the Firebird 4.0+ data types ``TIMESTAMP WITH TIME ZONE``, ``TIME
WITH TIME ZONE``, ``DECFLOAT(16|34)`` and ``INT128`` with a version gate of
``(4, 0, 0)`` — requesting any of them on an older dialect raises
``UnsupportedFeatureError``.
"""

from __future__ import annotations

import re
from typing import Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.dialect.mixins import DDLTypeMixin
from rhosocial.activerecord.backend.dialect.protocols import DDLTypeSupport
from rhosocial.activerecord.backend.expression.types import (
    BigIntType,
    BooleanType,
    CharType,
    CustomType,
    DataType,
    DateType,
    DateTimeType,
    DecimalType,
    DoubleType,
    FloatType,
    IntegerType,
    SmallIntType,
    TextType,
    TimeType,
    TimestampType,
    VarCharType,
)

from ..expression.types import (
    FirebirdDecFloatType,
    FirebirdInt128Type,
    FirebirdTimeStampTzType,
    FirebirdTimeTzType,
)


class FirebirdTypeSupportMixin(DDLTypeMixin, DDLTypeSupport):

    @DDLTypeMixin.handles(IntegerType)
    def format_data_type_integer(self, data_type: IntegerType) -> Tuple[str, tuple]:
        return "INTEGER", ()

    @DDLTypeMixin.handles(BigIntType)
    def format_data_type_bigint(self, data_type: BigIntType) -> Tuple[str, tuple]:
        return "BIGINT", ()

    @DDLTypeMixin.handles(SmallIntType)
    def format_data_type_smallint(self, data_type: SmallIntType) -> Tuple[str, tuple]:
        return "SMALLINT", ()

    @DDLTypeMixin.handles(FloatType)
    def format_data_type_float(self, data_type: FloatType) -> Tuple[str, tuple]:
        return "FLOAT", ()

    @DDLTypeMixin.handles(DoubleType)
    def format_data_type_double(self, data_type: DoubleType) -> Tuple[str, tuple]:
        return "DOUBLE PRECISION", ()

    @DDLTypeMixin.handles(DecimalType)
    def format_data_type_decimal(self, data_type: DecimalType) -> Tuple[str, tuple]:
        if data_type.precision is not None and data_type.scale is not None:
            return f"DECIMAL({data_type.precision}, {data_type.scale})", ()
        if data_type.precision is not None:
            return f"DECIMAL({data_type.precision})", ()
        return "DECIMAL", ()

    @DDLTypeMixin.handles(BooleanType)
    def format_data_type_boolean(self, data_type: BooleanType) -> Tuple[str, tuple]:
        return "BOOLEAN", ()

    @DDLTypeMixin.handles(VarCharType)
    def format_data_type_varchar(self, data_type: VarCharType) -> Tuple[str, tuple]:
        return (f"VARCHAR({data_type.length})" if data_type.length is not None else "VARCHAR(255)"), ()

    @DDLTypeMixin.handles(CharType)
    def format_data_type_char(self, data_type: CharType) -> Tuple[str, tuple]:
        return (f"CHAR({data_type.length})" if data_type.length is not None else "CHAR(1)"), ()

    @DDLTypeMixin.handles(TextType)
    def format_data_type_text(self, data_type: TextType) -> Tuple[str, tuple]:
        return "BLOB SUB_TYPE TEXT", ()

    @DDLTypeMixin.handles(DateTimeType)
    def format_data_type_datetime(self, data_type: DateTimeType) -> Tuple[str, tuple]:
        return "TIMESTAMP", ()

    @DDLTypeMixin.handles(DateType)
    def format_data_type_date(self, data_type: DateType) -> Tuple[str, tuple]:
        return "DATE", ()

    @DDLTypeMixin.handles(TimeType)
    def format_data_type_time(self, data_type: TimeType) -> Tuple[str, tuple]:
        return "TIME", ()

    @DDLTypeMixin.handles(TimestampType)
    def format_data_type_timestamp(self, data_type: TimestampType) -> Tuple[str, tuple]:
        return "TIMESTAMP", ()

    @DDLTypeMixin.handles(FirebirdTimeStampTzType)
    def format_data_type_timestamptz(self, data_type: FirebirdTimeStampTzType) -> Tuple[str, tuple]:
        """Format TIMESTAMP WITH TIME ZONE (Firebird 4.0+)."""
        self._check_fb4_type("TIMESTAMP WITH TIME ZONE")
        return "TIMESTAMP WITH TIME ZONE", ()

    @DDLTypeMixin.handles(FirebirdTimeTzType)
    def format_data_type_timetz(self, data_type: FirebirdTimeTzType) -> Tuple[str, tuple]:
        """Format TIME WITH TIME ZONE (Firebird 4.0+)."""
        self._check_fb4_type("TIME WITH TIME ZONE")
        return "TIME WITH TIME ZONE", ()

    @DDLTypeMixin.handles(FirebirdDecFloatType)
    def format_data_type_decfloat(self, data_type: FirebirdDecFloatType) -> Tuple[str, tuple]:
        """Format DECFLOAT(16|34) (Firebird 4.0+)."""
        self._check_fb4_type("DECFLOAT")
        return f"DECFLOAT({data_type.precision})", ()

    @DDLTypeMixin.handles(FirebirdInt128Type)
    def format_data_type_int128(self, data_type: FirebirdInt128Type) -> Tuple[str, tuple]:
        """Format INT128 (Firebird 4.0+)."""
        self._check_fb4_type("INT128")
        return "INT128", ()

    def _check_fb4_type(self, feature: str) -> None:
        """Raise unless the dialect targets Firebird 4.0 or later.

        TIME ZONE / DECFLOAT / INT128 data types were all introduced in
        Firebird 4.0.
        """
        version = getattr(self, 'version', (4, 0, 0))
        if version < (4, 0, 0):
            raise UnsupportedFeatureError(
                self.name,
                feature,
                f"Firebird 4.0 or later is required for the {feature} data type.",
            )

    # --- Parsing ---

    _FB_INTEGER_TYPES = re.compile(r"^(?:INTEGER|INT|BIGINT|SMALLINT)\b", re.IGNORECASE)
    _FB_FLOAT_TYPES = re.compile(r"^(?:FLOAT|DOUBLE\s+PRECISION|REAL)\b", re.IGNORECASE)
    _FB_DECIMAL_TYPES = re.compile(r"^(?:DECIMAL|NUMERIC)\b", re.IGNORECASE)
    _FB_STRING_TYPES = re.compile(r"^(?:VARCHAR|CHAR|CHARACTER)\b", re.IGNORECASE)
    _FB_BLOB_TYPES = re.compile(r"^(?:BLOB)\b", re.IGNORECASE)
    _FB_DATE_TYPES = re.compile(r"^(?:DATE|TIMESTAMP|TIME)\b", re.IGNORECASE)
    _FB_BOOLEAN_TYPES = re.compile(r"^(?:BOOLEAN)\b", re.IGNORECASE)

    def parse_type(self, raw: str) -> DataType:
        stripped = raw.strip()
        upper = stripped.upper()

        if self._FB_INTEGER_TYPES.match(upper):
            if upper.startswith("BIGINT"):
                return BigIntType()
            if upper.startswith("SMALLINT"):
                return SmallIntType()
            return IntegerType()

        if self._FB_FLOAT_TYPES.match(upper):
            if "DOUBLE" in upper:
                return DoubleType()
            return FloatType()

        if self._FB_DECIMAL_TYPES.match(upper):
            nums = re.findall(r"\d+", stripped)
            if len(nums) >= 2:
                return DecimalType(int(nums[0]), int(nums[1]))
            if len(nums) == 1:
                return DecimalType(int(nums[0]))
            return DecimalType()

        if self._FB_STRING_TYPES.match(upper):
            length_match = re.search(r"\((\d+)", stripped)
            length = int(length_match.group(1)) if length_match else None
            if upper.startswith("VARCHAR"):
                return VarCharType(length or 255)
            return CharType(length or 1)

        if self._FB_BLOB_TYPES.match(upper):
            return TextType()

        if self._FB_DATE_TYPES.match(upper):
            if upper.startswith("TIME"):
                return TimeType()
            if upper.startswith("DATE"):
                if upper.strip() == "DATE":
                    return DateType()
                return DateTimeType()
            return DateTimeType()

        if self._FB_BOOLEAN_TYPES.match(upper):
            return BooleanType()

        return CustomType(stripped)