# tests/rhosocial/activerecord_firebird_test/feature/backend/test_object_kind_checks.py
"""A statement given the wrong kind of catalogue object is refused at render time.

Every object here carries its own ``format_method``, so the dialect dispatches on
what the caller passed rather than on what the statement meant. Before these
checks, a wrong kind was not an error at all: it rendered valid SQL naming the
wrong thing. ``CreateSequenceExpression(d, Table(d, "users"))`` produced a
well-formed ``CREATE SEQUENCE`` whose name was a table, because the dialect
reached ``format_table_object`` and got SQL it was happy with.

The check lives in the formatter, not the constructor, and that placement is the
point worth keeping:

* at construction the dialect may not be settled yet -- the testsuite builds
  ``Table(None, "ddl_spec_orders")`` for a foreign-key fixture and binds the
  dialect later -- and the slots may not be filled, so a constructor cannot
  decide; and
* the formatter can say *both* things at once, that this is a type error and
  that this dialect cannot spell that kind of object.

So the tests below assert two things per statement, and neither alone is
enough. The wrong kind must raise ``TypeError`` naming the field, and the right
kind must still render -- otherwise a check that refuses everything would pass
every one of these.
"""

import pytest

from rhosocial.activerecord.backend.expression.core import Column, Literal
from rhosocial.activerecord.backend.expression.objects import (
    Domain,
    Function,
    Sequence,
    Table,
    Trigger,
    View,
)
from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate
from rhosocial.activerecord.backend.expression.sources import NamedRelationRef
from rhosocial.activerecord.backend.expression.statements import (
    ColumnDefinition,
    ddl_alter,
    ddl_domain,
    ddl_sequence,
    ddl_table,
    ddl_trigger,
    dml,
)
from rhosocial.activerecord.backend.expression.statements.ddl_domain import (
    RenameDomainAction,
)
from rhosocial.activerecord.backend.expression.statements.ddl_trigger import (
    TriggerEvent,
    TriggerTiming,
)
from rhosocial.activerecord.backend.expression.types import IntegerType
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect


@pytest.fixture
def dialect():
    return FirebirdDialect(version=(4, 0, 0))


def _column(d):
    return ColumnDefinition(d, "id", IntegerType(d))


def _predicate(d):
    return ComparisonPredicate(d, "=", Column(d, "a"), Column(d, "b"))


#: ``(label, build, make_right, make_wrong, field)``
#:
#: Each entry builds a statement this backend's own formatter renders, once with
#: the object kind the statement documents and once with a neighbouring kind.
#: Both halves are asserted in the same test, which is what makes the guard
#: non-vacuous: a formatter that raised ``TypeError`` unconditionally, or one
#: that checked nothing, would fail one half or the other.
WRONG_KIND_CASES = [
    (
        "create_sequence",
        lambda d, obj: ddl_sequence.CreateSequenceExpression(d, obj),
        lambda d: Sequence(d, "gen"),
        lambda d: Table(d, "users"),
        "CreateSequenceExpression.sequence",
    ),
    (
        "create_table",
        lambda d, obj: ddl_table.CreateTableExpression(d, obj, [_column(d)]),
        lambda d: Table(d, "users"),
        lambda d: View(d, "users"),
        "CreateTableExpression.table",
    ),
    (
        "alter_table",
        lambda d, obj: ddl_alter.AlterTableExpression(d, obj, []),
        lambda d: Table(d, "users"),
        lambda d: Sequence(d, "gen"),
        "AlterTableExpression.table",
    ),
    (
        "insert",
        lambda d, obj: dml.InsertExpression(
            d, into=obj, source=dml.ValuesSource(d, [[Literal(d, 1)]])
        ),
        lambda d: Table(d, "users"),
        lambda d: Sequence(d, "gen"),
        "InsertExpression.into",
    ),
    (
        "update",
        lambda d, obj: dml.UpdateExpression(d, obj, {"a": Literal(d, 1)}),
        lambda d: Table(d, "users"),
        lambda d: Sequence(d, "gen"),
        "UpdateExpression.table",
    ),
    (
        "delete",
        lambda d, obj: dml.DeleteExpression(d, [obj]),
        lambda d: Table(d, "users"),
        lambda d: Sequence(d, "gen"),
        "DeleteExpression.tables",
    ),
    (
        "merge",
        lambda d, obj: dml.MergeExpression(
            d,
            target_table=obj,
            source=NamedRelationRef(d, Table(d, "src")),
            on_condition=_predicate(d),
        ),
        lambda d: Table(d, "users"),
        lambda d: Sequence(d, "gen"),
        "MergeExpression.target_table",
    ),
    (
        "create_domain",
        lambda d, obj: ddl_domain.CreateDomainExpression(d, obj, IntegerType(d)),
        lambda d: Domain(d, "dom"),
        lambda d: Table(d, "users"),
        "CreateDomainExpression.domain",
    ),
    (
        "alter_domain",
        lambda d, obj: ddl_domain.AlterDomainExpression(
            d, obj, [RenameDomainAction(d, "other")]
        ),
        lambda d: Domain(d, "dom"),
        lambda d: Table(d, "users"),
        "AlterDomainExpression.domain",
    ),
]

