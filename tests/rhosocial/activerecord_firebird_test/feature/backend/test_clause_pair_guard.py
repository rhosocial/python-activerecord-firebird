# tests/rhosocial/activerecord_firebird_test/feature/backend/test_clause_pair_guard.py
"""Guard: the four states of every two-spelling clause pair Firebird consumes.

The round's rule: each spellable alternative has its own parameter, "unspecified"
is the state where none of the pair's parameters is set, and setting both raises
``ValueError`` at construction. The parameter selects the *spelling*; the
capability probe answers whether Firebird can express the option at all. A
spelling the server cannot express must be refused **by name** -- never dropped.

Firebird's grammar has no spelling for either side of every *declined* pair this
file covers (measured on 5.0.4 and 6.0.0; see the probes' docstrings), so the
four states through ``FirebirdDialect`` are:

====================  ==================================================
neither parameter     neither spelling rendered (the statement renders)
parameter A           ``UnsupportedFeatureError`` naming A's option
parameter B           ``UnsupportedFeatureError`` naming B's option
both parameters       ``ValueError`` at construction
====================  ==================================================

The lock-wait pair is the exception: ``WAIT`` and ``NO WAIT`` both prepare on
5.0.4 and 6.0.0 (measured), so its A/B states render the spelling instead of
refusing it. A case marks that with ``capable=True``, and its probe must answer
``True`` -- an answer that disagrees with the renderer is the defect.

A formatter that ignores one of the pair's parameters collapses state B into
"neither": the request is silently dropped and this file fails. That is the
defect the round exists to eliminate.

One pair is mandatory in its grammar rather than optional:
``AlterConstraint.enforced`` / ``not_enforced`` -- the action *is* the
enforcement keyword, so "neither" is refused as well. That case carries
``neither_error`` and is asserted accordingly.

The patterns are sentinels: ``TestPatternsMatchTheRealSpellings`` renders every
pair through ``DummyDialect`` (the switchboard that declares every capability
``True``) and asserts the patterns match the real spellings there. A pattern
that was wrong would fail that class, so a green guard cannot mean "the regex
never matches anything".

The final classes pin the nodes' parameter inventories: if core adds a
parameter to ``CreateSequenceExpression``, ``IdentityClause`` or
``TableConstraint`` and this backend does not consume it, the pins go red.
"""

import inspect
import re

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.core import Column
from rhosocial.activerecord.backend.expression.objects import (
    Function,
    MaterializedView,
    Sequence,
    Table,
    View,
)
from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate
from rhosocial.activerecord.backend.expression.query_sources import CTEExpression
from rhosocial.activerecord.backend.expression.statements.ddl_function import (
    DropFunctionExpression,
)
from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
    AlterConstraint,
)
from rhosocial.activerecord.backend.expression.statements.ddl_sequence import (
    AlterSequenceExpression,
    CreateSequenceExpression,
)
from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    CreateTableAsExpression,
    DropTableExpression,
    ForeignKeyConstraint,
    IdentityClause,
    TableConstraint,
    TableConstraintType,
)
from rhosocial.activerecord.backend.expression.statements.ddl_truncate import (
    TruncateExpression,
)
from rhosocial.activerecord.backend.expression.statements.ddl_view import (
    CreateMaterializedViewExpression,
    DropViewExpression,
    RefreshMaterializedViewExpression,
)
from rhosocial.activerecord.backend.expression.statements.dql import QueryExpression
from rhosocial.activerecord.backend.expression.transaction import (
    BeginTransactionExpression,
    SetTransactionExpression,
)
from rhosocial.activerecord.backend.impl.dummy.dialect import DummyDialect
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.mixins.cte import (
    FirebirdCTEMixin,
)
from rhosocial.activerecord.backend.impl.firebird.mixins.sequence import (
    FirebirdSequenceMixin,
)
from rhosocial.activerecord.backend.impl.firebird.mixins.ddl_table import (
    FirebirdTableMixin,
)
from rhosocial.activerecord.backend.impl.firebird.mixins.transaction import (
    FirebirdTransactionMixin,
)
from rhosocial.activerecord.backend.impl.firebird.mixins.truncate import (
    FirebirdTruncateMixin,
)


def _dialect():
    """The dialect the live suites target (Firebird 5)."""
    return FirebirdDialect((5, 0, 0))


def _table(d, name="t"):
    return Table(d, name)


def _fk(d, **kw):
    return ForeignKeyConstraint(
        d,
        columns=["a"],
        foreign_key_table=_table(d, "t2"),
        foreign_key_columns=["b"],
        name="fk",
        **kw,
    )


