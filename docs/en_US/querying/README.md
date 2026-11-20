# Querying

Query construction belongs to the core library. The Firebird-specific parts of the
query surface are:

- **[Date/time differences: `seconds_between`](seconds_between.md)** — signed,
  fractional elapsed seconds from `DATEDIFF(MILLISECOND FROM ... TO ...)`, with a
  `NUMERIC(18, 4)` cast for old client libraries.

Other dialect spellings worth remembering, all described where they matter:

- identifier folding: unquoted names are upper-cased and quoted — see
  [Field types & dialect](../modeling/field_types.md#nullability-and-identifier-folding);
- the row limit renders as `FETCH NEXT ... ROWS ONLY` (Firebird 3+) or
  `ROWS m TO n` (earlier) — see
  [Capability gates](../introduction/capability_gates.md#version-floors-that-change-spelling);
- a projection without a table uses `RDB$DATABASE`, the one-row relation — see
  [Join coverage](../introspection/README.md#join-coverage);
- signed fractional arithmetic must multiply by `0.001`, never divide by `1000.0` —
  see [Spelling](seconds_between.md#spelling).
