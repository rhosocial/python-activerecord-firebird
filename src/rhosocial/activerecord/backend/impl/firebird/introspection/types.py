# src/rhosocial/activerecord/backend/impl/firebird/introspection/types.py
"""Firebird-specific introspection results.

The core introspection contract describes relations and their parts. Firebird
has two object families the contract cannot describe without inventing a
meaning for them, so each gets its own typed result here rather than being
squeezed into ``IntrospectionTableInfo``/``IntrospectionColumnInfo``:

* **Generators** are Firebird's sequences. The core knows
  ``IntrospectionScope.SEQUENCE`` as a scope, but it has no sequence result
  type; ``FirebirdGeneratorInfo`` is the value that scope caches.
* **Domains** are Firebird's reusable type layer: a domain is a named set of
  type attributes (base type, length, charset, nullability, default, check)
  that columns, arguments and variables are declared from. There is no core
  "user-defined type" result, and a domain is not a table, a column or a
  schema, so ``FirebirdDomainInfo`` states what it actually is.

Both are plain dataclasses so the CLI's existing serializer (``asdict``) and
callers that compare or print them need no special case.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class FirebirdGeneratorInfo:
    """One generator (sequence) and the value it currently holds.

    ``value`` is read with ``GEN_ID(<name>, 0)``, which returns the current
    value without advancing it -- see
    :func:`~..query_nodes.generator_value_sql` for why that is the read.

    ``is_system`` is ``RDB$GENERATORS.RDB$SYSTEM_FLAG``: True for the
    generators Firebird itself owns (identity columns and other internal
    sequences), False for the ones a user created.
    """

    name: str
    value: int
    is_system: bool = False


@dataclass
class FirebirdDomainInfo:
    """One domain: a named, reusable set of type attributes.

    The fields mirror what ``CREATE DOMAIN`` accepts, because that is what a
    caller comparing a declared domain against a live one needs:

    ``base_type``
        The Firebird type as the catalogue records it (``VARCHAR``,
        ``INTEGER``, ``BLOB SUB_TYPE TEXT``, ``DECIMAL`` ...). Firebird
        encodes ``NUMERIC``/``DECIMAL`` as an integer field type plus a
        negative scale, so those two are named from that pair rather than
        being reported as the integer type underneath.

    ``length`` / ``character_length``
        ``RDB$FIELD_LENGTH`` (bytes on disk, which for character types depends
        on the charset's bytes-per-character) and, for character types,
        ``RDB$FIELD_CHARACTER_LENGTH`` (characters a caller may store).

    ``charset``
        The character set's *name*, resolved through ``RDB$CHARACTER_SETS``;
        ``None`` for non-character types, whose charset id is NULL. The id is
        a catalogue key, not something a caller can compare against a declared
        domain.

    ``nullable``
        The negation of ``RDB$FIELDS.RDB$NULL_FLAG`` (Firebird stores
        "not null", not "nullable", so a missing flag means nullable).

    ``default_source`` / ``check_source``
        The ``DEFAULT`` and ``CHECK`` clause text as the catalogue keeps it,
        both read from the domain's own ``RDB$FIELDS`` row
        (``RDB$FIELDS.RDB$DEFAULT_SOURCE`` and
        ``RDB$FIELDS.RDB$VALIDATION_SOURCE``). Firebird keeps a domain's
        default where a column's default also lives, on the same descriptor.
    """

    name: str
    base_type: str
    length: Optional[int] = None
    character_length: Optional[int] = None
    numeric_precision: Optional[int] = None
    numeric_scale: Optional[int] = None
    charset: Optional[str] = None
    nullable: bool = True
    default_source: Optional[str] = None
    check_source: Optional[str] = None
    is_system: bool = False
    description: Optional[str] = None


#: ``RDB$OBJECT_TYPE``/``RDB$DEPENDENT_TYPE`` codes, as ``RDB$TYPES`` lists them
#: on the server. Read from the catalogue rather than from memory: the codes are
#: part of Firebird's on-disk contract, not of any SQL standard.
OBJECT_TYPE_NAMES = {
    0: "RELATION",
    1: "VIEW",
    2: "TRIGGER",
    3: "COMPUTED_FIELD",
    4: "VALIDATION",
    5: "PROCEDURE",
    6: "INDEX_EXPRESSION",
    7: "EXCEPTION",
    8: "USER",
    9: "FIELD",
    10: "INDEX",
    11: "CHARACTER_SET",
    12: "USER_GROUP",
    13: "ROLE",
    14: "GENERATOR",
    15: "UDF",
    16: "BLOB_FILTER",
    17: "COLLATION",
    18: "PACKAGE",
    19: "PACKAGE BODY",
    37: "INDEX_CONDITION",
}


def object_type_name(code: Optional[int]) -> Optional[str]:
    """Translate a catalogue type code, keeping an unknown code visible."""
    if code is None:
        return None
    return OBJECT_TYPE_NAMES.get(code, str(code))


@dataclass
class FirebirdExceptionInfo:
    """One ``RDB$EXCEPTIONS`` row: a named message a PSQL block can raise."""

    name: str
    number: Optional[int] = None
    message: Optional[str] = None
    owner: Optional[str] = None
    is_system: bool = False
    description: Optional[str] = None


@dataclass
class FirebirdProcedureInfo:
    """One stored procedure's signature.

    ``source`` is filled only when the caller asked for it: a PSQL body is a
    blob of arbitrary size and a listing of signatures is a different question.
    """

    name: str
    procedure_id: Optional[int] = None
    inputs: Optional[int] = None
    outputs: Optional[int] = None
    procedure_type: Optional[int] = None
    owner: Optional[str] = None
    valid_blr: Optional[int] = None
    private_flag: Optional[int] = None
    sql_security: Optional[int] = None
    description: Optional[str] = None
    is_system: bool = False
    source: Optional[str] = None


@dataclass
class FirebirdProcedureParameterInfo:
    """One parameter of one procedure.

    ``kind`` is ``"input"`` or ``"output"``: Firebird keeps both in
    ``RDB$PROCEDURE_PARAMETERS`` and tells them apart with ``RDB$PARAMETER_TYPE``.
    """

    name: Optional[str] = None
    position: Optional[int] = None
    kind: Optional[str] = None
    data_type: Optional[str] = None
    character_length: Optional[int] = None
    numeric_precision: Optional[int] = None
    numeric_scale: Optional[int] = None
    nullable: bool = True
    default_source: Optional[str] = None
    description: Optional[str] = None


@dataclass
class FirebirdFunctionInfo:
    """One function, PSQL or legacy UDF.

    ``is_legacy`` says which: a legacy UDF names ``module_name`` and
    ``entrypoint`` and has no PSQL body.
    """

    name: str
    function_type: Optional[int] = None
    is_legacy: bool = False
    is_deterministic: bool = False
    return_argument: Optional[int] = None
    owner: Optional[str] = None
    valid_blr: Optional[int] = None
    engine_name: Optional[str] = None
    module_name: Optional[str] = None
    entrypoint: Optional[str] = None
    private_flag: Optional[int] = None
    sql_security: Optional[int] = None
    description: Optional[str] = None
    is_system: bool = False
    source: Optional[str] = None


@dataclass
class FirebirdFunctionArgumentInfo:
    """One argument (or the return slot) of one function."""

    position: Optional[int] = None
    name: Optional[str] = None
    mechanism: Optional[int] = None
    data_type: Optional[str] = None
    character_length: Optional[int] = None
    numeric_precision: Optional[int] = None
    numeric_scale: Optional[int] = None
    nullable: bool = True
    default_source: Optional[str] = None
    description: Optional[str] = None


@dataclass
class FirebirdConstraintInfo:
    """One row of ``RDB$RELATION_CONSTRAINTS``, with its CHECK text when any.

    Every kind lives here -- ``PRIMARY KEY``, ``UNIQUE``, ``FOREIGN KEY``,
    ``CHECK`` and the ``NOT NULL`` rows Firebird records as constraints. The
    CHECK predicate is the source of the trigger the check relation points at,
    which is why it arrives in the same result instead of a second question.
    """

    name: str
    constraint_type: Optional[str] = None
    table_name: Optional[str] = None
    deferrable: Optional[str] = None
    initially_deferred: Optional[str] = None
    index_name: Optional[str] = None
    check_trigger: Optional[str] = None
    check_source: Optional[str] = None


@dataclass
class FirebirdRoleInfo:
    """One role.

    ``has_system_privileges`` is ``RDB$SYSTEM_PRIVILEGES``: whether the role
    carries system privileges, which no other catalogue column says.
    """

    name: str
    owner: Optional[str] = None
    has_system_privileges: bool = False
    is_system: bool = False
    description: Optional[str] = None


@dataclass
class FirebirdPrivilegeInfo:
    """One grant, from ``RDB$USER_PRIVILEGES``.

    ``privilege`` stays the catalogue's own letter (``S``, ``I``, ``U``, ``D``,
    ``R`` for SQL privileges; other letters for the system privileges Firebird 4
    stores in the same relation). ``grantee_type`` and ``object_type`` are
    translated to names where the catalogue defines them, because a bare number
    is not an answer a caller can act on.
    """

    grantee: Optional[str] = None
    grantee_type: Optional[str] = None
    grantor: Optional[str] = None
    privilege: Optional[str] = None
    grant_option: Optional[int] = None
    object_name: Optional[str] = None
    object_type: Optional[str] = None
    field_name: Optional[str] = None


@dataclass
class FirebirdCharsetInfo:
    """One character set known to this database."""

    name: str
    charset_id: Optional[int] = None
    form_of_use: Optional[str] = None
    number_of_characters: Optional[int] = None
    bytes_per_character: Optional[int] = None
    default_collation: Optional[str] = None
    function_name: Optional[str] = None
    is_system: bool = False
    description: Optional[str] = None


@dataclass
class FirebirdCollationInfo:
    """One collation, with the character set it belongs to."""

    name: str
    charset: Optional[str] = None
    collation_id: Optional[int] = None
    base_collation: Optional[str] = None
    specific_attributes: Optional[str] = None
    function_name: Optional[str] = None
    is_system: bool = False
    description: Optional[str] = None


@dataclass
class FirebirdDependencyInfo:
    """One edge of ``RDB$DEPENDENCIES``.

    One row per edge, in one direction: what depends (``dependent_*``) and what
    it depends on (``depended_on_*``). A caller asking about one object gets the
    edges where it appears on either side.
    """

    dependent_name: Optional[str] = None
    dependent_type: Optional[str] = None
    depended_on_name: Optional[str] = None
    depended_on_type: Optional[str] = None
    field_name: Optional[str] = None


@dataclass
class FirebirdViewRelationInfo:
    """One relation a view reads, with the context its BLR uses for it."""

    view_name: Optional[str] = None
    relation_name: Optional[str] = None
    view_context: Optional[int] = None
    context_name: Optional[str] = None
    context_type: Optional[str] = None


@dataclass
class FirebirdPublicationInfo:
    """One logical-replication publication (Firebird 4 and later)."""

    name: str
    owner: Optional[str] = None
    active: bool = False
    auto_enable: bool = False
    is_system: bool = False


__all__ = [
    "FirebirdCharsetInfo",
    "FirebirdCollationInfo",
    "FirebirdConstraintInfo",
    "FirebirdDependencyInfo",
    "FirebirdDomainInfo",
    "FirebirdExceptionInfo",
    "FirebirdFunctionArgumentInfo",
    "FirebirdFunctionInfo",
    "FirebirdGeneratorInfo",
    "FirebirdProcedureInfo",
    "FirebirdProcedureParameterInfo",
    "FirebirdPublicationInfo",
    "FirebirdPrivilegeInfo",
    "FirebirdRoleInfo",
    "FirebirdViewRelationInfo",
    "OBJECT_TYPE_NAMES",
    "object_type_name",
]
