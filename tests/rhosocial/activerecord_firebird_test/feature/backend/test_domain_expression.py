# tests/rhosocial/activerecord_firebird_test/feature/backend/test_domain_expression.py
"""Tests for Firebird DOMAIN statement expressions.

Covers ``CREATE DOMAIN`` (type + DEFAULT + NOT NULL + CHECK), every
``ALTER DOMAIN`` clause (SET/DROP DEFAULT, SET/DROP NOT NULL, ADD/DROP
CONSTRAINT, TYPE) and ``DROP DOMAIN``. All tests are pure construction —
no database connection.
"""

from rhosocial.activerecord.backend.expression.types import VarCharType
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.expression import (
    FirebirdAlterDomainExpression,
    FirebirdCreateDomainExpression,
    FirebirdDomainAlterMode,
    FirebirdDropDomainExpression,
)


class TestCreateDomain:
    def test_create_domain_default_and_check(self):
        dialect = FirebirdDialect((4, 0, 0))
        expr = FirebirdCreateDomainExpression(
            dialect,
            "dm_zip",
            VarCharType(10),
            default="00000",
            check="VALUE SIMILAR TO '[0-9]{5}'",
        )
        sql, params = expr.to_sql()
        assert sql == (
            'CREATE DOMAIN "DM_ZIP" AS VARCHAR(10) '
            "DEFAULT '00000' CHECK (VALUE SIMILAR TO '[0-9]{5}')"
        )
        assert params == ()

    def test_create_domain_not_null(self):
        dialect = FirebirdDialect((4, 0, 0))
        expr = FirebirdCreateDomainExpression(dialect, "dm_code", VarCharType(8), not_null=True)
        sql, params = expr.to_sql()
        assert sql == 'CREATE DOMAIN "DM_CODE" AS VARCHAR(8) NOT NULL'
        assert params == ()

    def test_create_domain_minimal(self):
        dialect = FirebirdDialect((4, 0, 0))
        expr = FirebirdCreateDomainExpression(dialect, "dm_amt", VarCharType(10))
        sql, params = expr.to_sql()
        assert sql == 'CREATE DOMAIN "DM_AMT" AS VARCHAR(10)'
        assert params == ()

    def test_create_domain_supports_flag(self):
        dialect = FirebirdDialect((4, 0, 0))
        assert dialect.supports_domain() is True
        assert dialect.supports_create_domain() is True


class TestAlterDomain:
    def _alter(self, dialect, mode, **kwargs):
        return FirebirdAlterDomainExpression(dialect, "dm_zip", mode, **kwargs).to_sql()

    def test_set_default(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = self._alter(dialect, FirebirdDomainAlterMode.SET_DEFAULT, value="12345")
        assert sql == "ALTER DOMAIN \"DM_ZIP\" SET DEFAULT '12345'"
        assert params == ()

    def test_drop_default(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = self._alter(dialect, FirebirdDomainAlterMode.DROP_DEFAULT)
        assert sql == 'ALTER DOMAIN "DM_ZIP" DROP DEFAULT'
        assert params == ()

    def test_set_not_null(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = self._alter(dialect, FirebirdDomainAlterMode.SET_NOT_NULL)
        assert sql == 'ALTER DOMAIN "DM_ZIP" SET NOT NULL'
        assert params == ()

    def test_drop_not_null(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = self._alter(dialect, FirebirdDomainAlterMode.DROP_NOT_NULL)
        assert sql == 'ALTER DOMAIN "DM_ZIP" DROP NOT NULL'
        assert params == ()

    def test_add_constraint(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = self._alter(
            dialect,
            FirebirdDomainAlterMode.ADD_CONSTRAINT,
            constraint_name="chk",
            constraint_sql="VALUE SIMILAR TO '[0-9]{5}'",
        )
        assert sql == (
            'ALTER DOMAIN "DM_ZIP" ADD CONSTRAINT "CHK" '
            "CHECK (VALUE SIMILAR TO '[0-9]{5}')"
        )
        assert params == ()

    def test_drop_constraint(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = self._alter(
            dialect,
            FirebirdDomainAlterMode.DROP_CONSTRAINT,
            constraint_name="chk",
        )
        assert sql == 'ALTER DOMAIN "DM_ZIP" DROP CONSTRAINT "CHK"'
        assert params == ()

    def test_set_type(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = self._alter(
            dialect,
            FirebirdDomainAlterMode.SET_TYPE,
            data_type=VarCharType(12),
        )
        assert sql == 'ALTER DOMAIN "DM_ZIP" TYPE VARCHAR(12)'
        assert params == ()


class TestDropDomain:
    def test_drop_domain(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdDropDomainExpression(dialect, "dm_zip").to_sql()
        assert sql == 'DROP DOMAIN "DM_ZIP"'
        assert params == ()


class TestDomainDispatch:
    def test_expression_to_sql_delegates_to_dialect(self):
        from rhosocial.activerecord.backend.impl.firebird.mixins.domain import FirebirdDomainMixin

        dialect = FirebirdDialect((4, 0, 0))
        assert type(dialect).format_create_domain_statement == FirebirdDomainMixin.format_create_domain_statement
        assert type(dialect).format_alter_domain_statement == FirebirdDomainMixin.format_alter_domain_statement
        assert type(dialect).format_drop_domain_statement == FirebirdDomainMixin.format_drop_domain_statement

    def test_supports_domain_true_across_supported_versions(self):
        assert FirebirdDialect((2, 5, 0)).supports_domain() is True
        assert FirebirdDialect((5, 0, 0)).supports_domain() is True
