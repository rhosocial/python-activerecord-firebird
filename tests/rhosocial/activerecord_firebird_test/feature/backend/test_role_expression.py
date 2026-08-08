# tests/rhosocial/activerecord_firebird_test/feature/backend/test_role_expression.py
"""Tests for Firebird CREATE/ALTER/DROP ROLE expressions.

``CREATE ROLE`` / ``DROP ROLE`` are gated at ``(2, 5, 0)`` while ``ALTER ROLE``
requires Firebird 3.0. All tests are pure construction — no database connection.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.expression import (
    FirebirdAlterRoleExpression,
    FirebirdCreateRoleExpression,
    FirebirdDropRoleExpression,
    FirebirdRoleAlterClause,
)


class TestCreateRole:
    def test_create_role(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdCreateRoleExpression(dialect, "r").to_sql()
        assert sql == 'CREATE ROLE "R"'
        assert params == ()

    def test_create_role_fb2_5(self):
        dialect = FirebirdDialect((2, 5, 0))
        sql, params = FirebirdCreateRoleExpression(dialect, "r").to_sql()
        assert sql == 'CREATE ROLE "R"'
        assert params == ()


class TestAlterRole:
    def test_alter_role_set_default(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdAlterRoleExpression(dialect, "r").to_sql()
        assert sql == 'ALTER ROLE "R" SET DEFAULT'
        assert params == ()

    def test_alter_role_set_active(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdAlterRoleExpression(
            dialect, "r", clause=FirebirdRoleAlterClause.SET_ACTIVE
        ).to_sql()
        assert sql == 'ALTER ROLE "R" SET ACTIVE'
        assert params == ()

    def test_alter_role_set_auto_admin(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdAlterRoleExpression(
            dialect, "r", clause=FirebirdRoleAlterClause.SET_AUTO_ADMIN
        ).to_sql()
        assert sql == 'ALTER ROLE "R" SET AUTO_ADMIN'
        assert params == ()

    def test_alter_role_drop_auto_admin(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdAlterRoleExpression(
            dialect, "r", clause=FirebirdRoleAlterClause.DROP_AUTO_ADMIN
        ).to_sql()
        assert sql == 'ALTER ROLE "R" DROP AUTO_ADMIN'
        assert params == ()

    def test_alter_role_rename_to(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdAlterRoleExpression(
            dialect, "r", clause=FirebirdRoleAlterClause.RENAME_TO, new_name="r2"
        ).to_sql()
        assert sql == 'ALTER ROLE "R" RENAME TO "R2"'
        assert params == ()

    def test_alter_role_requires_fb3(self):
        dialect = FirebirdDialect((2, 5, 0))
        with pytest.raises(UnsupportedFeatureError):
            FirebirdAlterRoleExpression(dialect, "r").to_sql()


class TestDropRole:
    def test_drop_role(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdDropRoleExpression(dialect, "r").to_sql()
        assert sql == 'DROP ROLE "R"'
        assert params == ()


class TestRoleDispatch:
    def test_expression_to_sql_delegates_to_dialect(self):
        from rhosocial.activerecord.backend.impl.firebird.mixins.role import FirebirdRoleMixin

        dialect = FirebirdDialect((4, 0, 0))
        assert type(dialect).format_create_role_statement == FirebirdRoleMixin.format_create_role_statement
        assert type(dialect).format_alter_role_statement == FirebirdRoleMixin.format_alter_role_statement
        assert type(dialect).format_drop_role_statement == FirebirdRoleMixin.format_drop_role_statement

    def test_supports_role_flags(self):
        assert FirebirdDialect((2, 5, 0)).supports_roles() is True
        assert FirebirdDialect((2, 5, 0)).supports_create_role() is True
        assert FirebirdDialect((2, 5, 0)).supports_drop_role() is True
        assert FirebirdDialect((2, 5, 0)).supports_alter_role() is False
        assert FirebirdDialect((3, 0, 0)).supports_alter_role() is True