def _check(d, **kw):
    return TableConstraint(
        d,
        TableConstraintType.CHECK,
        name="ck",
        check_condition=ComparisonPredicate(d, ">", Column(d, "a"), Column(d, "b")),
        **kw,
    )


class PairCase:
    """One two-spelling clause pair, its builder and its refusal evidence.

    ``capable=True`` marks a pair both of whose spellings the server accepts:
    the A/B states render (and the probe must answer ``True``) instead of
    raising. The default is the declined case.
    """

    def __init__(
        self,
        case_id,
        builder,
        a,
        b,
        a_pattern,
        b_pattern,
        a_feature,
        b_feature=None,
        a_probe=None,
        b_probe=None,
        a_value=True,
        b_value=True,
        neither_error=None,
        capable=False,
    ):
        self.case_id = case_id
        self.builder = builder
        self.a = a
        self.b = b
        self.a_pattern = re.compile(a_pattern)
        self.b_pattern = re.compile(b_pattern)
        self.a_feature = a_feature
        self.b_feature = b_feature or a_feature
        self.a_probe = a_probe
        self.b_probe = b_probe or a_probe
        self.a_value = a_value
        self.b_value = b_value
        self.neither_error = neither_error
        self.capable = capable

    def render(self, dialect, **kwargs):
        sql, _params = self.builder(dialect, **kwargs).to_sql()
        return sql

    def matches_a(self, sql):
        return bool(self.a_pattern.search(sql))

    def matches_b(self, sql):
        return bool(self.b_pattern.search(sql))


