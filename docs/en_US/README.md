# rhosocial-activerecord Firebird Backend Documentation

> 🤖 **AI Learning Assistant**: Key concepts in this documentation are marked with 💡 AI prompt markers. When you encounter a concept you don't understand, you can ask the AI assistant directly.
>
> **Example:** "How does the Firebird backend render `seconds_between`? Why is async not recommended for production?"
>
> 📖 **See also**: [Core library documentation](https://github.com/rhosocial/python-activerecord/tree/main/docs/en_US)

The Firebird backend is the Firebird database backend implementation for
[rhosocial-activerecord](https://github.com/rhosocial/python-activerecord). It uses
the official `firebird-driver` package and speaks Firebird's own SQL dialect:
domains, generators/sequences, PSQL procedures and functions, the `RDB$` catalogue,
`GEN_ID`/`NEXT VALUE FOR`, `DATEDIFF`, and Firebird transaction semantics.

This documentation covers **only what is specific to this backend**. It does not
restate the core library's ActiveRecord, query or migration documentation.

> ⚠️ **Async is experimental.** `firebird-driver` has no native asynchronous API.
> `AsyncFirebirdBackend` is a thread-pool wrapper kept for API-shape parity and is
> **not recommended for production**. Use the synchronous `FirebirdBackend` for
> production workloads. See [Supported versions](introduction/supported_versions.md).

## Table of Contents

1. **[Introduction](introduction/README.md)**
     * **[Overview](introduction/README.md)**: what this backend is, how it relates to the core library
     * **[Supported versions](introduction/supported_versions.md)**: Firebird 3+, Python 3.11–3.15, driver requirements
     * **[Capability gates & fail-fast](introduction/capability_gates.md)**: the `supports_*` probes, version floors and what is refused

2. **[Installation](installation/README.md)**
     * **[Installation guide](installation/installation.md)**: pip install, client library, dependency notes
     * **[Connection configuration](installation/configuration.md)**: DSN forms, environment variables, charset, role, timezone

3. **[Modeling](modeling/README.md)**
     * **[Firebird field types & dialect](modeling/field_types.md)**: BLOB sub-types, arrays, `DECFLOAT`, `INT128`, zoned temporal types, identity columns, identifier folding and nullability

4. **[Querying](querying/README.md)**
     * **[Date/time differences: `seconds_between`](querying/seconds_between.md)**: signed, fractional `DATEDIFF(MILLISECOND, ...)` spelling and its cast

5. **[DDL](ddl/README.md)**
     * **[Domains, generators and routines](ddl/domains_generators_routines.md)**: reusable domains, generators/sequences, `GEN_ID`/`NEXT VALUE FOR`, stored procedures, PSQL functions, exceptions

6. **[Transactions](transactions/README.md)**
     * **[Transactions and savepoints](transactions/README.md)**: transaction manager, isolation-level mapping, `WAIT`/`NO WAIT`, savepoints, transactional DDL

7. **[Introspection](introspection/README.md)**
     * **[Database introspection](introspection/README.md)**: the `RDB$` catalogue families, generators/domains/routines, dependency edges, data families, CLI introspect types and capability gates

8. **[Command Line](cli/README.md)**
     * **[CLI usage](cli/README.md)**: `python -m rhosocial.activerecord.backend.impl.firebird`

9. **[Testing](testing/README.md)**
     * **[Test configuration](testing/README.md)**: scenario YAML, environment variables, CI matrix, local targeted runs

10. **[Runnable examples](../examples/README.md)**
     * **[connection.py](../examples/connection.py)**: config + declarative model + first CRUD
     * **[ddl.py](../examples/ddl.py)**: table DDL plus a domain, generator and stored procedure
     * **[introspection.py](../examples/introspection.py)**: catalogue and data families

---

> 📖 **Core Library Documentation**: To learn about the complete functionality of the ActiveRecord framework, refer to the [rhosocial-activerecord documentation](https://github.com/rhosocial/python-activerecord/tree/main/docs/en_US).

> 📦 **Dependency note**: this backend requires `rhosocial-activerecord>=1.0.0.dev30,<2.0.0` and
> `firebird-driver>=2.0.0`. Until the required core version is published, install both
> from source (see [Installation guide](installation/installation.md)).
