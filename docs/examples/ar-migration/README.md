# ActiveRecord-layer migration examples — Firebird

Offline (no server) example of Firebird's partition-lifecycle backend
suggestions. The single script instantiates a `FirebirdDialect`, calls all eight
`suggest_partition_*` methods, and prints each suggestion's tri-state
`operations` value. No connection and no `ctx.apply()` are used.

Run from the repository root with `PYTHONPATH=src`:

```bash
python docs/examples/ar-migration/01_partition_build.py
```

| Script | Scenarios |
|---|---|
| `01_partition_build.py` | All eight suggestion points (`build`, `table_drop`, `table_alter`, `add`, `drop`, `split`, `merge`, `retention`) each return `operations is False` |

## Firebird-specific differences

- **No native table partitioning**: Firebird has no `PARTITION BY` storage
  clause and no partition-maintenance verbs. Every capability probe
  (`supports_*_partitioning`, `supports_add_partition`,
  `supports_drop_partition`) is False.
- **Explicit unsupported state**: rather than staying silent, all eight
  `suggest_partition_*` methods return `operations is False`, so callers can
  report partitioning as unavailable. There are no expression nodes to render
  with `expr.to_sql()` and no SQL strings in this example.
- This backend is synchronous only (firebird-driver has no real async), so there
  is no async suggestion counterpart.

For the shared index and the core SQLite examples, see the core repository's
`docs/examples/ar-migration/README.md`.
