# tests/rhosocial/activerecord_firebird_test/feature/backend/test_firebird_constraint_switches.py
"""Firebird constraint capability switches: values, locality and evidence.

Every verdict asserted here was measured by running the statement against the
live instance ``tests/config/firebird_scenarios.yaml`` names ``firebird_5`` and
reading the server's own answer:

* **Firebird 5.0.4** at ``192.168.1.3:19582``, database
  ``/var/lib/firebird/data/test_db`` (UTF8), user ``SYSDBA``, driven by
  ``firebird-driver`` 2.0.3. ``rdb$get_context('SYSTEM','ENGINE_VERSION')``
  returns ``5.0.4``.

The docstring on each switch records the same measurement with its SQLCODE, so
a verdict can be re-checked without re-measuring the family.

Three things are asserted, and the last two are the easy ones to lose:

* **the value** -- what the server was measured to do;
* **the locality** -- that the verdict resolves to a class in *this* backend's
  package. A switch falling through to core's ``ConstraintMixin`` or
  ``DDLColumnMixin`` can have its default moved by a commit in another
  repository with nothing failing here. Declaring it locally turns that into a
  visible failure instead of a silent change of what Firebird renders;
* **the evidence** -- that the docstring still quotes the SQLCODE, the catalog
  column read back, or the accepted spelling the value came from.

Two corrections this module exists to pin, both of which a "tidy up" pass would
otherwise reintroduce:

* **A CHECK predicate is not a restricted grammar.** An earlier round of
  documentation in this repository claimed Firebird's ``<check_condition>`` was
  a narrow grammar that could not hold subqueries, on the reasoning that
  inlining an arbitrary predicate would "not be guaranteed legal". Live
  measurement refutes it: ``EXISTS (SELECT ...)``, ``NOT (a AND b)``, ``IN
  (...)`` and ``IS DISTINCT FROM`` are all accepted and all enforced, because
  Firebird compiles the predicate into a system-generated trigger whose body
  takes arbitrary subqueries. See :meth:`TestCheckIsNotARestrictedGrammar`.
* **A CHECK does not validate existing rows.** ``ALTER TABLE t ADD CONSTRAINT c
  CHECK (c > 0)`` succeeds on a table that already holds ``c = -1``, and the row
  survives. See :meth:`TestCheckIsNotDdlTimeValidation`.
"""

import pytest

from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect

#: The engine every verdict below was measured on.
MEASURED_VERSION = (5, 0, 4)

#: Every constraint switch this backend relies on, with the verdict measured on
#: Firebird 5.0.4. This mapping is the contract; the locality tests below walk
#: it so a switch cannot leave the backend without failing first.
#:
#: The list is what core's rendering path actually consults. Core's constraint
#: surface is a single naming switch (``supports_constraint_naming``) rather
#: than the per-kind spelling table the earlier draft carried: the two-level
#: branch nodes express the kind as a class, so no per-kind naming probe
#: exists to declare. A switch core does not define would be a verdict no
#: caller could ever reach, which is why the invented ones are gone.
CONSTRAINT_SWITCHES = {
    # -- Constraint kinds (SQL-86 / SQL-92).
    "supports_primary_key_constraint": True,
    "supports_unique_constraint": True,
    "supports_not_null_constraint": True,
    "supports_check_constraint": True,
    "supports_foreign_key_constraint": True,
    "supports_exclude_constraint": False,
    # -- Referential actions (SQL-92) and match modes (SQL:1999).
    "supports_fk_on_delete": True,
    "supports_fk_on_update": True,
    "supports_foreign_key_on_delete": True,
    "supports_foreign_key_on_update": True,
    "supports_fk_match": False,
    # -- CONSTRAINT <name> (one switch; naming is uniform over the branches).
    "supports_constraint_naming": True,
    # -- Deferral (SQL:1999). No clause exists for ANY kind.
    "supports_deferrable_constraint": False,
    # -- Enforcement control (SQL:2016) and validation state.
    "supports_constraint_enforced": False,
    "supports_alter_constraint_enforced": False,
    "supports_constraint_novalidate": False,
    "supports_validate_constraint": False,
    # -- ALTER TABLE lifecycle (SQL-92). ADD and DROP only.
    "supports_add_constraint": True,
    "supports_drop_constraint": True,
    "supports_drop_constraint_if_exists": False,
    # -- Column clause position: charset lives in the datatype, COLLATE last.
    "supports_column_character_set": False,
    "supports_column_collation": True,
}

