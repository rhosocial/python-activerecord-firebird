"""Firebird async introspector — wraps sync cursor ops in a thread pool."""

from typing import Any, Dict, List, Optional

from rhosocial.activerecord.backend.introspection.base import (
    IntrospectorMixin,
    AsyncAbstractIntrospector,
)
from rhosocial.activerecord.backend.introspection.types import (
    DatabaseInfo,
    TableInfo,
    TableType,
    ColumnInfo,
    IndexInfo,
    IndexColumnInfo,
    IndexType,
    ForeignKeyInfo,
    ReferentialAction,
    ViewInfo,
    TriggerInfo,
)

# Firebird field types mapping (shared with sync introspector)
FB_FIELD_TYPES = {
    7: "SMALLINT",
    8: "INTEGER",
    9: "QUAD",
    10: "FLOAT",
    11: "D_FLOAT",
    12: "DATE",
    13: "TIME",
    14: "CHAR",
    16: "BIGINT",
    23: "BOOLEAN",
    24: "DECFLOAT",
    27: "DOUBLE PRECISION",
    35: "TIMESTAMP",
    37: "VARCHAR",
    40: "CSTRING",
    45: "BLOB_ID",
    261: "BLOB",
}

FB_BLOB_SUB_TYPES = {
    0: "BINARY",
    1: "TEXT",
}


