# tests/rhosocial/activerecord_firebird_test/feature/backend/test_ddl_extensions.py
"""Offline unit coverage for Firebird DDL extension formatters.

Domain / package / routine DDL previously had no direct tests; the codecov
report showed concentrated misses in these mixins (see
.claude/plan/2026-08-26/coverage-restoration.md).
"""
import pytest

from rhosocial.activerecord.backend.expression.types.integer import IntegerType
from rhosocial.activerecord.backend.expression.types.numeric import DecimalType
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.expression.ddl.domain import (
    FirebirdAlterDomainExpression,
    FirebirdCreateDomainExpression,
    FirebirdDomainAlterMode,
    FirebirdDropDomainExpression,
)
from rhosocial.activerecord.backend.impl.firebird.expression.ddl.package import (
    FirebirdCreatePackageBodyExpression,
    FirebirdCreatePackageExpression,
    FirebirdDropPackageExpression,
)


@pytest.fixture(scope="module")
def dialect() -> FirebirdDialect:
    return FirebirdDialect((4, 0))


class TestDomainDDL:
    def test_create_domain_full(self, dialect):
        expr = FirebirdCreateDomainExpression(
            dialect, "salary_range", data_type=DecimalType(precision=10, scale=2),
            default=0, not_null=True, check="VALUE >= 0",
        )
        sql, params = expr.to_sql()
        assert sql == (
            "CREATE DOMAIN \"SALARY_RANGE\" AS DECIMAL(10, 2) "
            "DEFAULT 0 NOT NULL CHECK (VALUE >= 0)"
        )
        assert params == ()

    def test_create_domain_minimal(self, dialect):
        sql, _ = FirebirdCreateDomainExpression(
            dialect, "flag", data_type=IntegerType()
        ).to_sql()
        assert sql == "CREATE DOMAIN \"FLAG\" AS INTEGER"

    def test_alter_domain_all_modes(self, dialect):
        cases = [
            (FirebirdDomainAlterMode.SET_DEFAULT, 'ALTER DOMAIN "D" SET DEFAULT 7'),
            (FirebirdDomainAlterMode.DROP_DEFAULT, 'ALTER DOMAIN "D" DROP DEFAULT'),
            (FirebirdDomainAlterMode.SET_NOT_NULL, 'ALTER DOMAIN "D" SET NOT NULL'),
            (FirebirdDomainAlterMode.DROP_NOT_NULL, 'ALTER DOMAIN "D" DROP NOT NULL'),
        ]
        extra_kwargs = {FirebirdDomainAlterMode.SET_DEFAULT: {"value": 7}}
        for mode, expected in cases:
            sql, _ = FirebirdAlterDomainExpression(
                dialect, "d", mode=mode, **extra_kwargs.get(mode, {})
            ).to_sql()
            assert sql == expected

    def test_alter_domain_add_constraint(self, dialect):
        sql, _ = FirebirdAlterDomainExpression(
            dialect, "d", mode=FirebirdDomainAlterMode.ADD_CONSTRAINT,
            constraint_name="ck", constraint_sql="VALUE > 0",
        ).to_sql()
        assert sql == 'ALTER DOMAIN "D" ADD CONSTRAINT "CK" CHECK (VALUE > 0)'

    def test_drop_domain(self, dialect):
        sql, _ = FirebirdDropDomainExpression(dialect, "obsolete").to_sql()
        assert sql == 'DROP DOMAIN "OBSOLETE"'


class TestPackageDDL:
    def test_create_package_with_body(self, dialect):
        sql, _ = FirebirdCreatePackageExpression(
            dialect, "pkg_inventory", body="  PROCEDURE p();"
        ).to_sql()
        assert 'CREATE PACKAGE "PKG_INVENTORY"' in sql
        assert "PROCEDURE p();" in sql

    def test_create_package_body(self, dialect):
        sql, _ = FirebirdCreatePackageBodyExpression(
            dialect, "pkg_inventory", body="IMPLEMENTATION"
        ).to_sql()
        assert 'CREATE PACKAGE BODY "PKG_INVENTORY"' in sql
        assert "IMPLEMENTATION" in sql

    def test_drop_package_variants(self, dialect):
        header_sql, _ = FirebirdDropPackageExpression(dialect, "pkg_old").to_sql()
        assert header_sql == 'DROP PACKAGE "PKG_OLD"'
        body_sql, _ = FirebirdDropPackageExpression(dialect, "pkg_old", body=True).to_sql()
        assert body_sql == 'DROP PACKAGE BODY "PKG_OLD"'