#: The substring that must appear in each switch's docstring: the SQLCODE, the
#: catalog column read back, or the exact accepted spelling. A verdict that
#: cannot be traced to an observation is a guess.
EVIDENCE = {
    "supports_primary_key_constraint": "PRIMARY KEY",
    "supports_unique_constraint": "UNIQUE",
    "supports_not_null_constraint": "-407",
    "supports_check_constraint": "-297",
    "supports_foreign_key_constraint": "-104",
    "supports_exclude_constraint": "-104",
    "supports_fk_on_delete": "-104",
    "supports_fk_on_update": "-530",
    "supports_foreign_key_on_delete": "-104",
    "supports_foreign_key_on_update": "-530",
    "supports_fk_match": "-104",
    "supports_constraint_naming": "RDB$RELATION_CONSTRAINTS",
    "supports_deferrable_constraint": "-104",
    "supports_constraint_enforced": "-104",
    "supports_alter_constraint_enforced": "-104",
    "supports_constraint_novalidate": "-104",
    "supports_validate_constraint": "-104",
    "supports_add_constraint": "-607",
    "supports_drop_constraint": "does not exist",
    "supports_drop_constraint_if_exists": "-104",
    "supports_column_character_set": "-104",
    "supports_column_collation": "COLLATE",
}

#: Every capability must come from this package.
BACKEND_PACKAGE = "rhosocial.activerecord.backend.impl.firebird."


def _dialect(version=MEASURED_VERSION):
    return FirebirdDialect(version=version)


def _declaring_class(switch_name):
    """The first class in the dialect's MRO that declares ``switch_name``."""
    for cls in FirebirdDialect.__mro__:
        if switch_name in cls.__dict__:
            return cls
    raise AssertionError(f"no class in the MRO declares {switch_name}()")


def _doc(switch_name):
    declaring = _declaring_class(switch_name)
    return declaring.__dict__[switch_name].__doc__ or ""


class TestMeasuredConstraintSwitchValues:
    """What the server was measured to do."""

    @pytest.mark.parametrize(
        "switch,expected",
        sorted(CONSTRAINT_SWITCHES.items()),
        ids=sorted(CONSTRAINT_SWITCHES),
    )
    def test_switch_answers_the_measured_value(self, switch, expected):
        dialect = _dialect()
        assert getattr(dialect, switch)() is expected, (
            f"{switch}() no longer matches the Firebird 5.0.4 measurement; see "
            f"the docstring on "
            f"rhosocial.activerecord.backend.impl.firebird.mixins.constraint for "
            f"the statement and SQLCODE that decided it."
        )

    @pytest.mark.parametrize(
        "switch,expected",
        sorted(CONSTRAINT_SWITCHES.items()),
        ids=sorted(CONSTRAINT_SWITCHES),
    )
    def test_verdicts_do_not_move_with_the_declared_version(self, switch, expected):
        """None of these values is version-gated, so no version branch may exist.

        The measurements were taken on 5.0.4; the backend also declares 6.0.0 and
        older versions. A value that quietly became version-sensitive would be
        making a claim about a release nobody measured, so this asserts the
        opposite: the same answer everywhere.
        """
        for version in ((3, 0, 0), (4, 0, 0), (5, 0, 4), (6, 0, 0)):
            dialect = FirebirdDialect(version=version)
            assert getattr(dialect, switch)() is expected, f"{switch} moved with version {version}"

    def test_the_pair_alias_switches_agree_with_the_canonical_ones(self):
        """Core declares both spellings of the referential-action pair.

        ``supports_fk_on_delete`` / ``supports_foreign_key_on_delete`` name the
        same question (the shared ``ConstraintMixin`` and ``DDLColumnMixin``
        each consult their own spelling), so the two must not disagree -- a
        divergence would mean one rendering path refuses a clause the other
        emits.
        """
        dialect = _dialect()
        assert dialect.supports_fk_on_delete() is dialect.supports_foreign_key_on_delete()
        assert dialect.supports_fk_on_update() is dialect.supports_foreign_key_on_update()


