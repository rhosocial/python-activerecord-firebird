# Migrations on the Firebird backend

> **Scope.** This page assumes the [core Migration System](https://github.com/rhosocial/python-activerecord/tree/main/docs/en_US/migration/README.md)
> is already familiar: versions, directions, `@migration`, `run_migration_group`,
> `MigrationRecordStore`, `named-migration`, and the two authoring APIs. It does **not**
> repeat that material. Everything below is specific to running migrations through **this**
> backend: configuring `firebird-driver`, what Firebird's transactional DDL means for a
> migration run, SQL dialect and server-version gating, and the wiring of both authoring
> styles. Whenever a detail belongs to the system rather than to Firebird, it is left to
> the core chapter.

> ⚠️ **Synchronous only.** `firebird-driver` has no asynchronous API. `AsyncFirebirdBackend`
> is a thread-pool wrapper kept for API-shape parity, and this backend's CLI **refuses**
> `--async` (exit 1). Do not use `run_migration_group_async()` or `AsyncNamedMigration`
> here; every snippet on this page is synchronous. See
> [Async status](../introduction/supported_versions.md#async-status).

## 1. Configuring this backend for migrations

Migrations use the same connection objects as the rest of the backend. Build a
`FirebirdConnectionConfig`, pass it to `FirebirdBackend`, connect, and adapt the dialect
to the server:

```python
from rhosocial.activerecord.backend.impl.firebird.backend import FirebirdBackend
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

config = FirebirdConnectionConfig.from_env()  # FIREBIRD_* environment variables
backend = FirebirdBackend(connection_config=config)
backend.connect()
backend.introspect_and_adapt()  # teach the dialect the server version before rendering gated DDL
```

`FirebirdConnectionConfig.from_env()` reads `FIREBIRD_HOST`, `FIREBIRD_PORT`,
`FIREBIRD_DATABASE`, `FIREBIRD_USERNAME`/`FIREBIRD_USER`, `FIREBIRD_PASSWORD`,
`FIREBIRD_CHARSET`, `FIREBIRD_ROLE` and the pool/SSL settings. An explicit config is
equally valid:

```python
config = FirebirdConnectionConfig(
    database="localhost/3050:/var/lib/firebird/data/test.fdb",
    username="SYSDBA",
    password="masterkey",
    charset="UTF8",
)
```

`introspect_and_adapt()` is the step most often forgotten. This backend's dialect answers
capability questions from the adapted server version; an unadapted dialect declines gated
features rather than guessing a floor. Since DDL rendering consults the same gates, call it
before a migration run — the `named-migration` CLI does this for you. Connection flags and
environment variables are listed in [CLI usage](../cli/README.md) and
[Connection configuration](../installation/configuration.md).

Leave `FirebirdConnectionConfig.autocommit` at its default (`False`) for migration runs;
the transactional behaviour described next depends on statements staying inside a
transaction.

## 2. Transactional DDL and version records

Firebird **does** support transactional DDL. `FirebirdDialect.supports_transactional_ddl()`
returns `True`: `CREATE`, `ALTER` and `DROP` participate in the transaction, so a group of
schema statements can be committed together or rolled back as a unit. If you issue DDL
directly, wrap it with the backend's context manager:

```python
with backend.transaction():
    backend.execute(statement.to_sql()[0], fetch=False)
```

`run_migration_group` manages transactions with its own `TransactionMode.AUTO` default;
the core chapter explains that option, so it is not repeated here. The practical
consequence for this backend is simply that a failed DDL statement does not leave a
half-applied schema — the transaction can be rolled back.

**Version records are outside the database.** The built-in `JSONFileMigrationRecordStore`
writes a JSON file; that write is not part of the Firebird transaction. A DDL rollback
therefore does not roll the record file back — the core library writes a record only after
a successful run, which is what keeps the two in step. Use an absolute, durable path (or a
custom store) and point both UP and DOWN at the same file. Record semantics themselves are
documented in the core chapter.

## 3. SQL dialect, server versions and identifier folding

Three Firebird-specific details change how migration DDL behaves:

- **Database SQL dialect (1 vs 3).** A Firebird database carries its own SQL dialect.
  Dialect 3 is the modern default and the one this backend's dialect, type renderers and
  capability gates are built against. Legacy dialect 1 databases differ in ways that
  matter to migrations — for example `NUMERIC`/`DECIMAL` handling, the absence of dialect-3
  features such as native `BOOLEAN` and identity columns, and different delimited-identifier
  rules. A migration that renders cleanly for dialect 3 may be refused by a dialect 1
  server. If you must touch a legacy dialect 1 database, validate on a copy first and plan
  a conversion to dialect 3; do not assume the generated DDL transfers unchanged.
- **Identifier folding.** Unquoted names fold to upper case and are quoted by this dialect.
  Use one consistent spelling for a table across its create, drop and record versions;
  mixing `widgets` and `WIDGETS` in introspection or cleanup is a common migration bug. See
  [Field types & dialect](../modeling/field_types.md#nullability-and-identifier-folding).
- **Version-gated features.** Prefer expression objects (for example a model's
  `create_table_statement()` passed to `ctx.apply()`) over hand-written SQL text: the
  dialect can then refuse a feature the connected server does not have instead of emitting
  SQL it will reject. Representative gates:

| Feature | Minimum server |
|---------|----------------|
| `DATEDIFF`, transactional DDL | 2.5 / all supported |
| CTE, window functions, `RETURNING`, `BOOLEAN`, identity columns, sequences, `OFFSET/FETCH` | 3.0 |
| `DECFLOAT`, `INT128`, zoned temporal types, `SKIP LOCKED`, publications | 4.0 |

The authoritative lists are in [Supported versions](../introduction/supported_versions.md)
and [Capability gates & fail-fast](../introduction/capability_gates.md).

## 4. Function-style migrations (synchronous)

This is the recommended path. A migration function applies model DDL through
`ctx.apply()`, and `run_migration_group` renders it through this backend's dialect:

```python
from rhosocial.activerecord.backend.migration import (
    migration,
    MigrationDirection,
    run_migration_group,
)
from rhosocial.activerecord.backend.migration.record import JSONFileMigrationRecordStore


@migration("v001_create_widgets", description="create the widgets table")
def create_widgets(ctx):
    if ctx.direction == MigrationDirection.UP:
        ctx.apply(Widget.create_table_statement(backend=ctx.backend))
    else:
        ctx.apply(Widget.drop_table_statement(if_exists=True, backend=ctx.backend))


store = JSONFileMigrationRecordStore("/var/lib/firebird/migration_records.json")
fqn = "myapp.migrations:create_widgets"
preview = run_migration_group(backend, [fqn], dry_run=True)  # renders only; writes nothing
result = run_migration_group(backend, [fqn], record_store=store)
```

Do not reach for the async counterpart of the group runner: on this backend it would only
wrap the same driver calls in an executor. The full, runnable dry-run → UP → DOWN flow is
in [`docs/examples/migration/01_function_migration.py`](../../examples/migration/01_function_migration.py).

## 5. Class-style `NamedMigration` and the `named-migration` CLI (synchronous)

The legacy class API is supported for existing migrations. A class declares a version and
implements `up()`/`down()`; using `ctx.apply()` keeps the DDL inside the Firebird dialect:

```python
from rhosocial.activerecord.backend.migration import (
    NamedMigration,
    MigrationContext,
    MigrationDirection,
    MigrationRunner,
    JSONFileMigrationRecordStore,
)


class V001CreateWidgets(NamedMigration):
    version = "v001_create_widgets"

    def up(self, ctx: MigrationContext) -> None:
        ctx.apply(Widget.create_table_statement(backend=ctx.backend))

    def down(self, ctx: MigrationContext) -> None:
        ctx.apply(Widget.drop_table_statement(if_exists=True, backend=ctx.backend))


runner = MigrationRunner("myapp.migrations.V001CreateWidgets")
result = runner.run(backend, MigrationDirection.UP, record_store=JSONFileMigrationRecordStore("records.json"))
```

The same class can be driven from this backend's CLI. The command builds a `FirebirdBackend`,
connects, calls `introspect_and_adapt()` and dispatches to the shared migration helper:

```bash
python -m rhosocial.activerecord.backend.impl.firebird named-migration \
    myapp.migrations.V001CreateWidgets \
    --database localhost/3050:/var/lib/firebird/data/test.fdb \
    --direction up --record-store ./records.json
```

`--direction down`, `--list`, `--describe`, `--all`, `--single-transaction` and the
`FIREBIRD_*` connection flags/env vars are available; run `--help` for the full set.
Passing `--async` exits 1 with an explanatory error — the official driver has no async
support and the CLI will not pretend otherwise.

> Class-style `--dry-run` only captures SQL emitted through named expressions; `ctx.apply()`
> statements are not included in that summary. For a faithful preview on this backend, use
> the function-style `run_migration_group(dry_run=True)` path. This split is explained in
> the core chapter's dry-run section.

The programmatic and CLI wiring is shown in
[`docs/examples/migration/02_named_migration.py`](../../examples/migration/02_named_migration.py).

## 6. Quick checklist

1. Set `FIREBIRD_*` (or build a `FirebirdConnectionConfig`) and keep `autocommit=False`.
2. Connect with `FirebirdBackend` and call `introspect_and_adapt()` before rendering DDL.
3. Stay synchronous — no `--async`, no async runner, no async migration classes.
4. Render DDL through expression objects/models so version and dialect gates apply.
5. Use one consistent (upper-case) table name spelling; check whether the target database is
   dialect 3.
6. Keep `JSONFileMigrationRecordStore` on a stable absolute path, shared by UP and DOWN.

## 7. Further reading

- [Core Migration System](https://github.com/rhosocial/python-activerecord/tree/main/docs/en_US/migration/README.md) — the system itself: ordering, dependencies, records, dry run, CLI and exceptions.
- [Core migration examples](https://github.com/rhosocial/python-activerecord/tree/main/docs/examples/migration) — additional function-style scenarios.
- [Runnable Firebird migration examples](../../examples/migration/README.md)
- [Transactions and savepoints](../transactions/README.md) — Firebird transaction semantics.
