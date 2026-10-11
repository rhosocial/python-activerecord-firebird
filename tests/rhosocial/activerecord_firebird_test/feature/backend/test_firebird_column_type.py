# tests/rhosocial/activerecord_firebird_test/feature/backend/test_firebird_column_type.py
"""Firebird's column-type table: completeness, refusals, and what they cost.

Pure construction and capability questions -- no database connection.

The five ``None`` answers (``dict``, the container family) are the assertions
here that matter most, because they are the only places where Firebird differs
from a portable baseline and where a silent fallback would be the worst
outcome: a ``dict`` field would resolve to ``JSONColumn``, take ``json_path()``
calls that render ``->>``, and fail at the server on 5.0.4 and 6.0.0 alike with
``-104 Token unknown - ->``. See ``mixins/column_type.py`` for the measurements.

The protocol has no inherited table, so completeness is a *contract this test
states*: the common types are listed here, in the framework's reading order, and
held against the dialect's answer.
"""

import datetime
import decimal
import enum
import typing
import uuid
from typing import Any, Tuple

import pytest

from rhosocial.activerecord.backend.dialect.mixins import ColumnTypeMixin
from rhosocial.activerecord.backend.expression.column_types import (
    BinaryColumn,
    BooleanColumn,
    ColumnBase,
    IntegerColumn,
    JSONColumn,
    NumericColumn,
    StringColumn,
    TimestampColumn,
    UUIDColumn,
)
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.mixins import (
    FirebirdColumnTypeMixin,
)
from rhosocial.activerecord.base.field_proxy import (
    ColumnTypeResolutionError,
    FieldAccessor,
)
from rhosocial.activerecord.base.fields import UseColumnType

#: The framework's common Python types, in declared reading order. The order is
#: the protocol's: ``bool`` ahead of ``int`` (a truth value is not an integer)
#: and ``enum.Enum`` before the subclass walk (a ``(int, Enum)`` stays an enum).
COMMON_TYPES: Tuple[Any, ...] = (
    bool,
    int,
    float,
    decimal.Decimal,
    str,
    bytes,
    bytearray,
    datetime.date,
    datetime.time,
    datetime.datetime,
    datetime.timedelta,
    uuid.UUID,
    dict,
    list,
    tuple,
    set,
    frozenset,
    enum.Enum,
)

#: The entries Firebird answers ``None`` for. Five, and every one of them is
#: deliberate -- see :mod:`...mixins.column_type` for the measurements.
FIREBIRD_REFUSALS = frozenset({dict, list, tuple, set, frozenset})

_ENTRY_IDS = [getattr(entry, "__name__", str(entry)) for entry in COMMON_TYPES]

#: The thirteen entries Firebird answers with a real column class -- the
#: eighteen, minus the five deliberate refusals.
_ANSWERED_TYPES = tuple(e for e in COMMON_TYPES if e not in FIREBIRD_REFUSALS)
_ANSWERED_IDS = [getattr(entry, "__name__", str(entry)) for entry in _ANSWERED_TYPES]


class Weekday(enum.Enum):
    MONDAY = "monday"


def resolve(dialect: FirebirdDialect, annotation: Any, declared: Any = None):
    """The model layer's own selection step, invoked without a model.

    Reading the table directly would miss everything the selection adds: the
    peel of ``Optional``/``Annotated``, the enum branch, the subclass walk, and
    the refusal a ``None`` answer produces.
    """
    return FieldAccessor._select_column_class(dialect, annotation, declared)


@pytest.fixture(params=[(2, 5, 0), (3, 0, 0), (4, 0, 0), (5, 0, 0), (6, 0, 0)])
def dialect(request):
    """Every Firebird version this backend targets, 2.5 through 6.0.

    Parametrised because the claim under test is that **no cell changes with the
    version**, and a table that is only checked on one server cannot support that
    claim.
    """
    return FirebirdDialect(request.param)