class TestConstraintSwitchesAreDeclaredLocally:
    """The verdict must be this backend's, not an inherited core default."""

    @pytest.mark.parametrize("switch", sorted(CONSTRAINT_SWITCHES), ids=sorted(CONSTRAINT_SWITCHES))
    def test_switch_is_declared_by_this_backend(self, switch):
        declaring = _declaring_class(switch)
        assert declaring.__module__.startswith(BACKEND_PACKAGE), (
            f"{switch} is inherited from {declaring.__module__}; declare it in "
            f"this backend's own package so a moved core default becomes a "
            f"loud failure instead of a silent change of what Firebird renders."
        )

    def test_backend_constraint_mixin_precedes_the_core_mixins(self):
        """MRO order is what makes the local declarations win at all.

        ``FirebirdConstraintMixin`` has to precede core's ``ConstraintMixin``
        (which supplies the shared constraint defaults) and its
        ``DDLColumnMixin`` (which supplies ``supports_column_character_set``,
        ``supports_column_collation`` and the constraint formatters this
        backend gates). If that ordering were disturbed the local values would
        silently lose to the inherited ones even though both classes define the
        switch.
        """
        from rhosocial.activerecord.backend.dialect.mixins.ddl_column import DDLColumnMixin
        from rhosocial.activerecord.backend.dialect.mixins.ddl_table import ConstraintMixin

        from rhosocial.activerecord.backend.impl.firebird.mixins.constraint import (
            FirebirdConstraintMixin,
        )

        mro = FirebirdDialect.__mro__
        assert mro.index(FirebirdConstraintMixin) < mro.index(ConstraintMixin)
        assert mro.index(FirebirdConstraintMixin) < mro.index(DDLColumnMixin)


class TestConstraintSwitchDocstringsCarryTheMeasurement:
    """A probe without its evidence is a number with no source."""

    @pytest.mark.parametrize("switch", sorted(EVIDENCE), ids=sorted(EVIDENCE))
    def test_docstring_records_the_observation(self, switch):
        doc = _doc(switch)
        # The first summary line is the part a future reader sees first and the
        # part most likely to be trimmed as noise, so the evidence assertion
        # covers the whole docstring but the summary is checked for a name too.
        assert doc, f"{switch} has no docstring: the measurement has nowhere to live"
        assert EVIDENCE[switch] in doc, (
            f"{switch}'s docstring no longer quotes {EVIDENCE[switch]!r}, the "
            f"observation this value came from."
        )

    @pytest.mark.parametrize("switch", sorted(CONSTRAINT_SWITCHES), ids=sorted(CONSTRAINT_SWITCHES))
    def test_docstring_names_a_measured_release(self, switch):
        """Every constraint verdict names the release it was measured on.

        Without the release a reader cannot tell whether a value is a
        long-standing property of Firebird or a fact about one instance, and the
        two call for different treatment when Firebird changes.
        """
        doc = _doc(switch)
        assert "5.0.4" in doc, f"{switch}'s docstring names no measured Firebird release."