#: Positive fragments use a negative lookbehind where the positive spelling is a
#: substring of the negative one ("CYCLE" inside "NO CYCLE", and friends).
PAIR_CASES = (
    PairCase(
        "CreateSequenceExpression.cycle",
        lambda d, **kw: CreateSequenceExpression(d, Sequence(d, "s"), **kw),
        "cycle",
        "no_cycle",
        r"(?<!NO )CYCLE\b",
        r"NO CYCLE\b",
        "SEQUENCE CYCLE",
        a_probe="supports_sequence_cycle",
    ),
    PairCase(
        "CreateSequenceExpression.order",
        lambda d, **kw: CreateSequenceExpression(d, Sequence(d, "s"), **kw),
        "order",
        "no_order",
        r"(?<!NO )ORDER\b",
        r"NO ORDER\b",
        "SEQUENCE ORDER",
        a_probe="supports_sequence_order",
    ),
    PairCase(
        "CreateSequenceExpression.cache",
        lambda d, **kw: CreateSequenceExpression(d, Sequence(d, "s"), **kw),
        "cache",
        "no_cache",
        r"CACHE 10\b",
        r"NO CACHE\b",
        "SEQUENCE CACHE",
        a_probe="supports_sequence_cache",
        a_value=10,
    ),
    PairCase(
        "AlterSequenceExpression.cycle",
        lambda d, **kw: AlterSequenceExpression(d, Sequence(d, "s"), **kw),
        "cycle",
        "no_cycle",
        r"(?<!NO )CYCLE\b",
        r"NO CYCLE\b",
        "ALTER SEQUENCE CYCLE",
        a_probe="supports_sequence_cycle",
    ),
    PairCase(
        "AlterSequenceExpression.order",
        lambda d, **kw: AlterSequenceExpression(d, Sequence(d, "s"), **kw),
        "order",
        "no_order",
        r"(?<!NO )ORDER\b",
        r"NO ORDER\b",
        "ALTER SEQUENCE ORDER",
        a_probe="supports_sequence_order",
    ),
    PairCase(
        "AlterSequenceExpression.cache",
        lambda d, **kw: AlterSequenceExpression(d, Sequence(d, "s"), **kw),
        "cache",
        "no_cache",
        r"CACHE 10\b",
        r"NO CACHE\b",
        "ALTER SEQUENCE CACHE",
        a_probe="supports_sequence_cache",
        a_value=10,
    ),
    PairCase(
        "IdentityClause.cycle",
        lambda d, **kw: IdentityClause(d, **kw),
        "cycle",
        "no_cycle",
        r"(?<!NO )CYCLE\b",
        r"NO CYCLE\b",
        "IDENTITY CYCLE",
        a_probe="supports_identity_cycle",
    ),
    PairCase(
        "IdentityClause.order",
        lambda d, **kw: IdentityClause(d, **kw),
        "order",
        "no_order",
        r"(?<!NO )ORDER\b",
        r"NO ORDER\b",
        "IDENTITY ORDER",
        a_probe="supports_identity_order",
    ),
    PairCase(
        "IdentityClause.cache",
        lambda d, **kw: IdentityClause(d, **kw),
        "cache",
        "no_cache",
        r"CACHE 10\b",
        r"NO CACHE\b",
        "IDENTITY CACHE",
        a_probe="supports_identity_cache",
        a_value=10,
    ),
    PairCase(
        "TableConstraint.deferrable",
        _fk,
        "deferrable",
        "not_deferrable",
        r"(?<!NOT )DEFERRABLE\b",
        r"NOT DEFERRABLE\b",
        "DEFERRABLE constraint",
        a_probe="supports_deferrable_constraint",
    ),
    PairCase(
        "TableConstraint.initially_deferred",
        _fk,
        "initially_deferred",
        "initially_immediate",
        r"INITIALLY DEFERRED\b",
        r"INITIALLY IMMEDIATE\b",
        "INITIALLY DEFERRED/IMMEDIATE constraint",
        a_probe="supports_deferrable_constraint",
    ),
    PairCase(
        "TableConstraint.enforced",
        _check,
        "enforced",
        "not_enforced",
        r"(?<!NOT )ENFORCED\b",
        r"NOT ENFORCED\b",
        "ENFORCED/NOT ENFORCED constraint",
        a_probe="supports_constraint_enforced",
    ),
    PairCase(
        "AlterConstraint.enforced",
        lambda d, **kw: AlterConstraint(
            d, "c", constraint_type=TableConstraintType.CHECK, **kw
        ),
        "enforced",
        "not_enforced",
        r"(?<!NOT )ENFORCED\b",
        r"NOT ENFORCED\b",
        "ALTER CONSTRAINT ENFORCED/NOT ENFORCED",
        a_probe="supports_alter_constraint_enforced",
        neither_error="AlterConstraint requires exactly one of",
    ),
    PairCase(
        "BeginTransactionExpression.deferrable",
        lambda d, **kw: BeginTransactionExpression(d, **kw),
        "deferrable",
        "not_deferrable",
        r"(?<!NOT )DEFERRABLE\b",
        r"NOT DEFERRABLE\b",
        "DEFERRABLE transaction",
        a_probe="supports_deferrable_transaction",
    ),
    PairCase(
        "SetTransactionExpression.deferrable",
        lambda d, **kw: SetTransactionExpression(d, **kw),
        "deferrable",
        "not_deferrable",
        r"(?<!NOT )DEFERRABLE\b",
        r"NOT DEFERRABLE\b",
        "DEFERRABLE transaction",
        a_probe="supports_deferrable_transaction",
    ),
    # Firebird's lock-wait pair is *not* declined: both spellings prepare on
    # 5.0.4 and 6.0.0 (measured; see FirebirdTransactionMixin's probe). The
    # parameters must therefore render, one spelling each, and the probe must
    # answer True -- a dialect whose formatter drops one of them collapses the
    # states this case distinguishes.
    PairCase(
        "BeginTransactionExpression.wait",
        lambda d, **kw: BeginTransactionExpression(d, **kw),
        "wait",
        "no_wait",
        r"(?<!NO )WAIT\b",
        r"NO WAIT\b",
        "transaction WAIT",
        "transaction NO WAIT",
        a_probe="supports_transaction_wait",
        capable=True,
    ),
    PairCase(
        "SetTransactionExpression.wait",
        lambda d, **kw: SetTransactionExpression(d, **kw),
        "wait",
        "no_wait",
        r"(?<!NO )WAIT\b",
        r"NO WAIT\b",
        "transaction WAIT",
        "transaction NO WAIT",
        a_probe="supports_transaction_wait",
        capable=True,
    ),
    PairCase(
        "DropTableExpression.cascade",
        lambda d, **kw: DropTableExpression(d, _table(d), **kw),
        "cascade",
        "restrict",
        r"CASCADE\b",
        r"RESTRICT\b",
        "DROP TABLE ... CASCADE",
        "DROP TABLE ... RESTRICT",
        a_probe="supports_drop_table_cascade",
        b_probe="supports_drop_table_restrict",
    ),
    PairCase(
        "DropViewExpression.cascade",
        lambda d, **kw: DropViewExpression(d, View(d, "v"), **kw),
        "cascade",
        "restrict",
        r"CASCADE\b",
        r"RESTRICT\b",
        "DROP VIEW CASCADE",
        "DROP VIEW RESTRICT",
        a_probe="supports_cascade_view",
        b_probe="supports_restrict_view",
    ),
    PairCase(
        "DropFunctionExpression.cascade",
        lambda d, **kw: DropFunctionExpression(d, Function(d, "f"), **kw),
        "cascade",
        "restrict",
        r"CASCADE\b",
        r"RESTRICT\b",
        "DROP FUNCTION CASCADE",
        "DROP FUNCTION RESTRICT",
        a_probe="supports_drop_function_cascade",
        b_probe="supports_drop_function_restrict",
    ),
)

