# tests/rhosocial/activerecord_firebird_test/feature/backend/test_introspection_sql_builders.py
"""Offline tests for the Firebird introspector's and status introspector's builders.

Every catalogue query this backend asks is a ``QueryStatement`` over ``RDB$`` /
``MON$`` relations, rendered by the dialect (org guide §16.2). These tests read
the questions back off the rendered statements: that each value the caller
supplies is still a bind parameter, that each literal the old text wrote inline
is still inline, and that the projection order and aliases -- which are what
the parsers above look up -- did not move.

The identifier spelling is this dialect's: Firebird folds unquoted names to
upper case and quotes every name it renders, so ``RDB$RELATIONS`` renders as
``"RDB$RELATIONS"`` and ``rf.RDB$FIELD_NAME`` as ``"RF"."RDB$FIELD_NAME"``.
Both forms name the same catalogue object, and the quoted one is what
``format_identifier`` produces for every other name in this backend.
"""

import pytest

from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.introspection.async_introspector import (
    FirebirdAsyncIntrospectorMixin,
)
from rhosocial.activerecord.backend.impl.firebird.introspection.status_introspector import (
    FirebirdStatusIntrospectorMixin,
)


class IntrospectionProbe(FirebirdAsyncIntrospectorMixin):
    def __init__(self, dialect):
        self._backend = type("_B", (), {"dialect": dialect})()


class StatusProbe(FirebirdStatusIntrospectorMixin):
    def __init__(self, dialect):
        self._backend = type("_B", (), {"dialect": dialect})()


@pytest.fixture
def dialect():
    return FirebirdDialect(version=(4, 0, 0))


@pytest.fixture
def probe(dialect):
    return IntrospectionProbe(dialect)


@pytest.fixture
def status(dialect):
    return StatusProbe(dialect)


class TestDatabaseInfo:
    def test_reads_the_attachment_name(self, probe):
        sql, params = probe._build_database_info_sql()
        assert sql == 'SELECT "MON$DATABASE_NAME" FROM "MON$DATABASE"'
        assert params == ()


class TestTableList:
    def test_default_excludes_system_relations(self, probe):
        sql, params = probe._build_table_list_sql(None, False, True, None)
        assert sql == (
            'SELECT "RDB$RELATION_NAME", "RDB$VIEW_BLR" FROM "RDB$RELATIONS" '
            'WHERE "RDB$SYSTEM_FLAG" = 0 ORDER BY "RDB$RELATION_NAME"'
        )
        assert params == ()

    def test_without_views_adds_the_blr_test(self, probe):
        sql, _ = probe._build_table_list_sql(None, False, False, None)
        assert 'AND "RDB$VIEW_BLR" IS NULL' in sql

    def test_with_system_relations_has_no_where(self, probe):
        """The old statement's bare ``1=1`` was clause assembly, not a condition."""
        sql, _ = probe._build_table_list_sql(None, True, True, None)
        assert "WHERE" not in sql
        assert "1=1" not in sql
        assert sql == (
            'SELECT "RDB$RELATION_NAME", "RDB$VIEW_BLR" FROM "RDB$RELATIONS" '
            'ORDER BY "RDB$RELATION_NAME"'
        )


class TestColumnList:
    def test_projection_order_and_aliases(self, probe):
        sql, params = probe._build_column_list_sql("orders", None)
        # The parsers read these names, in this order.
        expected_aliases = [
            "COLUMN_NAME",
            "FIELD_TYPE",
            "FIELD_SUB_TYPE",
            "CHAR_LENGTH",
            "PRECISION",
            "SCALE",
            "NULL_FLAG",
            "DEFAULT_SOURCE",
            "POSITION",
            "COMPUTED_SOURCE",
        ]
        positions = [sql.index(f'AS "{a}"') for a in expected_aliases]
        assert positions == sorted(positions)
        assert params == ("orders",)
        assert "?" in sql and "'orders'" not in sql

    def test_joins_the_domain_the_column_was_declared_from(self, probe):
        sql, _ = probe._build_column_list_sql("orders", None)
        assert (
            'FROM "RDB$RELATION_FIELDS" AS "RF" JOIN "RDB$FIELDS" AS "F" '
            'ON "RF"."RDB$FIELD_SOURCE" = "F"."RDB$FIELD_NAME"' in sql
        )
        assert sql.endswith('ORDER BY "RF"."RDB$POSITION"')


class TestIndexList:
    def test_projection_and_binding(self, probe):
        sql, params = probe._build_index_list_sql("orders", None)
        assert 'AS "INDEX_NAME"' in sql and 'AS "FIELD_POSITION"' in sql
        assert params == ("orders",)
        assert sql.endswith('ORDER BY "I"."RDB$INDEX_NAME", "ISG"."RDB$FIELD_POSITION"')