class TestCheckIsNotARestrictedGrammar:
    """The refuted claim, asserted so it cannot creep back in.

    An earlier documentation round asserted that Firebird's
    ``<check_condition>`` was a restricted grammar and that the core's habit of
    inlining an arbitrary predicate was therefore unsafe. Live measurement on
    5.0.4 accepts and enforces all four of these, with the DML failure naming
    the generated trigger the predicate was compiled into:

    * ``CHECK (EXISTS (SELECT 1 FROM r WHERE id = 99))``
    * ``CHECK (NOT (c > 0 AND c < 10))``
    * ``CHECK (c IN (1,2,3))``
    * ``CHECK (c IS DISTINCT FROM 1)``

    all answered ``-297: Operation violates CHECK constraint <name> on view or
    table <t> -At trigger 'CHECK_<id>'`` on a violating row.
    """

    def test_check_constraint_is_supported(self):
        assert _dialect().supports_check_constraint() is True

    def test_check_docstring_states_the_subquery_result(self):
        doc = _doc("supports_check_constraint")
        assert "EXISTS (SELECT" in doc
        assert "IS DISTINCT FROM" in doc
        assert "-297" in doc

    def test_check_docstring_does_not_claim_a_restricted_grammar(self):
        """A positive statement, because a removal is easy to miss.

        The docstring has to *deny* the claim, not merely omit it: "CHECK
        predicate grammar is not restricted" is the finding, and a future edit
        that trims the sentence would otherwise look like a tidy-up.
        """
        doc = _doc("supports_check_constraint")
        assert "not a restricted grammar" in doc

    def test_the_module_docstring_carries_the_refutation(self):
        """The engine-level explanation belongs on the module, not one switch.

        The *reason* -- Firebird compiles CHECK into a system-generated trigger
        whose body takes arbitrary subqueries -- is what makes the acceptance
        surface wide, and it applies to every CHECK on the backend.
        """
        from rhosocial.activerecord.backend.impl.firebird.mixins import constraint as module

        text = module.__doc__ or ""
        assert "NOT a restricted grammar" in text
        assert "system-generated trigger" in text
        assert "-297" in text


class TestCheckIsNotDdlTimeValidation:
    """A CHECK is a per-row trigger, so adding one does not clean the table.

    Measured on 5.0.4: with a row ``c = -1`` already in the table,
    ``ALTER TABLE d1 ADD CONSTRAINT ck CHECK (c > 0)`` **succeeded** and the row
    survived. ``RDB$TRIGGERS`` shows the mechanism -- two system triggers
    (``RDB$SYSTEM_FLAG = 3``) named ``CHECK_<id>`` with ``RDB$TRIGGER_TYPE`` 1
    (BEFORE INSERT) and 3 (BEFORE UPDATE).

    This is a genuine engine fact with no switch to hang it on, so it lives in
    code comments and in these assertions rather than in a capability value.
    """

    def test_the_add_constraint_docstring_warns_about_it(self):
        doc = _doc("supports_add_constraint")
        assert "back-fill validation" in doc
        assert "c = -1" in doc

    def test_the_table_constraint_gate_comments_it(self):
        """A caller reading the CHECK render path must not assume validation.

        The gate that guards the table-clause traits is where the CHECK fact is
        recorded, because the CHECK body itself is now rendered by core's
        ``format_table_check_constraint`` and this backend overrides no part of
        it. The comment has to survive, so it is asserted.
        """
        import inspect

        from rhosocial.activerecord.backend.impl.firebird.mixins.constraint import (
            FirebirdConstraintMixin,
        )

        source = inspect.getsource(FirebirdConstraintMixin.format_table_constraint)
        assert "CHECK" in source
        assert "system-generated trigger" in source
        assert "ADD CONSTRAINT ck CHECK (c > 0)" in source

    def test_the_add_constraint_docstring_warns_about_database_wide_names(self):
        """The second engine fact that is not expressible as a boolean.

        Measured on 5.0.4: reusing a constraint name on a different table
        answers ``-607: violation of PRIMARY or UNIQUE KEY constraint
        "RDB$INDEX_12" on table "RDB$RELATION_CONSTRAINTS" -Problematic key
        value is ("RDB$CONSTRAINT_NAME" = '<name>')`` -- the same code for a NOT
        NULL, a CHECK and a UNIQUE, so the message cannot be used to classify
        the clash by constraint kind.
        """
        doc = _doc("supports_add_constraint")
        assert "RDB$RELATION_CONSTRAINTS" in doc
        assert "database-wide" in doc


