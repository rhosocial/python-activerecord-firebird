# tests/rhosocial/activerecord_firebird_test/feature/backend/construct/ddl/test_alter_column_type.py
"""A column type change is rendered as Firebird's ``ALTER COLUMN c TYPE``.

Firebird has no ``SET DATA TYPE`` spelling: changing a column's type is
``ALTER TABLE ... ALTER COLUMN col TYPE datatype``. The backend formatter must
emit that clause so the rejected standard spelling never reaches the server.

Pure-construction tests: no database connection is required.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.statements import AlterTableStatement
from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
    AlterColumnAction,
    ColumnAlterOperation,
)
from rhosocial.activerecord.backend.expression.types import IntegerType, VarCharType
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect


@pytest.fixture
def dialect():
    return FirebirdDialect()


class TestAlterColumnTypeRendering:
    def test_set_data_type_renders_as_type_clause(self, dialect):
        action = AlterColumnAction(
            dialect,
            "c",
            ColumnAlterOperation.SET_DATA_TYPE,
            new_value=IntegerType(dialect),
        )
        sql, params = action.to_sql()
        assert sql == 'ALTER COLUMN "C" TYPE INTEGER'
        assert "SET DATA TYPE" not in sql
        assert params == ()

    def test_set_data_type_in_alter_table_statement(self, dialect):
        action = AlterColumnAction(
            dialect,
            "c",
            ColumnAlterOperation.SET_DATA_TYPE,
            new_value=VarCharType(dialect, length=20),
        )
        stmt = AlterTableStatement(dialect, Table(dialect, "t"), actions=[action])
        sql, params = stmt.to_sql()
        assert sql == 'ALTER TABLE "T" ALTER COLUMN "C" TYPE VARCHAR(20)'
        assert "SET DATA TYPE" not in sql
        assert params == ()

    def test_set_data_type_accepts_raw_operation_spelling(self, dialect):
        action = AlterColumnAction(
            dialect, "c", "SET DATA TYPE", new_value=IntegerType(dialect)
        )
        assert action.to_sql()[0] == 'ALTER COLUMN "C" TYPE INTEGER'

    def test_non_type_properties_keep_the_core_gate(self, dialect):
        # SET/DROP DEFAULT and SET/DROP NOT NULL are not offered through this
        # action on Firebird; the delegated core formatter still refuses them.
        action = AlterColumnAction(
            dialect, "c", ColumnAlterOperation.SET_DEFAULT, new_value="'x'"
        )
        with pytest.raises(UnsupportedFeatureError):
            action.to_sql()
