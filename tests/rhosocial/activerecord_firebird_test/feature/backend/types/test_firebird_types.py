# tests/rhosocial/activerecord_firebird_test/feature/backend/types/test_firebird_types.py
"""Tests for the Firebird 4.0+ data type mappings.

Covers ``TIMESTAMP WITH TIME ZONE``, ``TIME WITH TIME ZONE``,
``DECFLOAT(16|34)`` and ``INT128`` through ``format_data_type``, plus the
``(4, 0, 0)`` version gate. All tests are pure construction — no database
connection.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.types import DecimalType
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.expression import (
    FirebirdDecFloatType,
    FirebirdInt128Type,
    FirebirdTimeStampTzType,
    FirebirdTimeTzType,
)


class TestFirebirdTzTypes:
    def test_timestamp_with_time_zone(self):
        dialect = FirebirdDialect((4, 0, 0))
        assert dialect.format_data_type(FirebirdTimeStampTzType()) == (
            "TIMESTAMP WITH TIME ZONE",
            (),
        )

    def test_timestamp_with_time_zone_bound_to_sql(self):
        dialect = FirebirdDialect((4, 0, 0))
        assert FirebirdTimeStampTzType(dialect=dialect).to_sql() == ("TIMESTAMP WITH TIME ZONE", ())

    def test_time_with_time_zone(self):
        dialect = FirebirdDialect((4, 0, 0))
        assert dialect.format_data_type(FirebirdTimeTzType()) == (
            "TIME WITH TIME ZONE",
            (),
        )

    def test_tz_types_are_core_tz_subclasses(self):
        from rhosocial.activerecord.backend.expression.types import TimeTzType, TimestampTzType

        assert isinstance(FirebirdTimeStampTzType(), TimestampTzType)
        assert isinstance(FirebirdTimeTzType(), TimeTzType)


class TestFirebirdDecFloat:
    def test_decfloat_16(self):
        dialect = FirebirdDialect((4, 0, 0))
        assert dialect.format_data_type(FirebirdDecFloatType()) == ("DECFLOAT(16)", ())

    def test_decfloat_34(self):
        dialect = FirebirdDialect((4, 0, 0))
        assert dialect.format_data_type(FirebirdDecFloatType(precision=34)) == ("DECFLOAT(34)", ())

    def test_decfloat_invalid_precision(self):
        with pytest.raises(ValueError):
            FirebirdDecFloatType(precision=20)

    def test_decfloat_bound_to_sql(self):
        dialect = FirebirdDialect((4, 0, 0))
        assert FirebirdDecFloatType(dialect=dialect).to_sql() == ("DECFLOAT(16)", ())


class TestFirebirdInt128:
    def test_int128(self):
        dialect = FirebirdDialect((4, 0, 0))
        assert dialect.format_data_type(FirebirdInt128Type()) == ("INT128", ())

    def test_int128_bound_to_sql(self):
        dialect = FirebirdDialect((4, 0, 0))
        assert FirebirdInt128Type(dialect=dialect).to_sql() == ("INT128", ())


class TestFirebirdTypeVersionGating:
    def test_all_fb4_types_raise_on_fb3(self):
        dialect = FirebirdDialect((3, 0, 0))
        for data_type in (
            FirebirdTimeStampTzType(),
            FirebirdTimeTzType(),
            FirebirdDecFloatType(),
            FirebirdDecFloatType(precision=34),
            FirebirdInt128Type(),
        ):
            with pytest.raises(UnsupportedFeatureError):
                dialect.format_data_type(data_type)

    def test_all_fb4_types_raise_on_fb2_5(self):
        dialect = FirebirdDialect((2, 5, 0))
        for data_type in (
            FirebirdTimeStampTzType(),
            FirebirdTimeTzType(),
            FirebirdDecFloatType(),
            FirebirdInt128Type(),
        ):
            with pytest.raises(UnsupportedFeatureError):
                dialect.format_data_type(data_type)

    def test_capability_flags_gated(self):
        assert FirebirdDialect((4, 0, 0)).supports_decfloat() is True
        assert FirebirdDialect((3, 0, 0)).supports_decfloat() is False


class TestFirebirdNumeric38:
    def test_numeric_38_2(self):
        dialect = FirebirdDialect((4, 0, 0))
        assert dialect.format_data_type(DecimalType(precision=38, scale=2)) == ("DECIMAL(38, 2)", ())
