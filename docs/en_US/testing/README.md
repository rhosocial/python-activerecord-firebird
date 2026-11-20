# Test configuration

## What the suite needs

Tests run against **real Firebird servers**, not against rendered SQL strings.
Each test leg needs:

- a reachable Firebird server (CI uses 5 and 6-snapshot);
- the native `libfbclient2` client library;
- `rhosocial-activerecord` and `rhosocial-activerecord-testsuite` installed from the
  local/matching branches rather than from published packages;
- a scenario configuration telling the fixtures which database to use.

## Scenario configuration

The fixtures read `tests/config/firebird_scenarios.yaml`. Each scenario names one
server and one existing base database file:

```yaml
scenarios:
  firebird_5:
    host: firebird-5.n.rho.im
    port: 3050
    database: /var/lib/firebird/data/test_db
    username: SYSDBA
    password: password
    charset: UTF8
    autocommit: false
    timezone: UTC
```

Point at a different file with `FIREBIRD_SCENARIOS_CONFIG_PATH`. The examples under
[`examples/`](../../examples/README.md) use the same resolution order: that
environment variable, then the repository's scenario file, then `FIREBIRD_*`
environment variables (`FIREBIRD_HOST`, `FIREBIRD_PORT`, `FIREBIRD_DATABASE`,
`FIREBIRD_USERNAME`, `FIREBIRD_PASSWORD`, …). With no server configured they print
instructions and exit non-zero; they never invent results.

## CI matrix

`.github/workflows/test.yml` starts a `firebirdsql/firebird` container per leg and
runs the whole `tests/` tree with `pytest -n auto`:

| Python | Firebird |
|--------|----------|
| 3.11 | 5 |
| 3.12 | 6-snapshot |
| 3.13 | 5 |
| 3.14 | 6-snapshot |
| 3.15 | 6-snapshot (GIL only; no free-threaded driver wheel) |

Two limits worth remembering when reading test results:

- there is no Firebird 4 or earlier leg, so the `publications` gate's `False`
  branch is pinned by unit tests against a simulated version, while its `True`
  branch runs live;
- declined introspection families have no statement to run, so their correctness
  is the `False` answer itself and the CLI tests pin the refusal.

## Local runs

Keep local runs targeted — the suite is too large to execute in full locally.
For a single module or case:

```powershell
$env:PYTHONPATH='tests'
.venv3.14\Scripts\python.exe -m pytest tests/rhosocial/activerecord_firebird_test/feature/backend/construct/mixins/test_ddl_source_mixin.py -q
```

Install the test tools into the project virtual environment first:

```bash
pip install -e ".[test,dev]"
pip install -e ../python-activerecord-testsuite
```

The testsuite must be installed from the local checkout: the bare package name in
the extras can pull an older published release that lacks modules this backend
imports. `PYTHONPATH=tests` is needed so the provider registry is importable.

## Examples as smoke tests

The scripts in [`examples/`](../../examples/README.md) are not part of `pytest`,
but they are runnable against the same scenario configuration. They create and
drop their own objects where needed and are useful for checking a new server or
client-library installation. They verify with `python -m py_compile` when no server
is available, which checks syntax without a database.
