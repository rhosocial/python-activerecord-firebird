# tests/rhosocial/activerecord_firebird_test/feature/backend/test_firebird_type_protocol.py
"""
Firebird type protocol conformance tests.

Verifies the two-level data-type contract between the core ``DataType``
system and the Firebird backend:

- ``supports_data_type_<name>`` / ``format_data_type_<name>`` 1:1
  correspondence on ``FirebirdDialect``;
- ``supports_data_types()`` merges the ``firebird_*`` namespaced family
  with the core family;
- ``suggested_data_types()`` values are real ``DataType`` classes and its
  keys are disjoint from the supported keys;
- Firebird-specific range checks live in the formatters (DECIMAL/FLOAT
  precision);
- ``dialect_options`` forwards through construction and participates in
  equality.
"""

import pytest

from rhosocial.activerecord.backend.dialect.mixins.ddl_type import DDLTypeMixin
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
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.expression.types import (
    FirebirdDecFloatType,
    FirebirdInt128Type,
    FirebirdTimeStampTzType,
    FirebirdTimeTzType,
)


@pytest.fixture
def dialect():
    return FirebirdDialect((4, 0, 0))


@pytest.fixture
def dialect_3():
    return FirebirdDialect((3, 0, 0))


class TestSupportFormatCorrespondence:
    """Every format_data_type_<name> has supports_data_type_<name>, 1:1."""

    def test_format_family_equals_supports_family(self, dialect):
        format_names = {
            member[len("format_data_type_"):]
            for member in dir(FirebirdDialect)
            if member.startswith("format_data_type_")
        }
        support_names = {
            member[len("supports_data_type_"):]
            for member in dir(FirebirdDialect)
            if member.startswith("supports_data_type_")
        }
        assert format_names, "FirebirdDialect must implement format_data_type_* members"
        assert format_names == support_names

    def test_supports_data_types_covers_every_formatter(self, dialect):
        format_names = {
            member[len("format_data_type_"):]
            for member in dir(FirebirdDialect)
            if member.startswith("format_data_type_")
        }
        supported = dialect.supports_data_types()
        assert set(supported) == format_names

    def test_supports_data_types_returns_classes(self, dialect):
        for name, klass in dialect.supports_data_types().items():
            assert isinstance(klass, type), name
            assert issubclass(klass, DataType), name

    def test_inherits_mixin_scan_implementation(self, dialect):
        assert FirebirdDialect.supports_data_types is DDLTypeMixin.supports_data_types


class TestSupportsDataTypesMapping:
    """supports_data_types() merges firebird_* namespaced and core entries."""

    def test_includes_firebird_namespaced_entries(self, dialect):
        supported = dialect.supports_data_types()
        assert "firebird_decimal" in supported
        assert "firebird_float" in supported
        assert "firebird_double" in supported
        assert "firebird_blob_subtype" in supported
        assert "firebird_timestamptz" in supported
        assert "firebird_timetz" in supported
        assert "firebird_decfloat" in supported
        assert "firebird_int128" in supported

    def test_includes_core_entries(self, dialect):
        supported = dialect.supports_data_types()
        assert "integer" in supported
        assert supported["integer"] is IntegerType
        assert "varchar" in supported
        assert "decimal" in supported
        assert "float" in supported
        assert "double" in supported
        assert "boolean" in supported
        assert "date" in supported
        assert "timestamp" in supported
        assert "text" in supported
        assert "blob" in supported
        assert "uuid" in supported

    def test_per_type_support_methods_are_truthful(self, dialect):
        supported = dialect.supports_data_types()
        for name in supported:
            checker = getattr(dialect, f"supports_data_type_{name}")
            assert checker() is True, name


class TestSuggestedDataTypes:
    """suggested_data_types(): real classes, disjoint from supported keys."""

    def test_returns_dict(self, dialect):
        result = dialect.suggested_data_types()
        assert isinstance(result, dict)

    def test_values_are_data_type_classes(self, dialect):
        suggestions = dialect.suggested_data_types()
        for key, klass in suggestions.items():
            assert isinstance(klass, type), key
            assert issubclass(klass, DataType), key

    def test_keys_disjoint_from_supported(self, dialect):
        suggestions = dialect.suggested_data_types()
        supported = dialect.supports_data_types()
        assert not (set(suggestions) & set(supported))

    def test_json_suggested_as_text(self, dialect):
        suggestions = dialect.suggested_data_types()
        assert "json" in suggestions
        assert suggestions["json"] is TextType

    def test_jsonb_suggested_as_text(self, dialect):
        suggestions = dialect.suggested_data_types()
        assert "jsonb" in suggestions
        assert suggestions["jsonb"] is TextType

    def test_enum_suggested_as_varchar(self, dialect):
        suggestions = dialect.suggested_data_types()
        assert "enum" in suggestions
        assert suggestions["enum"] is VarCharType