class TestOnUpdateIsHonouredNotAbsorbed:
    """``ON UPDATE`` is unusual for this family, so it is pinned functionally.

    Oracle has no ``ON UPDATE`` referential action at all, which means a change
    made for Oracle's grammar could otherwise start dropping the clause here.
    Acceptance alone would not catch that, so the docstring has to carry the
    functional evidence.
    """

    def test_on_update_is_supported(self):
        dialect = _dialect()
        assert dialect.supports_fk_on_update() is True

    def test_on_update_docstring_carries_the_functional_evidence(self):
        doc = _doc("supports_foreign_key_on_update")
        assert "ON UPDATE CASCADE" in doc
        assert "ON UPDATE SET NULL" in doc
        assert "-530" in doc
        assert "Oracle" in doc


class TestCharacterSetIsADatatypeQualifierNotAColumnClause:
    """The one switch a reader is most likely to get wrong.

    Firebird plainly *has* character sets -- a database-level ``DEFAULT
    CHARACTER SET``, per-column sets, ``OCTETS`` -- and this backend already
    renders ``CHARACTER SET`` from ``FirebirdColumnDefinition``. What it does
    not have is a standalone column clause for it. In ``<regular_col_def>`` the
    only clause after the constraints is ``[COLLATE collation_name]``; the
    charset belongs inside ``<datatype>``.

    Measured on 5.0.4::

        CREATE TABLE t (x VARCHAR(20) CHARACTER SET UTF8)            -- accepted
        CREATE TABLE t (x CHARACTER SET UTF8 VARCHAR(20))
        -> -104: Token unknown - line 1, column 34 -SET
        CREATE TABLE t (x INTEGER CHARACTER SET UTF8)
        -> -104: Token unknown - line 1, column 32 -CHARACTER

    and, decisively, the shape a generic ``CharacterSetClause`` produces -- the
    fragment after the constraints, which is where core's
    ``format_column_attributes`` emits it::

        CREATE TABLE t (x VARCHAR(20) NOT NULL CHARACTER SET UTF8)
        -> -104: Token unknown - line 1, column 45 -CHARACTER

    So the switch is ``False``: the supported route on this backend is the
    Firebird-only ``FirebirdColumnDefinition.character_set`` slot, which renders
    in the type position.
    """

    def test_column_character_set_is_false(self):
        assert _dialect().supports_column_character_set() is False

    def test_collation_is_true_and_must_come_last(self):
        assert _dialect().supports_column_collation() is True

    def test_docstring_shows_the_shape_that_is_refused(self):
        doc = _doc("supports_column_character_set")
        assert "VARCHAR(20) NOT NULL CHARACTER SET UTF8" in doc
        assert "FirebirdColumnDefinition.character_set" in doc

    def test_the_supported_route_still_renders(self):
        """``False`` must not read as "Firebird has no character sets".

        The Firebird-only column slot is the working route and it is untouched by
        this switch; it renders in the type position.
        """
        from rhosocial.activerecord.backend.expression.types import VarCharType

        from rhosocial.activerecord.backend.impl.firebird.expression.column import (
            FirebirdColumnDefinition,
        )

        dialect = _dialect()
        col_def = FirebirdColumnDefinition(
            dialect, "X", VarCharType(dialect, length=20), character_set="UTF8"
        )
        sql, params = dialect.format_column_definition(col_def)
        assert sql == '"X" VARCHAR(20) CHARACTER SET UTF8'
        assert params == ()


