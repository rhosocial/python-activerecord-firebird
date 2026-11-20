# Migration examples (Firebird backend)

Synchronous examples for running migrations through this backend's classes. The
[migration system itself](https://github.com/rhosocial/python-activerecord/tree/main/docs/en_US/migration/README.md)
belongs to the core library; see the [backend-specific migration guide](../../en_US/migration/README.md)
for configuration, transactional DDL, dialect/version gating and the sync-only rule.

Both scripts need a reachable Firebird database. Connection settings come from the
`FIREBIRD_*` environment variables (see [Test configuration](../../en_US/testing/README.md)).
With no database configured they print setup instructions and exit non-zero — they
never fabricate output.

| Script | Demonstrates |
|--------|--------------|
| [`01_function_migration.py`](01_function_migration.py) | `@migration` + `ctx.apply()` with model DDL rendered by the Firebird dialect; `run_migration_group` dry run → real UP → DOWN with a `JSONFileMigrationRecordStore` |
| [`02_named_migration.py`](02_named_migration.py) | class-style `NamedMigration` using `up()`/`down()` with `ctx.apply()`; programmatic `MigrationRunner` plus the equivalent `named-migration` CLI invocation |

Run from the repository root, for example:

```powershell
$env:FIREBIRD_DATABASE='localhost/3050:/var/lib/firebird/data/test.fdb'
$env:FIREBIRD_USERNAME='SYSDBA'
$env:FIREBIRD_PASSWORD='masterkey'
.venv3.14\Scripts\python.exe docs\examples\migration\01_function_migration.py
.venv3.14\Scripts\python.exe docs\examples\migration\02_named_migration.py
```

No Firebird server is needed to verify syntax:

```bash
python -m py_compile docs/examples/migration/01_function_migration.py docs/examples/migration/02_named_migration.py
```

Both examples are **synchronous only**. `firebird-driver` has no async API, and this
backend's CLI refuses `--async` (exit 1), so there are no async migration examples here.
