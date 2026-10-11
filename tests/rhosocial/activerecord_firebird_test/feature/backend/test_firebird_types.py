# tests/rhosocial/activerecord_firebird_test/feature/backend/test_firebird_types.py
"""Tests for the Firebird 4.0+ data type mappings.

Covers ``TIMESTAMP WITH TIME ZONE``, ``TIME WITH TIME ZONE``,
``DECFLOAT(16|34)`` and ``INT128`` through ``format_data_type``, the
``(4, 0, 0)`` version gate, and ``FirebirdFloatType``'s ``FLOAT(bin_prec)``.
All tests are pure construction — no database connection.

Documentation-based, not measured: ``fbclient`` is not installed on this
machine, so nothing here was executed against a Firebird server. The
authorities are the Firebird 4.0 language reference (§3.2.1.1 for ``FLOAT``,
§3.4 for the zoned types, D.11 ``RDB$FIELDS`` for the catalog codes) and the
Firebird 4.0 release notes (CORE-6109 for the ``FLOAT(p)`` meaning change).
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.types import CustomType, DecimalType
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.expression import (
    FirebirdDecFloatType,
    FirebirdFloatType,
    FirebirdInt128Type,
    FirebirdTimeStampTzType,
    FirebirdTimeWithoutTimeZoneType,
    FirebirdTimeTzType,
)


class TestFirebirdTzTypes:
    """``TIME``/``TIMESTAMP WITH TIME ZONE`` — the whole declaration, no argument.

    Documentation-based, not measured. Firebird 4.0 and 5.0 language references,
    §3.4.2 (``TIME [{WITHOUT | WITH} TIME ZONE]``) and §3.4.3 (``TIMESTAMP
    [{WITHOUT | WITH} TIME ZONE]``), and the §3.12 Data Type Declaration Syntax,
    which carries the same two productions and no precision argument — while
    ``FLOAT [(bin_prec)]`` and ``DECFLOAT [(dec_prec)]`` in the same production do
    have one, so the absence is the documentation's.

    A declared precision is therefore **refused by name**, not rendered. These
    three formatters used to emit ``TIMESTAMP(6) WITH TIME ZONE``,
    ``TIME(6) WITH TIME ZONE`` and ``TIME(6) WITHOUT TIME ZONE`` for
    ``precision=6``, which is grammar Firebird does not have;
    FirebirdSQL/firebird#4779 (CORE-4459) requests it and is still open.
    """

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

    @pytest.mark.parametrize("cls,declaration", [
        (FirebirdTimeStampTzType, "TIMESTAMP WITH TIME ZONE"),
        (FirebirdTimeTzType, "TIME WITH TIME ZONE"),
        (FirebirdTimeWithoutTimeZoneType, "TIME WITHOUT TIME ZONE"),
    ])
    @pytest.mark.parametrize("precision", [0, 3, 6])
    def test_a_declared_precision_is_refused_by_name(self, cls, declaration,
                                                     precision):
        """The refusal must name the field and say why, so a caller can act."""
        dialect = FirebirdDialect((4, 0, 0))
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            dialect.format_data_type(cls(dialect, precision=precision))
        message = str(excinfo.value)
        assert "precision" in message
        assert declaration in message
        assert "4779" in message

    @pytest.mark.parametrize("cls", [
        FirebirdTimeStampTzType, FirebirdTimeTzType,
        FirebirdTimeWithoutTimeZoneType,
    ])
    def test_no_precision_renders_the_bare_declaration(self, cls):
        """``precision=None`` is untouched by the refusal."""
        dialect = FirebirdDialect((4, 0, 0))
        assert dialect.format_data_type(cls(dialect)) == (
            dialect.format_data_type(cls(dialect, precision=None))
        )
        assert "(" not in dialect.format_data_type(cls(dialect))[0]

    def test_tz_types_are_core_tz_subclasses(self):
        from rhosocial.activerecord.backend.expression.types import TimeTzType, TimestampTzType

        assert isinstance(FirebirdTimeStampTzType(), TimestampTzType)
        assert isinstance(FirebirdTimeTzType(), TimeTzType)


class TestFirebirdDecFloat:
    """The width is 16 or 34, and a bare ``DECFLOAT`` is 34.

    Documentation-based, not measured: ``fbclient`` is not installed here, so no
    ``DECFLOAT`` column was ever created. The authority is the Firebird 4.0 and
    5.0 language references, §3.2.2.1 *DECFLOAT* — ``DECFLOAT [(dec_prec)]``,
    *"Precision in decimal digits, either 16 or 34. Default is 34."* — with §3.1
    Table 3.1 agreeing (*"If the precision is not specified, 34 is used by
    default"*).

    The two ``test_decfloat_*`` tests below used to construct
    ``FirebirdDecFloatType(dialect)`` with no width and assert ``DECFLOAT(16)``,
    which was this class's constructor default rather than Firebird's. A bare
    ``DECFLOAT`` is legal Firebird, so "what does it mean" has one documented
    answer and the default follows it; the explicit-``16`` cases are unchanged.
    """

    def test_decfloat_16(self):
        dialect = FirebirdDialect((4, 0, 0))
        assert dialect.format_data_type(
            FirebirdDecFloatType(dialect, precision=16)
        ) == ("DECFLOAT(16)", ())

    def test_decfloat_34(self):
        dialect = FirebirdDialect((4, 0, 0))
        assert dialect.format_data_type(FirebirdDecFloatType(precision=34)) == ("DECFLOAT(34)", ())

    def test_bare_decfloat_is_the_documented_default(self):
        """§3.2.2.1: *"either 16 or 34; Default is 34."*"""
        dialect = FirebirdDialect((4, 0, 0))
        assert FirebirdDecFloatType(dialect).precision == 34
        assert dialect.format_data_type(FirebirdDecFloatType(dialect)) == ("DECFLOAT(34)", ())

    def test_decfloat_invalid_precision(self):
        with pytest.raises(ValueError):
            FirebirdDecFloatType(precision=20)

    def test_decfloat_bound_to_sql(self):
        dialect = FirebirdDialect((4, 0, 0))
        assert FirebirdDecFloatType(dialect=dialect).to_sql() == ("DECFLOAT(34)", ())


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
            FirebirdDecFloatType(dialect),
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
            FirebirdDecFloatType(dialect),
            FirebirdInt128Type(),
        ):
            with pytest.raises(UnsupportedFeatureError):
                dialect.format_data_type(data_type)

    def test_capability_flags_gated(self):
        assert FirebirdDialect((4, 0, 0)).supports_decfloat() is True
        assert FirebirdDialect((3, 0, 0)).supports_decfloat() is False


class TestFirebirdNumeric18:
    def test_numeric_18_2(self):
        dialect = FirebirdDialect((4, 0, 0))
        assert dialect.format_data_type(DecimalType(precision=18, scale=2)) == ("DECIMAL(18, 2)", ())


class TestFirebirdFloatBinaryPrecision:
    """``FLOAT(bin_prec)`` — the identity field is honoured, not dropped.

    Documentation-based, not measured. Firebird 4.0 language reference
    §3.12.1 gives the declaration syntax as ``REAL | FLOAT [(bin_prec)] |
    DOUBLE PRECISION`` and §3.2.1.1 gives ``bin_prec`` as "precision in binary
    digits, default is 24; 1 - 24: 32-bit single precision; 25 - 53: 64-bit
    double precision". Firebird 4.0 release notes, CORE-6109: before 4.0 the same
    argument counted *decimal* digits, so the string names different columns on
    either side of that boundary.
    """

    def test_bare_float(self):
        dialect = FirebirdDialect((4, 0, 0))
        assert dialect.format_data_type(FirebirdFloatType(dialect)) == ("FLOAT", ())

    @pytest.mark.parametrize("precision", [1, 24, 25, 53])
    def test_precision_is_written(self, precision):
        dialect = FirebirdDialect((4, 0, 0))
        assert dialect.format_data_type(
            FirebirdFloatType(precision=precision)
        ) == (f"FLOAT({precision})", ())

    @pytest.mark.parametrize("precision", [0, 54])
    def test_precision_outside_the_documented_range_raises(self, precision):
        dialect = FirebirdDialect((4, 0, 0))
        with pytest.raises(ValueError, match="between 1 and 53"):
            dialect.format_data_type(FirebirdFloatType(precision=precision))

    def test_two_precisions_are_two_columns(self):
        dialect = FirebirdDialect((4, 0, 0))
        single = FirebirdFloatType(precision=24)
        double = FirebirdFloatType(precision=53)
        assert single != double
        assert dialect.format_data_type(single)[0] != dialect.format_data_type(
            double
        )[0]

    def test_precision_raises_on_firebird_3(self):
        """``FLOAT(10)`` meant ten decimal digits there and ten bits here."""
        dialect = FirebirdDialect((3, 0, 0))
        with pytest.raises(UnsupportedFeatureError, match="FLOAT"):
            dialect.format_data_type(FirebirdFloatType(precision=24))

    def test_bare_float_renders_on_firebird_3(self):
        """Single precision on both sides, so the type needs no gate."""
        assert FirebirdDialect((3, 0, 0)).format_data_type(
            FirebirdFloatType()
        ) == ("FLOAT", ())

    def test_support_flag_is_not_gated(self):
        """Gating it would drop ``firebird_float`` on a dialect that renders it."""
        assert FirebirdDialect((3, 0, 0)).supports_data_type_firebird_float() is True


class TestFirebirdFourTypesParseToRealClasses:
    """The two FB4 catalog codes, from the words the introspector writes.

    ``RDB$FIELDS.RDB$FIELD_TYPE`` reports 24 for ``DECFLOAT(16)``, 25 for
    ``DECFLOAT(34)`` and 26 for ``INT128`` (language reference, D.11). Before
    these were recognised, code 26 produced ``CustomType(raw="INT128")`` — an
    opaque name that renders itself back into DDL — and code 24 produced the
    unqualified word ``DECFLOAT``, which is what made a 16-digit and a 34-digit
    column compare equal.
    """

    @pytest.mark.parametrize("raw,precision", [
        ("DECFLOAT(16)", 16),
        ("DECFLOAT(34)", 34),
        ("decfloat(34)", 34),
    ])
    def test_decfloat_reaches_its_class_with_its_precision(self, raw, precision):
        parsed = FirebirdDialect((4, 0, 0)).parse_type(raw)
        assert isinstance(parsed, FirebirdDecFloatType)
        assert parsed.precision == precision

    def test_bare_decfloat_uses_the_documented_default(self):
        """``dec_prec``: "either 16 or 34; Default is 34" (§3.2.2.1, DECFLOAT)."""
        parsed = FirebirdDialect((4, 0, 0)).parse_type("DECFLOAT")
        assert isinstance(parsed, FirebirdDecFloatType)
        assert parsed.precision == 34

    def test_decfloat_is_not_a_fixed_point_decimal(self):
        dialect = FirebirdDialect((4, 0, 0))
        assert dialect.parse_type("DECFLOAT(16)") != DecimalType(precision=16)
        assert dialect.parse_type("DECIMAL(16)") == DecimalType(precision=16)

    def test_int128_reaches_its_class(self):
        parsed = FirebirdDialect((4, 0, 0)).parse_type("INT128")
        assert isinstance(parsed, FirebirdInt128Type)
        assert parsed.PARAMETERS == ()

    def test_int128_is_not_read_as_integer(self):
        """``INT128`` holds -2**127..2**127-1; ``INTEGER`` holds 32 bits."""
        dialect = FirebirdDialect((4, 0, 0))
        assert dialect.parse_type("INT128") != dialect.parse_type("INTEGER")
        assert dialect.parse_type("INT128") != dialect.parse_type("BIGINT")

    @pytest.mark.parametrize("raw", ["DECFLOAT(34)", "DECFLOAT", "INT128"])
    def test_kept_verbatim_on_firebird_3(self, raw):
        """An older grammar has no such type, so the declaration is not rewritten.

        Answering with a narrower real type would render a *different* column and
        say nothing about why.
        """
        assert isinstance(
            FirebirdDialect((3, 0, 0)).parse_type(raw), CustomType
        )
