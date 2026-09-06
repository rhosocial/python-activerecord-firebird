# tests/rhosocial/activerecord_firebird_test/feature/backend/introspection/test_async_introspector.py
"""Offline unit tests for Firebird async introspection.

Covers :class:`FirebirdAsyncIntrospectorMixin` and :class:`AsyncFirebirdIntrospector`
without a live Firebird server: a scripted executor answers SQL with hand-built
rows, and the real FirebirdDialect is used so type parsing is exercised for real.
Parse/build methods that are not reachable through the current base-class wiring
(``_build_column_list_sql``, ``_build_index_list_sql``, ``_make_primary_key_sql``,
view SQL generation) are exercised directly.
"""
from types import SimpleNamespace

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.types._base import DataType
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.introspection.async_introspector import (
    AsyncFirebirdIntrospector,
    FirebirdAsyncIntrospectorMixin,
)
from rhosocial.activerecord.backend.impl.firebird.introspection.status_introspector import (
    AsyncFirebirdStatusIntrospector,
)
from rhosocial.activerecord.backend.introspection.types import (
    ReferentialAction,
    TableType,
)

COLUMN_ROWS = [
    {
        "COLUMN_NAME": "ID",
        "FIELD_TYPE": 8,
        "FIELD_SUB_TYPE": 0,
        "CHAR_LENGTH": None,
        "PRECISION": 18,
        "SCALE": 0,
        "NULL_FLAG": 1,
        "DEFAULT_SOURCE": None,
        "POSITION": 0,
        "COMPUTED_SOURCE": None,
    },
    {
        "COLUMN_NAME": "NAME",
        "FIELD_TYPE": 37,
        "FIELD_SUB_TYPE": 0,
        "CHAR_LENGTH": 255,
        "PRECISION": None,
        "SCALE": None,
        "NULL_FLAG": None,
        "DEFAULT_SOURCE": "default 'john'",
        "POSITION": 1,
        "COMPUTED_SOURCE": None,
    },
    {
        "COLUMN_NAME": "NOTES",
        "FIELD_TYPE": 261,
        "FIELD_SUB_TYPE": 1,
        "CHAR_LENGTH": None,
        "PRECISION": None,
        "SCALE": None,
        "NULL_FLAG": None,
        "DEFAULT_SOURCE": None,
        "POSITION": 2,
        "COMPUTED_SOURCE": None,
    },
    {
        "COLUMN_NAME": "BLOB_BIN",
        "FIELD_TYPE": 261,
        "FIELD_SUB_TYPE": 0,
        "CHAR_LENGTH": None,
        "PRECISION": None,
        "SCALE": None,
        "NULL_FLAG": None,
        "DEFAULT_SOURCE": None,
        "POSITION": 3,
        "COMPUTED_SOURCE": None,
    },
    {
        "COLUMN_NAME": "CODE",
        "FIELD_TYPE": 999,
        "FIELD_SUB_TYPE": 0,
        "CHAR_LENGTH": None,
        "PRECISION": None,
        "SCALE": None,
        "NULL_FLAG": None,
        "DEFAULT_SOURCE": None,
        "POSITION": 4,
        "COMPUTED_SOURCE": None,
    },
    {
        "COLUMN_NAME": "CH",
        "FIELD_TYPE": 14,
        "FIELD_SUB_TYPE": 0,
        "CHAR_LENGTH": 10,
        "PRECISION": None,
        "SCALE": None,
        "NULL_FLAG": None,
        "DEFAULT_SOURCE": None,
        "POSITION": 5,
        "COMPUTED_SOURCE": None,
    },
    {
        "COLUMN_NAME": None,
        "FIELD_TYPE": 23,
        "FIELD_SUB_TYPE": 0,
        "CHAR_LENGTH": None,
        "PRECISION": None,
        "SCALE": None,
        "NULL_FLAG": None,
        "DEFAULT_SOURCE": None,
        "POSITION": 6,
        "COMPUTED_SOURCE": None,
    },
]

