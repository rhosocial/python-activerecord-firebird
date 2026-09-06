# BackendGroup and BackendManager (Firebird)

This document describes how to use `BackendGroup` and `BackendManager` with the Firebird backend. For detailed API documentation, refer to the [core library documentation](../../../rhosocial-activerecord/docs/en_US/connection/connection_management.md).

## Backend Group Architecture

`rhosocial-activerecord` follows a namespace package layout: each backend is maintained in its own repository and installs into the `rhosocial.activerecord.backend.impl` namespace. The Firebird backend, for example, lives in `rhosocial.activerecord.backend.impl.firebird`. This design lets multiple backends — SQLite, MySQL, PostgreSQL, Firebird, and others — coexist in the same environment.

`BackendGroup` binds a set of models to a single backend instance (one connection target), while `BackendManager` manages several groups so different modules or tenants can each use their own database. The Firebird backend plugs into this architecture through `FirebirdBackend` and `FirebirdConnectionConfig`.

## Quick Example

```python
from rhosocial.activerecord.connection import BackendGroup
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend, FirebirdConnectionConfig
from rhosocial.activerecord.model import ActiveRecord


class User(ActiveRecord):
    name: str
    email: str


# Using context manager
with BackendGroup(
    name="main",
    models=[User],
    config=FirebirdConnectionConfig(
        host="localhost",
        port=3050,
        database="/var/lib/firebird/3.0/data/myapp.fdb",
        username="SYSDBA",
        password="masterkey",
    ),
    backend_class=FirebirdBackend,
) as group:
    user = User(name="John", email="john@example.com")
    user.save()

# Using multiple groups via BackendManager
from rhosocial.activerecord.connection import BackendManager

manager = BackendManager()
manager.create_group(
    name="main",
    models=[User],
    config=FirebirdConnectionConfig(host="localhost", database="/data/main.fdb"),
    backend_class=FirebirdBackend,
)
manager.create_group(
    name="stats",
    config=FirebirdConnectionConfig(host="localhost", database="/data/stats.fdb"),
    backend_class=FirebirdBackend,
)

main_backend = manager.get_group("main").get_backend()
stats_backend = manager.get_group("stats").get_backend()
```

## Querying with Expressions

Build queries with expression classes instead of raw SQL strings. Use `with_()` to eagerly load related records:

```python
# Eager-load related posts for active users
users = User.query().with_('posts').where(User.c.status == 'active').all()
```

Expressions produce a `(sql, params)` pair through `to_sql()`:

```python
from rhosocial.activerecord.backend.expression import Column, Literal

dialect = backend.dialect
expr = Column(dialect, "status") == Literal(dialect, "active")
sql, params = expr.to_sql()
# sql    -> 'status = ?'
# params -> ('active',)
```

## Firebird-Specific Features

### Connection Pool Configuration

The Firebird backend uses `DBUtils` for connection pooling. Install it with the `pooling` extra and configure the pool fields on `FirebirdConnectionConfig`:

```python
config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    pool_size=5,      # Enable pooling with 5 connections
    pool_timeout=30,  # Seconds to wait for a free connection
)
```

### Character Set and Wire Compression

Firebird connections default to UTF-8. Set `charset`, `use_unicode`, and `wire_compression` on the config as needed:

```python
config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    charset="UTF8",
    use_unicode=True,
    wire_compression=True,
)
```

### Server-Side Services

Firebird databases are commonly run under the `fbguard` service, which supervises `fbserver` and restarts it automatically after a crash. `fbguard` runs server-side; from the backend's perspective the connection is a normal `localhost:3050` TCP link, so no special configuration is required in `FirebirdConnectionConfig`.