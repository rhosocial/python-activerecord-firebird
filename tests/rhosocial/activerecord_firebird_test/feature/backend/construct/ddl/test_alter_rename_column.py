# tests/rhosocial/activerecord_firebird_test/feature/backend/construct/ddl/test_alter_rename_column.py
"""A column rename is rendered as Firebird's ``ALTER COLUMN old TO new``.

Firebird has no ``RENAME COLUMN`` clause: the vendor spelling inside
``ALTER TABLE`` is ``ALTER [COLUMN] oldname TO newname``. The backend
formatter must emit that clause so the rejected standard spelling never
reaches the server.

Pure-construction tests: no database connection is required.
"""

import pytest

from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.statements import AlterTableStatement
from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
    RenameColumnAction,
)
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect


@pytest.fixture
def dialect():
    return FirebirdDialect((5, 0, 0))


class TestRenameColumnRendering:
    def test_renders_vendor_spelling(self, dialect):
        assert dialect.supports_rename_column() is True
        sql, params = RenameColumnAction(dialect, "old_name", "new_name").to_sql()
        assert sql == 'ALTER COLUMN "OLD_NAME" TO "NEW_NAME"'
        assert "RENAME COLUMN" not in sql
        assert params == ()

    def test_renders_inside_alter_table(self, dialect):
        stmt = AlterTableStatement(
            dialect,
            Table(dialect, "t"),
            [RenameColumnAction(dialect, "a", "b")],
        )
        sql, params = stmt.to_sql()
        assert sql == 'ALTER TABLE "T" ALTER COLUMN "A" TO "B"'
        assert "RENAME COLUMN" not in sql
        assert params == ()
