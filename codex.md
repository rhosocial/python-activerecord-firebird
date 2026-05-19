# rhosocial-activerecord-firebird

Firebird backend for rhosocial-activerecord. Uses `firebird-driver`.

## Architecture

- `FirebirdBackend` extends `StorageBackend` + mixins
- `FirebirdDialect` extends `SQLDialectBase` + all feature mixins
- `FirebirdConnectionConfig` extends `ConnectionConfig` with host/port/database/user/password
- Type adapters in `adapters.py`

## Key SQL Differences

- Identifier quoting: double quotes
- Parameter placeholder: ?
- RETURNING clause supported
- UPSERT via UPDATE OR INSERT ... MATCHING
- Sequences via CREATE SEQUENCE / GEN_ID
- Transactions: SET TRANSACTION ISOLATION LEVEL
- Pagination: ROWS m TO n