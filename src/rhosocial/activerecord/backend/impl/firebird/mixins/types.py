# src/rhosocial/activerecord/backend/impl/firebird/mixins/types.py
"""Firebird DataType formatting mixin.

Covers the Firebird 4.0+ data types ``TIMESTAMP WITH TIME ZONE``, ``TIME
WITH TIME ZONE``, ``DECFLOAT(16|34)`` and ``INT128`` with a version gate of
 ``(4, 0, 0)`` — requesting any of them on an older dialect raises
``UnsupportedFeatureError``.
"""

from __future__ import annotations

import re
from typing import Dict, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.dialect.mixins import DDLTypeMixin
from rhosocial.activerecord.backend.dialect.protocols import DDLTypeSupport
from rhosocial.activerecord.backend.expression.types import (
    BigIntType,
    BinaryType,
    BlobType,
    BooleanType,
    CharType,
    CustomType,
    DataType,
    DateType,
    DateTimeType,
    DecimalType,
    DoubleType,
    FloatType,
    IntType,
    IntegerType,
    SmallIntType,
    TextType,
    TimeTzType,
    TimeType,
    TimestampTzType,
    TimestampType,
    TinyIntType,
    UUIDType,
    VarBinaryType,
    VarCharType,
)

from .version_boundaries import _norm_version
from ..expression.types import (
    FirebirdDecimalType,
    FirebirdDecFloatType,
    FirebirdDoubleType,
    FirebirdFloatType,
    FirebirdInt128Type,
    FirebirdBlobSubType,
    FirebirdTimeStampTzType,
    FirebirdTimeTzType,
)


