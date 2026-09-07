# tests/rhosocial/activerecord_firebird_test/feature/backend/ddl/test_ddl_spec_protocol.py
"""Firebird DDL feature-spec claiming tests (``build_spec``).

Generic Specs translate via the core ``DDLSpecBuildingMixin`` (inherited from
``SQLDialectBase``); the Firebird dialect claims them without any backend-side
override. Firebird declares no partition capability (all partition capability
bits are ``False``), so partition claiming is asserted only at the marker
level: the base ``PartitionSpec`` stays unclaimed and the generated table
remains unpartitioned. Foreign/unclaimed Specs return ``None`` (silently
ignored).
"""

import pytest

from rhosocial.activerecord.base import (
    CheckSpec, DefaultSpec, ForeignKeySpec, IndexSpec,
    NotNullSpec, PartitionSpec, PrimaryKeySpec, UniqueSpec,
)
from rhosocial.activerecord.backend.expression.core import Column
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect


@pytest.fixture
def dialect():
    return FirebirdDialect(version=(4, 0, 6))


class TestProtocolConformance:
    def test_build_spec_returns_none_for_unknown(self, dialect):
        assert dialect.build_spec(object()) is None

    def test_build_spec_returns_none_for_base_partition_marker(self, dialect):
        # Firebird declares no partition capability (all partition capability
        # bits are False), so the base PartitionSpec marker is not claimed and
        # the core default (None) holds.
        assert dialect.build_spec(PartitionSpec()) is None


class TestGenericSpecTranslation:
    def test_unique_spec(self, dialect):
        result = dialect.build_spec(UniqueSpec(["a", "b"], name="uq_ab"))
        assert result.columns == ["a", "b"]

    def test_check_spec_lazy(self, dialect):
        result = dialect.build_spec(
            CheckSpec(lambda d: Column(d, "age") >= 18, name="ck_age")
        )
        assert result.check_condition is not None

    def test_not_null_spec(self, dialect):
        result = dialect.build_spec(NotNullSpec(column="a"))
        from rhosocial.activerecord.backend.expression.statements.ddl_table import (
            ColumnConstraint, ColumnConstraintType)
        assert isinstance(result, ColumnConstraint)
        assert result.constraint_type == ColumnConstraintType.NOT_NULL

    def test_primary_key_single(self, dialect):
        result = dialect.build_spec(PrimaryKeySpec(["id"]))
        from rhosocial.activerecord.backend.expression.statements.ddl_table import (
            ColumnConstraint, ColumnConstraintType)
        assert isinstance(result, ColumnConstraint)
        assert result.constraint_type == ColumnConstraintType.PRIMARY_KEY

    def test_primary_key_composite(self, dialect):
        result = dialect.build_spec(PrimaryKeySpec(["a", "b"]))
        from rhosocial.activerecord.backend.expression.statements.ddl_table import TableConstraint
        assert isinstance(result, TableConstraint)
        assert result.columns == ["a", "b"]

    def test_default_spec(self, dialect):
        result = dialect.build_spec(DefaultSpec(column="status", value="active"))
        assert result.constraint_type.name == "DEFAULT"

    def test_foreign_key_spec(self, dialect):
        result = dialect.build_spec(
            ForeignKeySpec(["user_id"], "users", ["id"], on_delete="CASCADE")
        )
        from rhosocial.activerecord.backend.expression.statements.ddl_table import ForeignKeyConstraint
        assert isinstance(result, ForeignKeyConstraint)

    def test_index_spec(self, dialect):
        result = dialect.build_spec(IndexSpec(columns=["email"], name="ix_email"))
        from rhosocial.activerecord.backend.expression.statements.ddl_table import IndexDefinition
        assert isinstance(result, IndexDefinition)


class TestModelIntegration:
    def test_model_spec_constraints(self, dialect):
        from rhosocial.activerecord.model import ActiveRecord

        class T(ActiveRecord):
            __table_name__ = "t"
            __table_constraints__ = [
                UniqueSpec(columns=["a", "b"], name="uq_ab"),
                CheckSpec(lambda d: Column(d, "x") >= 0, name="ck_x"),
            ]
            a: int
            b: int
            x: int

        expr = T.generate_create_table(dialect)
        sql, _ = expr.to_sql()
        assert "UNIQUE" in sql
        assert "CHECK" in sql

    def test_model_unclaimed_partition_is_ignored(self, dialect):
        from rhosocial.activerecord.model import ActiveRecord

        class T(ActiveRecord):
            __table_name__ = "t"
            __table_partition__ = [PartitionSpec()]
            x: int

        expr = T.generate_create_table(dialect)
        assert expr.partition is None
