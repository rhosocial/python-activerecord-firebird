# Runnable examples

Three scripts using this backend's classes and declarative ActiveRecord models.
They require a reachable Firebird database; connection settings come from
`FIREBIRD_*` environment variables or `tests/config/firebird_scenarios.yaml`.

| Script | Shows |
|--------|-------|
| [`connection.py`](connection.py) | `FirebirdConnectionConfig`, DSN, `ActiveRecord` model, `configure()`, first CRUD |
| [`ddl.py`](ddl.py) | Table DDL plus a domain, a generator and a stored procedure; transactional DDL |
| [`introspection.py`](introspection.py) | Catalogue families (generators, domains, procedures, dependencies) and data families |

Run from the repository root, for example:

```powershell
$env:FIREBIRD_DATABASE='localhost/3050:/var/lib/firebird/data/test.fdb'
$env:FIREBIRD_USERNAME='SYSDBA'
$env:FIREBIRD_PASSWORD='masterkey'
.venv3.14\Scripts\python.exe docs\examples\connection.py
```

All three scripts print setup instructions and exit non-zero when no database is
configured — they never fabricate output. With no database available, syntax can
still be verified with:

```bash
python -m py_compile docs/examples/connection.py docs/examples/ddl.py docs/examples/introspection.py
```

See [Test configuration](../en_US/testing/README.md) for the scenario file format
and environment variables.
