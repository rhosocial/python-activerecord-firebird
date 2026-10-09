# tests/rhosocial/activerecord_firebird_test/feature/backend/test_firebird_column_suggestion.py
"""Firebird's column-type suggestion table and its operation narrowing.

Pure construction and capability questions -- no database connection.

The two refusals (``dict``, the container family) are the assertions here that
matter most, because they are the two places where Firebird differs from core's
default table and where a silent fallback would be the worst outcome: a ``dict``
field would resolve to ``JSONColumn``, take ``json_path()`` calls that render
``->>``, and fail at the server on 5.0.4 and 6.0.0 alike with ``-104 Token
unknown - ->``. See ``mixins/column_suggestion.py`` for the measurements.
"""

import datetime
import decimal
import enum
import typing
import uuid

import pytest

from rhosocial.activerecord.backend.expression import (
    BinaryColumn,
    BooleanColumn,
    COLUMN_TYPE_ENTRIES,
    ColumnTypeResolutionError,
    DateTimeColumn,
    DecimalColumn,
    FloatColumn,
    IntegerColumn,
    JSONColumn,
    NumericColumn,
    StringColumn,
    UNSUPPORTED,
    UUIDColumn,
)
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect


class Weekday(enum.Enum):
    MONDAY = "monday"


@pytest.fixture(params=[(2, 5, 0), (3, 0, 0), (4, 0, 0), (5, 0, 0), (6, 0, 0)])
def dialect(request):
    """Every Firebird version this backend targets, 2.5 through 6.0.

    Parametrised because the claim under test is that **no cell changes with the
    version**, and a table that is only checked on one server cannot support that
    claim.
    """
    return FirebirdDialect(request.param)


class TestCompleteness:
    """Every protocol entry is answered, and none is left blank."""

    def test_answers_every_entry_of_the_protocol_list(self, dialect):
        assert set(dialect.suggested_column_types()) == set(COLUMN_TYPE_ENTRIES)

    def test_no_entry_is_blank(self, dialect):
        """A hole and a refusal must not look the same.

        ``None`` would be unreadable -- "not filled in yet" and "this backend
        cannot express it" are different facts, and only the second is
        actionable. Every value is either a column class or the sentinel.
        """
        for entry, column_class in dialect.suggested_column_types().items():
            assert column_class is not None, f"{entry!r} is blank"
            assert column_class is UNSUPPORTED or isinstance(column_class, type)

    def test_the_table_is_the_same_on_every_firebird_version(self):
        """The version-independence claim, asserted rather than asserted-in-prose.

        BOOLEAN (3.0) and TIMESTAMP WITH TIME ZONE (4.0) are storage gates and
        live on the DataType side; a column class names an operation set, and
        none of these operations changes shape with the server version. If a
        future Firebird release did change one, this test is where it should be
        noticed and the branch written.
        """
        versions = ((2, 5, 0), (3, 0, 0), (4, 0, 0), (5, 0, 0), (6, 0, 0))
        tables = [FirebirdDialect(version).suggested_column_types() for version in versions]
        assert all(table == tables[0] for table in tables)

    def test_suggested_column_types_returns_a_copy(self, dialect):
        """A caller walking the table cannot corrupt the next resolution."""
        table = dialect.suggested_column_types()
        table.pop(str)
        assert str in dialect.suggested_column_types()


class TestBaseline:
    """The ten-end common baseline, which Firebird confirms entry by entry."""

    @pytest.mark.parametrize(
        "annotation, expected",
        [
            (bool, BooleanColumn),
            (int, IntegerColumn),
            (float, FloatColumn),
            (decimal.Decimal, DecimalColumn),
            (str, StringColumn),
            (bytes, BinaryColumn),
            (bytearray, BinaryColumn),
            (datetime.date, DateTimeColumn),
            (datetime.time, DateTimeColumn),
            (datetime.datetime, DateTimeColumn),
            (datetime.timedelta, NumericColumn),
            (uuid.UUID, UUIDColumn),
            (enum.Enum, StringColumn),
        ],
    )
    def test_entry_resolves_to_its_column_class(self, dialect, annotation, expected):
        assert dialect.column_class_for(annotation) is expected

    def test_tz_aware_datetime_uses_the_temporal_class(self, dialect):
        """A ``datetime`` with a ``tzinfo`` normalises to the same entry.

        The zone is a storage question here -- ``TIMESTAMP`` is Firebird's
        synonym for the WITHOUT TIME ZONE type -- so the operations do not
        differ; see ``FirebirdTypeSupportMixin._LOSSY_SUBSTITUTIONS``.
        """
        aware = datetime.datetime(2026, 10, 9, 12, 0, tzinfo=datetime.timezone.utc)
        assert dialect.column_class_for(type(aware)) is DateTimeColumn

    def test_an_enum_subclass_resolves_to_the_string_class(self, dialect):
        assert dialect.column_class_for(Weekday) is StringColumn