class FirebirdAsyncIntrospectorMixin(IntrospectorMixin):
    """Shared build/parse logic for Firebird introspection (async path)."""

    def _get_default_schema(self) -> str:
        return ""

    def _get_version(self) -> tuple:
        dialect_ver = getattr(self._backend.dialect, 'version', None)
        if dialect_ver:
            return dialect_ver
        return (3, 0, 0)

    def _make_database_info_sql(self) -> str:
        """Return SQL to query basic database info."""
        return "SELECT MON$DATABASE_NAME FROM MON$DATABASE", ()

    def _make_table_list_sql(self, schema: Optional[str] = None,
                              include_system: bool = False,
                              include_views: bool = True,
                              table_type: Optional[str] = None) -> str:
        if include_system:
            where = ""
        else:
            where = "AND RDB$SYSTEM_FLAG = 0"
        if include_views:
            view_clause = ""
        else:
            view_clause = "AND RDB$VIEW_BLR IS NULL"
        sql = (
            "SELECT RDB$RELATION_NAME, RDB$VIEW_BLR "
            "FROM RDB$RELATIONS "
            f"WHERE 1=1 {where} {view_clause} "
            "ORDER BY RDB$RELATION_NAME"
        )
        return sql, ()

    def _make_column_list_sql(self, table_name: str, schema: Optional[str] = None) -> str:
        sql = """
            SELECT
                rf.RDB$FIELD_NAME AS COLUMN_NAME,
                f.RDB$FIELD_TYPE AS FIELD_TYPE,
                f.RDB$FIELD_SUB_TYPE AS FIELD_SUB_TYPE,
                f.RDB$CHARACTER_LENGTH AS CHAR_LENGTH,
                f.RDB$FIELD_PRECISION AS PRECISION,
                f.RDB$FIELD_SCALE AS SCALE,
                rf.RDB$NULL_FLAG AS NULL_FLAG,
                rf.RDB$DEFAULT_SOURCE AS DEFAULT_SOURCE,
                rf.RDB$POSITION AS POSITION,
                rf.RDB$COMPUTED_SOURCE AS COMPUTED_SOURCE
            FROM RDB$RELATION_FIELDS rf
            JOIN RDB$FIELDS f ON rf.RDB$FIELD_SOURCE = f.RDB$FIELD_NAME
            WHERE rf.RDB$RELATION_NAME = ?
            ORDER BY rf.RDB$POSITION
        """
        return sql, (table_name,)

    def _make_index_list_sql(self, table_name: str, schema: Optional[str] = None) -> str:
        sql = """
            SELECT
                i.RDB$INDEX_NAME AS INDEX_NAME,
                i.RDB$UNIQUE_FLAG AS UNIQUE_FLAG,
                i.RDB$INDEX_INACTIVE AS INACTIVE,
                i.RDB$INDEX_TYPE AS INDEX_TYPE,
                isg.RDB$FIELD_NAME AS FIELD_NAME,
                isg.RDB$FIELD_POSITION AS FIELD_POSITION
            FROM RDB$INDICES i
            JOIN RDB$INDEX_SEGMENTS isg
                ON i.RDB$INDEX_NAME = isg.RDB$INDEX_NAME
            WHERE i.RDB$RELATION_NAME = ?
            ORDER BY i.RDB$INDEX_NAME, isg.RDB$FIELD_POSITION
        """
        return sql, (table_name,)

    def _make_primary_key_sql(self, table_name: str) -> str:
        sql = """
            SELECT isg.RDB$FIELD_NAME
            FROM RDB$INDICES i
            JOIN RDB$INDEX_SEGMENTS isg
                ON i.RDB$INDEX_NAME = isg.RDB$INDEX_NAME
            WHERE i.RDB$RELATION_NAME = ?
              AND i.RDB$UNIQUE_FLAG = 1
              AND i.RDB$INDEX_NAME LIKE 'RDB$PRIMARY%'
            ORDER BY isg.RDB$FIELD_POSITION
        """
        return sql, (table_name,)

    def _make_foreign_key_sql(self, table_name: str, schema: Optional[str] = None) -> str:
        sql = """
            SELECT
                rc.RDB$CONSTRAINT_NAME AS CONSTRAINT_NAME,
                rc.RDB$INDEX_NAME AS INDEX_NAME,
                seg.RDB$FIELD_NAME AS COLUMN_NAME,
                ref.RDB$RELATION_NAME AS REF_TABLE,
                ref_seg.RDB$FIELD_NAME AS REF_COLUMN,
                rc.RDB$DELETE_RULE AS DELETE_RULE
            FROM RDB$REF_CONSTRAINTS rc
            JOIN RDB$INDEX_SEGMENTS seg
                ON rc.RDB$INDEX_NAME = seg.RDB$INDEX_NAME
            JOIN RDB$INDICES i
                ON rc.RDB$INDEX_NAME = i.RDB$INDEX_NAME
            JOIN RDB$INDEX_SEGMENTS ref_seg
                ON rc.RDB$CONSTRAINT_NAME_UQ = ref_seg.RDB$INDEX_NAME
            JOIN RDB$INDICES ref_i
                ON rc.RDB$CONSTRAINT_NAME_UQ = ref_i.RDB$INDEX_NAME
            JOIN RDB$RELATIONS ref
                ON ref_i.RDB$RELATION_NAME = ref.RDB$RELATION_NAME
            WHERE i.RDB$RELATION_NAME = ?
            ORDER BY seg.RDB$FIELD_POSITION
        """
        return sql, (table_name,)

    def _make_view_list_sql(self, schema: Optional[str] = None) -> str:
        sql = """
            SELECT RDB$RELATION_NAME, RDB$VIEW_SOURCE
            FROM RDB$RELATIONS
            WHERE RDB$SYSTEM_FLAG = 0
              AND RDB$VIEW_BLR IS NOT NULL
            ORDER BY RDB$RELATION_NAME
        """
        return sql, ()

    # ------------------------------------------------------------------
    # Parse methods
    # ------------------------------------------------------------------

    def _parse_database_info(self, rows: List[Dict[str, Any]]) -> DatabaseInfo:
        version = self._get_version()
        return DatabaseInfo(
            name=str(rows[0].get("MON$DATABASE_NAME", "")) if rows else "",
            version=".".join(str(v) for v in version),
            version_tuple=version,
            vendor="Firebird",
        )

    def _parse_tables(self, rows: List[Dict[str, Any]],
                       schema: Optional[str]) -> List[TableInfo]:
        tables = []
        for row in rows:
            name = str(row.get("RDB$RELATION_NAME", "")).strip()
            if not name:
                continue
            is_view = row.get("RDB$VIEW_BLR") is not None
            tables.append(
                TableInfo(
                    name=name,
                    schema=schema or "",
                    table_type=TableType.VIEW if is_view else TableType.BASE_TABLE,
                )
            )
        return tables

    def _parse_columns(self, rows: List[Dict[str, Any]],
                        table_name: str,
                        schema: str) -> List[ColumnInfo]:
        from rhosocial.activerecord.backend.expression.types._base import DataType

        columns = []
        for row in rows:
            field_type = row.get("FIELD_TYPE")
            sub_type = row.get("FIELD_SUB_TYPE")
            char_len = row.get("CHAR_LENGTH")
            precision = row.get("PRECISION")
            scale = row.get("SCALE")

            type_name = FB_FIELD_TYPES.get(field_type, f"UNKNOWN({field_type})")
            if type_name == "BLOB":
                blob_sub = FB_BLOB_SUB_TYPES.get(sub_type, str(sub_type))
                type_name = f"BLOB SUB_TYPE {blob_sub}"
            elif type_name in ("VARCHAR", "CHAR") and char_len:
                type_name = f"{type_name}({char_len})"

            dialect = getattr(self._backend, "dialect", None)
            parsed_data_type = (
                DataType.parse_data_type_str(dialect, type_name)
                if dialect
                else None
            )

            columns.append(
                ColumnInfo(
                    name=str(row.get("COLUMN_NAME", "")).strip() if row.get("COLUMN_NAME") else None,
                    table_name=table_name,
                    schema=schema,
                    ordinal_position=row.get("POSITION"),
                    data_type=type_name.lower() if type_name else None,
                    data_type_full=type_name,
                    parsed_data_type=parsed_data_type,
                    nullable=row.get("NULL_FLAG") is None,
                    default_value=str(row.get("DEFAULT_SOURCE", "")).strip() if row.get("DEFAULT_SOURCE") else None,
                    comment=None,
                    character_maximum_length=char_len,
                    numeric_precision=precision,
                    numeric_scale=scale,
                    collation=None,
                )
            )
        return columns

    def _parse_indexes(self, rows: List[Dict[str, Any]],
                        table_name: str,
                        schema: str) -> List[IndexInfo]:
        indexes: Dict[str, IndexInfo] = {}
        for row in rows:
            name = str(row.get("INDEX_NAME", "")).strip()
            if not name:
                continue
            if name not in indexes:
                is_primary = "PRIMARY" in name.upper()
                indexes[name] = IndexInfo(
                    name=name,
                    table_name=table_name,
                    schema=schema,
                    is_unique=row.get("UNIQUE_FLAG") == 1,
                    is_primary=is_primary,
                    index_type=IndexType.UNKNOWN,
                    columns=[],
                )
            col_name = str(row.get("FIELD_NAME", "")).strip() if row.get("FIELD_NAME") else None
            if col_name:
                indexes[name].columns.append(
                    IndexColumnInfo(
                        name=col_name,
                        ordinal_position=int(row.get("FIELD_POSITION", 1)),
                        is_descending=False,
                    )
                )
        return list(indexes.values())

    def _parse_foreign_keys(self, rows: List[Dict[str, Any]],
                             table_name: str,
                             schema: str) -> List[ForeignKeyInfo]:
        action_map = {
            "CASCADE": ReferentialAction.CASCADE,
            "SET NULL": ReferentialAction.SET_NULL,
            "SET DEFAULT": ReferentialAction.SET_DEFAULT,
            "NO ACTION": ReferentialAction.NO_ACTION,
            "RESTRICT": ReferentialAction.RESTRICT,
        }
        fk_map: Dict[str, ForeignKeyInfo] = {}
        for row in rows:
            name = str(row.get("CONSTRAINT_NAME", "")).strip()
            if not name:
                continue
            if name not in fk_map:
                delete_rule = str(row.get("DELETE_RULE", "")).strip() if row.get("DELETE_RULE") else "NO ACTION"
                fk_map[name] = ForeignKeyInfo(
                    name=name,
                    table_name=table_name,
                    schema=schema,
                    referenced_table=str(row.get("REF_TABLE", "")).strip(),
                    on_update=ReferentialAction.NO_ACTION,
                    on_delete=action_map.get(delete_rule, ReferentialAction.NO_ACTION),
                    columns=[],
                    referenced_columns=[],
                )
            col = str(row.get("COLUMN_NAME", "")).strip() if row.get("COLUMN_NAME") else None
            ref_col = str(row.get("REF_COLUMN", "")).strip() if row.get("REF_COLUMN") else None
            if col:
                fk_map[name].columns.append(col)
            if ref_col:
                fk_map[name].referenced_columns.append(ref_col)
        return list(fk_map.values())

    def _parse_views(self, rows: List[Dict[str, Any]],
                      schema: str) -> List[ViewInfo]:
        return [
            ViewInfo(
                name=str(row.get("RDB$RELATION_NAME", "")).strip(),
                schema=schema,
                definition=str(row.get("RDB$VIEW_SOURCE", "")) if row.get("RDB$VIEW_SOURCE") else None,
                check_option=None,
                is_updatable=False,
            )
            for row in rows if row.get("RDB$RELATION_NAME")
        ]

    def _parse_triggers(self, rows: List[Dict[str, Any]],
                         schema: str) -> List[TriggerInfo]:
        return []

    def _build_database_info_sql(self):
        return self._make_database_info_sql()

    def _build_table_list_sql(self, schema, include_system, include_views, table_type):
        return self._make_table_list_sql(schema, include_system, include_views, table_type)

    def _build_column_list_sql(self, table_name, schema):
        return self._make_column_list_sql(table_name, schema)

    def _build_index_list_sql(self, table_name, schema):
        return self._make_index_list_sql(table_name, schema)

    def _build_primary_key_sql(self, table_name, schema):
        return self._make_primary_key_sql(table_name)

    def _build_foreign_key_sql(self, table_name, schema):
        return self._make_foreign_key_sql(table_name, schema)

    def _build_view_list_sql(self, schema):
        return self._make_view_list_sql(schema)


class AsyncFirebirdIntrospector(FirebirdAsyncIntrospectorMixin, AsyncAbstractIntrospector):
    """Asynchronous Firebird schema introspector.

    Uses the thread-pool-based executor from AsyncFirebirdBackend to
    run sync fdb cursor operations in a background thread.
    """

    def __init__(self, backend, executor):
        super().__init__(backend, executor)

    async def get_table_info(
        self, table_name: str, schema: Optional[str] = None
    ) -> Optional[TableInfo]:
        from copy import copy
        tables = await self.list_tables(schema)
        table = next((t for t in tables if t.name == table_name), None)
        if table is None:
            return None
        table = copy(table)
        table.columns = await self.list_columns(table_name, schema)
        table.indexes = await self.list_indexes(table_name, schema)
        table.foreign_keys = await self.list_foreign_keys(table_name, schema)
        return table