INDEX_ROWS = [
    {
        "INDEX_NAME": "RDB$PRIMARY1",
        "UNIQUE_FLAG": 1,
        "INACTIVE": None,
        "INDEX_TYPE": 0,
        "FIELD_NAME": "ID",
        "FIELD_POSITION": 0,
    },
    {
        "INDEX_NAME": "RDB$PRIMARY1",
        "UNIQUE_FLAG": 1,
        "INACTIVE": None,
        "INDEX_TYPE": 0,
        "FIELD_NAME": "CODE",
        "FIELD_POSITION": 1,
    },
    {
        "INDEX_NAME": "IDX_NAME",
        "UNIQUE_FLAG": 0,
        "INACTIVE": None,
        "INDEX_TYPE": 1,
        "FIELD_NAME": "NAME",
        "FIELD_POSITION": 0,
    },
    {
        "INDEX_NAME": "IDX_NO_COL",
        "UNIQUE_FLAG": 0,
        "INACTIVE": None,
        "INDEX_TYPE": 1,
        "FIELD_NAME": None,
        "FIELD_POSITION": 0,
    },
    {
        "INDEX_NAME": "   ",
        "UNIQUE_FLAG": 0,
        "INACTIVE": None,
        "INDEX_TYPE": 1,
        "FIELD_NAME": "X",
        "FIELD_POSITION": 0,
    },
]

FK_ROWS = [
    {
        "CONSTRAINT_NAME": "FK_DEPT",
        "INDEX_NAME": "FK_DEPT",
        "COLUMN_NAME": "DEPT_ID",
        "REF_TABLE": "DEPARTMENTS",
        "REF_COLUMN": "ID",
        "DELETE_RULE": "CASCADE",
    },
    {
        "CONSTRAINT_NAME": "FK_DEPT",
        "INDEX_NAME": "FK_DEPT",
        "COLUMN_NAME": "DEPT_CODE",
        "REF_TABLE": "DEPARTMENTS",
        "REF_COLUMN": "CODE",
        "DELETE_RULE": "CASCADE",
    },
    {
        "CONSTRAINT_NAME": "FK_OWNER",
        "INDEX_NAME": "FK_OWNER",
        "COLUMN_NAME": "OWNER_ID",
        "REF_TABLE": "USERS",
        "REF_COLUMN": "ID",
        "DELETE_RULE": "SET NULL",
    },
    {
        "CONSTRAINT_NAME": "FK_X",
        "INDEX_NAME": "FK_X",
        "COLUMN_NAME": "X_ID",
        "REF_TABLE": "T_X",
        "REF_COLUMN": "ID",
        "DELETE_RULE": "SET DEFAULT",
    },
    {
        "CONSTRAINT_NAME": "FK_Y",
        "INDEX_NAME": "FK_Y",
        "COLUMN_NAME": "Y_ID",
        "REF_TABLE": "T_Y",
        "REF_COLUMN": "ID",
        "DELETE_RULE": "RESTRICT",
    },
    {
        "CONSTRAINT_NAME": "FK_DEFAULT",
        "INDEX_NAME": "FK_DEFAULT",
        "COLUMN_NAME": "Z_ID",
        "REF_TABLE": "T_Z",
        "REF_COLUMN": None,
        "DELETE_RULE": None,
    },
    {
        "CONSTRAINT_NAME": "FK_WEIRD",
        "INDEX_NAME": "FK_WEIRD",
        "COLUMN_NAME": None,
        "REF_TABLE": "T_W",
        "REF_COLUMN": "ID",
        "DELETE_RULE": "SOMETHING NEW",
    },
    {
        "CONSTRAINT_NAME": "",
        "INDEX_NAME": "",
        "COLUMN_NAME": "",
        "REF_TABLE": "",
        "REF_COLUMN": "",
        "DELETE_RULE": "",
    },
]