class TestCompleteness:
    """Every protocol entry is answered, and every refusal is a decision."""

    def test_answers_every_entry_of_the_protocol_list(self, dialect):
        assert set(dialect.suggested_column_types()) == set(COMMON_TYPES)

    @pytest.mark.parametrize("entry", COMMON_TYPES, ids=_ENTRY_IDS)
    def test_every_entry_is_answered_with_a_class_or_a_deliberate_none(
        self, dialect, entry
    ):
        """An answer is a class or ``None``; nothing else, and never a blank.

        A hole (a key the table does not carry) and a refusal (a key answered
        ``None``) are different facts, and only the second is actionable. Every
        key is here, so a hole would already have failed the test above; this one
        keeps the *value* honest as well.
        """
        table = dialect.suggested_column_types()
        assert entry in table
        answer = table[entry]
        if answer is None:
            assert entry in FIREBIRD_REFUSALS, f"{entry!r} answers None undeliberately"
            return
        assert isinstance(answer, type) and issubclass(answer, ColumnBase)

    def test_the_refusals_are_exactly_the_measured_five(self, dialect):
        """``None`` is the last resort, so the set of them must stay small.

        Enumerated rather than counted: an entry that drifts into a refusal is
        exactly the regression this assertion exists to name.
        """
        table = dialect.suggested_column_types()
        assert {e for e, c in table.items() if c is None} == FIREBIRD_REFUSALS
        assert dialect.unsupported_column_entries == FIREBIRD_REFUSALS

    def test_a_refusal_is_not_propagated_to_the_other_entries(self, dialect):
        """One ``None`` must not make the whole backend unusable.

        A single bad cell would otherwise be indistinguishable from a backend
        that answers nothing at all.
        """
        assert resolve(dialect, str) is StringColumn
        assert resolve(dialect, int) is IntegerColumn

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

    def test_the_extras_table_defaults_to_nothing(self, dialect):
        """Firebird models no Python type of its own beyond the common ones.

        The core default is ``{}``; overriding it to say the same thing would be
        a second place to keep in step.
        """
        assert dialect.suggested_extra_column_types() == {}


class TestComposition:
    """The dialect really does answer with *Firebird's* table."""

    def test_the_dialect_composes_the_mixin(self, dialect):
        assert issubclass(FirebirdDialect, FirebirdColumnTypeMixin)
        assert isinstance(dialect, FirebirdColumnTypeMixin)

    def test_the_answer_is_the_firebird_one_not_an_inherited_stub(self):
        """``ColumnTypeMixin`` supplies no table, so a mix-up would be loud.

        The consequence of the composition is asserted through the method
        identity: were ``FirebirdColumnTypeMixin`` dropped from the base list,
        ``suggested_column_types`` would resolve to core's raising default
        instead of Firebird's table.
        """
        assert FirebirdColumnTypeMixin.__bases__ == (ColumnTypeMixin,)
        assert (
            FirebirdDialect.suggested_column_types
            is FirebirdColumnTypeMixin.suggested_column_types
        )

    def test_core_withholds_any_inherited_table(self):
        """The rebuild's own ruling, restated against this backend's base.

        ``ColumnTypeMixin`` has no default table: an entry a dialect does not
        answer is reported against the dialect's name, never filled in from a
        core-side guess about a server core has never seen.
        """

        class Bare(ColumnTypeMixin):
            pass

        with pytest.raises(NotImplementedError):
            Bare().suggested_column_types()
        assert Bare().suggested_extra_column_types() == {}


class TestBaseline:
    """The common baseline, which Firebird confirms entry by entry."""

    @pytest.mark.parametrize(
        "annotation, expected",
        [
            (bool, BooleanColumn),
            (int, IntegerColumn),
            (float, NumericColumn),
            (decimal.Decimal, NumericColumn),
            (str, StringColumn),
            (bytes, BinaryColumn),
            (bytearray, BinaryColumn),
            (datetime.date, TimestampColumn),
            (datetime.time, TimestampColumn),
            (datetime.datetime, TimestampColumn),
            (datetime.timedelta, NumericColumn),
            (uuid.UUID, UUIDColumn),
            (enum.Enum, StringColumn),
        ],
    )
    def test_entry_resolves_to_its_column_class(self, dialect, annotation, expected):
        assert resolve(dialect, annotation) is expected

    @pytest.mark.parametrize("entry", _ANSWERED_TYPES, ids=_ANSWERED_IDS)
    def test_every_answered_class_can_be_built_and_renders(self, dialect, entry):
        """A table answer is only real if the column it names can be built.

        The selection answering correctly and the object refusing to build would
        leave the failure at query time, with a message about a column rather
        than about the annotation. The five refused entries are excluded on
        purpose: they are asserted above to fail *here*, at the selection step.
        """
        column_class = resolve(dialect, entry)
        column = column_class(dialect, "c")
        assert isinstance(column, ColumnBase)
        assert column.to_sql() == ('"C"', ())

    def test_bool_is_its_own_entry_not_an_integer(self, dialect):
        """``bool`` is an ``int`` subclass; the entry order is what keeps them apart.

        Without the order, ``bool`` would walk to ``int`` and a truth-value field
        would offer integer arithmetic.
        """
        assert COMMON_TYPES.index(bool) < COMMON_TYPES.index(int)
        assert resolve(dialect, bool) is not resolve(dialect, int)

    def test_tz_aware_datetime_uses_the_temporal_class(self, dialect):
        """A ``datetime`` with a ``tzinfo`` normalises to the same entry.

        The zone is a storage question here -- ``TIMESTAMP`` is Firebird's
        synonym for the WITHOUT TIME ZONE type -- so the operations do not
        differ; see ``FirebirdTypeSupportMixin._LOSSY_SUBSTITUTIONS``.
        """
        aware = datetime.datetime(2026, 10, 9, 12, 0, tzinfo=datetime.timezone.utc)
        assert resolve(dialect, type(aware)) is TimestampColumn

    def test_an_enum_subclass_resolves_to_the_string_class(self, dialect):
        assert resolve(dialect, Weekday) is StringColumn


