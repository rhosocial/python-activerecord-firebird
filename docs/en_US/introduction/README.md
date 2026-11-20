# Overview

`rhosocial-activerecord-firebird` is the Firebird backend for the
[rhosocial-activerecord](https://github.com/rhosocial/python-activerecord) framework.
It provides `FirebirdBackend` (synchronous) and the experimental `AsyncFirebirdBackend`,
a `FirebirdConnectionConfig`, a version-aware `FirebirdDialect`, Firebird-specific
expression/DDL types, a transaction manager and a catalogue introspector.

## What the backend adds over the core library

The core library defines the ActiveRecord model, query and migration surfaces. This
backend owns everything that has to be spelled Firebird's way:

- **Connection**: the `firebird-driver` DSN form `host/port:database`, charset `UTF8`,
  SQL role, session timezone, and the `FIREBIRD_*` environment variables.
- **Dialect**: identifier folding (unquoted names are upper-cased and quoted),
  a `LIMIT`/`OFFSET` renderer that switches between `FETCH NEXT ... ROWS ONLY` and
  `ROWS m TO n` by server version, and `supports_*` capability answers keyed to
  `version_at_least()`.
- **Types**: Firebird `BLOB SUB_TYPE`, arrays, `DECFLOAT`, `INT128`,
  `TIME/TIMESTAMP WITH TIME ZONE`, and identity columns backed by system generators.
- **DDL objects**: domains, generators/sequences, PSQL procedures and functions,
  exceptions, roles and packages, with expression classes that render through the
  dialect.
- **Transactions**: native `firebird-driver` begin/commit/rollback, savepoints and
  Firebird isolation-level names (`READ COMMITTED`, `SNAPSHOT`, `SNAPSHOT TABLE STABILITY`).
- **Introspection**: the `RDB$` catalogue and `MON$DATABASE`, plus data families that
  measure the rows themselves. See [Database introspection](../introspection/README.md).
- **`seconds_between`**: signed fractional distance via
  `DATEDIFF(MILLISECOND FROM ... TO ...)`. See [Date/time differences](../querying/seconds_between.md).

## Relationship with the core library

The backend is a `StorageBackend` implementation. Models are configured with the
core `configure()` classmethod, passing a `FirebirdConnectionConfig` and this
backend's class:

```python
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.backend.impl.firebird.backend import FirebirdBackend
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

config = FirebirdConnectionConfig(
    host="localhost",
    port=3050,
    database="/var/lib/firebird/data/test.fdb",
    username="SYSDBA",
    password="masterkey",
)
User.configure(config, FirebirdBackend)
```

The model, field and query API that follows is the core library's; only the
configuration above is Firebird-specific. A complete script is in
[`examples/connection.py`](../../examples/connection.py).

## Sync and async — choose sync

`FirebirdBackend` is the production backend. `AsyncFirebirdBackend` is a
**pseudo-async, experimental** wrapper: `firebird-driver` has no native async API,
so every call is dispatched to a thread pool. It exists for API-shape parity and
tests, not for production use; see
[Supported versions](supported_versions.md#async-status).

## How to read this documentation

Each chapter describes one Firebird-specific surface and links to runnable scripts
under [`examples/`](../../examples/README.md). Capability answers are stated where
the feature is described, and collected in
[Capability gates & fail-fast](capability_gates.md).
