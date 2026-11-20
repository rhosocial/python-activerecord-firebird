# CLI usage

The backend ships a command-line surface:

```bash
python -m rhosocial.activerecord.backend.impl.firebird <command> [options]
```

Run with `--help` for the full option set of any command.

## Commands

| Command | Purpose |
|---------|---------|
| `info` | Server/connection information |
| `query` | Execute SQL and print results |
| `introspect` | Read the catalogue and data families (see below) |
| `status` | Backend/driver status, including offline checks |
| `named-expression` | Manage named expressions |
| `named-procedure` | Manage named procedures |
| `named-procedure-graph` | Inspect the named-procedure dependency graph |
| `named-migration` | Manage named migrations |
| `named-connection` | Manage named connections |

Shell examples for the `named-*` commands live in the package's `examples/cli/bash/`
directory.

## Introspection command

```bash
python -m rhosocial.activerecord.backend.impl.firebird introspect tables \
  --database /path/to/test_db
```

`--database` is required; connection parameters otherwise come from flags or the
environment. The `--async` flag exists for API-shape parity and is **refused**
(exit 1): `firebird-driver` has no async support and the CLI will not silently
degrade to a synchronous run that looks asynchronous. Output formats are `table`
(default), `json`, `csv` and `tsv`.

Connection flags and environment variables:

| Flag | Environment variable | Description |
|------|---------------------|-------------|
| `--host` | `FIREBIRD_HOST` | Host (default `localhost`) |
| `--port` | `FIREBIRD_PORT` | Port (default 3050) |
| `--database` | `FIREBIRD_DATABASE` | Database path (required) |
| `--user` | `FIREBIRD_USER` | Username |
| `--password` | `FIREBIRD_PASSWORD` | Password |
| `--charset` | `FIREBIRD_CHARSET` | Connection charset (default `UTF8`) |
| `--role` | `FIREBIRD_ROLE` | SQL role |
| `--ssl` | `FIREBIRD_SSL` | SSL mode |

The introspection command adapts the dialect before applying its capability gate:
a type whose probe answers `False` exits 2 without running a query, and a name a
type cannot use is also refused rather than ignored. The complete list of the
twenty-nine introspect types, their flags and their capability probes is in
[Command Line Introspection](../introspection/README.md#command-line-introspection).