PAIR_IDS = [case.case_id for case in PAIR_CASES]


class TestFourStatesArePairwiseDistinguishable:
    """Neither / A / B / both, each through FirebirdDialect."""

    @pytest.mark.parametrize("case", PAIR_CASES, ids=PAIR_IDS)
    def test_neither_set_renders_neither_spelling(self, case):
        if case.neither_error is not None:
            # Mandatory pair: the action *is* the keyword, so "neither" is
            # refused as well. That is its own state, distinct from both.
            with pytest.raises(ValueError, match=case.neither_error):
                case.render(_dialect())
            return
        sql = case.render(_dialect())
        assert not case.matches_a(sql), (
            f"{case.case_id}: with neither parameter set the SQL still spells "
            f"{case.a!r}: {sql!r}"
        )
        assert not case.matches_b(sql), (
            f"{case.case_id}: with neither parameter set the SQL still spells "
            f"{case.b!r}: {sql!r}"
        )

    @pytest.mark.parametrize("case", PAIR_CASES, ids=PAIR_IDS)
    def test_a_set_is_refused_or_renders_a(self, case):
        if case.capable:
            sql = case.render(_dialect(), **{case.a: case.a_value})
            assert case.matches_a(sql), (
                f"{case.case_id}: setting {case.a!r} did not render its spelling: {sql!r}"
            )
            assert not case.matches_b(sql), (
                f"{case.case_id}: setting {case.a!r} also rendered {case.b!r}: {sql!r}"
            )
            return
        with pytest.raises(UnsupportedFeatureError, match=re.escape(case.a_feature)):
            case.render(_dialect(), **{case.a: case.a_value})

    @pytest.mark.parametrize("case", PAIR_CASES, ids=PAIR_IDS)
    def test_b_set_is_refused_or_renders_b(self, case):
        if case.capable:
            sql = case.render(_dialect(), **{case.b: case.b_value})
            assert case.matches_b(sql), (
                f"{case.case_id}: setting {case.b!r} did not render its spelling: {sql!r}"
            )
            assert not case.matches_a(sql), (
                f"{case.case_id}: setting {case.b!r} also rendered {case.a!r}: {sql!r}"
            )
            return
        with pytest.raises(UnsupportedFeatureError, match=re.escape(case.b_feature)):
            case.render(_dialect(), **{case.b: case.b_value})

    @pytest.mark.parametrize("case", PAIR_CASES, ids=PAIR_IDS)
    def test_both_set_is_refused_at_construction(self, case):
        with pytest.raises(
            ValueError, match=f"{case.a} and {case.b} are mutually exclusive options"
        ):
            case.render(_dialect(), **{case.a: case.a_value, case.b: case.b_value})

    @pytest.mark.parametrize("case", PAIR_CASES, ids=PAIR_IDS)
    def test_probe_matches_the_formatter(self, case):
        """The renderer's answer and the capability answer cannot disagree."""
        dialect = _dialect()
        for probe_name in {case.a_probe, case.b_probe}:
            assert probe_name is not None, f"{case.case_id}: no probe declared"
            probe = getattr(dialect, probe_name, None)
            assert callable(probe), f"{case.case_id}: {probe_name} is not answered"
            if case.capable:
                assert probe() is True, (
                    f"{case.case_id}: {probe_name} answers {probe()!r} but the "
                    f"formatter renders the option; declaration and renderer disagree"
                )
            else:
                assert probe() is False, (
                    f"{case.case_id}: {probe_name} answers True but the formatter "
                    f"refuses the option; declaration and renderer disagree"
                )


