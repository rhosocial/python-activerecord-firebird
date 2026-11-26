# Capability gates & fail-fast

The `FirebirdDialect` answers capability questions through `supports_*` methods.
A `True` means "this SQL renders and the server accepts it"; a `False` means
"do not ask for this here" — the formatter refuses to render rather than emit
statement text the server would reject. It never means "the result was empty".

## Version-keyed answers

Most gates are derived from the adapted server version:

```python
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect

dialect = FirebirdDialect(version=(5, 0, 4))
dialect.supports_window_functions()        # True  (Firebird 3+)
dialect.supports_decfloat()                # True  (Firebird 4+)
dialect.supports_skip_locked()             # True  (Firebird 4+)
```

The same mechanism gates DDL and DML entry points: `supports_create_table()`,
`supports_alter_table()`, `supports_trigger()`, `supports_function()`,
`supports_sequence_object()`, `supports_returning()`, `supports_merge_statement()`,
`supports_execute_block()`, and so on. A few are constant: DDL participates in
transactions (`supports_transactional_ddl()` is `True`), and savepoints are
supported by the transaction manager.

## Function-level gates

`suggest_functions()` returns the SQL-function catalogue: a `FunctionSuggestion`
whose `functions` mapping answers per name, built from version floors.
For example, `datediff` is gated at Firebird 2.5; read
`suggest_functions().functions["datediff"]` before constructing a `seconds_between`
node. See
[Date/time differences](../querying/seconds_between.md#availability).

## Introspection gates

Introspection has its own probe set, described in detail in
[Database introspection](../introspection/README.md#what-firebird-answers):

- twenty-three probes answer `True` unconditionally;
- `supports_table_storage_introspection()` answers `False` unconditionally
  (per-table storage is `gstat` output, not a catalogue question);
- `supports_publication_introspection()` answers `True` from Firebird 4.0.0;
- the four operational families (`unused-indexes`, `table-stats`, `runtime`,
  `index-stats`), DDL extraction, object dependencies, partitions and extensions
  remain `False`.

The CLI consults the same map: a probe answering `False` exits 2 before any query
runs. A `False` result is deliberately different from an empty list — an empty
list says a question was asked and nothing was found.

## Version floors that change spelling

Some features exist on every supported version but are *spelled* differently:

- `seconds_between` always uses `DATEDIFF`; its `NUMERIC(18, 4)` cast exists so
  Firebird 3 client libraries can decode the result.
- The row bound for `value-samples` renders `FETCH NEXT ... ROWS ONLY` from
  Firebird 3 and `ROWS m TO n` before it; this is a renderer decision, not a gate.
- Identifier folding applies everywhere: an unquoted name is upper-cased and
  quoted. Catalogue reads therefore need the catalogue's spelling (see
  [Columns](../introspection/README.md#columns)).