class ScriptedExecutor:
    """Async executor that answers SQL with pre-built rows by keyword matching."""

    def __init__(self, **rows_by_sql):
        self._rows = rows_by_sql
        self.calls = []

    async def execute(self, sql, params=()):
        self.calls.append((sql, params))
        return self._rows_for(sql)

    def _rows_for(self, sql):
        upper = (sql or "").upper()
        if "MON$DATABASE_NAME" in upper:
            return self._rows.get("database", [])
        if "RDB$VIEW_SOURCE" in upper:
            return self._rows.get("views", [])
        if "RDB$REF_CONSTRAINTS" in upper:
            return self._rows.get("foreign_keys", [])
        if "RDB$PRIMARY" in upper:
            return self._rows.get("primary_keys", [])
        if "RDB$INDICES" in upper:
            return self._rows.get("indexes", [])
        if "RDB$RELATION_FIELDS" in upper:
            return self._rows.get("columns", [])
        if "RDB$RELATIONS" in upper:
            return self._rows.get("tables", [])
        return []


@pytest.fixture
def dialect():
    """Return an adapted FirebirdDialect with a known version tuple."""
    d = FirebirdDialect()
    d.version = (3, 0, 0)
    return d


@pytest.fixture
def backend(dialect):
    """Return a bare backend object exposing only a real Firebird dialect."""
    return SimpleNamespace(dialect=dialect)


@pytest.fixture
def executor():
    """Return a scripted executor preloaded with representative Firebird rows."""
    return ScriptedExecutor(
        database=[{"MON$DATABASE_NAME": "/tmp/app.fdb"}],
        tables=[
            {"RDB$RELATION_NAME": "EMPLOYEES", "RDB$VIEW_BLR": None},
            {"RDB$RELATION_NAME": "V_ACTIVE", "RDB$VIEW_BLR": b"x\x00blr"},
            {"RDB$RELATION_NAME": "   ", "RDB$VIEW_BLR": None},
        ],
        columns=COLUMN_ROWS,
        indexes=INDEX_ROWS,
        primary_keys=[{"RDB$FIELD_NAME": "ID"}, {"RDB$FIELD_NAME": "CODE"}],
        foreign_keys=FK_ROWS,
        views=[
            {"RDB$RELATION_NAME": "V_ACTIVE", "RDB$VIEW_SOURCE": "SELECT 1 FROM EMPLOYEES"},
            {"RDB$RELATION_NAME": "V_EMPTY", "RDB$VIEW_SOURCE": None},
            {"RDB$RELATION_NAME": "", "RDB$VIEW_SOURCE": None},
        ],
    )


@pytest.fixture
def introspector(backend, executor):
    """Return an AsyncFirebirdIntrospector wired to the scripted executor."""
    return AsyncFirebirdIntrospector(backend, executor)