class TestPatternsMatchTheRealSpellings:
    """Sentinels: the patterns must match the spellings on a capable dialect."""

    @pytest.mark.parametrize("case", PAIR_CASES, ids=PAIR_IDS)
    def test_a_pattern_matches_dummy_render(self, case):
        sql = case.render(DummyDialect(), **{case.a: case.a_value})
        assert case.matches_a(sql), (
            f"{case.case_id}: the A pattern does not match the real spelling "
            f"rendered by DummyDialect: {sql!r}"
        )
        assert not case.matches_b(sql), (
            f"{case.case_id}: the A pattern matched B's spelling too: {sql!r}"
        )

    @pytest.mark.parametrize("case", PAIR_CASES, ids=PAIR_IDS)
    def test_b_pattern_matches_dummy_render(self, case):
        sql = case.render(DummyDialect(), **{case.b: case.b_value})
        assert case.matches_b(sql), (
            f"{case.case_id}: the B pattern does not match the real spelling "
            f"rendered by DummyDialect: {sql!r}"
        )
        assert not case.matches_a(sql), (
            f"{case.case_id}: the B pattern matched A's spelling too: {sql!r}"
        )

    def test_dummy_is_capable_of_every_covered_pair(self):
        """If Dummy ever declines a pair, the sentinel above would go vacuous."""
        dialect = DummyDialect()
        for case in PAIR_CASES:
            for probe_name in {case.a_probe, case.b_probe}:
                assert getattr(dialect, probe_name)() is True, (
                    f"DummyDialect answers {probe_name} False; the sentinel "
                    f"cannot render {case.case_id}"
                )


class TestGuardIsNotVacuous:
    """Guards so the checks above cannot pass by accident."""

    def test_every_case_has_two_distinct_parameters(self):
        for case in PAIR_CASES:
            assert case.a != case.b, case.case_id

    def test_every_pair_is_covered(self):
        """The pairs this backend consumes are all in the table."""
        expected = {
            "CreateSequenceExpression.cycle",
            "CreateSequenceExpression.order",
            "CreateSequenceExpression.cache",
            "AlterSequenceExpression.cycle",
            "AlterSequenceExpression.order",
            "AlterSequenceExpression.cache",
            "IdentityClause.cycle",
            "IdentityClause.order",
            "IdentityClause.cache",
            "TableConstraint.deferrable",
            "TableConstraint.initially_deferred",
            "TableConstraint.enforced",
            "AlterConstraint.enforced",
            "BeginTransactionExpression.deferrable",
            "SetTransactionExpression.deferrable",
            "BeginTransactionExpression.wait",
            "SetTransactionExpression.wait",
            "DropTableExpression.cascade",
            "DropViewExpression.cascade",
            "DropFunctionExpression.cascade",
        }
        covered = {case.case_id for case in PAIR_CASES}
        missing = expected - covered
        assert not missing, f"pairs in scope but not guarded: {sorted(missing)}"


# ---------------------------------------------------------------------------
# Parameter inventory completeness
# ---------------------------------------------------------------------------
#
# If core adds a parameter to one of these nodes, the pins below go red until
# the backend consumes it. The CREATE SEQUENCE formatter is a Firebird copy of
# core's, so "consumes" is checked against its source; the identity clause and
# the ALTER-side sequence formatter are core's, so the backend's share is the
# probes, which must all be answered.

CREATE_SEQUENCE_PARAMS = {
    "self",
    "dialect",
    "sequence",
    "if_not_exists",
    "start",
    "increment",
    "minvalue",
    "maxvalue",
    "cycle",
    "no_cycle",
    "cache",
    "no_cache",
    "order",
    "no_order",
    "owned_by",
}

IDENTITY_CLAUSE_PARAMS = {
    "self",
    "dialect",
    "generation",
    "start",
    "increment",
    "minvalue",
    "maxvalue",
    "cycle",
    "no_cycle",
    "order",
    "no_order",
    "cache",
    "no_cache",
}

TABLE_CONSTRAINT_PARAMS = {
    "self",
    "dialect",
    "constraint_type",
    "name",
    "columns",
    "check_condition",
    "foreign_key_table",
    "foreign_key_columns",
    "deferrable",
    "not_deferrable",
    "initially_deferred",
    "initially_immediate",
    "validation",
    "enforced",
    "not_enforced",
}

#: Every identity option probe the core ``format_identity_clause`` consults.
IDENTITY_OPTION_PROBES = (
    "supports_identity_column",
    "supports_identity_generation_always",
    "supports_identity_start",
    "supports_identity_increment",
    "supports_identity_minvalue",
    "supports_identity_maxvalue",
    "supports_identity_cycle",
    "supports_identity_order",
    "supports_identity_cache",
)

#: The pair parameters the Firebird table-constraint formatter must consume.
TABLE_CONSTRAINT_PAIR_PARAMS = (
    "deferrable",
    "not_deferrable",
    "initially_deferred",
    "initially_immediate",
    "enforced",
    "not_enforced",
)