CASE_IDS = [case[0] for case in WRONG_KIND_CASES]


class TestWrongObjectKindIsRefused:
    """Each statement refuses a wrong object kind by name, and still renders the right one."""

    @pytest.mark.parametrize(
        "label,build,make_right,make_wrong,field", WRONG_KIND_CASES, ids=CASE_IDS
    )
    def test_wrong_kind_raises_and_right_kind_renders(
        self, dialect, label, build, make_right, make_wrong, field
    ):
        # -- the right kind must still produce SQL. This is the half that stops a
        #    guard from being "always raise and call it a check".
        right_sql, _ = build(dialect, make_right(dialect)).to_sql()
        assert right_sql, f"{label}: the documented object kind rendered nothing"

        # -- the wrong kind must be refused, by name, so a caller can see which
        #    argument is at fault.
        with pytest.raises(TypeError) as exc_info:
            build(dialect, make_wrong(dialect)).to_sql()
        message = str(exc_info.value)
        assert field in message, (
            f"{label}: the error names {message!r}, which does not point at "
            f"{field!r} -- a caller has to be able to see which argument is wrong"
        )

    @pytest.mark.parametrize(
        "label,build,make_right,make_wrong,field", WRONG_KIND_CASES, ids=CASE_IDS
    )
    def test_the_two_kinds_produce_different_sql(
        self, dialect, label, build, make_right, make_wrong, field
    ):
        """Right and wrong kinds must not be indistinguishable.

        Before the guard, the wrong kind produced the wrong-but-well-formed SQL.
        Now it produces none, so the two outcomes differ -- which is the whole
        point, and which a check that only fired sometimes would not satisfy.
        """
        right_sql, _ = build(dialect, make_right(dialect)).to_sql()
        try:
            build(dialect, make_wrong(dialect)).to_sql()
        except TypeError as exc:
            wrong_outcome = str(exc)
        else:
            pytest.fail(
                f"{label}: a wrong object kind rendered {right_sql!r} with no "
                f"error -- the statement named the wrong thing and said nothing"
            )
        assert wrong_outcome != right_sql

    def test_create_trigger_refuses_a_table_where_a_trigger_belongs(self, dialect):
        expr = ddl_trigger.CreateTriggerExpression(
            dialect,
            trigger=Table(dialect, "trg"),
            table=Table(dialect, "users"),
            timing=TriggerTiming.BEFORE,
            events=[TriggerEvent.INSERT],
            function=Function(dialect, "fn"),
        )
        with pytest.raises(TypeError, match=r"CreateTriggerExpression\.trigger"):
            expr.to_sql()

    def test_create_trigger_refuses_a_trigger_where_a_relation_belongs(self, dialect):
        expr = ddl_trigger.CreateTriggerExpression(
            dialect,
            trigger=Trigger(dialect, "trg"),
            table=Trigger(dialect, "other"),
            timing=TriggerTiming.BEFORE,
            events=[TriggerEvent.INSERT],
            function=Function(dialect, "fn"),
        )
        with pytest.raises(TypeError, match=r"CreateTriggerExpression\.table"):
            expr.to_sql()

    @pytest.mark.parametrize(
        "make_wrong,expected",
        [
            (lambda d: Sequence(d, "gen"), "Sequence"),
            (lambda d: View(d, "v"), "View"),
            (lambda d: Domain(d, "dom"), "Domain"),
            (lambda d: 42, "int"),
        ],
        ids=["sequence", "view", "domain", "plain-int"],
    )
    def test_table_reference_refuses_anything_but_a_table_or_a_string(
        self, dialect, make_wrong, expected
    ):
        with pytest.raises(TypeError) as exc_info:
            dialect.format_table_reference(make_wrong(dialect))
        assert expected in str(exc_info.value)

    def test_delete_names_the_position_of_the_bad_entry(self, dialect):
        """A list parameter says *where*, which a single field name cannot.

        Every entry is checked, so a bad entry cannot hide behind a good one at
        position 0 -- and the message names the position rather than leaving the
        caller to work out which one was wrong.
        """
        expr = dml.DeleteExpression(dialect, [Table(dialect, "ok"), Sequence(dialect, "gen")])
        with pytest.raises(TypeError) as exc_info:
            expr.to_sql()
        message = str(exc_info.value)
        assert "DeleteExpression.tables" in message
        assert "Sequence" in message
        assert "position 1" in message, (
            f"the message names the position only as {message!r}; a caller with a "
            f"list of targets cannot act on 'some entry is wrong'"
        )


