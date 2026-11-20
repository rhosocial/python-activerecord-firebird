# Transactions and savepoints

Firebird has real ACID transactions. This backend uses the native
`firebird-driver` transaction API directly; there is no emulation and no
degradation to a no-op.

## The transaction manager

`FirebirdTransactionManager` delegates to the underlying connection:

| Operation | Driver call |
|-----------|-------------|
| begin | `connection.begin()` |
| commit | `connection.commit()` |
| rollback | `connection.rollback()` |
| create savepoint | `connection.savepoint(name)` |
| rollback to savepoint | `connection.rollback(savepoint=name)` |

Savepoints are supported (`supports_savepoint()` is `True`), so nested units of
work can be undone independently.

## Using a transaction

The backend exposes a `transaction()` context manager:

```python
from rhosocial.activerecord.backend.impl.firebird.backend import FirebirdBackend
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

backend = FirebirdBackend(connection_config=FirebirdConnectionConfig(
    database="localhost/3050:/var/lib/firebird/data/test.fdb",
    username="SYSDBA", password="masterkey",
))
backend.connect()

with backend.transaction():
    backend.execute("INSERT INTO ORDERS (ID, CODE) VALUES (1, 'A')", fetch=False)
    backend.execute("INSERT INTO ORDERS (ID, CODE) VALUES (2, 'B')", fetch=False)
# committed on exit; an exception rolls back
```

The manager itself also implements `__enter__`/`__exit__`: entering begins a
transaction, a normal exit commits (falling back to rollback if the commit fails),
and an exception exits by rolling back.

## Isolation levels

Core `IsolationLevel` values map to Firebird's own names:

| Core level | Firebird name |
|------------|---------------|
| `READ_UNCOMMITTED` | `READ COMMITTED` (Firebird has no dirty read) |
| `READ_COMMITTED` | `READ COMMITTED` |
| `REPEATABLE_READ` | `SNAPSHOT` |
| `SERIALIZABLE` | `SNAPSHOT TABLE STABILITY` |

The dialect exposes `supports_snapshot_isolation()` and
`supports_table_stability()` for these levels, plus `supports_wait_option()` and
`supports_lock_timeout()` for conflict handling. `WAIT` / `NO WAIT` spellings are
only rendered when the dialect answers `True` for the wait option; asking for a
conflict clause the dialect refuses raises rather than emitting it.

## DDL in transactions

`supports_transactional_ddl()` is `True`: `CREATE`, `ALTER` and `DROP` statements
participate in the transaction. A failed migration can therefore be rolled back
as a unit, which is why the DDL example groups its statements inside a transaction.
See [DDL](../ddl/README.md).

## Async note

`AsyncFirebirdTransactionManager` mirrors the synchronous API, but the async
backend itself is experimental and pseudo-async (thread-pool wrapped). Do not rely
on it for production transaction semantics; use `FirebirdBackend`. See
[Async status](../introduction/supported_versions.md#async-status).
