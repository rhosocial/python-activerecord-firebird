"""Firebird async introspector — wraps sync cursor ops in a thread pool."""

from typing import Any, Dict, List, Optional

from rhosocial.activerecord.backend.introspection.base import (
    IntrospectorMixin,
    AsyncAbstractIntrospector,
)
from rhosocial.activerecord.backend.introspection.cache import (
    IntrospectionCache,
)
from rhosocial.activerecord.backend.introspection.types import (
    IntrospectionDatabaseInfo,
    IntrospectionTableInfo,
    TableType,
    IntrospectionColumnInfo,
    IndexInfo,
    IndexColumnInfo,
    IndexType,
    IntrospectionForeignKeyInfo,
    ReferentialAction,
    IntrospectionViewInfo,
    IntrospectionTriggerInfo,
)
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

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
    # Firebird 4.0's new types, per the language reference, D.11 RDB$FIELDS
    # (RDB$FIELD_TYPE), which also documents RDB$EXTERNAL_TYPE with the same
    # codes.
    #
    # DECFLOAT is **two** codes, not one: 24 is DECFLOAT(16) and 25 is DECFLOAT(34)
    # -- there is no bare "DECFLOAT" code, because the width is what the code
    # records (RDB$FIELD_LENGTH agrees: 8 bytes for DECFLOAT(16), 16 for
    # DECFLOAT(34)). Both are written here *with* the precision for that reason.
    # A single entry mapping both codes to the unqualified word "DECFLOAT" would
    # make a 16-digit column and a 34-digit column report the same type name,
    # and FirebirdDecFloatType carries precision in PARAMETERS -- so they would
    # also compare equal as value objects, and the differ would report no change
    # between them. That is the identity loss this table exists to avoid, and it
    # is worse than having no entry at all: an unknown code at least announces
    # itself as UNKNOWN(n).
    24: "DECFLOAT(16)",
    25: "DECFLOAT(34)",
    # INT128 is Firebird 4's own 128-bit signed integer (CORE-6366). It is not
    # BIGINT under another name -- -2**127 .. 2**127-1 against BIGINT's
    # -2**63 .. 2**63-1 -- so it gets its own class, FirebirdInt128Type, rather
    # than being folded into the 64-bit one.
    26: "INT128",
    27: "DOUBLE PRECISION",
    # Firebird 4.0 added the zoned date-time types. RDB$FIELDS.RDB$FIELD_TYPE
    # carries 28/29 for them, per the language reference, D.11 RDB$FIELDS. The
    # words are the ones Firebird's own grammar writes, so a name this table
    # invents here is a name parse_type() could not recognise.
    28: "TIME WITH TIME ZONE",
    29: "TIMESTAMP WITH TIME ZONE",
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
    """Shared build/parse logic for Firebird introspection (async path).

    Namespaces
    ----------
    Firebird has one namespace, so every SQL builder here takes the ``schema``
    argument the core ``IntrospectorMixin`` passes down and **rejects a
    non-empty one** rather than ignoring it. The parameter exists because the
    core base declares it; Firebird has nothing to put in it. Silently
    discarding it would return the whole database's tables for a request that
    asked for one schema's tables -- an answer that looks successful and is
    about the wrong objects, which is the failure this layer exists to prevent.

    The system tables these queries read (``RDB$RELATIONS``,
    ``RDB$RELATION_FIELDS``, ``RDB$INDICES``, ``RDB$REF_CONSTRAINTS``) are
    ordinary relations reached unqualified and filtered with
    ``RDB$SYSTEM_FLAG``; ``RDB$`` is a naming convention, not a schema.
    """

    def _get_default_schema(self) -> str:
        """The namespace every Firebird object lives in -- there is only one.

        Empty rather than ``None`` because callers treat the empty string as
        "no namespace given", which is exactly the case here.
        """
        return ""

    def _reject_namespace(self, schema: Optional[str]) -> Optional[str]:
        """Accept the empty namespace; refuse any other.

        Args:
            schema: The namespace a caller asked to introspect, or ``None`` /
                ``""`` for "the whole database".

        Returns:
            ``None``, so callers can write ``schema = self._reject_namespace(schema)``.

        Raises:
            UnsupportedFeatureError: ``schema`` names something Firebird has.
        """
        if schema:
            raise UnsupportedFeatureError(
                self.dialect.name,
                "schema-scoped introspection",
                suggestion=(
                    f"Firebird has a single unnamed namespace, so {schema!r} "
                    f"cannot be selected from: the whole database is the only "
                    f"scope. Pass schema=None."
                ),
            )
        return None

    def _get_version(self) -> tuple:
        dialect_ver = getattr(self._backend.dialect, 'version', None)
        if dialect_ver:
            return dialect_ver
        return (3, 0, 0)

    def _make_database_info_sql(self) -> str:
        """Return SQL to query basic database info."""
        from ..query_nodes import column, relation, select_sql

        d = self.dialect
        return select_sql(
            d, [column(d, "MON$DATABASE_NAME")], from_=relation(d, "MON$DATABASE")
        )

    def _make_table_list_sql(self, schema: Optional[str] = None,
                              include_system: bool = False,
                              include_views: bool = True,
                              table_type: Optional[str] = None) -> str:
        """Tables (and views) of the database, by relation name.

        ``RDB$SYSTEM_FLAG = 0`` drops the catalogue's own relations and
        ``RDB$VIEW_BLR IS NULL`` drops views; both are conditions of the
        question, not data, so they stay inline exactly as the text had them.
        The old statement also opened its WHERE with a bare ``1=1`` to make
        the optional clauses append cleanly -- that was clause assembly
        mechanics, not a condition, and the tree makes it unnecessary.
        """
        from ..query_nodes import (
            column,
            compare,
            conjunction,
            literal,
            null_test,
            relation,
            select_sql,
        )

        self._reject_namespace(schema)
        d = self.dialect
        conditions = []
        if not include_system:
            conditions.append(
                compare(d, "eq", column(d, "RDB$SYSTEM_FLAG"), literal(d, 0, inline=True))
            )
        if not include_views:
            conditions.append(null_test(d, column(d, "RDB$VIEW_BLR")))
        return select_sql(
            d,
            [column(d, "RDB$RELATION_NAME"), column(d, "RDB$VIEW_BLR")],
            from_=relation(d, "RDB$RELATIONS"),
            where=conjunction(d, *conditions) if conditions else None,
            order_by=[column(d, "RDB$RELATION_NAME")],
        )

    def _make_column_list_sql(self, table_name: str, schema: Optional[str] = None) -> str:
        """The columns of one relation, with the domain each is built on.

        ``RDB$RELATION_FIELDS`` holds the per-column facts and ``RDB$FIELDS``
        the domain the column was declared from, so the two are joined through
        ``RDB$FIELD_SOURCE``. The relation name is a bind position.
        """
        from ..query_nodes import (
            column,
            compare,
            join,
            literal,
            relation,
            select_sql,
        )

        self._reject_namespace(schema)
        d = self.dialect
        joined = join(
            d,
            relation(d, "RDB$RELATION_FIELDS", alias="rf"),
            relation(d, "RDB$FIELDS", alias="f"),
            condition=compare(
                d,
                "eq",
                column(d, "RDB$FIELD_SOURCE", "rf"),
                column(d, "RDB$FIELD_NAME", "f"),
            ),
        )
        return select_sql(
            d,
            [
                column(d, "RDB$FIELD_NAME", "rf", alias="COLUMN_NAME"),
                column(d, "RDB$FIELD_TYPE", "f", alias="FIELD_TYPE"),
                column(d, "RDB$FIELD_SUB_TYPE", "f", alias="FIELD_SUB_TYPE"),
                column(d, "RDB$CHARACTER_LENGTH", "f", alias="CHAR_LENGTH"),
                column(d, "RDB$FIELD_PRECISION", "f", alias="PRECISION"),
                column(d, "RDB$FIELD_SCALE", "f", alias="SCALE"),
                column(d, "RDB$NULL_FLAG", "rf", alias="NULL_FLAG"),
                column(d, "RDB$DEFAULT_SOURCE", "rf", alias="DEFAULT_SOURCE"),
                column(d, "RDB$POSITION", "rf", alias="POSITION"),
                column(d, "RDB$COMPUTED_SOURCE", "rf", alias="COMPUTED_SOURCE"),
            ],
            from_=joined,
            where=compare(
                d,
                "eq",
                column(d, "RDB$RELATION_NAME", "rf"),
                literal(d, table_name),
            ),
            order_by=[column(d, "RDB$POSITION", "rf")],
        )

    def _make_index_list_sql(self, table_name: str, schema: Optional[str] = None) -> str:
        """The indexes of one relation with their key columns, in key order."""
        from ..query_nodes import (
            column,
            compare,
            join,
            literal,
            relation,
            select_sql,
        )

        self._reject_namespace(schema)
        d = self.dialect
        joined = join(
            d,
            relation(d, "RDB$INDICES", alias="i"),
            relation(d, "RDB$INDEX_SEGMENTS", alias="isg"),
            condition=compare(
                d,
                "eq",
                column(d, "RDB$INDEX_NAME", "i"),
                column(d, "RDB$INDEX_NAME", "isg"),
            ),
        )
        return select_sql(
            d,
            [
                column(d, "RDB$INDEX_NAME", "i", alias="INDEX_NAME"),
                column(d, "RDB$UNIQUE_FLAG", "i", alias="UNIQUE_FLAG"),
                column(d, "RDB$INDEX_INACTIVE", "i", alias="INACTIVE"),
                column(d, "RDB$INDEX_TYPE", "i", alias="INDEX_TYPE"),
                column(d, "RDB$FIELD_NAME", "isg", alias="FIELD_NAME"),
                column(d, "RDB$FIELD_POSITION", "isg", alias="FIELD_POSITION"),
            ],
            from_=joined,
            where=compare(
                d,
                "eq",
                column(d, "RDB$RELATION_NAME", "i"),
                literal(d, table_name),
            ),
            order_by=[
                column(d, "RDB$INDEX_NAME", "i"),
                column(d, "RDB$FIELD_POSITION", "isg"),
            ],
        )

    def _make_primary_key_sql(self, table_name: str) -> str:
        """The primary key's columns: the relation's unique ``RDB$PRIMARY%`` index.

        Firebird names a primary key's backing index ``RDB$PRIMARY<n>``, so the
        index name is matched by a LIKE pattern -- a literal of the question,
        not data, and inline exactly as the text had it.
        """
        from ..query_nodes import (
            column,
            compare,
            conjunction,
            join,
            like,
            literal,
            relation,
            select_sql,
        )

        d = self.dialect
        joined = join(
            d,
            relation(d, "RDB$INDICES", alias="i"),
            relation(d, "RDB$INDEX_SEGMENTS", alias="isg"),
            condition=compare(
                d,
                "eq",
                column(d, "RDB$INDEX_NAME", "i"),
                column(d, "RDB$INDEX_NAME", "isg"),
            ),
        )
        return select_sql(
            d,
            [column(d, "RDB$FIELD_NAME", "isg")],
            from_=joined,
            where=conjunction(
                d,
                compare(
                    d,
                    "eq",
                    column(d, "RDB$RELATION_NAME", "i"),
                    literal(d, table_name),
                ),
                compare(
                    d,
                    "eq",
                    column(d, "RDB$UNIQUE_FLAG", "i"),
                    literal(d, 1, inline=True),
                ),
                like(d, column(d, "RDB$INDEX_NAME", "i"), "RDB$PRIMARY%"),
            ),
            order_by=[column(d, "RDB$FIELD_POSITION", "isg")],
        )

    def _make_foreign_key_sql(self, table_name: str, schema: Optional[str] = None) -> str:
        """The outgoing foreign keys of one relation, with their targets.

        Six relation reads: the constraint and its referencing index, that
        index's own segments, the unique index the constraint points at and
        that index's segments, and finally the target relation itself. Each
        join is stated where it belongs rather than in one flat FROM list, so
        which relation reads to which is visible in the tree.
        """
        from ..query_nodes import (
            column,
            compare,
            join,
            literal,
            relation,
            select_sql,
        )

        self._reject_namespace(schema)
        d = self.dialect
        # seg reads the referencing index's columns; ref_seg the referenced
        # index's. Both join on an index name, so they are kept apart by the
        # distinct relations they hang from, not by name alone.
        joined = join(
            d,
            join(
                d,
                join(
                    d,
                    join(
                        d,
                        join(
                            d,
                            relation(d, "RDB$REF_CONSTRAINTS", alias="rc"),
                            relation(d, "RDB$INDEX_SEGMENTS", alias="seg"),
                            condition=compare(
                                d,
                                "eq",
                                column(d, "RDB$INDEX_NAME", "rc"),
                                column(d, "RDB$INDEX_NAME", "seg"),
                            ),
                        ),
                        relation(d, "RDB$INDICES", alias="i"),
                        condition=compare(
                            d,
                            "eq",
                            column(d, "RDB$INDEX_NAME", "rc"),
                            column(d, "RDB$INDEX_NAME", "i"),
                        ),
                    ),
                    relation(d, "RDB$INDEX_SEGMENTS", alias="ref_seg"),
                    condition=compare(
                        d,
                        "eq",
                        column(d, "RDB$CONSTRAINT_NAME_UQ", "rc"),
                        column(d, "RDB$INDEX_NAME", "ref_seg"),
                    ),
                ),
                relation(d, "RDB$INDICES", alias="ref_i"),
                condition=compare(
                    d,
                    "eq",
                    column(d, "RDB$CONSTRAINT_NAME_UQ", "rc"),
                    column(d, "RDB$INDEX_NAME", "ref_i"),
                ),
            ),
            relation(d, "RDB$RELATIONS", alias="ref"),
            condition=compare(
                d,
                "eq",
                column(d, "RDB$RELATION_NAME", "ref_i"),
                column(d, "RDB$RELATION_NAME", "ref"),
            ),
        )
        return select_sql(
            d,
            [
                column(d, "RDB$CONSTRAINT_NAME", "rc", alias="CONSTRAINT_NAME"),
                column(d, "RDB$INDEX_NAME", "rc", alias="INDEX_NAME"),
                column(d, "RDB$FIELD_NAME", "seg", alias="COLUMN_NAME"),
                column(d, "RDB$RELATION_NAME", "ref", alias="REF_TABLE"),
                column(d, "RDB$FIELD_NAME", "ref_seg", alias="REF_COLUMN"),
                column(d, "RDB$DELETE_RULE", "rc", alias="DELETE_RULE"),
            ],
            from_=joined,
            where=compare(
                d,
                "eq",
                column(d, "RDB$RELATION_NAME", "i"),
                literal(d, table_name),
            ),
            order_by=[column(d, "RDB$FIELD_POSITION", "seg")],
        )

    def _make_view_list_sql(self, schema: Optional[str] = None) -> str:
        """The database's views: relations that are neither system nor baseless.

        ``RDB$VIEW_BLR IS NOT NULL`` is what makes a relation a view;
        ``RDB$VIEW_SOURCE`` carries its text.
        """
        from ..query_nodes import (
            column,
            compare,
            conjunction,
            literal,
            null_test,
            relation,
            select_sql,
        )

        self._reject_namespace(schema)
        d = self.dialect
        return select_sql(
            d,
            [column(d, "RDB$RELATION_NAME"), column(d, "RDB$VIEW_SOURCE")],
            from_=relation(d, "RDB$RELATIONS"),
            where=conjunction(
                d,
                compare(
                    d, "eq", column(d, "RDB$SYSTEM_FLAG"), literal(d, 0, inline=True)
                ),
                null_test(d, column(d, "RDB$VIEW_BLR"), is_not=True),
            ),
            order_by=[column(d, "RDB$RELATION_NAME")],
        )

    # ------------------------------------------------------------------
    # Parse methods
    # ------------------------------------------------------------------

    def _parse_database_info(self, rows: List[Dict[str, Any]]) -> IntrospectionDatabaseInfo:
        version = self._get_version()
        return IntrospectionDatabaseInfo(
            name=str(rows[0].get("MON$DATABASE_NAME", "")) if rows else "",
            version=".".join(str(v) for v in version),
            version_tuple=version,
            vendor="Firebird",
        )

    def _parse_tables(self, rows: List[Dict[str, Any]],
                       schema: Optional[str]) -> List[IntrospectionTableInfo]:
        tables = []
        for row in rows:
            name = str(row.get("RDB$RELATION_NAME", "")).strip()
            if not name:
                continue
            is_view = row.get("RDB$VIEW_BLR") is not None
            tables.append(
                IntrospectionTableInfo(
                    name=name,
                    schema=schema or "",
                    table_type=TableType.VIEW if is_view else TableType.BASE_TABLE,
                )
            )
        return tables

    def _parse_columns(self, rows: List[Dict[str, Any]],
                        table_name: str,
                        schema: str) -> List[IntrospectionColumnInfo]:
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
                IntrospectionColumnInfo(
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
                             schema: str) -> List[IntrospectionForeignKeyInfo]:
        action_map = {
            "CASCADE": ReferentialAction.CASCADE,
            "SET NULL": ReferentialAction.SET_NULL,
            "SET DEFAULT": ReferentialAction.SET_DEFAULT,
            "NO ACTION": ReferentialAction.NO_ACTION,
            "RESTRICT": ReferentialAction.RESTRICT,
        }
        fk_map: Dict[str, IntrospectionForeignKeyInfo] = {}
        for row in rows:
            name = str(row.get("CONSTRAINT_NAME", "")).strip()
            if not name:
                continue
            if name not in fk_map:
                delete_rule = str(row.get("DELETE_RULE", "")).strip() if row.get("DELETE_RULE") else "NO ACTION"
                fk_map[name] = IntrospectionForeignKeyInfo(
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
                      schema: str) -> List[IntrospectionViewInfo]:
        return [
            IntrospectionViewInfo(
                name=str(row.get("RDB$RELATION_NAME", "")).strip(),
                schema=schema,
                definition=str(row.get("RDB$VIEW_SOURCE", "")) if row.get("RDB$VIEW_SOURCE") else None,
                check_option=None,
                is_updatable=False,
            )
            for row in rows if row.get("RDB$RELATION_NAME")
        ]

    def _parse_triggers(self, rows: List[Dict[str, Any]],
                         schema: str) -> List[IntrospectionTriggerInfo]:
        return []

    # ------------------------------------------------------------------
    # Core ``IntrospectorMixin`` entry points
    #
    # Each of these is the method the core base class calls; the ``_make_*``
    # helpers above hold the SQL. Every one of them routes ``schema`` through
    # ``_reject_namespace`` before the SQL is built, so the core's habit of
    # substituting ``_get_default_schema()`` for a missing schema cannot turn
    # into a silently accepted namespace.
    # ------------------------------------------------------------------

    def _build_database_info_sql(self):
        return self._make_database_info_sql()

    def _build_table_list_sql(self, schema, include_system, include_views, table_type):
        return self._make_table_list_sql(schema, include_system, include_views, table_type)

    def _build_column_list_sql(self, table_name, schema):
        return self._make_column_list_sql(table_name, schema)

    def _build_index_list_sql(self, table_name, schema):
        return self._make_index_list_sql(table_name, schema)

    def _build_primary_key_sql(self, table_name, schema):
        # A primary key is found from the table's unique RDB$PRIMARY% index,
        # so there is nothing for a namespace to narrow -- but the argument is
        # still refused rather than dropped, so this entry point behaves like
        # its siblings instead of being the one that quietly ignores it.
        self._reject_namespace(schema)
        return self._make_primary_key_sql(table_name)

    def _build_foreign_key_sql(self, table_name, schema):
        return self._make_foreign_key_sql(table_name, schema)

    def _build_view_list_sql(self, schema, include_system: bool = False):
        return self._make_view_list_sql(schema)


class AsyncFirebirdIntrospector(FirebirdAsyncIntrospectorMixin, AsyncAbstractIntrospector):
    """Asynchronous Firebird schema introspector.

    Uses the thread-pool-based executor from AsyncFirebirdBackend to
    run sync fdb cursor operations in a background thread.
    """

    def __init__(
        self,
        backend,
        executor,
        cache: Optional[IntrospectionCache] = None,
    ):
        super().__init__(backend, executor, cache)
        self._status_instance = None

    @property
    def status(self):
        """Firebird status introspector (lazily created)."""
        from .status_introspector import AsyncFirebirdStatusIntrospector
        if self._status_instance is None:
            self._status_instance = AsyncFirebirdStatusIntrospector(self._backend)
        return self._status_instance

    async def get_table_info(
        self, table_name: str, schema: Optional[str] = None
    ) -> Optional[IntrospectionTableInfo]:
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