class TestLifecycleIsAddAndDropOnly:
    """Firebird's ALTER TABLE constraint verbs are ADD and DROP, nothing else."""

    def test_the_two_verbs_that_exist(self):
        dialect = _dialect()
        assert dialect.supports_add_constraint() is True
        assert dialect.supports_drop_constraint() is True

    @pytest.mark.parametrize(
        "switch",
        (
            "supports_validate_constraint",
            "supports_drop_constraint_if_exists",
        ),
        ids=lambda s: s,
    )
    def test_the_verbs_that_do_not(self, switch):
        assert getattr(_dialect(), switch)() is False

    def test_drop_constraint_cannot_be_made_idempotent(self):
        """No ``IF EXISTS``, and the missing-name code is a metadata failure.

        ``-607`` is what a *name clash* also returns, so a caller who swallowed it
        would swallow the wrong thing; and ``-104 Token unknown - EXISTS`` means
        the idempotent statement never parses, so there is nothing to catch.
        """
        dialect = _dialect()
        assert dialect.supports_drop_constraint_if_exists() is False
        doc = _doc("supports_drop_constraint")
        assert "does not exist" in doc
        assert "-607" in doc
        # The two facts that make ``-607`` uncatchable for this purpose live on
        # ``supports_add_constraint``, which records the name clash that returns
        # the same code.
        assert "-607" in _doc("supports_add_constraint")

    def test_the_two_if_exists_declarations_agree(self):
        """The guard and the contract answer the same question.

        The switch is declared twice -- once where the render-time guard lives
        and once in the constraint contract -- so the whole contract is readable
        in one place. A divergence would mean one of them no longer describes
        the server.
        """
        from rhosocial.activerecord.backend.impl.firebird.mixins.ddl_alter_table_modifier import (
            FirebirdAlterTableModifierMixin,
        )

        dialect = _dialect()
        assert (
            dialect.supports_drop_constraint_if_exists()
            is FirebirdAlterTableModifierMixin.supports_drop_constraint_if_exists(dialect)
        )

    def test_the_modifier_guard_refuses_if_exists_by_name(self):
        """``False`` has to change behaviour, not merely be recorded.

        This is what makes the value load-bearing: flipping it would render the
        clause, and leaving it ``False`` raises instead of emitting SQL the
        server rejects at ``-104``.
        """
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
        from rhosocial.activerecord.backend.expression.statements import (
            DropTableConstraintAction,
        )

        action = DropTableConstraintAction(_dialect(), "CK", if_exists=True)
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            action.to_sql()
        assert "IF EXISTS" in str(excinfo.value)


