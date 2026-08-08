# tests/rhosocial/activerecord_firebird_test/feature/backend/test_comment_expression.py
"""Tests for Firebird COMMENT ON expressions.

``COMMENT ON`` annotates metadata objects and is available since Firebird 2.5
(gated here at ``(2, 5, 0)``). All tests are pure construction — no database
connection.
"""

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