class TestSQLBuilders:
    """Tests for the Firebird SQL builder methods."""

    def test_get_default_schema_is_empty(self, introspector):
        """The default schema must be an empty string for Firebird."""
        assert introspector._get_default_schema() == "", "Firebird has no schema namespace"

    def test_make_database_info_sql(self, introspector):
        """The database info SQL must query MON$DATABASE and carry no params."""
        sql, params = introspector._make_database_info_sql()
        assert "MON$DATABASE_NAME" in sql, "database SQL must select MON$DATABASE_NAME"
        assert "MON$DATABASE" in sql, "database SQL must query MON$DATABASE"
        assert params == (), "database info query must not need parameters"

    def test_make_table_list_sql_all_variants(self, introspector):
        """System tables are hidden unless requested; views are excluded when requested."""
        sql_default, params = introspector._make_table_list_sql()
        assert "RDB$SYSTEM_FLAG = 0" in sql_default, "system tables must be hidden by default"
        assert params == (), "table list query must not need parameters"
        sql_system, _ = introspector._make_table_list_sql(include_system=True)
        assert "RDB$SYSTEM_FLAG" not in sql_system, "system filter must be dropped when include_system is set"
        sql_no_views, _ = introspector._make_table_list_sql(include_views=False)
        assert "RDB$VIEW_BLR IS NULL" in sql_no_views, "views must be excluded when include_views is False"
        assert "ORDER BY RDB$RELATION_NAME" in sql_default, "table list must be ordered by name"

    def test_make_column_list_sql(self, introspector):
        """Column SQL must join RDB$RELATION_FIELDS to RDB$FIELDS and bind the table."""
        sql, params = introspector._make_column_list_sql("EMPLOYEES")
        assert "RDB$RELATION_FIELDS" in sql, "column SQL must read RDB$RELATION_FIELDS"
        assert "RDB$FIELDS" in sql, "column SQL must join RDB$FIELDS"
        assert params == ("EMPLOYEES",), "column query must bind the table name"

    def test_make_index_list_sql(self, introspector):
        """Index SQL must join RDB$INDICES to RDB$INDEX_SEGMENTS."""
        sql, params = introspector._make_index_list_sql("EMPLOYEES")
        assert "RDB$INDICES" in sql, "index SQL must read RDB$INDICES"
        assert "RDB$INDEX_SEGMENTS" in sql, "index SQL must join RDB$INDEX_SEGMENTS"
        assert params == ("EMPLOYEES",), "index query must bind the table name"

    def test_make_primary_key_sql(self, introspector):
        """Primary key SQL must filter on RDB$PRIMARY index names."""
        sql, params = introspector._make_primary_key_sql("EMPLOYEES")
        assert "RDB$PRIMARY" in sql, "primary key SQL must match RDB$PRIMARY indexes"
        assert params == ("EMPLOYEES",), "primary key query must bind the table name"

    def test_make_foreign_key_sql(self, introspector):
        """Foreign key SQL must join RDB$REF_CONSTRAINTS and bind the table."""
        sql, params = introspector._make_foreign_key_sql("EMPLOYEES")
        assert "RDB$REF_CONSTRAINTS" in sql, "foreign key SQL must read RDB$REF_CONSTRAINTS"
        assert params == ("EMPLOYEES",), "foreign key query must bind the table name"

    def test_make_view_list_sql(self, introspector):
        """View SQL must only return non-system relations with a view BLR."""
        sql, params = introspector._make_view_list_sql()
        assert "RDB$VIEW_SOURCE" in sql, "view SQL must select RDB$VIEW_SOURCE"
        assert "RDB$VIEW_BLR IS NOT NULL" in sql, "view SQL must filter on RDB$VIEW_BLR IS NOT NULL"
        assert params == (), "view list query must not need parameters"

    def test_build_wrappers_delegate_to_make_methods(self, introspector):
        """Each _build_* wrapper must return the same SQL as its _make_* method."""
        assert introspector._build_database_info_sql() == introspector._make_database_info_sql(), (
            "database build wrapper must delegate to _make_database_info_sql"
        )
        assert introspector._build_table_list_sql(None, False, True, None) == introspector._make_table_list_sql(), (
            "table build wrapper must delegate to _make_table_list_sql"
        )
        assert introspector._build_column_list_sql("T", None) == introspector._make_column_list_sql("T"), (
            "column build wrapper must delegate to _make_column_list_sql"
        )
        assert introspector._build_index_list_sql("T", None) == introspector._make_index_list_sql("T"), (
            "index build wrapper must delegate to _make_index_list_sql"
        )
        assert introspector._build_primary_key_sql("T", None) == introspector._make_primary_key_sql("T"), (
            "primary key build wrapper must delegate to _make_primary_key_sql"
        )
        assert introspector._build_foreign_key_sql("T", None) == introspector._make_foreign_key_sql("T"), (
            "foreign key build wrapper must delegate to _make_foreign_key_sql"
        )
        assert introspector._build_view_list_sql(None) == introspector._make_view_list_sql(), (
            "view build wrapper must delegate to _make_view_list_sql"
        )


class TestVersionHelpers:
    """Tests for version resolution helpers."""

    def test_get_version_uses_dialect_version(self, dialect, backend, executor):
        """The dialect version tuple must be returned verbatim."""
        introspector = AsyncFirebirdIntrospector(backend, executor)
        assert introspector._get_version() == (3, 0, 0), "dialect version must be preferred"

    def test_get_version_falls_back_to_default(self, executor):
        """A dialect without a version must fall back to the Firebird 3 default."""
        backend = SimpleNamespace(dialect=SimpleNamespace(version=None))
        introspector = AsyncFirebirdIntrospector(backend, executor)
        assert introspector._get_version() == (3, 0, 0), "default version (3, 0, 0) must be used"

    def test_get_version_without_dialect_attr(self, executor):
        """A backend with a None dialect must still resolve the default version."""
        introspector = AsyncFirebirdIntrospector(SimpleNamespace(dialect=None), executor)
        assert introspector._get_version() == (3, 0, 0), "missing dialect version must not raise"


