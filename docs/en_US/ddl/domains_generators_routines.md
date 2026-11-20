# Domains, generators and routines

Firebird has a richer schema vocabulary than the portable DDL subset. This backend
models those objects as expression classes that render through the dialect, and
introspects them from the `RDB$` catalogue.

## Domains

A domain is Firebird's reusable type layer: a named base type with an optional
charset, collation, default, `NOT NULL` and `CHECK` clause. Columns can be declared
from a domain instead of repeating that definition.

```sql
CREATE DOMAIN POSITIVE_INT AS INTEGER
  NOT NULL
  CHECK (VALUE > 0);
```

The backend exposes:

- `FirebirdCreateDomainExpression`, `FirebirdAlterDomainExpression`,
  `FirebirdDropDomainExpression` in
  `...firebird.expression.ddl.domain`;
- `FirebirdDomainType` in `...firebird.types`, whose `to_sql()` renders a domain
  body from a base type plus the options described in
  [Field types](../modeling/field_types.md#domains-as-a-type-layer).

The alter expression is strict: an action that does not change anything is refused
rather than rendered as a no-op, and an action whose fields cannot be expressed on
this server is rejected by name. Domains are listed by
`introspector.list_domains()` and `get_domain_info()`;
see [Domains and generators](../introspection/README.md#generators-and-domains).

## Generators and sequences

A generator (also called a sequence) is Firebird's value source. `CREATE GENERATOR`
and `CREATE SEQUENCE` name the same object family. The dialect renders both
`GEN_ID(name, step)` and `NEXT VALUE FOR name`:

```python
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.expression.generator import (
    GenIdExpression, NextValueForExpression,
)

dialect = FirebirdDialect(version=(5, 0, 4))
GenIdExpression(dialect, "ORDER_ID_GEN", step=1)      # GEN_ID(ORDER_ID_GEN, 1)
NextValueForExpression(dialect, "ORDER_ID_GEN")       # NEXT VALUE FOR ORDER_ID_GEN
```

`GEN_ID(name, 0)` **reads** a generator's current value without advancing it; this
is exactly how introspection answers generator values. A generator name cannot be
bound as a parameter, so the reader issues one `GEN_ID` per generator and caches
the result.

On an identity column, Firebird creates a system generator behind the scenes. The
catalogue links them through `RDB$RELATION_FIELDS.RDB$GENERATOR_NAME` (Firebird 3+),
which is how introspection reports `owner_table`, `owner_column` and `identity_type`.

`FirebirdCreateSequenceStatement` lives in `...firebird.expression.ddl.sequence`.
See [Generators and domains](../introspection/README.md#generators-and-domains) for
the listing API and the role of the cache.

## Stored procedures and PSQL functions

Stored routines are written in PSQL and have a `BEGIN ... END` body. The expression
classes are in `...firebird.expression.ddl.routine`:

- `FirebirdCreateProcedureStatement(dialect, name, params=..., returns=..., body=..., mode=...)`
- `FirebirdCreateFunctionStatement(dialect, name, params=..., returns=..., body=..., mode=...)`
- `FirebirdDropRoutineStatement(dialect, name, routine_type="PROCEDURE", mode=...)`
- `FirebirdRoutineMode`: `CREATE`, `CREATE_OR_ALTER`, `RECREATE`, `DROP`.

Procedures are gated at Firebird 2.5 and stored functions at Firebird 3.0. A
routine's parameter list and its body are separate concepts from the routine itself:
introspection offers `list_procedure_parameters()` and `list_function_arguments()`
as their own families, because the catalogue keeps them in separate relations
(inputs first, then outputs; the return slot is included for functions).

## Named exceptions

`CREATE EXCEPTION name 'message'` creates a PSQL exception that routines can raise
with `EXCEPTION name`. `FirebirdCreateExceptionStatement` renders it from
`...firebird.expression.ddl.exception`; the catalogue family is
`list_exceptions()` / `get_exception_info()`.

## Roles, packages and users

The dialect also carries expression/renderer support for roles, packages and user
objects. These are schema or security objects rather than per-table types:
`supports_create_package()` is version-gated, and this backend's introspection does
not offer a `packages` family because `CREATE PACKAGE` was refused on the servers
it measured. See
[Engine objects with no family](../introspection/README.md#engine-objects-with-no-family).

## Executing the DDL

Expression objects render with `.to_sql()`, and the rendered statement can be sent
through the backend:

```python
sql, params = statement.to_sql()
backend.execute(sql, params or (), fetch=False)
```

Because DDL is transactional here, wrap a group of statements in
`with backend.transaction():` when they must all succeed or all be undone. A
complete, runnable example is [`examples/ddl.py`](../../examples/ddl.py).
