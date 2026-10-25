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
    IntrospectionScope,
)

from .types import FirebirdDomainInfo, FirebirdGeneratorInfo

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

# The table-trigger values of ``RDB$TRIGGER_TYPE`` (language reference D.32.1).
# It is a closed list, not a bitmask a caller can decode by shifting: the same
# integer means a different combination at each magnitude (17 is INSERT|UPDATE,
# 25 is INSERT|DELETE, 113 is all three). Database-level triggers carry values
# in the thousands and are excluded by the question itself, which requires a
# relation name.
FB_TRIGGER_TYPES = {
    1: ("BEFORE", ("INSERT",)),
    2: ("AFTER", ("INSERT",)),
    3: ("BEFORE", ("UPDATE",)),
    4: ("AFTER", ("UPDATE",)),
    5: ("BEFORE", ("DELETE",)),
    6: ("AFTER", ("DELETE",)),
    17: ("BEFORE", ("INSERT", "UPDATE")),
    18: ("AFTER", ("INSERT", "UPDATE")),
    25: ("BEFORE", ("INSERT", "DELETE")),
    26: ("AFTER", ("INSERT", "DELETE")),
    27: ("BEFORE", ("UPDATE", "DELETE")),
    28: ("AFTER", ("UPDATE", "DELETE")),
    113: ("BEFORE", ("INSERT", "UPDATE", "DELETE")),
    114: ("AFTER", ("INSERT", "UPDATE", "DELETE")),
}