class TestRightObjectKindStillRenders:
    """The documented object kinds produce the SQL a caller would read.

    The parametrized pair above already refuses a wrong kind and renders a right
    one; these pin the *text*, so a guard added in the wrong place -- one that
    renders and then complains, or one that changes the spelling -- is caught.
    """

    def test_create_sequence(self, dialect):
        # The dispatched formatter is Firebird's own
        # ``format_create_sequence_statement``, reached because
        # ``FirebirdSequenceMixin`` precedes ``SequenceMixin`` in the bases. It
        # never emits ``NO CYCLE``: Firebird's grammar has no such words.
        sql, params = ddl_sequence.CreateSequenceExpression(
            dialect, Sequence(dialect, "gen")
        ).to_sql()
        assert sql == 'CREATE SEQUENCE "GEN"'
        assert params == ()

    def test_create_sequence_is_guarded_on_the_path_that_actually_runs(self, dialect):
        """The dispatched formatter refuses a wrong object kind.

        The same guard is asserted through ``to_sql()`` and through a direct
        call, so a rename that put the method out of the dispatch's reach would
        show up as a ``TypeError`` from the wrong place.
        """
        wrong = ddl_sequence.CreateSequenceExpression(dialect, Table(dialect, "users"))
        with pytest.raises(TypeError, match=r"CreateSequenceExpression\.sequence"):
            wrong.to_sql()
        with pytest.raises(TypeError, match=r"CreateSequenceExpression\.sequence"):
            dialect.format_create_sequence_statement(wrong)

    def test_create_table(self, dialect):
        sql, _ = ddl_table.CreateTableExpression(
            dialect, Table(dialect, "users"), [_column(dialect)]
        ).to_sql()
        assert sql == 'CREATE TABLE "USERS" ("ID" INTEGER)'

    def test_alter_table(self, dialect):
        sql, _ = ddl_alter.AlterTableExpression(dialect, Table(dialect, "users"), []).to_sql()
        assert sql == 'ALTER TABLE "USERS"'

    def test_insert(self, dialect):
        sql, params = dml.InsertExpression(
            dialect,
            into=Table(dialect, "users"),
            source=dml.ValuesSource(dialect, [[Literal(dialect, 1)]]),
        ).to_sql()
        assert sql == 'INSERT INTO "USERS"  VALUES (?)'
        assert params == (1,)

    def test_update(self, dialect):
        sql, params = dml.UpdateExpression(
            dialect, Table(dialect, "users"), {"a": Literal(dialect, 1)}
        ).to_sql()
        assert sql == 'UPDATE "USERS" SET "A" = ?'
        assert params == (1,)

    def test_delete(self, dialect):
        sql, _ = dml.DeleteExpression(dialect, [Table(dialect, "users")]).to_sql()
        assert sql == 'DELETE FROM "USERS"'

    def test_create_domain(self, dialect):
        sql, _ = ddl_domain.CreateDomainExpression(
            dialect, Domain(dialect, "dom"), IntegerType(dialect)
        ).to_sql()
        assert sql == 'CREATE DOMAIN "DOM" AS INTEGER'

    def test_alter_domain(self, dialect):
        sql, _ = ddl_domain.AlterDomainExpression(
            dialect, Domain(dialect, "dom"), [RenameDomainAction(dialect, "other")]
        ).to_sql()
        assert sql == 'ALTER DOMAIN "DOM" TO "OTHER"'

    def test_create_trigger(self, dialect):
        sql, _ = ddl_trigger.CreateTriggerExpression(
            dialect,
            trigger=Trigger(dialect, "trg"),
            table=Table(dialect, "users"),
            timing=TriggerTiming.BEFORE,
            events=[TriggerEvent.INSERT],
            function=Function(dialect, "fn"),
        ).to_sql()
        assert sql.startswith('CREATE TRIGGER "TRG"')
        assert 'ON "USERS"' in sql

    @pytest.mark.parametrize(
        "make_ref,expected",
        [
            (lambda d: Table(d, "users"), '"USERS"'),
            (lambda d: "users", '"USERS"'),
        ],
        ids=["table-object", "bare-string"],
    )
    def test_table_reference_accepts_both_documented_shapes(self, dialect, make_ref, expected):
        assert dialect.format_table_reference(make_ref(dialect)) == expected


class TestStringIsAcceptedOnlyWhereItIsDocumented:
    """One formatter takes a bare str on purpose; the rest do not.

    The ORM layer hands the backend a bare table name and there is nothing else
    it could mean, so ``format_table_reference`` wraps a ``str`` rather than
    refusing it. That is the single exception, and it is why that guard is a
    union rather than an ``isinstance`` -- and why the other formatters, which
    are handed an object by contract, refuse it.
    """

    def test_table_reference_wraps_a_bare_string(self, dialect):
        assert dialect.format_table_reference("users") == '"USERS"'

    @pytest.mark.parametrize("value", [42, None, ["users"]])
    def test_table_reference_refuses_everything_else(self, dialect, value):
        with pytest.raises(TypeError, match="format_table_reference"):
            dialect.format_table_reference(value)

    def test_table_reference_refuses_a_neighbouring_object_kind(self, dialect):
        """A Sequence is the near miss: it is an object, and renders happily."""
        with pytest.raises(TypeError) as exc_info:
            dialect.format_table_reference(Sequence(dialect, "gen"))
        assert "Sequence" in str(exc_info.value)