class TestUnsupportedEntries:
    """The two cells Firebird answers ``UNSUPPORTED``, and what they cost."""

    @pytest.mark.parametrize("annotation", [dict, list, tuple, set, frozenset])
    def test_answers_unsupported_for_dict_and_the_container_family(self, dialect, annotation):
        assert dialect.suggested_column_types()[annotation] is UNSUPPORTED

    def test_dict_fails_at_definition_time_naming_UseColumnType(self, dialect):
        """The consequence, asserted rather than documented.

        A model field annotated ``dict`` fails where the field is written, and
        the message points at the escape hatch -- which is the whole point of
        refusing here rather than answering ``JSONColumn`` and failing at the
        database with ``-104 Token unknown - ->``.
        """
        with pytest.raises(ColumnTypeResolutionError) as excinfo:
            dialect.column_class_for(dict)
        assert "UseColumnType" in str(excinfo.value)

    def test_the_refusal_names_the_dialect_and_the_entry(self, dialect):
        with pytest.raises(ColumnTypeResolutionError) as excinfo:
            dialect.column_class_for(dict)
        message = str(excinfo.value)
        assert type(dialect).__name__ in message
        assert "UNSUPPORTED" in message

    @pytest.mark.parametrize("annotation", [list, tuple, set, frozenset])
    def test_the_container_family_fails_at_definition_time_too(self, dialect, annotation):
        """Firebird's array columns exist; declaring one from here does not.

        ``ARR_INT INTEGER [4]`` is real Firebird, but the bounds are part of the
        type and core's ``ArrayType`` carries only a dimensionality, so there is
        nothing this framework could write. See the module docstring.
        """
        with pytest.raises(ColumnTypeResolutionError) as excinfo:
            dialect.column_class_for(annotation)
        assert "UseColumnType" in str(excinfo.value)

    def test_optional_dict_is_peeled_before_the_lookup(self, dialect):
        """``Optional[dict]`` normalises to ``dict`` and gets the same refusal."""
        with pytest.raises(ColumnTypeResolutionError):
            dialect.column_class_for(typing.Optional[dict])

    def test_unsupported_entries_property_lists_exactly_those_five(self, dialect):
        assert dialect.unsupported_column_entries == {dict, list, tuple, set, frozenset}


class TestEscapeHatch:
    """An explicit declaration bypasses the table -- and what it really buys."""

    def test_explicit_declaration_bypasses_the_unsupported_entry(self, dialect):
        from rhosocial.activerecord.base.fields import UseColumnType

        assert dialect.column_class_for(dict, UseColumnType(JSONColumn)) is JSONColumn

    def test_the_hatch_is_a_declaration_not_a_repair(self, dialect):
        """Declaring ``JSONColumn`` here buys a text column, and the narrowing says so.

        On Firebird the honest operations for a declared ``JSONColumn`` are
        whole-document equality and CAST: ``json_path`` / ``json_value`` are both
        refused below, and no released server has the JSON functions.
        """
        assert dialect.supports_column_operation("JSONColumn", "json_path") is False
        assert dialect.supports_column_operation("JSONColumn", "json_value") is False


class TestOperationNarrowing:
    """``supports_column_operation`` -- narrowings are enumerable and exact."""

    def test_ilike_is_unavailable_and_like_is_not(self, dialect):
        """The one narrowing the protocol's own table names for Firebird.

        Measured ``-104 Token unknown`` for ``ILIKE`` on 5.0.4 and 6.0.0. ``LIKE``
        is measured working on both, so it is not narrowed. ``CONTAINING`` and
        ``SIMILAR TO`` (4.0+) are the dialect-native substitutes, and ``SIMILAR
        TO`` is SQL wildcard syntax rather than a regular expression, so neither
        is ``ilike`` under another name.
        """
        assert dialect.supports_column_operation("StringColumn", "ilike") is False
        assert dialect.supports_column_operation("StringColumn", "like") is True

    @pytest.mark.parametrize(
        "column_name, op",
        [
            ("JSONColumn", "json_path"),
            ("JSONColumn", "json_value"),
            ("ArrayColumn", "array_length"),
            ("ArrayColumn", "unnest"),
        ],
    )
    def test_json_and_array_operations_are_narrowed(self, dialect, column_name, op):
        assert dialect.supports_column_operation(column_name, op) is False

    def test_narrowings_are_exactly_the_declared_set(self, dialect):
        """An exhaustive set, so a new narrowing cannot be added unasserted."""
        assert dialect.UNAVAILABLE_COLUMN_OPERATIONS == frozenset(
            {
                ("StringColumn", "ilike"),
                ("JSONColumn", "json_path"),
                ("JSONColumn", "json_value"),
                ("ArrayColumn", "array_length"),
                ("ArrayColumn", "unnest"),
            }
        )

    def test_comparison_and_cast_are_never_narrowed(self, dialect):
        """What Firebird does support stays available.

        Whole-document equality and ``CAST`` are the two operations measured
        working on a ``BLOB SUB_TYPE TEXT`` document, which is why the declared
        ``JSONColumn`` escape hatch is not a fiction.
        """
        assert dialect.supports_column_operation("JSONColumn", "cast") is True
        assert dialect.supports_column_operation("StringColumn", "upper") is True
        assert dialect.supports_column_operation("StringColumn", "length") is True

    def test_length_is_not_narrowed_for_the_charset_reason(self, dialect):
        """``length`` counts characters *for a column that declares a charset*.

        With no ``CHARACTER SET`` it counts bytes -- ``VARCHAR(5)`` rejects 9
        bytes -- but that is a property of the column's declaration, not a
        missing operation, so it is recorded rather than narrowed away.
        """
        assert dialect.supports_column_operation("StringColumn", "length") is True
        assert dialect.supports_column_operation("StringColumn", "octet_length") is True