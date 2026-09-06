# Introduction

## Firebird Backend Overview

`rhosocial-activerecord-firebird` is the Firebird database backend implementation for the rhosocial-activerecord core library. It provides complete ActiveRecord pattern support, optimized specifically for Firebird database features.

💡 *AI Prompt:* "What makes Firebird different from other databases? What are its key advantages?"

## Synchronous and Asynchronous

The Firebird backend provides both synchronous and asynchronous APIs that are functionally equivalent. The documentation will use synchronous examples throughout, but the asynchronous API usage is identical—just replace method calls with their async equivalents.

For example:

```python
# Synchronous usage
backend = FirebirdBackend(...)
backend.connect()
users = backend.find('User')

# Asynchronous usage
backend = AsyncFirebirdBackend(...)
await backend.connect()
users = await backend.find('User')
```

## Why Named Features?

Named features let you **encode complex configurations as a single name**, avoiding verbose command-line arguments and enabling parameter combinations that cannot be expressed through CLI flags alone.

**Named Connection** — encapsulates all connection parameters:

```bash
# Without named connection: long argument list
rhosocial-activerecord-firebird query \
    --host prod-db.example.com --port 3050 --database /data/myapp.fdb \
    --user SYSDBA --password secret \
    "SELECT * FROM users"

# With named connection: one name holds everything
rhosocial-activerecord-firebird query \
    --named-connection myapp.connections.prod_readonly \
    "SELECT * FROM users"
```

**Named Expression** — encapsulates complex query logic:

```bash
# Without named expression: complex SQL that's hard to shell-escape
rhosocial-activerecord-firebird query \
    "SELECT u.name, COUNT(o.id) as order_count FROM users u LEFT JOIN orders o ON u.id = o.user_id WHERE o.created_at >= '2026-01-01' GROUP BY u.id HAVING COUNT(o.id) > 5 ORDER BY order_count DESC ROWS 20"

# With named expression: one name, typed parameters
rhosocial-activerecord-firebird named-expression \
    myapp.queries.high_value_customers \
    --param since=2026-01-01 --param min_orders=5
```

**Named Procedure** — encapsulates multi-step workflows:

```bash
# Without named procedure: multiple sequential commands
rhosocial-activerecord-firebird query "BEGIN TRANSACTION; ..."
rhosocial-activerecord-firebird query "UPDATE inventory ..."
rhosocial-activerecord-firebird query "INSERT INTO orders ..."
rhosocial-activerecord-firebird query "COMMIT;"

# With named procedure: one command, transaction managed
rhosocial-activerecord-firebird named-procedure \
    myapp.workflows.place_order \
    --param user_id=42 --param product_id=100 --param quantity=3
```

**Named Migration** — encapsulates versioned schema changes with dependencies:

```bash
rhosocial-activerecord-firebird named-migration up add_users_table
rhosocial-activerecord-firebird named-migration down add_users_table
```

| Feature | Benefit |
|---------|---------|
| Named Connection | Store connection config in versionable Python code; share across scripts |
| Named Expression | Encapsulate complex SQL; type-safe parameters; reuse across tools |
| Named Procedure | Multi-query workflows with transaction management; parallel execution |
| Named Migration | Versioned schema changes with dependency tracking; up/down support |

## Quick Links

- **[Relationship with Core Library](./relationship.md)**: Learn how the Firebird backend works with the core library
- **[Supported Versions](./supported_versions.md)**: View supported Firebird, Python, and dependency versions

💡 *AI Prompt:* "What are the important new features in Firebird 4.0 compared to Firebird 3.0?"