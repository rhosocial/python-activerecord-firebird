# DDL

Portable table DDL (`create_table`, `drop_table`, column and constraint statements)
is supplied by the core library and rendered through `FirebirdDialect`. This
chapter covers the DDL objects that exist only in Firebird:

- [Domains, generators and routines](domains_generators_routines.md) — reusable
  domains, generators/sequences, `GEN_ID`/`NEXT VALUE FOR`, stored procedures,
  PSQL functions and named exceptions.

Two facts shape Firebird DDL:

- **DDL participates in transactions** — `supports_transactional_ddl()` is `True`,
  so a `CREATE`/`ALTER`/`DROP` can be rolled back. See
  [Transactions](../transactions/README.md).
- **There is no explicit `NULL` constraint.** A nullable column is written by
  omitting `NOT NULL`; the token `NULL` is rejected by the server.

A runnable script that creates a domain, a generator and a stored procedure
alongside a declarative model is in [`examples/ddl.py`](../../examples/ddl.py).