class TestDialectRangeValidation:
    """Dialect-specific range checks live inside the formatters."""

    def test_decimal_precision_over_18_raises(self, dialect):
        data_type = DecimalType(precision=19, scale=2)
        with pytest.raises(ValueError, match="between 1 and 18"):
            dialect.format_data_type(data_type)

    def test_decimal_scale_over_18_raises(self, dialect):
        data_type = DecimalType(precision=18, scale=19)
        with pytest.raises(ValueError, match="between 0 and 18"):
            dialect.format_data_type(data_type)

    def test_decimal_scale_over_precision_raises(self, dialect):
        data_type = DecimalType(precision=10, scale=11)
        with pytest.raises(ValueError, match="cannot exceed"):
            dialect.format_data_type(data_type)

    def test_decimal_valid_range_renders(self, dialect):
        sql, _ = dialect.format_data_type(DecimalType(precision=18, scale=2))
        assert sql == "DECIMAL(18, 2)"

    def test_float_precision_over_24_raises(self, dialect):
        with pytest.raises(ValueError, match="between 1 and 24"):
            dialect.format_data_type(FloatType(precision=25))

    def test_float_valid_precision_renders(self, dialect):
        sql, _ = dialect.format_data_type(FloatType(precision=24))
        assert sql == "FLOAT(24)"

    def test_float_no_precision_renders(self, dialect):
        sql, _ = dialect.format_data_type(FloatType())
        assert sql == "FLOAT"


class TestFB4TypeGating:
    """FB4-gated types must render on 4.0+ and raise on older."""

    def test_fb4_types_render_on_4_0(self, dialect):
        assert dialect.format_data_type(FirebirdTimeStampTzType()) == (
            "TIMESTAMP WITH TIME ZONE", ()
        )
        assert dialect.format_data_type(FirebirdTimeTzType()) == (
            "TIME WITH TIME ZONE", ()
        )
        assert dialect.format_data_type(FirebirdDecFloatType(precision=16)) == (
            "DECFLOAT(16)", ()
        )
        assert dialect.format_data_type(FirebirdDecFloatType(precision=34)) == (
            "DECFLOAT(34)", ()
        )
        assert dialect.format_data_type(FirebirdInt128Type()) == (
            "INT128", ()
        )

    def test_fb4_types_raise_on_3_0(self, dialect_3):
        for data_type in (
            FirebirdTimeStampTzType(),
            FirebirdTimeTzType(),
            FirebirdDecFloatType(),
            FirebirdInt128Type(),
        ):
            with pytest.raises(Exception):
                dialect_3.format_data_type(data_type)

    def test_fb4_support_flags_gated(self, dialect, dialect_3):
        assert dialect.supports_data_type_firebird_timestamptz() is True
        assert dialect_3.supports_data_type_firebird_timestamptz() is False
        assert dialect.supports_data_type_firebird_timetz() is True
        assert dialect_3.supports_data_type_firebird_timetz() is False
        assert dialect.supports_data_type_firebird_decfloat() is True
        assert dialect_3.supports_data_type_firebird_decfloat() is False
        assert dialect.supports_data_type_firebird_int128() is True
        assert dialect_3.supports_data_type_firebird_int128() is False


class TestDialectOptions:
    """dialect_options forwards through construction and affects equality."""

    def test_construction_forwards_dialect_options(self, dialect):
        data_type = FirebirdDecFloatType(
            dialect=dialect, precision=16,
            dialect_options={"key": "value"},
        )
        assert data_type.dialect_options == {"key": "value"}

    def test_dialect_options_participate_in_equality(self, dialect):
        a = FirebirdDecFloatType(
            dialect=dialect, precision=16,
            dialect_options={"key": "value"},
        )
        b = FirebirdDecFloatType(
            dialect=dialect, precision=16,
            dialect_options={"key": "value"},
        )
        c = FirebirdDecFloatType(
            dialect=dialect, precision=16,
            dialect_options={"key": "other"},
        )
        assert a == b
        assert a != c

    def test_equality_ignores_dialect(self, dialect):
        other = FirebirdDialect()
        assert FirebirdDecFloatType(precision=16) == FirebirdDecFloatType(precision=16)

    def test_semantic_params_drive_equality(self, dialect):
        assert FirebirdDecFloatType(precision=16) != FirebirdDecFloatType(precision=34)