class TestParameterInventoryIsComplete:
    """Core adding a parameter must fail here until the backend consumes it."""

    def test_create_sequence_signature_is_pinned(self):
        actual = set(inspect.signature(CreateSequenceExpression.__init__).parameters)
        assert actual == CREATE_SEQUENCE_PARAMS, (
            "CreateSequenceExpression's parameter list changed. The Firebird "
            "formatter is a copy of core's, so every new parameter must be "
            "consumed there and added to this pin.\n"
            f"  added:   {sorted(actual - CREATE_SEQUENCE_PARAMS)}\n"
            f"  removed: {sorted(CREATE_SEQUENCE_PARAMS - actual)}"
        )

    def test_firebird_sequence_formatter_consumes_every_parameter(self):
        source = inspect.getsource(FirebirdSequenceMixin.format_create_sequence_statement)
        missing = [
            name
            for name in CREATE_SEQUENCE_PARAMS
            if name not in {"self", "dialect"} and f"expr.{name}" not in source
        ]
        assert not missing, (
            "FirebirdSequenceMixin.format_create_sequence_statement does not read "
            f"these parameters: {missing}. A parameter the formatter never reads "
            "is silently dropped."
        )

    def test_identity_clause_signature_is_pinned(self):
        actual = set(inspect.signature(IdentityClause.__init__).parameters)
        assert actual == IDENTITY_CLAUSE_PARAMS, (
            "IdentityClause's parameter list changed; the backend must consume "
            "the new option before this pin is updated.\n"
            f"  added:   {sorted(actual - IDENTITY_CLAUSE_PARAMS)}\n"
            f"  removed: {sorted(IDENTITY_CLAUSE_PARAMS - actual)}"
        )

    def test_firebird_answers_every_identity_option_probe(self):
        dialect = _dialect()
        for probe_name in IDENTITY_OPTION_PROBES:
            probe = getattr(dialect, probe_name, None)
            assert callable(probe), f"FirebirdDialect does not answer {probe_name}"
            assert isinstance(probe(), bool), (
                f"{probe_name} must answer with a bool, got {probe()!r}"
            )

    def test_identity_declines_what_it_cannot_spell(self):
        """The measured identity answer: only START/INCREMENT are expressible."""
        dialect = _dialect()
        assert dialect.supports_identity_column() is True
        assert dialect.supports_identity_start() is True
        assert dialect.supports_identity_increment() is True
        for probe_name in (
            "supports_identity_minvalue",
            "supports_identity_maxvalue",
            "supports_identity_cycle",
            "supports_identity_order",
            "supports_identity_cache",
        ):
            assert getattr(dialect, probe_name)() is False, probe_name

    def test_table_constraint_signature_is_pinned(self):
        actual = set(inspect.signature(TableConstraint.__init__).parameters)
        assert actual == TABLE_CONSTRAINT_PARAMS, (
            "TableConstraint's parameter list changed; the Firebird formatter "
            "must consume the new parameter before this pin is updated.\n"
            f"  added:   {sorted(actual - TABLE_CONSTRAINT_PARAMS)}\n"
            f"  removed: {sorted(TABLE_CONSTRAINT_PARAMS - actual)}"
        )

    def test_firebird_table_constraint_formatter_consumes_every_pair(self):
        source = inspect.getsource(FirebirdTableMixin.format_table_constraint)
        missing = [
            name
            for name in TABLE_CONSTRAINT_PAIR_PARAMS
            if f"expr.{name}" not in source
        ]
        assert not missing, (
            "FirebirdTableMixin.format_table_constraint does not read these "
            f"parameters: {missing}. A parameter the formatter never reads is "
            "silently dropped."
        )


# ---------------------------------------------------------------------------
# The master probes the new core gates consult
# ---------------------------------------------------------------------------
#
# Core gave three previously-decorative probes a call site and added a fourth
# (supports_with_data_clause), and the transaction wait pair arrived with
# supports_transaction_wait. Firebird's answers are measured, not assumed --
# see each probe's docstring for the statements and the server responses. This
# class pins both halves: the answer, and the fact that the answer is
# Firebird's own declaration rather than an inherited default.

#: The Firebird mixin each probe must resolve to. The per-version answers are
#: asserted in the tests below; the point here is that the declaration is
#: Firebird's own, not an inherited core default.
MASTER_PROBES = (
    ("supports_transaction_wait", FirebirdTransactionMixin),
    ("supports_create_table_as", FirebirdTableMixin),
    ("supports_with_data_clause", FirebirdTableMixin),
    ("supports_materialized_cte", FirebirdCTEMixin),
    ("supports_truncate", FirebirdTruncateMixin),
)