class TestParseMethods:
    """Tests for the pure parse methods shared by sync and async paths."""

    def test_parse_database_info_with_name(self, introspector):
        """A row with MON$DATABASE_NAME must yield a populated DatabaseInfo."""
        info = introspector._parse_database_info([{"MON$DATABASE_NAME": "/tmp/app.fdb"}])
        assert info.name == "/tmp/app.fdb", "database name must be read from the row"
        assert info.version == "3.0.0", "version string must join the version tuple"
        assert info.version_tuple == (3, 0, 0), "version tuple must be preserved"
        assert info.vendor == "Firebird", "vendor must be Firebird"

    def test_parse_database_info_with_empty_rows(self, introspector):
        """Empty rows must yield an empty database name without crashing."""
        info = introspector._parse_database_info([])
        assert info.name == "", "missing rows must produce an empty database name"

    def test_parse_tables_distinguishes_tables_and_views(self, introspector):
        """Tables and views must be classified, and blank names skipped."""
        tables = introspector._parse_tables(
            [
                {"RDB$RELATION_NAME": "EMPLOYEES", "RDB$VIEW_BLR": None},
                {"RDB$RELATION_NAME": "V_ACTIVE", "RDB$VIEW_BLR": b"blr"},
                {"RDB$RELATION_NAME": "   ", "RDB$VIEW_BLR": None},
            ],
            None,
        )
        names = [t.name for t in tables]
        assert names == ["EMPLOYEES", "V_ACTIVE"], "blank relation names must be skipped"
        assert tables[0].table_type == TableType.BASE_TABLE, "relations without view BLR are base tables"
        assert tables[1].table_type == TableType.VIEW, "relations with view BLR are views"
        assert tables[0].schema == "", "schema must default to empty string"

    def test_parse_columns_maps_all_field_types(self, introspector):
        """Every Firebird field type branch must map to the expected data type text."""
        columns = introspector._parse_columns(COLUMN_ROWS, "EMPLOYEES", "")
        by_name = {c.name: c for c in columns}
        assert by_name["ID"].data_type_full == "INTEGER", "FIELD_TYPE 8 maps to INTEGER"
        assert by_name["ID"].data_type == "integer", "data_type must be lowercased"
        assert by_name["ID"].nullable is False, "NULL_FLAG set means NOT NULL"
        assert by_name["ID"].numeric_precision == 18, "precision must be carried through"
        assert by_name["ID"].numeric_scale == 0, "scale must be carried through"
        assert by_name["NAME"].data_type_full == "VARCHAR(255)", "CHAR_LENGTH must size VARCHAR"
        assert by_name["NAME"].character_maximum_length == 255, "CHAR_LENGTH must be exposed"
        assert by_name["NAME"].nullable is True, "missing NULL_FLAG means nullable"
        assert by_name["NAME"].default_value == "default 'john'", "DEFAULT_SOURCE must be stripped and kept"
        assert by_name["NOTES"].data_type_full == "BLOB SUB_TYPE TEXT", "sub type 1 maps to TEXT blob"
        assert by_name["BLOB_BIN"].data_type_full == "BLOB SUB_TYPE BINARY", "sub type 0 maps to BINARY blob"
        assert by_name["CODE"].data_type_full == "UNKNOWN(999)", "unmapped field types must be reported verbatim"
        assert by_name["CH"].data_type_full == "CHAR(10)", "CHAR_LENGTH must size CHAR"
        assert all(c.parsed_data_type is not None for c in columns if c.name), (
            "a real dialect must parse every recognized type"
        )
        assert any(c.parsed_data_type is not None for c in columns), "at least one type must be parsed"

    def test_parse_columns_without_dialect(self, executor):
        """A backend without a dialect must leave parsed_data_type as None."""
        introspector = AsyncFirebirdIntrospector(SimpleNamespace(), executor)
        columns = introspector._parse_columns(
            [{"COLUMN_NAME": "ID", "FIELD_TYPE": 8, "POSITION": 0}], "T", ""
        )
        assert columns[0].name == "ID", "column name must be read from the row"
        assert columns[0].parsed_data_type is None, "no dialect means no parsed type"

    def test_parse_columns_without_name_row(self, introspector):
        """A row whose COLUMN_NAME is falsy must produce a None column name."""
        columns = introspector._parse_columns(
            [{"COLUMN_NAME": "", "FIELD_TYPE": 7, "POSITION": 0}], "T", ""
        )
        assert columns[0].name is None, "blank column name must become None"

    def test_parse_indexes_groups_columns_and_marks_primary(self, introspector):
        """Multi-column indexes must be grouped and primary indexes detected."""
        indexes = introspector._parse_indexes(INDEX_ROWS, "EMPLOYEES", "")
        by_name = {i.name: i for i in indexes}
        assert "RDB$PRIMARY1" in by_name, "primary index must be present"
        assert by_name["RDB$PRIMARY1"].is_primary is True, "PRIMARY in the name marks the primary index"
        assert by_name["RDB$PRIMARY1"].is_unique is True, "UNIQUE_FLAG 1 marks a unique index"
        assert [c.name for c in by_name["RDB$PRIMARY1"].columns] == ["ID", "CODE"], (
            "multiple rows must be grouped into one index"
        )
        assert [c.ordinal_position for c in by_name["RDB$PRIMARY1"].columns] == [0, 1], (
            "field positions must be preserved in order"
        )
        assert by_name["IDX_NAME"].is_unique is False, "UNIQUE_FLAG 0 means non-unique"
        assert by_name["IDX_NO_COL"].columns == [], "rows without a field name add no column"
        assert "   " not in by_name, "blank index names must be skipped"

    def test_parse_foreign_keys_maps_delete_rules(self, introspector):
        """Every delete rule must map to the matching ReferentialAction."""
        fks = introspector._parse_foreign_keys(FK_ROWS, "EMPLOYEES", "")
        by_name = {f.name: f for f in fks}
        assert "FK_DEPT" in by_name, "grouped foreign key must be present"
        assert by_name["FK_DEPT"].columns == ["DEPT_ID", "DEPT_CODE"], "columns must be grouped in order"
        assert by_name["FK_DEPT"].referenced_columns == ["ID", "CODE"], "referenced columns must be grouped"
        assert by_name["FK_DEPT"].referenced_table == "DEPARTMENTS", "referenced table must be carried through"
        assert by_name["FK_DEPT"].on_delete == ReferentialAction.CASCADE, "CASCADE must map to CASCADE"
        assert by_name["FK_OWNER"].on_delete == ReferentialAction.SET_NULL, "SET NULL must map to SET_NULL"
        assert by_name["FK_X"].on_delete == ReferentialAction.SET_DEFAULT, "SET DEFAULT must map to SET_DEFAULT"
        assert by_name["FK_Y"].on_delete == ReferentialAction.RESTRICT, "RESTRICT must map to RESTRICT"
        assert by_name["FK_DEFAULT"].on_delete == ReferentialAction.NO_ACTION, (
            "missing rule must default to NO ACTION"
        )
        assert by_name["FK_DEFAULT"].referenced_columns == [], "missing reference column adds no entry"
        assert by_name["FK_WEIRD"].on_delete == ReferentialAction.NO_ACTION, (
            "unknown rule must fall back to NO ACTION"
        )
        assert by_name["FK_WEIRD"].columns == [], "missing column name adds no column"
        assert by_name["FK_WEIRD"].referenced_columns == ["ID"], "reference column still applies without local column"
        assert all(f.on_update == ReferentialAction.NO_ACTION for f in fks), "on_update must always be NO ACTION"
        assert "FK_UNKNOWN" not in by_name and "" not in by_name, "blank constraint names must be skipped"

    def test_parse_views_includes_optional_definition(self, introspector):
        """Views with and without a source must be parsed, blank names skipped."""
        views = introspector._parse_views(
            [
                {"RDB$RELATION_NAME": "V_ACTIVE", "RDB$VIEW_SOURCE": "SELECT 1"},
                {"RDB$RELATION_NAME": "V_EMPTY", "RDB$VIEW_SOURCE": None},
                {"RDB$RELATION_NAME": "", "RDB$VIEW_SOURCE": None},
            ],
            "",
        )
        assert len(views) == 2, "blank view names must be skipped"
        assert views[0].name == "V_ACTIVE", "view name must be read from the row"
        assert views[0].definition == "SELECT 1", "view definition must be carried through"
        assert views[1].definition is None, "missing view source must become None"

    def test_parse_triggers_returns_empty(self, introspector):
        """Firebird trigger parsing must currently return no triggers."""
        assert introspector._parse_triggers([{"RDB$TRIGGER_NAME": "TRG_1"}], "") == [], (
            "trigger parsing must return an empty list"
        )


