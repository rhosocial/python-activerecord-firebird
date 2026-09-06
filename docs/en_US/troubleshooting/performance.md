# Performance Issues

## Overview

This section covers performance analysis and optimization for Firebird databases.

## Slow Query Analysis

### Enable Query Logging

```python
import logging

# Enable query logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('rhosocial.activerecord')
logger.setLevel(logging.DEBUG)
```

### Use EXPLAIN

```python
# Analyze query execution plan
result = backend.execute("""
    EXPLAIN SELECT * FROM users 
    WHERE email LIKE '%@example.com' 
    ORDER BY created_at DESC
""")
print(result)
```

### Profile Queries

```python
import time

def profile_query(backend, query, params=None):
    """Profile query execution time."""
    start_time = time.time()
    result = backend.execute(query, params)
    end_time = time.time()
    print(f"Query time: {(end_time - start_time) * 1000:.2f}ms")
    return result
```

## Common Performance Issues

### Missing Indexes

```python
# Check for missing indexes
result = backend.execute("""
    SELECT rdb$relation_name, rdb$field_name
    FROM rdb$relation_fields
    WHERE rdb$relation_name = 'USERS'
    ORDER BY rdb$field_position
""")

# Create appropriate indexes
backend.execute("CREATE INDEX idx_users_email ON users (email)")
backend.execute("CREATE INDEX idx_users_created_at ON users (created_at)")
```

### Large Result Sets

```python
# Use pagination for large result sets
def get_users_page(backend, page=1, per_page=100):
    offset = (page - 1) * per_page
    return backend.execute("""
        SELECT * FROM users 
        ORDER BY id 
        ROWS ? TO ?
    """, (offset + 1, offset + per_page))
```

### Connection Pool Exhaustion

```python
# Monitor connection pool
config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    pool_size=10,  # Increase pool size
    pool_timeout=60  # Increase timeout
)
```

### Lock Conflicts

```python
# Detecting lock conflicts
from rhosocial.activerecord.backend import errors as exc

try:
    backend.transaction.begin()
    # Long-running operation
    backend.transaction.commit()
except exc.LockConflictError as e:
    print(f"Lock conflict detected: {e}")
    backend.transaction.rollback()
```

## Optimization Strategies

### Use Appropriate Isolation

```python
# Use READ COMMITTED for most cases
backend.transaction.begin(isolation_level=IsolationLevel.READ_COMMITTED)

# Use REPEATABLE READ when needed
backend.transaction.begin(isolation_level=IsolationLevel.REPEATABLE_READ)
```

### Keep Transactions Short

```python
# Good: Short transaction
backend.transaction.begin()
backend.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (100, 1))
backend.transaction.commit()

# Bad: Long transaction
backend.transaction.begin()
# Long processing...
backend.transaction.commit()
```

### Use Batch Operations

```python
# Good: Batch insert
def bulk_insert(backend, table, data_list):
    backend.transaction.begin()
    try:
        for data in data_list:
            backend.execute(
                f"INSERT INTO {table} (name, value) VALUES (?, ?)",
                (data['name'], data['value'])
            )
        backend.transaction.commit()
    except Exception as e:
        backend.transaction.rollback()
        raise

# Bad: Individual inserts
for data in data_list:
    backend.execute("INSERT INTO table (name) VALUES (?)", (data['name'],))
```

### Optimize Queries

```python
# Good: Specific columns
backend.execute("SELECT id, name, email FROM users WHERE active = 1")

# Bad: SELECT *
backend.execute("SELECT * FROM users WHERE active = 1")
```

## Monitoring

### Query Statistics

```python
def get_query_stats(backend):
    """Get query statistics."""
    result = backend.execute("""
        SELECT 
            rdb$relation_name,
            rdb$field_name
        FROM rdb$relation_fields
        WHERE rdb$relation_name = 'USERS'
    """)
    return result
```

### Connection Statistics

```python
def get_connection_stats(backend):
    """Get connection statistics."""
    return {
        'is_connected': backend.is_connected,
        'pool_size': backend.config.pool_size,
        'pool_timeout': backend.config.pool_timeout
    }
```

## Performance Tuning

### Database Configuration

```sql
-- Optimize Firebird configuration
-- Edit firebird.conf
```

### Index Optimization

```sql
-- Create covering indexes
CREATE INDEX idx_users_email_name ON users (email) INCLUDE (name)

-- Drop unused indexes
DROP INDEX idx_unused_index
```

### Query Optimization

```python
# Use EXPLAIN to analyze queries
result = backend.execute("EXPLAIN SELECT * FROM users WHERE email = ?", ('test@example.com',))
print(result)
```

## Best Practices

### Monitor Performance

```python
# Regular performance checks
def performance_check(backend):
    # Check slow queries
    result = backend.execute("EXPLAIN SELECT * FROM users")
    print(f"Query plan: {result}")
    
    # Check index usage
    result = backend.execute("""
        SELECT rdb$index_name
        FROM rdb$indices
        WHERE rdb$relation_name = 'USERS'
    """)
    print(f"Indexes: {result}")
```

### Optimize Regularly

```python
# Regular optimization
def optimize_database(backend):
    # Analyze tables
    backend.execute("ANALYZE users")
    
    # Rebuild indexes
    backend.execute("REBUILD INDEX idx_users_email")
```

### Use Connection Pooling

```python
# Always use connection pooling
config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    pool_size=5,
    pool_timeout=30
)
```

💡 *AI Prompt:* "How do I optimize Firebird queries for better performance?"