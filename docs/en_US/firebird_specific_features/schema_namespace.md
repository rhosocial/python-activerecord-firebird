# Firebird Schema Namespaces

**Firebird has no schema support in this backend.** Any attempt to qualify a name raises
`UnsupportedFeatureError` rather than quietly rendering an unqualified one.

That makes this page short, and it is worth reading precisely because the refusal is
deliberate: the alternative — dropping the namespace and returning SQL that names a
different object than the caller asked for — is the failure mode the rest of this backend
avoids everywhere else.

For the rules every backend shares, read the
[core guide](https://github.com/rhosocial/python-activerecord/tree/docs/docs/modeling/schema_namespace.md).

## What happens when you qualify a name

The dialect satisfies the `SchemaSupport` protocol structurally, so the qualification path
is wired up, and its capability probe reports the truth:

```python
from rhosocial.activerecord.backend.dialect.protocols import SchemaSupport

isinstance(dialect, SchemaSupport)   # True  -- the path is connected
dialect.supports_schema()            # False -- and it has no namespace to offer
```

The probe is what the render path consults, so a qualified name is refused:

```python
from rhosocial.activerecord.backend.expression.core import TableExpression

TableExpression(dialect, "t").to_sql()[0]
# "T"

TableExpression(dialect, "t", schema_name="app").to_sql()[0]
# UnsupportedFeatureError
```

```
UnsupportedFeatureError: 'Firebird' dialect does not support a schema-qualified
reference. Suggestion: Firebird has no namespace to qualify into, so
schema_name='app' cannot be used. TableExpression would render it as a name this
backend rejects.
```

Columns refuse it the same way:

```python
from rhosocial.activerecord.backend.expression.core import Column

Column(dialect, "id", table="t").to_sql()[0]
# "T"."ID"

Column(dialect, "id", table="t", schema_name="app").to_sql()[0]
# UnsupportedFeatureError
```

So does an index whose table you tried to qualify:

```python
CreateIndexExpression(
    dialect, "idx_t_id",
    TableExpression(dialect, "t", schema_name="app"),   # refused here
    ["id"],
).to_sql()[0]
# UnsupportedFeatureError
```

An unqualified index is fine:

```python
CreateIndexExpression(dialect, "idx_t_id", TableExpression(dialect, "t"), ["id"]).to_sql()[0]
# CREATE INDEX "IDX_T_ID" ON "T" ("ID")
```

## No schema DDL either

```
dialect.supports_create_schema()   # False
dialect.supports_drop_schema()     # False
```

Qualifying is refused and creating a namespace is not implemented — the two facts have the
same root, so neither is available.

## The table-name rule still applies

The absence of schemas does not relax how a table is named. Statements still take a
`TableExpression`, and a bare string is refused:

```python
CreateTableExpression(dialect, "t", columns)   # TypeError
DropTableExpression(dialect, "t")              # TypeError
TruncateExpression(dialect, "t")               # TypeError
AlterTableExpression(dialect, "t", actions)    # TypeError
InsertExpression(dialect, "t", source)         # TypeError
DeleteExpression(dialect, "t")                 # TypeError
```

```
TypeError: table must be a TableExpression, got str
```

This is the one part of the schema contract that is identical across every backend, and it
holds here for a plain reason: the rule is about naming a table unambiguously, not about
namespaces.

## Case folding

Unquoted identifiers are folded to upper case, which is the server's rule rather than the
library's:

```python
TableExpression(dialect, "t").to_sql()[0]   # "T", not "t"
Column(dialect, "id", table="t").to_sql()[0] # "T"."ID"
```

Pass `name_need_quote=False` and friends when you need the case preserved as written.

## Quick reference

| Written | Result |
|---|---|
| `TableExpression(d, "t")` | `"T"` |
| `Column(d, "id", table="t")` | `"T"."ID"` |
| `CreateTableExpression(d, "t", cols)` | `TypeError` |
| `TableExpression(d, "t", schema_name="app")` | `UnsupportedFeatureError` |
| `Column(d, "id", table="t", schema_name="app")` | `UnsupportedFeatureError` |
