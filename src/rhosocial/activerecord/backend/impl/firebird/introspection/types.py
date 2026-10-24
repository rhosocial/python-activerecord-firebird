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


__all__ = ["FirebirdDomainInfo", "FirebirdGeneratorInfo"]
