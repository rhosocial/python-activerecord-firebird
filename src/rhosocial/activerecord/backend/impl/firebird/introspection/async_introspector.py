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

from .types import (
    FirebirdCharsetInfo,
    FirebirdCollationInfo,
    FirebirdConstraintInfo,
    FirebirdDependencyInfo,
    FirebirdDomainInfo,
    FirebirdExceptionInfo,
    FirebirdFunctionArgumentInfo,
    FirebirdFunctionInfo,
    FirebirdGeneratorInfo,
    FirebirdProcedureInfo,
    FirebirdProcedureParameterInfo,
    FirebirdPublicationInfo,
    FirebirdPrivilegeInfo,
    FirebirdRoleInfo,
    FirebirdViewRelationInfo,
    object_type_name,
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
                # The constraint join says which kind an index is; the name only
                # says it when Firebird generated the name itself
                # (RDB$PRIMARYn). A primary key the user named PK_ORDERS carries
                # no such word, so the column is read first and the name is only
                # the fallback for a row that arrives without it.
                constraint_type = str(row.get("CONSTRAINT_TYPE") or "").strip().upper()
                is_primary = constraint_type == "PRIMARY KEY" or "PRIMARY" in name.upper()
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
        marks a relation as a view (see ``view_list_statement``); a view has
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

    # ------------------------------------------------------------------
    # Firebird-specific statement factories (schema objects)
    #
    # One factory per family the catalogue reports independently, which is
    # also one CLI dimension each: an item Firebird answers as its own row set
    # is not folded into a neighbour, and a family is not split into types the
    # server does not distinguish.
    #
    # Every factory takes the whole question -- the system filter, the object
    # name, the type filter -- so the statement is complete before it is
    # rendered and the formatter never has to guess a default.
    # ------------------------------------------------------------------

    def exception_list_statement(self, include_system: bool = False):
        """Return the statement that lists this database's exceptions."""
        from ..expression.introspection import FirebirdExceptionListQueryStatement

        return FirebirdExceptionListQueryStatement(self.dialect, include_system)

    def exception_info_statement(self, exception_name: str):
        """Return the statement that reads one exception."""
        from ..expression.introspection import FirebirdExceptionInfoQueryStatement

        return FirebirdExceptionInfoQueryStatement(self.dialect, exception_name)

    def procedure_list_statement(
        self, include_system: bool = False, include_source: bool = False
    ):
        """Return the statement that lists stored procedures."""
        from ..expression.introspection import FirebirdProcedureListQueryStatement

        return FirebirdProcedureListQueryStatement(
            self.dialect, include_system, include_source
        )

    def procedure_parameter_statement(self, procedure_name: str):
        """Return the statement that reads one procedure's parameters."""
        from ..expression.introspection import FirebirdProcedureParameterQueryStatement

        return FirebirdProcedureParameterQueryStatement(self.dialect, procedure_name)

    def function_list_statement(
        self, include_system: bool = False, include_source: bool = False
    ):
        """Return the statement that lists functions, PSQL and legacy alike."""
        from ..expression.introspection import FirebirdFunctionListQueryStatement

        return FirebirdFunctionListQueryStatement(
            self.dialect, include_system, include_source
        )

    def function_argument_statement(self, function_name: str):
        """Return the statement that reads one function's arguments."""
        from ..expression.introspection import FirebirdFunctionArgumentQueryStatement

        return FirebirdFunctionArgumentQueryStatement(self.dialect, function_name)

    def constraint_list_statement(
        self,
        table_name: Optional[str] = None,
        constraint_type: Optional[str] = None,
        include_system: bool = False,
    ):
        """Return the statement that lists constraints of every kind."""
        from ..expression.introspection import FirebirdConstraintListQueryStatement

        return FirebirdConstraintListQueryStatement(
            self.dialect, table_name, constraint_type, include_system
        )

    def role_list_statement(self, include_system: bool = False):
        """Return the statement that lists roles."""
        from ..expression.introspection import FirebirdRoleListQueryStatement

        return FirebirdRoleListQueryStatement(self.dialect, include_system)

    def privilege_statement(
        self,
        object_name: Optional[str] = None,
        user_name: Optional[str] = None,
        include_system: bool = False,
    ):
        """Return the statement that lists grants, optionally narrowed."""
        from ..expression.introspection import FirebirdPrivilegeQueryStatement

        return FirebirdPrivilegeQueryStatement(
            self.dialect, object_name, user_name, include_system
        )

    def charset_list_statement(self):
        """Return the statement that lists character sets."""
        from ..expression.introspection import FirebirdCharsetListQueryStatement

        return FirebirdCharsetListQueryStatement(self.dialect)

    def collation_list_statement(self, charset_name: Optional[str] = None):
        """Return the statement that lists collations, optionally of one charset."""
        from ..expression.introspection import FirebirdCollationListQueryStatement

        return FirebirdCollationListQueryStatement(self.dialect, charset_name)

    def dependency_statement(self, object_name: Optional[str] = None):
        """Return the statement that lists dependency edges."""
        from ..expression.introspection import FirebirdDependencyQueryStatement

        return FirebirdDependencyQueryStatement(self.dialect, object_name)

    def view_relation_statement(self, view_name: Optional[str] = None):
        """Return the statement that lists the relations a view reads."""
        from ..expression.introspection import FirebirdViewRelationQueryStatement

        return FirebirdViewRelationQueryStatement(self.dialect, view_name)

    def publication_list_statement(self, include_system: bool = False):
        """Return the statement that lists publications (Firebird 4 and later)."""
        from ..expression.introspection import FirebirdPublicationListQueryStatement

        return FirebirdPublicationListQueryStatement(self.dialect, include_system)

    # ------------------------------------------------------------------
    # Parsers for the schema-object families
    # ------------------------------------------------------------------

    @staticmethod
    def _blob_truthy(value: Any) -> bool:
        """Read a flag kept as a blob, without calling any non-empty blob true.

        ``RDB$ROLES.RDB$SYSTEM_PRIVILEGES`` is a bitmap: a role without system
        privileges still stores a row of zero bytes, and ``bool(b"\\x00")`` is
        True. Only a non-zero byte means the flag is set.
        """
        if value is None:
            return False
        if isinstance(value, (bytes, bytearray)):
            return any(value)
        return bool(str(value).strip())

    def parse_exceptions(
        self, rows: List[Dict[str, Any]]
    ) -> List[FirebirdExceptionInfo]:
        """Build the exception list from ``RDB$EXCEPTIONS`` rows."""
        result: List[FirebirdExceptionInfo] = []
        for row in rows:
            name = self._row_name(row, "EXCEPTION_NAME")
            if not name:
                continue
            result.append(
                FirebirdExceptionInfo(
                    name=name,
                    number=row.get("EXCEPTION_NUMBER"),
                    message=self._text_or_none(row.get("MESSAGE")),
                    owner=self._text_or_none(row.get("OWNER_NAME")),
                    is_system=bool(row.get("SYSTEM_FLAG")),
                    description=self._text_or_none(row.get("DESCRIPTION")),
                )
            )
        return result

    def parse_procedures(
        self, rows: List[Dict[str, Any]]
    ) -> List[FirebirdProcedureInfo]:
        """Build the procedure list from ``RDB$PROCEDURES`` rows."""
        result: List[FirebirdProcedureInfo] = []
        for row in rows:
            name = self._row_name(row, "PROCEDURE_NAME")
            if not name:
                continue
            result.append(
                FirebirdProcedureInfo(
                    name=name,
                    procedure_id=row.get("PROCEDURE_ID"),
                    inputs=row.get("INPUTS"),
                    outputs=row.get("OUTPUTS"),
                    procedure_type=row.get("PROCEDURE_TYPE"),
                    owner=self._text_or_none(row.get("OWNER_NAME")),
                    valid_blr=row.get("VALID_BLR"),
                    private_flag=row.get("PRIVATE_FLAG"),
                    sql_security=row.get("SQL_SECURITY"),
                    description=self._text_or_none(row.get("DESCRIPTION")),
                    is_system=bool(row.get("SYSTEM_FLAG")),
                    source=self._text_or_none(row.get("PROCEDURE_SOURCE")),
                )
            )
        return result

    def parse_procedure_parameters(
        self, rows: List[Dict[str, Any]]
    ) -> List[FirebirdProcedureParameterInfo]:
        """Build one procedure's parameter list.

        Inputs and outputs arrive in one ordered read; ``kind`` keeps them apart
        without the caller having to re-read the numeric type code.
        """
        result: List[FirebirdProcedureParameterInfo] = []
        for row in rows:
            parameter_type = row.get("PARAMETER_TYPE")
            result.append(
                FirebirdProcedureParameterInfo(
                    name=self._row_name(row, "PARAMETER_NAME") or None,
                    position=row.get("PARAMETER_NUMBER"),
                    kind={0: "input", 1: "output"}.get(
                        parameter_type, str(parameter_type)
                    ),
                    data_type=self._describe_domain_type(
                        row.get("FIELD_TYPE"),
                        row.get("FIELD_SUB_TYPE"),
                        row.get("SCALE"),
                    ),
                    character_length=row.get("CHARACTER_LENGTH"),
                    numeric_precision=row.get("PRECISION"),
                    numeric_scale=row.get("SCALE"),
                    nullable=row.get("NULL_FLAG") is None,
                    default_source=self._text_or_none(row.get("DEFAULT_SOURCE")),
                    description=self._text_or_none(row.get("DESCRIPTION")),
                )
            )
        return result

    def parse_functions(
        self, rows: List[Dict[str, Any]]
    ) -> List[FirebirdFunctionInfo]:
        """Build the function list from ``RDB$FUNCTIONS`` rows."""
        result: List[FirebirdFunctionInfo] = []
        for row in rows:
            name = self._row_name(row, "FUNCTION_NAME")
            if not name:
                continue
            result.append(
                FirebirdFunctionInfo(
                    name=name,
                    function_type=row.get("FUNCTION_TYPE"),
                    is_legacy=bool(row.get("LEGACY_FLAG")),
                    is_deterministic=bool(row.get("DETERMINISTIC_FLAG")),
                    return_argument=row.get("RETURN_ARGUMENT"),
                    owner=self._text_or_none(row.get("OWNER_NAME")),
                    valid_blr=row.get("VALID_BLR"),
                    engine_name=self._text_or_none(row.get("ENGINE_NAME")),
                    module_name=self._text_or_none(row.get("MODULE_NAME")),
                    entrypoint=self._text_or_none(row.get("ENTRYPOINT")),
                    private_flag=row.get("PRIVATE_FLAG"),
                    sql_security=row.get("SQL_SECURITY"),
                    description=self._text_or_none(row.get("DESCRIPTION")),
                    is_system=bool(row.get("SYSTEM_FLAG")),
                    source=self._text_or_none(row.get("FUNCTION_SOURCE")),
                )
            )
        return result

    def parse_function_arguments(
        self, rows: List[Dict[str, Any]]
    ) -> List[FirebirdFunctionArgumentInfo]:
        """Build one function's argument list, return slot included."""
        result: List[FirebirdFunctionArgumentInfo] = []
        for row in rows:
            result.append(
                FirebirdFunctionArgumentInfo(
                    position=row.get("ARGUMENT_POSITION"),
                    name=self._row_name(row, "ARGUMENT_NAME") or None,
                    mechanism=row.get("MECHANISM"),
                    data_type=self._describe_domain_type(
                        row.get("FIELD_TYPE"),
                        row.get("FIELD_SUB_TYPE"),
                        row.get("SCALE"),
                    ),
                    character_length=row.get("CHARACTER_LENGTH"),
                    numeric_precision=row.get("PRECISION"),
                    numeric_scale=row.get("SCALE"),
                    nullable=row.get("NULL_FLAG") is None,
                    default_source=self._text_or_none(row.get("DEFAULT_SOURCE")),
                    description=self._text_or_none(row.get("DESCRIPTION")),
                )
            )
        return result

    def parse_constraints(
        self, rows: List[Dict[str, Any]]
    ) -> List[FirebirdConstraintInfo]:
        """Build the constraint list, CHECK text included when the row has one."""
        result: List[FirebirdConstraintInfo] = []
        for row in rows:
            name = self._row_name(row, "CONSTRAINT_NAME")
            if not name:
                continue
            result.append(
                FirebirdConstraintInfo(
                    name=name,
                    constraint_type=self._text_or_none(row.get("CONSTRAINT_TYPE")),
                    table_name=self._text_or_none(row.get("RELATION_NAME")),
                    deferrable=self._text_or_none(row.get("DEFERRABLE")),
                    initially_deferred=self._text_or_none(
                        row.get("INITIALLY_DEFERRED")
                    ),
                    index_name=self._text_or_none(row.get("INDEX_NAME")),
                    check_trigger=self._text_or_none(row.get("CHECK_TRIGGER")),
                    check_source=self._text_or_none(row.get("CHECK_SOURCE")),
                )
            )
        return result

    def parse_roles(self, rows: List[Dict[str, Any]]) -> List[FirebirdRoleInfo]:
        """Build the role list from ``RDB$ROLES`` rows."""
        result: List[FirebirdRoleInfo] = []
        for row in rows:
            name = self._row_name(row, "ROLE_NAME")
            if not name:
                continue
            result.append(
                FirebirdRoleInfo(
                    name=name,
                    owner=self._text_or_none(row.get("OWNER_NAME")),
                    has_system_privileges=self._blob_truthy(
                        row.get("SYSTEM_PRIVILEGES")
                    ),
                    is_system=bool(row.get("SYSTEM_FLAG")),
                    description=self._text_or_none(row.get("DESCRIPTION")),
                )
            )
        return result

    def parse_privileges(
        self, rows: List[Dict[str, Any]]
    ) -> List[FirebirdPrivilegeInfo]:
        """Build the grant list from ``RDB$USER_PRIVILEGES`` rows.

        ``privilege`` is left as the catalogue's letter: the SQL privileges are
        ``S``/``I``/``U``/``D``/``R``, while Firebird 4's system privileges use
        other letters, and inventing a translation for the ones no release
        documents would be worse than passing them through.
        """
        result: List[FirebirdPrivilegeInfo] = []
        for row in rows:
            result.append(
                FirebirdPrivilegeInfo(
                    grantee=self._text_or_none(row.get("GRANTEE")),
                    grantee_type=object_type_name(row.get("GRANTEE_TYPE")),
                    grantor=self._text_or_none(row.get("GRANTOR")),
                    privilege=self._text_or_none(row.get("PRIVILEGE")),
                    grant_option=row.get("GRANT_OPTION"),
                    object_name=self._text_or_none(row.get("OBJECT_NAME")),
                    object_type=object_type_name(row.get("OBJECT_TYPE")),
                    field_name=self._text_or_none(row.get("FIELD_NAME")),
                )
            )
        return result

    def parse_charsets(self, rows: List[Dict[str, Any]]) -> List[FirebirdCharsetInfo]:
        """Build the character-set list."""
        result: List[FirebirdCharsetInfo] = []
        for row in rows:
            name = self._row_name(row, "CHARACTER_SET_NAME")
            if not name:
                continue
            result.append(
                FirebirdCharsetInfo(
                    name=name,
                    charset_id=row.get("CHARACTER_SET_ID"),
                    form_of_use=self._text_or_none(row.get("FORM_OF_USE")),
                    number_of_characters=row.get("NUMBER_OF_CHARACTERS"),
                    bytes_per_character=row.get("BYTES_PER_CHARACTER"),
                    default_collation=self._text_or_none(
                        row.get("DEFAULT_COLLATION_NAME")
                    ),
                    function_name=self._text_or_none(row.get("FUNCTION_NAME")),
                    is_system=bool(row.get("SYSTEM_FLAG")),
                    description=self._text_or_none(row.get("DESCRIPTION")),
                )
            )
        return result

    def parse_collations(
        self, rows: List[Dict[str, Any]]
    ) -> List[FirebirdCollationInfo]:
        """Build the collation list."""
        result: List[FirebirdCollationInfo] = []
        for row in rows:
            name = self._row_name(row, "COLLATION_NAME")
            if not name:
                continue
            result.append(
                FirebirdCollationInfo(
                    name=name,
                    charset=self._text_or_none(row.get("CHARACTER_SET_NAME")),
                    collation_id=row.get("COLLATION_ID"),
                    base_collation=self._text_or_none(row.get("BASE_COLLATION_NAME")),
                    specific_attributes=self._text_or_none(
                        row.get("SPECIFIC_ATTRIBUTES")
                    ),
                    function_name=self._text_or_none(row.get("FUNCTION_NAME")),
                    is_system=bool(row.get("SYSTEM_FLAG")),
                    description=self._text_or_none(row.get("DESCRIPTION")),
                )
            )
        return result

    def parse_dependencies(
        self, rows: List[Dict[str, Any]]
    ) -> List[FirebirdDependencyInfo]:
        """Build the dependency edge list."""
        result: List[FirebirdDependencyInfo] = []
        for row in rows:
            result.append(
                FirebirdDependencyInfo(
                    dependent_name=self._text_or_none(row.get("DEPENDENT_NAME")),
                    dependent_type=object_type_name(row.get("DEPENDENT_TYPE")),
                    depended_on_name=self._text_or_none(row.get("DEPENDED_ON_NAME")),
                    depended_on_type=object_type_name(row.get("DEPENDED_ON_TYPE")),
                    field_name=self._text_or_none(row.get("FIELD_NAME")),
                )
            )
        return result

    def parse_view_relations(
        self, rows: List[Dict[str, Any]]
    ) -> List[FirebirdViewRelationInfo]:
        """Build the view-relation list."""
        result: List[FirebirdViewRelationInfo] = []
        for row in rows:
            result.append(
                FirebirdViewRelationInfo(
                    view_name=self._text_or_none(row.get("VIEW_NAME")),
                    relation_name=self._text_or_none(row.get("RELATION_NAME")),
                    view_context=row.get("VIEW_CONTEXT"),
                    context_name=self._text_or_none(row.get("CONTEXT_NAME")),
                    context_type=object_type_name(row.get("CONTEXT_TYPE")),
                )
            )
        return result

    def parse_publications(
        self, rows: List[Dict[str, Any]]
    ) -> List[FirebirdPublicationInfo]:
        """Build the publication list."""
        result: List[FirebirdPublicationInfo] = []
        for row in rows:
            name = self._row_name(row, "PUBLICATION_NAME")
            if not name:
                continue
            result.append(
                FirebirdPublicationInfo(
                    name=name,
                    owner=self._text_or_none(row.get("OWNER_NAME")),
                    active=bool(row.get("ACTIVE_FLAG")),
                    auto_enable=bool(row.get("AUTO_ENABLE")),
                    is_system=bool(row.get("SYSTEM_FLAG")),
                )
            )
        return result


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

    # ------------------------------------------------------------------
    # Schema-object families
    #
    # One list method per family, one get method where a single object makes
    # sense, each cached under the schema scope with a discriminating key.
    # ------------------------------------------------------------------

    async def list_exceptions(
        self, include_system: bool = False
    ) -> List[FirebirdExceptionInfo]:
        """List the exceptions (named PSQL messages) of this database."""
        key = self._cache.key(
            IntrospectionScope.SCHEMA, extra=f"exceptions:{include_system}"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = self.exception_list_statement(include_system).to_sql()
        result = self.parse_exceptions(await self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    async def get_exception_info(
        self, name: str
    ) -> Optional[FirebirdExceptionInfo]:
        """Return the named exception, or ``None``."""
        found = self._find_by_name(await self.list_exceptions(), name)
        if found is not None:
            return found
        return self._find_by_name(
            await self.list_exceptions(include_system=True), name
        )

    async def list_procedures(
        self, include_system: bool = False, include_source: bool = False
    ) -> List[FirebirdProcedureInfo]:
        """List stored procedures, their signatures and optionally their bodies."""
        key = self._cache.key(
            IntrospectionScope.SCHEMA,
            extra=f"procedures:{include_system}:{include_source}",
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = self.procedure_list_statement(
            include_system, include_source
        ).to_sql()
        result = self.parse_procedures(await self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    async def get_procedure_info(
        self, name: str
    ) -> Optional[FirebirdProcedureInfo]:
        """Return the named procedure, or ``None``."""
        found = self._find_by_name(await self.list_procedures(), name)
        if found is not None:
            return found
        return self._find_by_name(
            await self.list_procedures(include_system=True), name
        )

    async def list_procedure_parameters(
        self, procedure_name: str
    ) -> List[FirebirdProcedureParameterInfo]:
        """List one procedure's parameters, inputs then outputs."""
        key = self._cache.key(
            IntrospectionScope.SCHEMA,
            extra=f"procedure-parameters:{procedure_name}",
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = self.procedure_parameter_statement(procedure_name).to_sql()
        result = self.parse_procedure_parameters(
            await self._executor.execute(sql, params)
        )
        self._cache.set(key, result)
        return result

    async def list_functions(
        self, include_system: bool = False, include_source: bool = False
    ) -> List[FirebirdFunctionInfo]:
        """List functions, PSQL and legacy UDF alike."""
        key = self._cache.key(
            IntrospectionScope.SCHEMA,
            extra=f"functions:{include_system}:{include_source}",
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = self.function_list_statement(
            include_system, include_source
        ).to_sql()
        result = self.parse_functions(await self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    async def get_function_info(self, name: str) -> Optional[FirebirdFunctionInfo]:
        """Return the named function, or ``None``."""
        found = self._find_by_name(await self.list_functions(), name)
        if found is not None:
            return found
        return self._find_by_name(
            await self.list_functions(include_system=True), name
        )

    async def list_function_arguments(
        self, function_name: str
    ) -> List[FirebirdFunctionArgumentInfo]:
        """List one function's arguments, the return slot included."""
        key = self._cache.key(
            IntrospectionScope.SCHEMA, extra=f"function-arguments:{function_name}"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = self.function_argument_statement(function_name).to_sql()
        result = self.parse_function_arguments(
            await self._executor.execute(sql, params)
        )
        self._cache.set(key, result)
        return result

    async def list_constraints(
        self,
        table_name: Optional[str] = None,
        constraint_type: Optional[str] = None,
        include_system: bool = False,
    ) -> List[FirebirdConstraintInfo]:
        """List constraints of every kind, optionally of one table or type."""
        key = self._cache.key(
            IntrospectionScope.TABLE,
            extra=f"constraints:{table_name}:{constraint_type}:{include_system}",
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = self.constraint_list_statement(
            table_name, constraint_type, include_system
        ).to_sql()
        result = self.parse_constraints(await self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    async def list_roles(
        self, include_system: bool = False
    ) -> List[FirebirdRoleInfo]:
        """List roles."""
        key = self._cache.key(
            IntrospectionScope.SCHEMA, extra=f"roles:{include_system}"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = self.role_list_statement(include_system).to_sql()
        result = self.parse_roles(await self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    async def list_privileges(
        self,
        object_name: Optional[str] = None,
        user_name: Optional[str] = None,
        include_system: bool = False,
    ) -> List[FirebirdPrivilegeInfo]:
        """List grants, optionally of one object and/or to one grantee."""
        key = self._cache.key(
            IntrospectionScope.SCHEMA,
            extra=f"privileges:{object_name}:{user_name}:{include_system}",
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = self.privilege_statement(
            object_name, user_name, include_system
        ).to_sql()
        result = self.parse_privileges(await self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    async def list_charsets(self) -> List[FirebirdCharsetInfo]:
        """List character sets."""
        key = self._cache.key(IntrospectionScope.SCHEMA, extra="charsets")
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = self.charset_list_statement().to_sql()
        result = self.parse_charsets(await self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    async def list_collations(
        self, charset_name: Optional[str] = None
    ) -> List[FirebirdCollationInfo]:
        """List collations, optionally of one character set."""
        key = self._cache.key(
            IntrospectionScope.SCHEMA, extra=f"collations:{charset_name}"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = self.collation_list_statement(charset_name).to_sql()
        result = self.parse_collations(await self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    async def list_dependencies(
        self, object_name: Optional[str] = None
    ) -> List[FirebirdDependencyInfo]:
        """List dependency edges, optionally those naming one object."""
        key = self._cache.key(
            IntrospectionScope.SCHEMA, extra=f"dependencies:{object_name}"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = self.dependency_statement(object_name).to_sql()
        result = self.parse_dependencies(await self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    async def list_view_relations(
        self, view_name: Optional[str] = None
    ) -> List[FirebirdViewRelationInfo]:
        """List the relations a view reads, optionally of one view."""
        key = self._cache.key(
            IntrospectionScope.VIEW, extra=f"view-relations:{view_name}"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = self.view_relation_statement(view_name).to_sql()
        result = self.parse_view_relations(await self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    async def list_publications(
        self, include_system: bool = False
    ) -> List[FirebirdPublicationInfo]:
        """List publications (Firebird 4 and later)."""
        key = self._cache.key(
            IntrospectionScope.SCHEMA, extra=f"publications:{include_system}"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = self.publication_list_statement(include_system).to_sql()
        result = self.parse_publications(await self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result