class TestRefusedEntries:
    """The five cells Firebird answers ``None``, and what they cost."""

    @pytest.mark.parametrize("annotation", sorted(FIREBIRD_REFUSALS, key=lambda c: c.__name__))
    def test_the_table_answers_none(self, dialect, annotation):
        assert dialect.suggested_column_types()[annotation] is None

    def test_dict_fails_at_definition_time_naming_UseColumnType(self, dialect):
        """The consequence, asserted rather than documented.

        A model field annotated ``dict`` fails where the field is written, and
        the message points at the escape hatch -- which is the whole point of
        refusing here rather than answering ``JSONColumn`` and failing at the
        database with ``-104 Token unknown - ->``.
        """
        with pytest.raises(ColumnTypeResolutionError) as excinfo:
            resolve(dialect, dict)
        message = str(excinfo.value)
        assert "UseColumnType" in message
        assert type(dialect).__name__ in message
        assert "no column class" in message

    @pytest.mark.parametrize("annotation", [list, tuple, set, frozenset])
    def test_the_container_family_fails_at_definition_time_too(self, dialect, annotation):
        """Firebird's array columns exist; declaring one from here does not.

        ``ARR_INT INTEGER [4]`` is real Firebird, but the bounds are part of the
        type and core's ``ArrayType`` carries only a dimensionality, so there is
        nothing this framework could write. See the module docstring.
        """
        with pytest.raises(ColumnTypeResolutionError) as excinfo:
            resolve(dialect, annotation)
        assert "UseColumnType" in str(excinfo.value)

    def test_optional_dict_is_peeled_before_the_lookup(self, dialect):
        """``Optional[dict]`` normalises to ``dict`` and gets the same refusal."""
        with pytest.raises(ColumnTypeResolutionError):
            resolve(dialect, typing.Optional[dict])

    def test_an_unregistered_custom_class_still_fails(self, dialect):
        """A class the framework does not model is unclassifiable, not a string.

        The refusal above is a decision about a *known* value family; this one is
        the ordinary "nobody answers for this annotation" path, so the two must
        not be conflated.
        """
        with pytest.raises(ColumnTypeResolutionError, match="Cannot choose a column class"):
            resolve(dialect, type("Money", (), {}))


class TestEscapeHatch:
    """An explicit declaration bypasses the table -- and what it really buys."""

    def test_explicit_declaration_bypasses_the_refused_entry(self, dialect):
        assert resolve(dialect, dict, UseColumnType(JSONColumn)) is JSONColumn

    def test_the_hatch_is_a_declaration_not_a_repair(self, dialect):
        """Declaring ``JSONColumn`` here buys a text column, and the evidence says so.

        On Firebird the honest operations for a declared ``JSONColumn`` are
        whole-document equality and CAST: no released server has the JSON path
        functions, so the accessor surface a caller gets from the class is not
        renderable. That is recorded in ``mixins/column_type.py`` rather than
        papered over by answering a column class the server cannot serve.
        """
        assert dialect.suggested_column_types()[dict] is None
        assert hasattr(JSONColumn, "json_path")
        assert hasattr(JSONColumn, "json_value")