class TestPublicAsyncAPI:
    """Tests for the async introspection public API with a scripted executor."""

    async def test_get_database_info(self, introspector, executor):
        """get_database_info must return the row database name and version."""
        info = await introspector.get_database_info()
        assert info.name == "/tmp/app.fdb", "database name must come from the executor rows"
        assert info.vendor == "Firebird", "vendor must be Firebird"
        assert info.version_tuple == (3, 0, 0), "version must come from the dialect"
        assert executor.calls, "executor must have been invoked"

    async def test_get_database_info_is_cached(self, introspector, executor):
        """A second call must reuse the cached result without another query."""
        first = await introspector.get_database_info()
        second = await introspector.get_database_info()
        assert first is second, "database info must be cached"
        assert len(executor.calls) == 1, "only one executor call is expected for a cached value"

    async def test_list_tables(self, introspector):
        """list_tables must parse base tables and views and apply the schema arg."""
        tables = await introspector.list_tables(schema="MAIN")
        assert [t.name for t in tables] == ["EMPLOYEES", "V_ACTIVE"], "blank names must be dropped"
        assert tables[0].table_type == TableType.BASE_TABLE, "EMPLOYEES is a base table"
        assert tables[1].table_type == TableType.VIEW, "V_ACTIVE is a view"

    async def test_list_columns_raises_unsupported_via_base_wiring(self, introspector):
        """The base wiring still routes columns to the generic expression, which Firebird lacks."""
        with pytest.raises(UnsupportedFeatureError):
            await introspector.list_columns("EMPLOYEES")

    async def test_list_foreign_keys(self, introspector):
        """list_foreign_keys must parse and group the scripted foreign keys."""
        fks = await introspector.list_foreign_keys("EMPLOYEES")
        names = [fk.name for fk in fks]
        assert "FK_DEPT" in names, "grouped foreign keys must be returned"
        assert len(fks) == 6, "blank-name row must be dropped"

    async def test_get_foreign_key_info_found(self, introspector):
        """get_foreign_key_info must locate a matching foreign key by name."""
        fk = await introspector.get_foreign_key_info("EMPLOYEES", "FK_OWNER")
        assert fk is not None, "existing foreign key must be found"
        assert fk.on_delete == ReferentialAction.SET_NULL, "SET NULL rule must be preserved"

    async def test_get_foreign_key_info_not_found(self, introspector):
        """get_foreign_key_info must return None for an unknown name."""
        assert await introspector.get_foreign_key_info("EMPLOYEES", "FK_NOPE") is None, (
            "unknown foreign key must yield None"
        )

    async def test_get_table_info_missing_table_returns_none(self, introspector):
        """get_table_info must return None when the table does not exist."""
        assert await introspector.get_table_info("NO_SUCH_TABLE") is None, (
            "missing table must yield None"
        )

    async def test_get_table_info_populates_details(self, introspector):
        """get_table_info must attach columns, indexes, and foreign keys to a copy."""
        from rhosocial.activerecord.backend.introspection.types import ColumnInfo, IndexInfo, ForeignKeyInfo

        async def fake_columns(table, schema=None):
            return [ColumnInfo(name="ID", table_name="EMPLOYEES")]

        async def fake_indexes(table, schema=None):
            return [IndexInfo(name="RDB$PRIMARY1", table_name="EMPLOYEES", is_primary=True)]

        async def fake_fks(table, schema=None):
            return [ForeignKeyInfo(name="FK_DEPT", table_name="EMPLOYEES", referenced_table="DEPARTMENTS")]

        introspector.list_columns = fake_columns
        introspector.list_indexes = fake_indexes
        introspector.list_foreign_keys = fake_fks
        info = await introspector.get_table_info("EMPLOYEES")
        assert info is not None, "existing table must be returned"
        assert [c.name for c in info.columns] == ["ID"], "columns must be attached"
        assert [i.name for i in info.indexes] == ["RDB$PRIMARY1"], "indexes must be attached"
        assert [fk.name for fk in info.foreign_keys] == ["FK_DEPT"], "foreign keys must be attached"

    async def test_table_exists_returns_false_for_missing(self, introspector):
        """table_exists must be False when get_table_info finds nothing."""
        assert await introspector.table_exists("GHOST") is False, "missing table must report False"

    async def test_list_views_raises_signature_mismatch(self, introspector):
        """list_views currently fails because the Firebird override drops include_system."""
        with pytest.raises(TypeError):
            await introspector.list_views()

    async def test_list_triggers_raises_unsupported(self, introspector):
        """list_triggers currently raises because the dialect lacks trigger support."""
        with pytest.raises(UnsupportedFeatureError):
            await introspector.list_triggers("EMPLOYEES")

    async def test_status_property_is_lazy_and_cached(self, backend, executor):
        """The status introspector must be created once and reused."""
        introspector = AsyncFirebirdIntrospector(backend, executor)
        status = introspector.status
        assert isinstance(status, AsyncFirebirdStatusIntrospector), "status must be an async status introspector"
        assert introspector.status is status, "status instance must be cached"
        assert introspector._status_instance is not None, "lazy instance must be stored"


