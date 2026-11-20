# Supported versions

## Firebird server

The dialect's capability probes use **Firebird 3.0 as the practical floor**: CTEs,
window functions, `RETURNING`, `BOOLEAN`, identity columns, sequences and
`OFFSET/FETCH` are all gated at `(3, 0, 0)`. Features introduced later carry their
own gates rather than raising the whole backend's floor:

| Feature | Minimum server |
|---------|----------------|
| `DATEDIFF` (used by `seconds_between`) | 2.5 |
| CTE, window functions, `RETURNING`, `BOOLEAN`, identity columns, sequences, `OFFSET/FETCH` | 3.0 |
| `SKIP LOCKED`, `LATERAL`, `DECFLOAT`, `INT128`, zoned temporal types, publications (`RDB$PUBLICATIONS`) | 4.0 |

`FirebirdDialect(version=(major, minor, patch))` accepts a two- or three-component
version; `version_at_least()` pads both sides before comparing, so `FirebirdDialect((4, 0))`
answers the same as `(4, 0, 0)`. An unadapted dialect answers `False` for a gated
feature — a capability nobody confirmed is not claimed. When connected through the
backend, call `backend.introspect_and_adapt()` before asking version-sensitive
questions (the CLI does this for you).

CI runs against **Firebird 5 and Firebird 6-snapshot** servers (see
[Test configuration](../testing/README.md)). Publication introspection is the one
family with a version gate: the probe answers `True` from Firebird 4.0.0 and
`False` below it.

## Python and packages

- Python `>=3.11` (declared by `pyproject.toml`; classifiers cover 3.11–3.15).
- `firebird-driver>=2.0.0` — the official Python driver, built on the native
  `libfbclient` client library.
- `rhosocial-activerecord>=1.0.0.dev30,<2.0.0` — the core library.

The client library must be installed separately on the host (`libfbclient2` on
Debian/Ubuntu). If it is not on the loader path, set `FIREBIRD_CLIENT_LIBRARY` to
the library file before connecting; the backend passes it to `firebird.driver.fbapi.load_api()`.

## Async status

> ⚠️ **Experimental — not for production.** `firebird-driver` has no asynchronous
> API. `AsyncFirebirdBackend` wraps every driver call in `run_in_executor`, and by
> default all instances share one single-worker executor because `libfbclient` is
> not thread-safe. It exists so the async API shape can be tested; it offers no
> real parallelism and is sensitive to connection storms under load. Prefer
> `FirebirdBackend`. The CLI's `--async` flag is refused for the same reason.
