# rhosocial-activerecord Firebird Backend Documentation

The Firebird backend is the Firebird implementation for
[rhosocial-activerecord](https://github.com/rhosocial/python-activerecord). It uses the
`firebird-driver` package and gates features on the connected server's version, because
Firebird has added capabilities across releases rather than all at once.

## Table of Contents

- **[Schema Namespaces](firebird_specific_features/schema_namespace.md)**: why Firebird refuses
  a qualified name instead of dropping the namespace, and the table-naming rule that still
  applies

## Key facts at a glance

| Question | Answer |
|---|---|
| Schema support | None — a qualified name raises `UnsupportedFeatureError` |
| `supports_schema()` | `False` |
| Unqualified table renders as | `"T"` |
| Unqualified column renders as | `"T"."ID"` |
| `CREATE SCHEMA` / `DROP SCHEMA` | Not implemented by this backend |
| Identifier case | Folded to upper case unless you ask otherwise |
| Table arguments | Still `TableExpression` only; a bare string raises `TypeError` |

## Related documentation

- **[Schema Namespaces (core guide)](https://github.com/rhosocial/python-activerecord/tree/docs/docs/modeling/schema_namespace.md)**:
  the dialect-independent rules that every backend shares

---

> ⚠️ **Dependency note**: this backend depends on the core library
> `rhosocial-activerecord`. Install it together with the core library rather than
> independently.
