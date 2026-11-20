# Firebird field types & dialect

## Where the types live

The backend re-exports Firebird-specific `DataType` subclasses from
`rhosocial.activerecord.backend.impl.firebird.types`:

```python
from rhosocial.activerecord.backend.impl.firebird.types import (
    FirebirdDecFloatType,     # DECFLOAT(16|34)   -- Firebird 4+
    FirebirdInt128Type,       # INT128            -- Firebird 4+
    FirebirdTimeTzType,       # TIME WITH TIME ZONE      -- Firebird 4+
    FirebirdTimeStampTzType,  # TIMESTAMP WITH TIME ZONE -- Firebird 4+
    FirebirdBlobType,
    FirebirdArrayType,
    FirebirdDomainType,
)
```

The expression layer also defines `FirebirdCharType` and `FirebirdVarCharType`.

## Numeric and temporal types worth knowing

| Firebird type | Python-side note | Gate |
|---------------|------------------|------|
| `NUMERIC(p, s)` / `DECIMAL(p, s)` | exact decimal; `seconds_between` casts to `NUMERIC(18, 4)` | all |
| `DECFLOAT(16|34)` | exact IEEE 754 decimal with an exponent; a bare `DECFLOAT` means precision 34, the same default the constructor uses | Firebird 4+ |
| `INT128` | signed 128-bit integer, a much wider range than `BIGINT` | Firebird 4+ |
| `BOOLEAN` | native boolean, not a `CHAR(1)` emulated flag | Firebird 3+ |
| `TIME WITH TIME ZONE`, `TIMESTAMP WITH TIME ZONE` | zoned temporal types; plain `TIME` is kept distinct | Firebird 4+ |

`DECFLOAT` is not a binary approximate `FLOAT`. Asking for a precision other than
16 or 34 is a construction error, not a silent fallback.

## BLOB sub-types

Firebird BLOBs are typed by sub-type. `FirebirdBlobType` renders the whole clause:

```python
blob = FirebirdBlobType(sub_type=1, segment_size=16384, character_set="UTF8")
blob.to_sql()
# BLOB SUB_TYPE 1 SEGMENT SIZE 16384 CHARACTER SET UTF8
```

| Sub-type | Meaning |
|----------|---------|
| `0` | binary / unstructured (default) |
| `1` | text with a character set |
| `2` | BLR (compiled database language) |
| `3` | ACL |
| `4` | delta ranges |
| `5` | formatted text |

BLOB columns are not comparable: `MIN`, `MAX` and `COUNT(DISTINCT ...)` are refused
at prepare time. The introspector handles this by projecting `NULL` slots for those
figures; see [Column profiles](../introspection/README.md#column-profiles).

## Arrays

Firebird has true multi-dimensional arrays. `FirebirdArrayType` composes the
declaration:

```python
FirebirdArrayType("INTEGER", dimensions=[5]).to_sql()           # INTEGER[5]
FirebirdArrayType("VARCHAR(30)", dimensions=[3, 4]).to_sql()    # VARCHAR(30)[3 AND 4]
FirebirdArrayType("INTEGER", dimensions=[(1, 10)]).to_sql()     # INTEGER[1:10]
```

## Domains as a type layer

`FirebirdDomainType` renders the body of a `CREATE DOMAIN` declaration — base
type, charset, collation, default, `NOT NULL` and check text:

```python
FirebirdDomainType(
    "VARCHAR(40)", character_set="UTF8", not_null=True,
    default="'unspecified'", check="VALUE <> ''",
).to_sql()
```

A domain is Firebird's reusable type layer, not a user-defined type in the
`CREATE TYPE` sense; standalone types do not exist. See
[Domains, generators and routines](../ddl/domains_generators_routines.md#domains).

## Identity columns and generators

An identity column is Firebird 3+'s `GENERATED ... AS IDENTITY`, backed by a system
generator. The dialect distinguishes it from the generic `AUTO_INCREMENT` marker,
which it refuses rather than rendering SQL the server would not accept. In
introspection output an identity column carries `is_auto_increment=True` plus the
raw identity type and backing generator in `extra`. See
[Columns](../introspection/README.md#columns).

## Nullability and identifier folding

Two rules surprise callers used to other engines:

1. **Firebird has no explicit `NULL` constraint keyword.** Writing `NULL` in DDL is
   rejected; absence of `NOT NULL` is how a nullable column is declared.
2. **Unquoted identifiers fold to upper case** and are then quoted by this dialect.
   A table declared as `orders` lives in the catalogue as `ORDERS`, and a column
   query that passes the lower-case spelling returns an empty list. Read names
   from `list_tables()` before asking about a table, or spell them upper case.

The column introspector reports `nullable` as `NULL_FLAG IS NULL` — Firebird records
nullability by the absence of a flag. See
[Capability gates](../introduction/capability_gates.md) for the version floors behind
these type spellings.
