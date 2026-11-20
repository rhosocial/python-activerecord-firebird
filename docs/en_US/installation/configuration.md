# Connection configuration

## The config object

`FirebirdConnectionConfig` extends the core `ConnectionConfig` with Firebird
options. The default port is **3050** and the default charset is **UTF8**.

```python
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

config = FirebirdConnectionConfig(
    host="localhost",
    port=3050,
    database="/var/lib/firebird/data/test.fdb",
    username="SYSDBA",
    password="masterkey",
    charset="UTF8",
)
```

| Option | Default | Meaning |
|--------|---------|---------|
| `host` | — | Server host; empty means a local/embedded-style path |
| `port` | `3050` | Server port |
| `database` | `None` | Database path or full connection string |
| `username` / `password` | `None` | Credentials (`user` is accepted as an alias by the backend) |
| `role` | `None` | SQL role assigned to the session |
| `charset` | `"UTF8"` | Connection character set |
| `timezone` | `None` | Passed as `session_time_zone` |
| `page_size` | `None` | Page size option retained in config |
| `wire_compression` | `False` | Wire compression option |
| `use_unicode` | `True` | Unicode string handling |
| `autocommit` | `False` | Autocommit flag |
| `timeout` | `None` | Connection timeout |

The class also inherits the core pool, SSL, charset, timezone, version and
logging mixins.

## DSN construction

`FirebirdBackend.connect()` builds the DSN from the config:

- if `host`, `port` and `database` are all set → `host/port:database`;
- if only `database` is set → `database` is passed verbatim (a local path or a
  full `host/port:path` string you supply yourself);
- with no `database` a `ConnectionError` is raised.

Both forms are shown below:

```python
FirebirdConnectionConfig(
    host="db.example.com", port=3050,
    database="/var/lib/firebird/data/app.fdb",
)  # -> db.example.com/3050:/var/lib/firebird/data/app.fdb

FirebirdConnectionConfig(database="localhost/3050:/var/lib/firebird/data/app.fdb")
```

## Environment variables

`FirebirdConnectionConfig.from_env(prefix="FIREBIRD_")` reads:

| Variable | Config key |
|----------|------------|
| `FIREBIRD_HOST` | `host` |
| `FIREBIRD_PORT` | `port` |
| `FIREBIRD_DATABASE` | `database` |
| `FIREBIRD_USERNAME` | `username` |
| `FIREBIRD_PASSWORD` | `password` |
| `FIREBIRD_ROLE` | `role` |
| `FIREBIRD_CHARSET` | `charset` |
| `FIREBIRD_PAGE_SIZE` | `page_size` |
| `FIREBIRD_POOL_SIZE` / `FIREBIRD_POOL_TIMEOUT` | pool options |
| `FIREBIRD_AUTOCOMMIT` | `autocommit` |
| `FIREBIRD_WIRE_COMPRESSION` | `wire_compression` |
| `FIREBIRD_TIMEOUT` | `timeout` |

Integer and boolean values are coerced; booleans accept `true`, `yes`, `1`, `on`.

```python
config = FirebirdConnectionConfig.from_env()
```

> The CLI introspection command uses a slightly different vocabulary —
> `FIREBIRD_USER` for the user and the same `FIREBIRD_*` names for the rest. See
> [CLI usage](../cli/README.md) and the environment-variable table in
> [Database introspection](../introspection/README.md#command-line-introspection).

## Connecting a model

```python
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.backend.impl.firebird.backend import FirebirdBackend

User.configure(config, FirebirdBackend)
```

Adapting the dialect to the connected server is optional for ordinary CRUD but
required before version-sensitive capability questions (publications, for
example): call `backend.introspect_and_adapt()`. The CLI does this before its
capability gate. See [Capability gates](../introduction/capability_gates.md).