class TestPrimaryKey:
    def test_unique_flag_and_name_pattern_are_literals(self, probe):
        sql, params = probe._build_primary_key_sql("orders", None)
        assert '"I"."RDB$UNIQUE_FLAG" = 1' in sql
        assert "\"I\".\"RDB$INDEX_NAME\" LIKE 'RDB$PRIMARY%'" in sql
        assert params == ("orders",)


class TestForeignKey:
    def test_six_relation_reads_are_stated(self, probe):
        sql, params = probe._build_foreign_key_sql("orders", None)
        for alias in ("RC", "SEG", "I", "REF_SEG", "REF_I", "REF"):
            assert f'AS "{alias}"' in sql
        assert params == ("orders",)

    def test_referencing_and_referenced_segments_stay_apart(self, probe):
        """Two reads of ``RDB$INDEX_SEGMENTS`` under different joins."""
        sql, _ = probe._build_foreign_key_sql("orders", None)
        assert 'AS "SEG"' in sql and 'AS "REF_SEG"' in sql
        assert '"RC"."RDB$INDEX_NAME" = "SEG"."RDB$INDEX_NAME"' in sql
        assert '"RC"."RDB$CONSTRAINT_NAME_UQ" = "REF_SEG"."RDB$INDEX_NAME"' in sql


class TestViewList:
    def test_blr_test_is_not_null(self, probe):
        sql, params = probe._build_view_list_sql(None)
        assert sql == (
            'SELECT "RDB$RELATION_NAME", "RDB$VIEW_SOURCE" FROM "RDB$RELATIONS" '
            'WHERE "RDB$SYSTEM_FLAG" = 0 AND "RDB$VIEW_BLR" IS NOT NULL '
            'ORDER BY "RDB$RELATION_NAME"'
        )
        assert params == ()


class TestIntrospectionQueriesMapping:
    """The dialect-level mapping names the same questions as the introspector."""

    def test_every_entry_is_a_rendered_pair(self, dialect):
        queries = dialect.INTROSPECTION_QUERIES
        assert set(queries) == {
            "tables",
            "columns",
            "indices",
            "triggers",
            "generators",
            "procedures",
        }
        for name, (sql, params) in queries.items():
            assert sql.startswith("SELECT "), name
            assert params == (), name

    def test_the_mapping_carries_no_text_template(self, dialect):
        """No ``self.p()`` marker survives into the shape view."""
        for name, (sql, params) in dialect.INTROSPECTION_QUERIES.items():
            assert "?" not in sql, name
            assert "%s" not in sql, name
            assert params == (), name


class TestStatusQueries:
    def test_version_reads_the_system_context(self, status):
        sql, params = status._version_string_sql()
        assert sql == (
            "SELECT RDB$GET_CONTEXT('SYSTEM', 'ENGINE_VERSION') AS \"VERSION\" "
            'FROM "RDB$DATABASE"'
        )
        assert params == ()

    def test_statement_and_attachment_counts(self, status):
        sql, params = status._statement_count_sql()
        assert sql == 'SELECT COUNT(*) AS "C" FROM "MON$STATEMENTS"'
        assert params == ()
        sql, params = status._attachment_count_sql()
        assert sql == 'SELECT COUNT(*) AS "C" FROM "MON$ATTACHMENTS"'
        assert params == ()

    def test_attachment_list_projection(self, status):
        sql, params = status._attachment_list_sql()
        for alias in ("ID", "USERNAME", "REMOTE_ADDR", "REMOTE_PID"):
            assert f'AS "{alias}"' in sql
        assert params == ()

    def test_database_size_casts_before_multiplying(self, status):
        """A smallint page size times a page count overflows 16 bits."""
        sql, params = status._database_size_sql()
        assert sql == (
            'SELECT CAST("MON$PAGE_SIZE" AS BIGINT) * "MON$PAGES" AS "SIZE_BYTES" '
            'FROM "MON$DATABASE"'
        )
        assert params == ()

    def test_database_files_projection(self, status):
        sql, params = status._database_files_sql()
        assert 'AS "FILE_ID"' in sql and 'AS "PAGES"' in sql and 'AS "SIZE_BYTES"' in sql
        assert params == ()

    def test_database_name_alias(self, status):
        sql, params = status._database_name_sql()
        assert sql == 'SELECT "MON$DATABASE_NAME" AS "NAME" FROM "MON$DATABASE"'
        assert params == ()

    def test_rdb_users_filters_null_names(self, status):
        sql, params = status._rdb_users_sql()
        assert sql == (
            'SELECT "USER_NAME" AS "USERNAME" FROM "RDB$USERS" '
            'WHERE "USER_NAME" IS NOT NULL ORDER BY "USER_NAME"'
        )
        assert params == ()

    def test_attached_users_is_the_distinct_fallback(self, status):
        sql, params = status._attached_users_sql()
        assert sql == (
            'SELECT DISTINCT "MON$USER" AS "USERNAME" FROM "MON$ATTACHMENTS" '
            'WHERE "MON$USER" IS NOT NULL'
        )
        assert params == ()