class FirebirdTypeSupportMixin(DDLTypeMixin, DDLTypeSupport):

    # --- Precision / scale validation helpers ---

    def _validate_numeric(self, precision, scale) -> None:
        """Validate Firebird NUMERIC/DECIMAL precision and scale.

        Firebird: precision 1-18, scale 0-18.
        """
        if precision is not None and not 1 <= precision <= 18:
            raise ValueError(
                f"Firebird DECIMAL precision must be between 1 and 18, "
                f"got {precision}."
            )
        if scale is not None and not 0 <= scale <= 18:
            raise ValueError(
                f"Firebird DECIMAL scale must be between 0 and 18, "
                f"got {scale}."
            )
        if (precision is not None and scale is not None
                and scale > precision):
            raise ValueError(
                f"Firebird DECIMAL scale ({scale}) cannot exceed "
                f"precision ({precision})."
            )

    def _validate_float_precision(self, precision) -> None:
        """Validate Firebird FLOAT binary precision.

        Firebird FLOAT (binary): 1-24.
        """
        if precision is not None and not 1 <= precision <= 24:
            raise ValueError(
                f"Firebird FLOAT precision must be between 1 and 24, "
                f"got {precision}."
            )

    # --- Core types (pure names) rendered to real Firebird SQL ---

    def format_data_type_integer(self, data_type: IntegerType) -> Tuple[str, tuple]:
        return "INTEGER", ()

    def format_data_type_int(self, data_type: IntType) -> Tuple[str, tuple]:
        return "INTEGER", ()

    def format_data_type_bigint(self, data_type: BigIntType) -> Tuple[str, tuple]:
        return "BIGINT", ()

    def format_data_type_smallint(self, data_type: SmallIntType) -> Tuple[str, tuple]:
        return "SMALLINT", ()

    def format_data_type_tinyint(self, data_type: TinyIntType) -> Tuple[str, tuple]:
        return "SMALLINT", ()

    def format_data_type_float(self, data_type: FloatType) -> Tuple[str, tuple]:
        self._validate_float_precision(data_type.precision)
        return (f"FLOAT({data_type.precision})" if data_type.precision is not None else "FLOAT"), ()

    def format_data_type_real(self, data_type: FloatType) -> Tuple[str, tuple]:
        return "FLOAT", ()

    def format_data_type_double(self, data_type: DoubleType) -> Tuple[str, tuple]:
        return "DOUBLE PRECISION", ()

    def format_data_type_decimal(self, data_type: DecimalType) -> Tuple[str, tuple]:
        self._validate_numeric(data_type.precision, data_type.scale)
        if data_type.precision is not None and data_type.scale is not None:
            return f"DECIMAL({data_type.precision}, {data_type.scale})", ()
        if data_type.precision is not None:
            return f"DECIMAL({data_type.precision})", ()
        return "DECIMAL", ()

    def format_data_type_boolean(self, data_type: BooleanType) -> Tuple[str, tuple]:
        return "BOOLEAN", ()

    def format_data_type_varchar(self, data_type: VarCharType) -> Tuple[str, tuple]:
        return (f"VARCHAR({data_type.length})" if data_type.length is not None else "VARCHAR(255)"), ()

    def format_data_type_char(self, data_type: CharType) -> Tuple[str, tuple]:
        return (f"CHAR({data_type.length})" if data_type.length is not None else "CHAR(1)"), ()

    def format_data_type_text(self, data_type: TextType) -> Tuple[str, tuple]:
        return "BLOB SUB_TYPE TEXT", ()

    def format_data_type_datetime(self, data_type: DateTimeType) -> Tuple[str, tuple]:
        return "TIMESTAMP", ()

    def format_data_type_date(self, data_type: DateType) -> Tuple[str, tuple]:
        return "DATE", ()

    def format_data_type_time(self, data_type: TimeType) -> Tuple[str, tuple]:
        return "TIME", ()

    def format_data_type_timetz(self, data_type: TimeTzType) -> Tuple[str, tuple]:
        return "TIME", ()

    def format_data_type_timestamp(self, data_type: TimestampType) -> Tuple[str, tuple]:
        return "TIMESTAMP", ()

    def format_data_type_timestamptz(self, data_type: TimestampTzType) -> Tuple[str, tuple]:
        return "TIMESTAMP", ()

    def format_data_type_blob(self, data_type: BlobType) -> Tuple[str, tuple]:
        return "BLOB", ()

    def format_data_type_binary(self, data_type: BinaryType) -> Tuple[str, tuple]:
        return (f"CHAR({data_type.length}) CHARACTER SET OCTETS" if data_type.length is not None else "BLOB"), ()

    def format_data_type_varbinary(self, data_type: VarBinaryType) -> Tuple[str, tuple]:
        return (f"VARCHAR({data_type.length}) CHARACTER SET OCTETS" if data_type.length is not None else "BLOB"), ()

    def format_data_type_uuid(self, data_type: UUIDType) -> Tuple[str, tuple]:
        return "CHAR(16) CHARACTER SET OCTETS", ()

    def format_data_type_custom(self, data_type: CustomType) -> Tuple[str, tuple]:
        return data_type.raw, ()

    # --- Firebird-specific type formatters (dispatch key = type name) ---

    def format_data_type_firebird_decimal(self, data_type: FirebirdDecimalType) -> Tuple[str, tuple]:
        self._validate_numeric(data_type.precision, data_type.scale)
        if data_type.precision is not None and data_type.scale is not None:
            return f"DECIMAL({data_type.precision}, {data_type.scale})", ()
        if data_type.precision is not None:
            return f"DECIMAL({data_type.precision})", ()
        return "DECIMAL", ()

    def format_data_type_firebird_float(self, data_type: FirebirdFloatType) -> Tuple[str, tuple]:
        return "FLOAT", ()

    def format_data_type_firebird_double(self, data_type: FirebirdDoubleType) -> Tuple[str, tuple]:
        return "DOUBLE PRECISION", ()

    def format_data_type_firebird_blob_subtype(self, data_type: FirebirdBlobSubType) -> Tuple[str, tuple]:
        return "BLOB SUB_TYPE TEXT", ()

    def format_data_type_firebird_timestamptz(self, data_type: FirebirdTimeStampTzType) -> Tuple[str, tuple]:
        """Format TIMESTAMP WITH TIME ZONE (Firebird 4.0+)."""
        self._check_fb4_type("TIMESTAMP WITH TIME ZONE")
        return "TIMESTAMP WITH TIME ZONE", ()

    def format_data_type_firebird_timetz(self, data_type: FirebirdTimeTzType) -> Tuple[str, tuple]:
        """Format TIME WITH TIME ZONE (Firebird 4.0+)."""
        self._check_fb4_type("TIME WITH TIME ZONE")
        return "TIME WITH TIME ZONE", ()

    def format_data_type_firebird_decfloat(self, data_type: FirebirdDecFloatType) -> Tuple[str, tuple]:
        """Format DECFLOAT(16|34) (Firebird 4.0+)."""
        self._check_fb4_type("DECFLOAT")
        return f"DECFLOAT({data_type.precision})", ()

    def format_data_type_firebird_int128(self, data_type: FirebirdInt128Type) -> Tuple[str, tuple]:
        """Format INT128 (Firebird 4.0+)."""
        self._check_fb4_type("INT128")
        return "INT128", ()

    def _check_fb4_type(self, feature: str) -> None:
        """Raise unless the dialect targets Firebird 4.0 or later.

        TIME ZONE / DECFLOAT / INT128 data types were all introduced in
        Firebird 4.0.
        """
        version = getattr(self, 'version', (4, 0, 0))
        if _norm_version(version) < (4, 0, 0):
            raise UnsupportedFeatureError(
                self.name,
                feature,
                f"Firebird 4.0 or later is required for the {feature} data type.",
            )

    # ------------------------------------------------------------------
    # DDLTypeSupport — per-type support declarations
    #
    # 1:1 correspondence with format_data_type_* family (protocol contract).
    # ------------------------------------------------------------------

    def supports_data_type_integer(self) -> bool:
        return True

    def supports_data_type_int(self) -> bool:
        return True

    def supports_data_type_bigint(self) -> bool:
        return True

    def supports_data_type_smallint(self) -> bool:
        return True

    def supports_data_type_tinyint(self) -> bool:
        return True

    def supports_data_type_float(self) -> bool:
        return True

    def supports_data_type_real(self) -> bool:
        return True

    def supports_data_type_double(self) -> bool:
        return True

    def supports_data_type_decimal(self) -> bool:
        return True

    def supports_data_type_boolean(self) -> bool:
        return True

    def supports_data_type_varchar(self) -> bool:
        return True

    def supports_data_type_char(self) -> bool:
        return True

    def supports_data_type_text(self) -> bool:
        return True

    def supports_data_type_datetime(self) -> bool:
        return True

    def supports_data_type_date(self) -> bool:
        return True

    def supports_data_type_time(self) -> bool:
        return True

    def supports_data_type_timetz(self) -> bool:
        return True

    def supports_data_type_timestamp(self) -> bool:
        return True

    def supports_data_type_timestamptz(self) -> bool:
        return True

    def supports_data_type_blob(self) -> bool:
        return True

    def supports_data_type_binary(self) -> bool:
        return True

    def supports_data_type_varbinary(self) -> bool:
        return True

    def supports_data_type_uuid(self) -> bool:
        return True

    def supports_data_type_custom(self) -> bool:
        return True

    def supports_data_type_firebird_decimal(self) -> bool:
        return True

    def supports_data_type_firebird_float(self) -> bool:
        return True

    def supports_data_type_firebird_double(self) -> bool:
        return True

    def supports_data_type_firebird_blob_subtype(self) -> bool:
        return True

    def supports_data_type_firebird_timestamptz(self) -> bool:
        return _norm_version(getattr(self, 'version', (4, 0, 0))) >= (4, 0, 0)

    def supports_data_type_firebird_timetz(self) -> bool:
        return _norm_version(getattr(self, 'version', (4, 0, 0))) >= (4, 0, 0)

    def supports_data_type_firebird_decfloat(self) -> bool:
        return _norm_version(getattr(self, 'version', (4, 0, 0))) >= (4, 0, 0)

    def supports_data_type_firebird_int128(self) -> bool:
        return _norm_version(getattr(self, 'version', (4, 0, 0))) >= (4, 0, 0)

    # ------------------------------------------------------------------
    # suggested_data_types()
    #
    # Firebird is ANSI SQL compliant but lacks native ARRAY, UUID, and
    # INTERVAL types. Suggestions reflect honest fallbacks.
    # ------------------------------------------------------------------

    def suggested_data_types(self) -> Dict[str, type]:
        """Cross-backend type-consistency suggestions for Firebird.

        Firebird does not have native JSON, JSONB, or ENUM types.
        Values are the suggested replacement DataType **classes**.
        """
        return {
            "json": TextType,
            "jsonb": TextType,
            "enum": VarCharType,
        }

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
                return DecimalType(precision=int(nums[0]), scale=int(nums[1]))
            if len(nums) == 1:
                return DecimalType(precision=int(nums[0]))
            return DecimalType()

        if self._FB_STRING_TYPES.match(upper):
            length_match = re.search(r"\((\d+)", stripped)
            length = int(length_match.group(1)) if length_match else None
            if upper.startswith("VARCHAR"):
                return VarCharType(length=length or 255)
            return CharType(length=length or 1)

        if self._FB_BLOB_TYPES.match(upper):
            return TextType()

        if self._FB_DATE_TYPES.match(upper):
            # TIMESTAMP must be tested before TIME: "TIMESTAMP".startswith("TIME")
            # is True, so the reversed order mis-parsed TIMESTAMP as TimeType.
            if upper.startswith("TIMESTAMP"):
                return DateTimeType()
            if upper.startswith("TIME"):
                return TimeType()
            if upper.startswith("DATE"):
                if upper.strip() == "DATE":
                    return DateType()
                return DateTimeType()
            return DateTimeType()

        if self._FB_BOOLEAN_TYPES.match(upper):
            return BooleanType()

        return CustomType(raw=stripped)
