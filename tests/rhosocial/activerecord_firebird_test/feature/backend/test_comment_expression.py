# tests/rhosocial/activerecord_firebird_test/feature/backend/test_comment_expression.py
"""Tests for Firebird COMMENT ON expressions.

``COMMENT ON`` annotates metadata objects and is available since Firebird 2.5
(gated here at ``(2, 5, 0)``). All tests are pure construction — no database
connection.
"""

import pytest

from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.expression import (
    FirebirdCommentExpression,
    FirebirdCommentObjectType,
)


class TestCommentOn:
    def _comment(self, dialect, object_type, object_name, comment=None):
        return FirebirdCommentExpression(dialect, object_type, object_name, comment).to_sql()

    def test_table(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = self._comment(dialect, FirebirdCommentObjectType.TABLE, "t", "meta")
        assert sql == "COMMENT ON TABLE \"T\" IS 'meta'"
        assert params == ()

    def test_column(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = self._comment(dialect, FirebirdCommentObjectType.COLUMN, "t.c", "col")
        assert sql == 'COMMENT ON COLUMN "T"."C" IS \'col\''
        assert params == ()

    def test_view(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = self._comment(dialect, FirebirdCommentObjectType.VIEW, "v", "a view")
        assert sql == "COMMENT ON VIEW \"V\" IS 'a view'"
        assert params == ()

    def test_procedure(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = self._comment(
            dialect, FirebirdCommentObjectType.PROCEDURE, "p", "proc"
        )
        assert sql == "COMMENT ON PROCEDURE \"P\" IS 'proc'"
        assert params == ()

    def test_function(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = self._comment(
            dialect, FirebirdCommentObjectType.FUNCTION, "f", "func"
        )
        assert sql == "COMMENT ON FUNCTION \"F\" IS 'func'"
        assert params == ()

    def test_external_function(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = self._comment(
            dialect, FirebirdCommentObjectType.EXTERNAL_FUNCTION, "efunc", "udf"
        )
        assert sql == 'COMMENT ON EXTERNAL FUNCTION "EFUNC" IS \'udf\''
        assert params == ()

    def test_domain(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = self._comment(
            dialect, FirebirdCommentObjectType.DOMAIN, "dm_zip", "zip"
        )
        assert sql == 'COMMENT ON DOMAIN "DM_ZIP" IS \'zip\''
        assert params == ()

    def test_exception(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = self._comment(
            dialect, FirebirdCommentObjectType.EXCEPTION, "e_bad", "bad"
        )
        assert sql == "COMMENT ON EXCEPTION \"E_BAD\" IS 'bad'"
        assert params == ()

    def test_trigger(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = self._comment(
            dialect, FirebirdCommentObjectType.TRIGGER, "trg", "trig"
        )
        assert sql == "COMMENT ON TRIGGER \"TRG\" IS 'trig'"
        assert params == ()

    def test_generator(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = self._comment(
            dialect, FirebirdCommentObjectType.GENERATOR, "gen", "generator"
        )
        assert sql == 'COMMENT ON GENERATOR "GEN" IS \'generator\''
        assert params == ()

    def test_sequence(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = self._comment(
            dialect, FirebirdCommentObjectType.SEQUENCE, "seq", "sequence"
        )
        assert sql == 'COMMENT ON SEQUENCE "SEQ" IS \'sequence\''
        assert params == ()

    def test_role(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = self._comment(dialect, FirebirdCommentObjectType.ROLE, "r", "role")
        assert sql == 'COMMENT ON ROLE "R" IS \'role\''
        assert params == ()

    def test_comment_null_removes(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = self._comment(dialect, FirebirdCommentObjectType.TABLE, "t", None)
        assert sql == 'COMMENT ON TABLE "T" IS NULL'
        assert params == ()

    def test_comment_escaping(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = self._comment(
            dialect, FirebirdCommentObjectType.TABLE, "t", "it's a test"
        )
        assert sql == "COMMENT ON TABLE \"T\" IS 'it''s a test'"
        assert params == ()

    def test_comment_fb2_5(self):
        dialect = FirebirdDialect((2, 5, 0))
        sql, params = self._comment(dialect, FirebirdCommentObjectType.TABLE, "t", "meta")
        assert sql == "COMMENT ON TABLE \"T\" IS 'meta'"
        assert params == ()


class TestCommentDispatch:
    def test_expression_to_sql_delegates_to_dialect(self):
        from rhosocial.activerecord.backend.impl.firebird.mixins.comment import (
            FirebirdCommentMixin,
        )

        dialect = FirebirdDialect((4, 0, 0))
        assert (
            type(dialect).format_comment_statement == FirebirdCommentMixin.format_comment_statement
        )

    def test_supports_comment_on_true_across_supported_versions(self):
        assert FirebirdDialect((2, 5, 0)).supports_comment_on() is True
        assert FirebirdDialect((5, 0, 0)).supports_comment_on() is True


#: Firebird's COMMENT ON targets that the framework's catalogue has **no kind
#: for**, so the target stays a plain string and is spelled by
#: ``format_identifier``. This is deliberate, not an omission: a role, a user, an
#: exception, a package and an external function are all things Firebird persists
#: and none of them is a ``SchemaObject`` in this framework's taxonomy, so there
#: is nothing to build and dispatch on kind has nothing to dispatch to.
STRING_ONLY_TARGETS = (
    FirebirdCommentObjectType.ROLE,
    FirebirdCommentObjectType.USER,
    FirebirdCommentObjectType.EXCEPTION,
    FirebirdCommentObjectType.PACKAGE,
    FirebirdCommentObjectType.EXTERNAL_FUNCTION,
    FirebirdCommentObjectType.DATABASE,
    FirebirdCommentObjectType.INDEX,
    FirebirdCommentObjectType.FILTER,
    FirebirdCommentObjectType.CHARACTER_SET,
    FirebirdCommentObjectType.COLLATION,
    FirebirdCommentObjectType.GLOBAL_MAPPING,
)


class TestObjectKindDispatchTable:
    """The dispatch is on object *kind*, and the string-only targets are pinned.

    The table used to be keyed by formatter name, which meant adding a kind meant
    adding a formatter; it is keyed by the object class each kind names, so a
    target that corresponds to a catalogue object is built and renders itself --
    which is what gives a namespace slot on it somewhere to be reported instead
    of being dropped.
    """

    def test_every_entry_names_a_schema_object_kind(self):
        from rhosocial.activerecord.backend.expression.objects import SchemaObject
        from rhosocial.activerecord.backend.impl.firebird.mixins.comment import (
            FirebirdCommentMixin,
        )

        table = FirebirdCommentMixin._COMMENT_OBJECT_KINDS
        assert table, "the dispatch table is empty; every target would stringify"
        for target, kind in table.items():
            assert isinstance(kind, type) and issubclass(kind, SchemaObject), (
                f"{target!r} dispatches to {kind!r}, which is not a SchemaObject "
                f"subclass -- an entry here must name something buildable"
            )

    @pytest.mark.parametrize("target", STRING_ONLY_TARGETS, ids=lambda t: t.name)
    def test_deliberate_exception_target_is_not_in_the_table(self, target):
        from rhosocial.activerecord.backend.impl.firebird.mixins.comment import (
            FirebirdCommentMixin,
        )

        assert target.value not in FirebirdCommentMixin._COMMENT_OBJECT_KINDS, (
            f"{target.value} gained an entry in the object-kind dispatch table. "
            f"Either it is right -- in which case this pin must be removed -- or "
            f"it dispatches to a kind that does not exist."
        )

    @pytest.mark.parametrize("target", STRING_ONLY_TARGETS, ids=lambda t: t.name)
    def test_deliberate_exception_target_renders_as_one_identifier(self, target):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdCommentExpression(
            dialect, target, "some_name", "c"
        ).to_sql()
        assert sql == f'COMMENT ON {target.value} "SOME_NAME" IS \'c\''
        assert params == ()

    @pytest.mark.parametrize("target", STRING_ONLY_TARGETS, ids=lambda t: t.name)
    def test_the_two_containers_are_handled_outside_the_table(self, target):
        """COLUMN and PARAMETER name a *member*, so they never reach the table."""
        from rhosocial.activerecord.backend.impl.firebird.mixins.comment import (
            FirebirdCommentMixin,
        )

        assert target.value not in FirebirdCommentMixin._COMMENT_OBJECT_KINDS
        assert FirebirdCommentObjectType.COLUMN.value not in FirebirdCommentMixin._COMMENT_OBJECT_KINDS
        assert FirebirdCommentObjectType.PARAMETER.value not in FirebirdCommentMixin._COMMENT_OBJECT_KINDS

    def test_object_kinds_render_through_the_object_layer(self):
        """A kind in the table quotes through format_identifier, like everything else."""
        dialect = FirebirdDialect((4, 0, 0))
        for target, kind in (
            (FirebirdCommentObjectType.TABLE, "TABLE"),
            (FirebirdCommentObjectType.VIEW, "VIEW"),
            (FirebirdCommentObjectType.GENERATOR, "GENERATOR"),
            (FirebirdCommentObjectType.SEQUENCE, "SEQUENCE"),
            (FirebirdCommentObjectType.DOMAIN, "DOMAIN"),
            (FirebirdCommentObjectType.PROCEDURE, "PROCEDURE"),
            (FirebirdCommentObjectType.FUNCTION, "FUNCTION"),
            (FirebirdCommentObjectType.TRIGGER, "TRIGGER"),
        ):
            sql, _ = FirebirdCommentExpression(dialect, target, "t", "c").to_sql()
            assert sql == f'COMMENT ON {kind} "T" IS \'c\''