class _FirebirdCarriersEnabled(FirebirdDialect):
    """The carriers on, the WITH [NO] DATA clause still declined.

    Firebird refuses ``CREATE TABLE ... AS`` on 5.x and materialized views in
    every version, so the clause gate cannot be observed through the real
    dialect. This witness enables the carriers and pins the clause answer to
    False, so the clause gate itself is exercised.
    """

    def supports_create_table_as(self) -> bool:
        return True

    def supports_with_data_clause(self) -> bool:
        return False

    def supports_materialized_view(self) -> bool:
        return True

    def supports_refresh_materialized_view(self) -> bool:
        return True


def _one_column_query(d):
    return QueryExpression(d, select=[Column(d, "id")], from_=Table(d, "t"))


class TestFirebirdAnswersTheMeasuredMasterProbes:
    """The measured answer, the declared answer and the renderer must agree."""

    @pytest.mark.parametrize(
        "probe_name,mixin", MASTER_PROBES, ids=[p[0] for p in MASTER_PROBES]
    )
    def test_probe_is_declared_on_the_firebird_mixin(self, probe_name, mixin):
        resolved = getattr(FirebirdDialect, probe_name)
        assert resolved is getattr(mixin, probe_name), (
            f"FirebirdDialect.{probe_name} resolves to "
            f"{getattr(resolved, '__qualname__', resolved)}; it must be declared "
            f"by {mixin.__name__} so the measured answer is explicit"
        )

    def test_transaction_wait_is_declared_true(self):
        for version in ((5, 0, 0), (6, 0, 0)):
            assert FirebirdDialect(version).supports_transaction_wait() is True, version

    def test_materialized_cte_is_declined_and_the_hint_refused(self):
        for version in ((5, 0, 0), (6, 0, 0)):
            d = FirebirdDialect(version)
            assert d.supports_materialized_cte() is False, version
            with pytest.raises(UnsupportedFeatureError, match="MATERIALIZED CTE"):
                CTEExpression(d, "c", _one_column_query(d), materialized=True).to_sql()
            with pytest.raises(UnsupportedFeatureError, match="NOT MATERIALIZED CTE"):
                CTEExpression(d, "c", _one_column_query(d), not_materialized=True).to_sql()
            sql, _ = CTEExpression(d, "c", _one_column_query(d)).to_sql()
            assert "MATERIALIZED" not in sql, sql

    def test_truncate_is_declined_and_refused_by_name(self):
        for version in ((5, 0, 0), (6, 0, 0)):
            d = FirebirdDialect(version)
            assert d.supports_truncate() is False, version
            with pytest.raises(UnsupportedFeatureError, match="TRUNCATE"):
                TruncateExpression(d, Table(d, "t")).to_sql()

    def test_create_table_as_is_version_gated(self):
        """Measured: 5.0.4 answers Token unknown - AS; 6.0.0 creates the table."""
        assert FirebirdDialect((5, 0, 0)).supports_create_table_as() is False
        assert FirebirdDialect((6, 0, 0)).supports_create_table_as() is True

        fb5 = FirebirdDialect((5, 0, 0))
        with pytest.raises(UnsupportedFeatureError, match=re.escape("CREATE TABLE ... AS")):
            CreateTableAsExpression(fb5, Table(fb5, "t"), _one_column_query(fb5)).to_sql()

        fb6 = FirebirdDialect((6, 0, 0))
        sql, _ = CreateTableAsExpression(fb6, Table(fb6, "t"), _one_column_query(fb6)).to_sql()
        assert sql == 'CREATE TABLE "T" AS SELECT "ID" FROM "T"', sql

    def test_with_data_clause_is_version_gated_and_the_gate_is_live(self):
        """Measured: 6.0.0 populates WITH DATA and leaves WITH NO DATA empty."""
        assert FirebirdDialect((5, 0, 0)).supports_with_data_clause() is False
        assert FirebirdDialect((6, 0, 0)).supports_with_data_clause() is True

        fb6 = FirebirdDialect((6, 0, 0))
        with_data, _ = CreateTableAsExpression(
            fb6, Table(fb6, "t"), _one_column_query(fb6), with_data=True
        ).to_sql()
        assert with_data.endswith("WITH DATA"), with_data
        no_data, _ = CreateTableAsExpression(
            fb6, Table(fb6, "t"), _one_column_query(fb6), no_data=True
        ).to_sql()
        assert no_data.endswith("WITH NO DATA"), no_data

        # The witness keeps the carriers but declines the clause: every
        # consumer must refuse the requested spelling by name.
        carrier = _FirebirdCarriersEnabled((6, 0, 0))
        assert carrier.supports_with_data_clause() is False
        for builder, keyword in (
            (
                lambda **kw: CreateTableAsExpression(
                    carrier, Table(carrier, "t"), _one_column_query(carrier), **kw
                ),
                "with_data",
            ),
            (
                lambda **kw: CreateTableAsExpression(
                    carrier, Table(carrier, "t"), _one_column_query(carrier), **kw
                ),
                "no_data",
            ),
            (
                lambda **kw: CreateMaterializedViewExpression(
                    carrier, MaterializedView(carrier, "mv"), _one_column_query(carrier), **kw
                ),
                "with_data",
            ),
            (
                lambda **kw: CreateMaterializedViewExpression(
                    carrier, MaterializedView(carrier, "mv"), _one_column_query(carrier), **kw
                ),
                "no_data",
            ),
            (
                lambda **kw: RefreshMaterializedViewExpression(
                    carrier, MaterializedView(carrier, "mv"), **kw
                ),
                "with_data",
            ),
            (
                lambda **kw: RefreshMaterializedViewExpression(
                    carrier, MaterializedView(carrier, "mv"), **kw
                ),
                "no_data",
            ),
        ):
            feature = "WITH DATA" if keyword == "with_data" else "WITH NO DATA"
            with pytest.raises(UnsupportedFeatureError, match=re.escape(feature)):
                builder(**{keyword: True}).to_sql()