class FirebirdAsyncIntrospectorMixin(IntrospectorMixin):
    """Shared parse logic for Firebird introspection, used by both I/O halves.

    Namespaces
    ----------
    Firebird has one namespace per database file, so the dialect refuses a
    non-empty ``schema`` when it renders a statement
    (:meth:`FirebirdIntrospectionMixin.reject_namespace`) rather than
    ignoring it. Silently discarding it would return the whole database's
    tables for a request that asked for one schema's tables -- an answer that
    looks successful and is about the wrong objects, which is the failure
    this layer exists to prevent.

    The system tables these questions read (``RDB$RELATIONS``,
    ``RDB$RELATION_FIELDS``, ``RDB$INDICES``, ``RDB$REF_CONSTRAINTS``) are
    ordinary relations reached unqualified and filtered with
    ``RDB$SYSTEM_FLAG``; ``RDB$`` is a naming convention, not a schema.

    The SQL belongs to the dialect. This mixin constructs a statement, hands
    it to the executor and parses the rows; the sync and async introspectors
    are separate classes that cannot coexist, and they share every parser and
    every Firebird-specific statement factory through this mixin.
    """

    @property
    def default_schema(self) -> str:
        """The namespace every Firebird object lives in -- there is only one.

        Empty rather than ``None`` because callers treat the empty string as
        "no namespace given", which is exactly the case here.
        """
        return ""

    def _get_version(self) -> tuple:
        dialect_ver = getattr(self._backend.dialect, 'version', None)
        if dialect_ver:
            return dialect_ver
        return (3, 0, 0)

    # ------------------------------------------------------------------
    # Firebird-specific statement factories
    #
    # Generators and domains have no core entry point: the core's scopes name
    # them (SEQUENCE; and SCHEMA for a database-wide type catalogue), but the
    # questions and their results are Firebird's own. Each factory returns a
    # statement with every parameter already collected; the dialect renders
    # it, the executor runs it, and the parser below reads the rows.
    # ------------------------------------------------------------------

    def generator_list_statement(self, include_system: bool = False):
        """Return the statement that lists this database's generators."""
        from ..expression.introspection import FirebirdGeneratorListQueryStatement

        return FirebirdGeneratorListQueryStatement(self.dialect, include_system)

    def generator_value_statement(self, generator_name: str):
        """Return the statement that reads one generator's current value."""
        from ..expression.introspection import FirebirdGeneratorValueQueryStatement

        return FirebirdGeneratorValueQueryStatement(self.dialect, generator_name)

    def domain_list_statement(self, include_system: bool = False):
        """Return the statement that lists this database's domains."""
        from ..expression.introspection import FirebirdDomainListQueryStatement

        return FirebirdDomainListQueryStatement(self.dialect, include_system)

    # ------------------------------------------------------------------
    # Parse methods
    # ------------------------------------------------------------------

    def parse_database_info(self, rows: List[Dict[str, Any]]) -> IntrospectionDatabaseInfo:
        version = self._get_version()
        return IntrospectionDatabaseInfo(
            name=str(rows[0].get("MON$DATABASE_NAME", "")) if rows else "",
            version=".".join(str(v) for v in version),
            version_tuple=version,
            vendor="Firebird",
        )

    def parse_tables(self, rows: List[Dict[str, Any]],
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

    def parse_columns(self, rows: List[Dict[str, Any]],
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

    def parse_indexes(self, rows: List[Dict[str, Any]],
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

    def parse_foreign_keys(self, rows: List[Dict[str, Any]],
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

    def parse_views(self, rows: List[Dict[str, Any]],
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

    def parse_view_info(self, rows: List[Dict[str, Any]],
                         view_name: str,
                         schema: str) -> Optional[IntrospectionViewInfo]:
        """One view from the rows a single-view query returned, or ``None``.

        The core manager asks this after ``_build_view_info_sql`` narrows the
        catalogue to one view, so the shape is ``parse_views`` on at most one
        row. ``list_views`` then does the filtering for the list question, and
        this parser does not repeat it: an empty row set means the name is not
        a view, which is exactly what ``None`` already says.

        ``RDB$VIEW_SOURCE`` is the definition and ``RDB$VIEW_BLR`` is what
        marks a relation as a view (see ``_make_view_list_sql``); a view has
        no ``CHECK OPTION`` in Firebird and is not updatable through the
        catalogue, so both stay absent rather than guessed.
        """
        matches = self.parse_views(rows, schema)
        return matches[0] if matches else None

    def parse_triggers(self, rows: List[Dict[str, Any]],
                         schema: str) -> List[IntrospectionTriggerInfo]:
        """Decode each trigger's timing and events from ``RDB$TRIGGER_TYPE``.

        The type integer is looked up in :data:`FB_TRIGGER_TYPES` rather than
        bit-shifted: Firebird's fourteen table-trigger values are a closed
        list, and the same bit at two magnitudes means two different event
        sets. A value outside the list (a DDL trigger, or a future addition)
        yields empty timing and events rather than a guess -- the question
        already excludes database-level rows, so reporting nothing is honest
        about the one case this decoder does not know.

        Firebird's table triggers are row-level only, and a trigger has no
        ``WHEN`` clause of its own (the condition lives in its PSQL body), so
        ``level`` is ``ROW`` and ``condition`` stays ``None``.
        """
        triggers: List[IntrospectionTriggerInfo] = []
        for row in rows:
            name = self._row_name(row, "TRIGGER_NAME")
            table_name = self._row_name(row, "TABLE_NAME")
            if not name or not table_name:
                continue
            timing, events = FB_TRIGGER_TYPES.get(
                row.get("TRIGGER_TYPE"), ("", ())
            )
            triggers.append(
                IntrospectionTriggerInfo(
                    name=name,
                    table_name=table_name,
                    schema=schema,
                    timing=timing,
                    events=list(events),
                    level="ROW",
                    definition=self._text_or_none(row.get("SOURCE")),
                    status="DISABLED" if row.get("INACTIVE") else "ENABLED",
                    extra={
                        "trigger_type": row.get("TRIGGER_TYPE"),
                        "sequence": row.get("SEQUENCE"),
                    },
                )
            )
        return triggers

    # ------------------------------------------------------------------
    # Generators and domains
    #
    # These two families are Firebird's own, so they have no ``_build_*``
    # entry point on the core mixin: the core has no question to ask about
    # them. What is shared here is what both directions need -- the row shape
    # a parser reads and the names a caller looks objects up by.
    # ------------------------------------------------------------------

    @staticmethod
    def _row_name(row: Dict[str, Any], key: str) -> str:
        """One catalogue name, stripped, or ``""`` when the row has none.

        Firebird's ``CHAR`` columns come back space-padded, and a name that is
        only padding is not an object.
        """
        raw = row.get(key)
        return str(raw).strip() if raw else ""

    @staticmethod
    def _text_or_none(value: Any) -> Optional[str]:
        """A catalogue text column as a stripped string, or ``None``.

        ``DEFAULT``/``CHECK``/description are ``BLOB TEXT``; the driver hands
        them back as ``str``, and an all-space body is the catalogue's way of
        saying "no source".
        """
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _find_by_name(items: List[Any], name: str) -> Optional[Any]:
        """The item named *name*, or ``None``.

        Firebird folds unquoted identifiers to upper case, so ``my_gen`` names
        ``MY_GEN`` unless it was created quoted. An exact match is tried first
        (so two names differing only by case stay distinguishable), then a
        case-insensitive one.
        """
        for item in items:
            if item.name == name:
                return item
        folded = name.upper()
        for item in items:
            if item.name.upper() == folded:
                return item
        return None

    @staticmethod
    def _describe_domain_type(
        field_type: Optional[int],
        sub_type: Optional[int],
        scale: Optional[int],
    ) -> str:
        """The domain's base type, from the catalogue's type codes.

        ``NUMERIC`` and ``DECIMAL`` are named from the pair Firebird records
        for them -- an integer field type with sub type 1 or 2 and a negative
        scale -- rather than from the integer type underneath, which is what
        the column parser reports. A domain's whole purpose is the attributes
        it attaches to a type, so naming the storage integer here would lose
        the one a caller declared.
        """
        if (
            field_type in (7, 8, 16, 26)
            and sub_type in (1, 2)
            and scale is not None
            and scale < 0
        ):
            return "NUMERIC" if sub_type == 1 else "DECIMAL"
        type_name = FB_FIELD_TYPES.get(field_type, f"UNKNOWN({field_type})")
        if type_name == "BLOB":
            blob_sub = FB_BLOB_SUB_TYPES.get(sub_type, str(sub_type))
            return f"BLOB SUB_TYPE {blob_sub}"
        return type_name

    def parse_generators(
        self,
        rows: List[Dict[str, Any]],
        values: Dict[str, int],
    ) -> List[FirebirdGeneratorInfo]:
        """Pair each generator row with the value read for that generator."""
        generators: List[FirebirdGeneratorInfo] = []
        for row in rows:
            name = self._row_name(row, "GENERATOR_NAME")
            if not name:
                continue
            generators.append(
                FirebirdGeneratorInfo(
                    name=name,
                    value=values[name],
                    is_system=bool(row.get("SYSTEM_FLAG")),
                )
            )
        return generators

    def parse_domains(self, rows: List[Dict[str, Any]]) -> List[FirebirdDomainInfo]:
        domains: List[FirebirdDomainInfo] = []
        for row in rows:
            name = self._row_name(row, "DOMAIN_NAME")
            if not name:
                continue
            charset = self._text_or_none(row.get("CHARACTER_SET_NAME"))
            domains.append(
                FirebirdDomainInfo(
                    name=name,
                    base_type=self._describe_domain_type(
                        row.get("FIELD_TYPE"),
                        row.get("FIELD_SUB_TYPE"),
                        row.get("SCALE"),
                    ),
                    length=row.get("FIELD_LENGTH"),
                    character_length=row.get("CHARACTER_LENGTH"),
                    numeric_precision=row.get("PRECISION"),
                    numeric_scale=row.get("SCALE"),
                    charset=charset,
                    nullable=row.get("NULL_FLAG") is None,
                    default_source=self._text_or_none(row.get("DEFAULT_SOURCE")),
                    check_source=self._text_or_none(row.get("VALIDATION_SOURCE")),
                    is_system=bool(row.get("SYSTEM_FLAG")),
                    description=self._text_or_none(row.get("DESCRIPTION")),
                )
            )
        return domains

    # ------------------------------------------------------------------
    # Core ``IntrospectorMixin`` entry points
    #
    # Each of these is the method the core base class calls; the ``_make_*``
    # helpers above hold the SQL. Every one of them routes ``schema`` through
    # ``_reject_namespace`` before the SQL is built, so the core's habit of
    # substituting ``default_schema`` for a missing schema cannot turn
    # into a silently accepted namespace.
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Firebird-specific object families
    #
    # Generators and domains have no core entry point: the core's scopes name
    # them (SEQUENCE; and SCHEMA for a database-wide type catalogue), but the
    # questions and their results are Firebird's own. These methods are the
    # async half of the pair the sync introspector declares -- same names,
    # same signatures, same returns.
    # ------------------------------------------------------------------

    async def list_generators(self, include_system: bool = False) -> List[FirebirdGeneratorInfo]:
        """List the generators (sequences) of this database with their values.

        One ``GEN_ID(<name>, 0)`` per generator: a generator name cannot be
        bound as a parameter, so the catalogue read and the value reads cannot
        be one statement. The result is cached, so the cost is paid once per
        cache generation rather than once per call.
        """
        key = self._cache.key(
            IntrospectionScope.SEQUENCE, extra=f"generators:{include_system}"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        sql, params = self.generator_list_statement(include_system).to_sql()
        rows = await self._executor.execute(sql, params)
        values: Dict[str, int] = {}
        for row in rows:
            name = self._row_name(row, "GENERATOR_NAME")
            if not name:
                continue
            value_sql, value_params = self.generator_value_statement(name).to_sql()
            value_rows = await self._executor.execute(value_sql, value_params)
            values[name] = int(value_rows[0]["GENERATOR_VALUE"])

        result = self.parse_generators(rows, values)
        self._cache.set(key, result)
        return result

    async def get_generator_info(self, name: str) -> Optional[FirebirdGeneratorInfo]:
        """Return the named generator (sequence), or ``None``.

        The default list answers first, so looking up a generator the user
        created never reads the system's own rows -- and never pays their
        ``GEN_ID`` calls. Only a name that list does not contain falls back to
        ``include_system=True``.
        """
        found = self._find_by_name(await self.list_generators(), name)
        if found is not None:
            return found
        return self._find_by_name(
            await self.list_generators(include_system=True), name
        )

    async def list_domains(self, include_system: bool = False) -> List[FirebirdDomainInfo]:
        """List the domains of this database with their declared attributes."""
        key = self._cache.key(
            IntrospectionScope.SCHEMA, extra=f"domains:{include_system}"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        sql, params = self.domain_list_statement(include_system).to_sql()
        result = self.parse_domains(await self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    async def get_domain_info(self, name: str) -> Optional[FirebirdDomainInfo]:
        """Return the named domain, or ``None``.

        The default list answers first; only a system domain's name needs the
        ``include_system=True`` pass.
        """
        found = self._find_by_name(await self.list_domains(), name)
        if found is not None:
            return found
        return self._find_by_name(await self.list_domains(include_system=True), name)