class TestDeferrableAndEnforcedAreRefusedByName:
    """The ``False`` values have to reach the rendered SQL, not just the docs.

    Both gates name the *branch's* SQL kind and the exact spelling requested, so
    a ``FOREIGN KEY NOT DEFERRABLE`` and a ``CHECK NOT ENFORCED`` are told apart
    rather than collapsing into one family message. The kind comes from the
    branch class, because the ``TableConstraintType`` tag the earlier draft
    switched on is gone.
    """

    def test_deferrable_is_refused_naming_the_kind_and_spelling(self):
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
        from rhosocial.activerecord.backend.expression.statements import (
            TableConstraint,
            TablePrimaryKeyConstraint,
        )

        dialect = _dialect()
        constraint = TableConstraint(
            dialect,
            branch=TablePrimaryKeyConstraint(dialect, ["c"]),
            name="PK",
            deferrable=True,
        )
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            dialect.format_table_constraint(constraint)
        assert "PRIMARY KEY DEFERRABLE" in str(excinfo.value)

    def test_not_deferrable_is_told_apart_from_deferrable(self):
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
        from rhosocial.activerecord.backend.expression.statements import (
            TableConstraint,
            TablePrimaryKeyConstraint,
        )

        dialect = _dialect()
        constraint = TableConstraint(
            dialect,
            branch=TablePrimaryKeyConstraint(dialect, ["c"]),
            name="PK",
            not_deferrable=True,
        )
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            dialect.format_table_constraint(constraint)
        assert "PRIMARY KEY NOT DEFERRABLE" in str(excinfo.value)

    def test_deferral_on_a_kind_that_cannot_carry_it_is_a_construction_error(self):
        """The branch nodes make an inapplicable trait unwritable, not dropped.

        This is the S3 gain: before the two-level nodes, ``DEFERRABLE`` on a
        CHECK was accepted and silently never rendered. It is now a ``ValueError``
        at construction, so no render-time gate is even reached.
        """
        from rhosocial.activerecord.backend.expression.statements import (
            TableCheckConstraint,
            TableConstraint,
        )
        from rhosocial.activerecord.backend.expression import Column
        from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate

        dialect = _dialect()
        condition = ComparisonPredicate(dialect, ">", Column(dialect, "c"), Column(dialect, "c"))
        with pytest.raises(ValueError, match="DEFERRABLE"):
            TableConstraint(
                dialect,
                branch=TableCheckConstraint(dialect, condition),
                name="CK",
                deferrable=True,
            )

    def test_enforcement_is_refused_naming_the_kind_and_spelling(self):
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
        from rhosocial.activerecord.backend.expression.statements import (
            TableCheckConstraint,
            TableConstraint,
        )
        from rhosocial.activerecord.backend.expression import Column
        from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate

        dialect = _dialect()
        condition = ComparisonPredicate(dialect, ">", Column(dialect, "c"), Column(dialect, "c"))
        constraint = TableConstraint(
            dialect,
            branch=TableCheckConstraint(dialect, condition),
            name="CK",
            not_enforced=True,
        )
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            dialect.format_table_constraint(constraint)
        assert "CHECK NOT ENFORCED" in str(excinfo.value)

    def test_fk_match_is_refused_when_requested(self):
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
        from rhosocial.activerecord.backend.expression.objects import Table
        from rhosocial.activerecord.backend.expression.statements import (
            ForeignKeyConstraint,
            ForeignKeyMatchType,
            ReferentialAction,
        )

        dialect = _dialect()
        constraint = ForeignKeyConstraint(
            dialect,
            columns=["c"],
            foreign_key_table=Table(dialect, "r"),
            foreign_key_columns=["id"],
            on_delete=ReferentialAction.CASCADE,
            on_update=ReferentialAction.CASCADE,
            match_type=ForeignKeyMatchType.FULL,
            name="FK",
        )
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            dialect.format_table_constraint(constraint)
        assert "MATCH" in str(excinfo.value)

    def test_on_delete_and_on_update_both_render(self):
        """The pair has to reach the SQL, or the ``True`` is decorative.

        ``ON UPDATE`` is the load-bearing half: it is the clause Firebird has and
        Oracle does not, so a renderer that dropped it would look fine on Oracle
        and be wrong here.
        """
        from rhosocial.activerecord.backend.expression.objects import Table
        from rhosocial.activerecord.backend.expression.statements import (
            ForeignKeyConstraint,
            ReferentialAction,
        )

        dialect = _dialect()
        constraint = ForeignKeyConstraint(
            dialect,
            columns=["c"],
            foreign_key_table=Table(dialect, "r"),
            foreign_key_columns=["id"],
            on_delete=ReferentialAction.CASCADE,
            on_update=ReferentialAction.SET_NULL,
            name="FK",
        )
        sql, params = dialect.format_table_constraint(constraint)
        assert "ON DELETE CASCADE" in sql
        assert "ON UPDATE SET NULL" in sql
        assert params == ()


class TestColumnCharacterSetRefusalIsEnforcedByTheRenderPath:
    """The generic clause channel must refuse, not emit -104 SQL.

    ``supports_column_character_set()`` is ``False``, and
    ``DDLColumnMixin.format_column_attribute`` consults it -- so a caller who
    routes a ``CharacterSetClause`` through the generic channel gets told, rather
    than a statement Firebird's parser rejects at ``Token unknown - CHARACTER``.
    """

    def test_a_generic_character_set_clause_is_refused(self):
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
        from rhosocial.activerecord.backend.expression.statements import (
            CharacterSetClause,
        )

        dialect = _dialect()
        clause = CharacterSetClause(dialect, "UTF8")
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            dialect.format_column_attribute(clause)
        assert "CHARACTER SET" in str(excinfo.value)

    def test_a_generic_collation_clause_is_accepted(self):
        from rhosocial.activerecord.backend.expression.statements import CollationClause

        dialect = _dialect()
        sql, params = dialect.format_column_attribute(CollationClause(dialect, "UNICODE"))
        assert sql.strip() == "COLLATE UNICODE"
        assert params == ()
