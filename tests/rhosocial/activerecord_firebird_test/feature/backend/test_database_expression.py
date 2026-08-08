# tests/rhosocial/activerecord_firebird_test/feature/backend/test_database_expression.py
"""Tests for Firebird CREATE / DROP DATABASE expressions.

Database creation/removal is operational DDL gated at ``(2, 5, 0)``. All tests
are pure construction — no database connection.
"""

from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.expression import (
    FirebirdCreateDatabaseExpression,
    FirebirdDatabaseSecurityMode,
    FirebirdDropDatabaseExpression,
)


class TestCreateDatabase:
    def test_create_database_minimal(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdCreateDatabaseExpression(dialect, "file.fdb").to_sql()
        assert sql == "CREATE DATABASE 'file.fdb'"
        assert params == ()

    def test_create_database_full(self):
        dialect = FirebirdDialect((4, 0, 0))
        expr = FirebirdCreateDatabaseExpression(
            dialect,
            "file.fdb",
            user="u",
            password="p",
            page_size=16384,
            default_character_set="UTF8",
            collation="UNICODE_CI",
            sql_dialect=3,
            force_write=True,
        )
        sql, params = expr.to_sql()
        assert sql == (
            "CREATE DATABASE 'file.fdb' USER 'u' PASSWORD 'p' "
            "PAGE_SIZE 16384 DEFAULT CHARACTER SET UTF8 "
            "COLLATION 'UNICODE_CI' DIALECT 3 FORCE WRITE"
        )
        assert params == ()

    def test_create_database_remote_alias(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdCreateDatabaseExpression(
            dialect,
            "baseserver:test",
            user="wizard",
            password="player",
            default_character_set="UTF8",
        ).to_sql()
        assert sql == (
            "CREATE DATABASE 'baseserver:test' "
            "USER 'wizard' PASSWORD 'player' DEFAULT CHARACTER SET UTF8"
        )
        assert params == ()

    def test_create_database_sql_security_enum(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdCreateDatabaseExpression(
            dialect, "file.fdb", sql_security=FirebirdDatabaseSecurityMode.DEFINER
        ).to_sql()
        assert sql == "CREATE DATABASE 'file.fdb' SQL SECURITY DEFINER"
        assert params == ()

    def test_create_database_sql_security_string(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdCreateDatabaseExpression(
            dialect, "file.fdb", sql_security="INVOKER"
        ).to_sql()
        assert sql == "CREATE DATABASE 'file.fdb' SQL SECURITY INVOKER"
        assert params == ()

    def test_create_database_quoting(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdCreateDatabaseExpression(
            dialect, "/path/to/it's.db", user="u", password="p'w"
        ).to_sql()
        assert sql == "CREATE DATABASE '/path/to/it''s.db' USER 'u' PASSWORD 'p''w'"
        assert params == ()


class TestDropDatabase:
    def test_drop_database(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdDropDatabaseExpression(dialect).to_sql()
        assert sql == "DROP DATABASE"
        assert params == ()


class TestDatabaseDispatch:
    def test_expression_to_sql_delegates_to_dialect(self):
        from rhosocial.activerecord.backend.impl.firebird.mixins.database import (
            FirebirdDatabaseMixin,
        )

        dialect = FirebirdDialect((4, 0, 0))
        assert (
            type(dialect).format_create_database_statement
            == FirebirdDatabaseMixin.format_create_database_statement
        )
        assert (
            type(dialect).format_drop_database_statement
            == FirebirdDatabaseMixin.format_drop_database_statement
        )

    def test_supports_create_database_true(self):
        assert FirebirdDialect((2, 5, 0)).supports_create_database() is True
        assert FirebirdDialect((2, 5, 0)).supports_drop_database() is True
        assert FirebirdDialect((5, 0, 0)).supports_create_database() is True
