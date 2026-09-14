# tests/rhosocial/activerecord_firebird_test/feature/backend/expression/test_expression_signatures.py
"""Tests for Firebird expression class signatures.

Each expression-dispatched ``format_*`` method has the
``(self, expr) -> Tuple[str, tuple]`` signature and reads its rendering data
from the expression node it is handed.

All tests are pure construction — no database connection.
"""

from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.expression import (
    BlobColumnExpression,
    BlobLiteralExpression,
    UpdateOrInsertExpression,
    AutonomousTransactionDoExpression,
    ExecuteBlockExpression,
)
from rhosocial.activerecord.backend.impl.firebird.expression.generator import (
    GenIdExpression,
)


class TestBlobColumnExpression:
    def test_blob_column_expression_to_sql(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = BlobColumnExpression(
            dialect, "photo", sub_type=0, segment_size=65536,
        ).to_sql()
        assert sql == '"PHOTO" BLOB SUB_TYPE 0 SEGMENT SIZE 65536'
        assert params == ()

    def test_blob_column_expression_with_charset(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = BlobColumnExpression(
            dialect, "data", sub_type=1, character_set="UTF8",
        ).to_sql()
        assert sql == '"DATA" BLOB SUB_TYPE 1 CHARACTER SET UTF8 SEGMENT SIZE 65536'
        assert params == ()


class TestBlobLiteralExpression:
    def test_blob_literal_expression_to_sql(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = BlobLiteralExpression(
            dialect, b"\xde\xad\xbe\xef",
        ).to_sql()
        assert sql == "X'deadbeef'"
        assert params == ()

    def test_blob_literal_expression_empty(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = BlobLiteralExpression(dialect, b"").to_sql()
        assert sql == "X''"
        assert params == ()


class TestUpdateOrInsertExpression:
    def test_update_or_insert_expression_to_sql(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = UpdateOrInsertExpression(
            dialect,
            "users",
            ["name", "email"],
            ["Alice", "alice@example.com"],
            ["email"],
        ).to_sql()
        assert sql == (
            'UPDATE OR INSERT INTO "USERS" ("NAME", "EMAIL") '
            'VALUES (?, ?) MATCHING ("EMAIL")'
        )
        assert params == ("Alice", "alice@example.com")

    def test_update_or_insert_expression_with_returning(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = UpdateOrInsertExpression(
            dialect,
            "users",
            ["name"],
            ["Bob"],
            ["name"],
            returning_columns=["id", "name"],
        ).to_sql()
        assert sql == (
            'UPDATE OR INSERT INTO "USERS" ("NAME") VALUES (?) '
            'MATCHING ("NAME") RETURNING "ID", "NAME"'
        )
        assert params == ("Bob",)


class TestAutonomousTransactionDoExpression:
    def test_autonomous_transaction_do_expression_to_sql(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = AutonomousTransactionDoExpression(
            dialect, "EXECUTE PROCEDURE do_thing;",
        ).to_sql()
        assert sql == "IN AUTONOMOUS TRANSACTION DO BEGIN\nEXECUTE PROCEDURE do_thing;\nEND"
        assert params == ()

    def test_autonomous_transaction_do_expression_preserves_begin(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = AutonomousTransactionDoExpression(
            dialect, "BEGIN\n  INSERT INTO log VALUES (1);\nEND",
        ).to_sql()
        assert sql == (
            "IN AUTONOMOUS TRANSACTION DO BEGIN\n"
            "  INSERT INTO log VALUES (1);\nEND"
        )
        assert params == ()


class TestExecuteBlockExpression:
    def test_execute_block_expression_to_sql(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = ExecuteBlockExpression(
            dialect, "INSERT INTO log VALUES (1);",
        ).to_sql()
        assert sql == (
            "EXECUTE BLOCK\nAS\nBEGIN\nINSERT INTO log VALUES (1);\nEND"
        )
        assert params == ()

    def test_execute_block_expression_with_params(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = ExecuteBlockExpression(
            dialect,
            "INSERT INTO log VALUES (:p_val);",
            params={"p_val": ("INTEGER", 42)},
        ).to_sql()
        assert sql == (
            "EXECUTE BLOCK (p_val INTEGER = ?)\n"
            "AS\nBEGIN\nINSERT INTO log VALUES (:p_val);\nEND"
        )
        assert params == (42,)


class TestGenIdExpression:
    def test_gen_id_expression_default_step(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = GenIdExpression(dialect, "gen_c").to_sql()
        assert sql == 'GEN_ID("GEN_C", 1)'
        assert params == ()

    def test_gen_id_expression_explicit_step(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = GenIdExpression(dialect, "gen_c", 2).to_sql()
        assert sql == 'GEN_ID("GEN_C", 2)'
        assert params == ()