# ---------------------------------------------------------------------------
# The transaction wait pair's wiring
# ---------------------------------------------------------------------------
#
# The pair arrived in core after the Phase 2 pass. Firebird's formatters must
# read both parameters; the dead pre-expression helper that hardcoded WAIT must
# not come back as a second, unreachable path.

BEGIN_TRANSACTION_PARAMS = {
    "self",
    "dialect",
    "isolation_level",
    "mode",
    "deferrable",
    "not_deferrable",
    "wait",
    "no_wait",
    "begin_type",
}

SET_TRANSACTION_PARAMS = {
    "self",
    "dialect",
    "isolation_level",
    "mode",
    "session",
    "deferrable",
    "not_deferrable",
    "wait",
    "no_wait",
}

#: The parameters the transaction formatters must read from the expression.
TRANSACTION_PAIR_PARAMS = ("_wait", "_no_wait")


class TestTransactionWaitPairIsWired:
    def test_begin_transaction_signature_is_pinned(self):
        actual = set(inspect.signature(BeginTransactionExpression.__init__).parameters)
        assert actual == BEGIN_TRANSACTION_PARAMS, (
            "BeginTransactionExpression's parameter list changed; the Firebird "
            "formatter must consume the new parameter before this pin is updated.\n"
            f"  added:   {sorted(actual - BEGIN_TRANSACTION_PARAMS)}\n"
            f"  removed: {sorted(BEGIN_TRANSACTION_PARAMS - actual)}"
        )

    def test_set_transaction_signature_is_pinned(self):
        actual = set(inspect.signature(SetTransactionExpression.__init__).parameters)
        assert actual == SET_TRANSACTION_PARAMS, (
            "SetTransactionExpression's parameter list changed; the Firebird "
            "formatter must consume the new parameter before this pin is updated.\n"
            f"  added:   {sorted(actual - SET_TRANSACTION_PARAMS)}\n"
            f"  removed: {sorted(SET_TRANSACTION_PARAMS - actual)}"
        )

    @pytest.mark.parametrize(
        "method_name",
        ["format_begin_transaction", "format_set_transaction"],
    )
    def test_firebird_formatter_consumes_both_wait_parameters(self, method_name):
        source = inspect.getsource(getattr(FirebirdTransactionMixin, method_name))
        missing = [
            name for name in TRANSACTION_PAIR_PARAMS if f"expr.{name}" not in source
        ]
        assert not missing, (
            f"FirebirdTransactionMixin.{method_name} does not read these "
            f"parameters: {missing}. A parameter the formatter never reads is "
            "silently dropped."
        )

    def test_the_dead_begin_helper_is_gone(self):
        """A second, unreachable rendering path is the defect, not the fix."""
        assert not hasattr(FirebirdTransactionMixin, "_format_begin_sql"), (
            "FirebirdTransactionMixin._format_begin_sql was the dead helper that "
            "hardcoded WAIT; the pair is rendered by the format_* methods now"
        )