class TestDirectSqlAndExecutor:
    """Tests for the scripted executor plumbing and direct build invocations."""

    async def test_executor_records_calls_and_params(self, executor):
        """The scripted executor must record SQL and params for later assertions."""
        await executor.execute("SELECT 1 FROM RDB$RELATIONS", ("A",))
        assert executor.calls[0] == ("SELECT 1 FROM RDB$RELATIONS", ("A",)), (
            "executor must record the exact sql and params"
        )

    async def test_executor_returns_empty_for_unknown_sql(self, executor):
        """Unknown SQL must yield an empty list rather than an error."""
        rows = await executor.execute("SELECT * FROM RDB$TRIGGERS")
        assert rows == [], "unknown SQL must return no rows"

    def test_mixin_can_be_constructed(self, dialect):
        """The mixin must be constructible on its own for parse-only use."""
        mixin = FirebirdAsyncIntrospectorMixin()
        mixin._backend = SimpleNamespace(dialect=dialect)
        assert mixin._get_default_schema() == "", "mixin default schema must be empty"

    async def test_full_overview_walkthrough(self, backend, executor):
        """A full walk of the public API must not raise outside known gaps."""
        from rhosocial.activerecord.backend.introspection.types import DatabaseInfo

        introspector = AsyncFirebirdIntrospector(backend, executor)
        info = await introspector.get_database_info()
        await introspector.list_tables()
        await introspector.list_foreign_keys("EMPLOYEES")
        assert isinstance(info, DatabaseInfo), "database info must be a DatabaseInfo instance"


def test_module_constants():
    """The module-level type maps must expose the documented Firebird codes."""
    from rhosocial.activerecord.backend.impl.firebird.introspection.async_introspector import (
        FB_BLOB_SUB_TYPES,
        FB_FIELD_TYPES,
    )

    assert FB_FIELD_TYPES[8] == "INTEGER", "field type 8 is INTEGER"
    assert FB_FIELD_TYPES[261] == "BLOB", "field type 261 is BLOB"
    assert FB_FIELD_TYPES[23] == "BOOLEAN", "field type 23 is BOOLEAN"
    assert FB_BLOB_SUB_TYPES[0] == "BINARY", "blob sub type 0 is BINARY"
    assert FB_BLOB_SUB_TYPES[1] == "TEXT", "blob sub type 1 is TEXT"
    assert type(DataType.parse_data_type_str(FirebirdDialect(), "VARCHAR(255)")).__name__ == "VarCharType", (
        "dialect must parse VARCHAR lengths"
    )