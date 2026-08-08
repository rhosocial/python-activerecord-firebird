# tests/rhosocial/activerecord_firebird_test/feature/backend/test_user_expression.py
"""Tests for Firebird CREATE/ALTER/DROP USER expressions.

SQL user management requires Firebird 3.0; all three statements are gated at
``(3, 0, 0)``. All tests are pure construction — no database connection.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.expression import (
    FirebirdAlterUserExpression,
    FirebirdCreateUserExpression,
    FirebirdDropUserExpression,
)


class TestCreateUser:
    def test_create_user_full(self):
        dialect = FirebirdDialect((4, 0, 0))
        expr = FirebirdCreateUserExpression(
            dialect,
            "u",
            "secret",
            first_name="Jo",
            middle_name="Q",
            last_name="Doe",
            grant_admin_role=True,
        )
        sql, params = expr.to_sql()
        assert sql == (
            'CREATE USER "U" PASSWORD \'secret\' '
            "FIRSTNAME 'Jo' MIDDLENAME 'Q' LASTNAME 'Doe' GRANT ADMIN ROLE"
        )
        assert params == ()

    def test_create_user_first_last(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdCreateUserExpression(
            dialect, "u", "secret", first_name="Jo", last_name="Doe"
        ).to_sql()
        assert sql == 'CREATE USER "U" PASSWORD \'secret\' FIRSTNAME \'Jo\' LASTNAME \'Doe\''
        assert params == ()

    def test_create_user_minimal(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdCreateUserExpression(dialect, "u", "secret").to_sql()
        assert sql == 'CREATE USER "U" PASSWORD \'secret\''
        assert params == ()


class TestAlterUser:
    def test_alter_user_password(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdAlterUserExpression(dialect, "u", password="newpass").to_sql()
        assert sql == 'ALTER USER "U" PASSWORD \'newpass\''
        assert params == ()

    def test_alter_user_credentials(self):
        dialect = FirebirdDialect((4, 0, 0))
        expr = FirebirdAlterUserExpression(
            dialect, "u", password="newpass", first_name="Jan", last_name="Do"
        )
        sql, params = expr.to_sql()
        assert sql == (
            'ALTER USER "U" PASSWORD \'newpass\' '
            "FIRSTNAME 'Jan' LASTNAME 'Do'"
        )
        assert params == ()

    def test_alter_user_admin_role(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdAlterUserExpression(
            dialect, "u", grant_admin_role=True
        ).to_sql()
        assert sql == 'ALTER USER "U" GRANT ADMIN ROLE'
        assert params == ()

    def test_alter_user_revoke_admin_role(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdAlterUserExpression(
            dialect, "u", revoke_admin_role=True
        ).to_sql()
        assert sql == 'ALTER USER "U" REVOKE ADMIN ROLE'
        assert params == ()


class TestDropUser:
    def test_drop_user(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdDropUserExpression(dialect, "u").to_sql()
        assert sql == 'DROP USER "U"'
        assert params == ()


class TestUserDispatch:
    def test_expression_to_sql_delegates_to_dialect(self):
        from rhosocial.activerecord.backend.impl.firebird.mixins.user import FirebirdUserMixin

        dialect = FirebirdDialect((4, 0, 0))
        assert type(dialect).format_create_user_statement == FirebirdUserMixin.format_create_user_statement
        assert type(dialect).format_alter_user_statement == FirebirdUserMixin.format_alter_user_statement
        assert type(dialect).format_drop_user_statement == FirebirdUserMixin.format_drop_user_statement


class TestUserVersionGating:
    def test_sql_user_management_requires_fb3(self):
        dialect = FirebirdDialect((2, 5, 0))
        with pytest.raises(UnsupportedFeatureError):
            FirebirdCreateUserExpression(dialect, "u", "secret").to_sql()
        with pytest.raises(UnsupportedFeatureError):
            FirebirdAlterUserExpression(dialect, "u", password="newpass").to_sql()
        with pytest.raises(UnsupportedFeatureError):
            FirebirdDropUserExpression(dialect, "u").to_sql()

    def test_supports_user_flags(self):
        assert FirebirdDialect((2, 5, 0)).supports_create_user() is False
        assert FirebirdDialect((2, 5, 0)).supports_alter_user() is False
        assert FirebirdDialect((2, 5, 0)).supports_drop_user() is False
        assert FirebirdDialect((3, 0, 0)).supports_create_user() is True
        assert FirebirdDialect((3, 0, 0)).supports_alter_user() is True
        assert FirebirdDialect((3, 0, 0)).supports_drop_user() is True
