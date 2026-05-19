# src/rhosocial/activerecord/backend/impl/firebird/introspection/introspector.py
"""Firebird schema introspector.

Uses Firebird system tables (RDB$) to introspect database schema.
"""

from typing import Any, Dict, List, Optional, Tuple

from rhosocial.activerecord.backend.introspection.base import (
    BaseIntrospector, IntrospectionResult
)


# Firebird field types mapping
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


class SyncFirebirdIntrospector(BaseIntrospector):
    """Synchronous Firebird schema introspector."""

    def __init__(self, backend):
        self.backend = backend

    def get_tables(self) -> List[str]:
        """Get all user table names.

        Returns:
            List of table names
        """
        cursor = self.backend._get_cursor()
        cursor.execute("""
            SELECT RDB$RELATION_NAME
            FROM RDB$RELATIONS
            WHERE RDB$SYSTEM_FLAG = 0
              AND RDB$VIEW_BLR IS NULL
            ORDER BY RDB$RELATION_NAME
        """)
        return [str(row[0]).strip() for row in cursor.fetchall()]

    def get_views(self) -> List[str]:
        """Get all view names.

        Returns:
            List of view names
        """
        cursor = self.backend._get_cursor()
        cursor.execute("""
            SELECT RDB$RELATION_NAME
            FROM RDB$RELATIONS
            WHERE RDB$SYSTEM_FLAG = 0
              AND RDB$VIEW_BLR IS NOT NULL
            ORDER BY RDB$RELATION_NAME
        """)
        return [str(row[0]).strip() for row in cursor.fetchall()]

    def get_columns(self, table_name: str) -> List[Dict[str, Any]]:
        """Get column information for a table.

        Args:
            table_name: Table name

        Returns:
            List of column info dicts
        """
        cursor = self.backend._get_cursor()
        cursor.execute("""
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
        """, (table_name,))

        columns = []
        for row in cursor.fetchall():
            field_type = row[1]
            sub_type = row[2]
            char_len = row[3]
            precision = row[4]
            scale = row[5]

            type_name = FB_FIELD_TYPES.get(field_type, f"UNKNOWN({field_type})")
            if type_name == "BLOB":
                blob_sub = FB_BLOB_SUB_TYPES.get(sub_type, str(sub_type))
                type_name = f"BLOB SUB_TYPE {blob_sub}"
            elif type_name in ("VARCHAR", "CHAR") and char_len:
                type_name = f"{type_name}({char_len})"

            columns.append({
                "name": str(row[0]).strip() if row[0] else None,
                "type": type_name,
                "nullable": row[6] is None,
                "default": str(row[7]).strip() if row[7] else None,
                "position": row[8],
                "computed": str(row[9]).strip() if row[9] else None,
            })

        return columns

    def get_indexes(self, table_name: str) -> List[Dict[str, Any]]:
        """Get index information for a table.

        Args:
            table_name: Table name

        Returns:
            List of index info dicts
        """
        cursor = self.backend._get_cursor()
        cursor.execute("""
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
        """, (table_name,))

        indexes = {}
        for row in cursor.fetchall():
            name = str(row[0]).strip()
            if name not in indexes:
                indexes[name] = {
                    "name": name,
                    "unique": row[1] == 1,
                    "active": row[2] != 1,
                    "type": "PRIMARY" if "PRIMARY" in name.upper() else "INDEX",
                    "columns": [],
                }
            col_name = str(row[4]).strip() if row[4] else None
            if col_name:
                indexes[name]["columns"].append(col_name)

        return list(indexes.values())

    def get_primary_key(self, table_name: str) -> Optional[List[str]]:
        """Get primary key columns for a table.

        Args:
            table_name: Table name

        Returns:
            List of PK column names or None
        """
        cursor = self.backend._get_cursor()
        cursor.execute("""
            SELECT isg.RDB$FIELD_NAME
            FROM RDB$INDICES i
            JOIN RDB$INDEX_SEGMENTS isg
                ON i.RDB$INDEX_NAME = isg.RDB$INDEX_NAME
            WHERE i.RDB$RELATION_NAME = ?
              AND i.RDB$UNIQUE_FLAG = 1
              AND i.RDB$INDEX_NAME LIKE 'RDB$PRIMARY%'
            ORDER BY isg.RDB$FIELD_POSITION
        """, (table_name,))

        cols = [str(row[0]).strip() for row in cursor.fetchall()]
        return cols if cols else None

    def get_foreign_keys(self, table_name: str) -> List[Dict[str, Any]]:
        """Get foreign key information for a table.

        Args:
            table_name: Table name

        Returns:
            List of FK info dicts
        """
        cursor = self.backend._get_cursor()
        cursor.execute("""
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
        """, (table_name,))

        fks = {}
        for row in cursor.fetchall():
            name = str(row[0]).strip()
            if name not in fks:
                delete_rule = str(row[5]).strip() if row[5] else "NO ACTION"
                fks[name] = {
                    "name": name,
                    "ref_table": str(row[3]).strip(),
                    "columns": [],
                    "ref_columns": [],
                    "on_delete": {"CASCADE": "CASCADE", "SET NULL": "SET NULL",
                                  "SET DEFAULT": "SET DEFAULT", "NO ACTION": "NO ACTION",
                                  "RESTRICT": "RESTRICT"}.get(delete_rule, "NO ACTION"),
                }
            col = str(row[2]).strip() if row[2] else None
            ref_col = str(row[4]).strip() if row[4] else None
            if col:
                fks[name]["columns"].append(col)
            if ref_col:
                fks[name]["ref_columns"].append(ref_col)

        return list(fks.values())

    def introspect(self, table_name: Optional[str] = None) -> IntrospectionResult:
        """Perform full introspection.

        Args:
            table_name: Optional specific table to introspect

        Returns:
            IntrospectionResult with all schema info
        """
        tables = [table_name] if table_name else self.get_tables()

        result = IntrospectionResult()
        for table in tables:
            result.tables[table] = {
                "columns": self.get_columns(table),
                "indexes": self.get_indexes(table),
                "primary_key": self.get_primary_key(table),
                "foreign_keys": self.get_foreign_keys(table),
            }

        result.views = self.get_views()
        return result


__all__ = ["SyncFirebirdIntrospector"]