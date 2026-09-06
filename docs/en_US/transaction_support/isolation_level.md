# Isolation Levels

## Overview

Firebird supports four transaction isolation levels with different concurrency and consistency guarantees.

## Isolation Levels

### Read Committed (Default)

```python
from rhosocial.activerecord.backend.transaction import IsolationLevel

# Only sees committed data
backend.transaction.begin(isolation_level=IsolationLevel.READ_COMMITTED)
try:
    # Operations here
    backend.transaction.commit()
except:
    backend.transaction.rollback()
```

**Characteristics:**
- Reads only committed data
- Non-repeatable reads possible
- Phantom reads possible
- Default for most databases

### Repeatable Read

```python
# Consistent view within transaction
backend.transaction.begin(isolation_level=IsolationLevel.REPEATABLE_READ)
try:
    # All reads see consistent snapshot
    result1 = backend.execute("SELECT * FROM users WHERE id = 1")
    # Even if another transaction modifies users, result1 remains consistent
    result2 = backend.execute("SELECT * FROM users WHERE id = 1")
    # result1 == result2
    backend.transaction.commit()
except:
    backend.transaction.rollback()
```

**Characteristics:**
- Consistent reads within transaction
- No non-repeatable reads
- Phantom reads possible
- Higher overhead than READ COMMITTED

### Serializable

```python
# Highest isolation level
backend.transaction.begin(isolation_level=IsolationLevel.SERIALIZABLE)
try:
    # Transactions are fully serialized
    backend.execute("UPDATE accounts SET balance = balance - 100 WHERE user_id = 1")
    backend.execute("UPDATE accounts SET balance = balance + 100 WHERE user_id = 2")
    backend.transaction.commit()
except:
    backend.transaction.rollback()
```

**Characteristics:**
- Fully serialized transactions
- No phantom reads
- Highest overhead
- May reduce concurrency

## Choosing Isolation Levels

### Use READ COMMITTED When:

- Reading mostly committed data
- Non-repeatable reads are acceptable
- Performance is critical

### Use REPEATABLE READ When:

- Consistent reads are required
- Multiple reads of same data must be identical
- Financial transactions

### Use SERIALIZABLE When:

- Complete isolation is required
- Data consistency is critical
- Audit trails

## Firebird-Specific Behavior

### Transaction lifetime

In Firebird, transaction isolation is affected by transaction lifetime:

```python
# Long-running transaction may cause issues
backend.transaction.begin()
# Long operation...
backend.transaction.commit()

# Better: Use shorter transactions
backend.transaction.begin()
# Quick operation
backend.transaction.commit()
```

### Record Versioning

Firebird uses MVCC with record versioning:

```python
# Each transaction sees its own snapshot
backend.transaction.begin()
result = backend.execute("SELECT * FROM users")
# Result is based on transaction start time
backend.transaction.commit()
```

## Python Examples

### Read Committed Example

```python
def read_committed_example(backend):
    # Transaction 1
    backend.transaction.begin()
    backend.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))
    # Not visible to other transactions yet
    
    # Transaction 2 (concurrent)
    backend.transaction.begin()
    result = backend.execute("SELECT * FROM users")
    # Alice is NOT visible (not committed)
    backend.transaction.commit()
    
    # Commit Transaction 1
    backend.transaction.commit()
    
    # Transaction 3
    backend.transaction.begin()
    result = backend.execute("SELECT * FROM users")
    # Alice IS visible (committed)
    backend.transaction.commit()
```

### Repeatable Read Example

```python
def repeatable_read_example(backend):
    backend.transaction.begin(isolation_level=IsolationLevel.REPEATABLE_READ)
    
    # First read
    result1 = backend.execute("SELECT * FROM users WHERE id = 1")
    
    # Another transaction updates the row
    # (this would be a separate backend instance)
    
    # Second read - same result
    result2 = backend.execute("SELECT * FROM users WHERE id = 1")
    assert result1 == result2
    
    backend.transaction.commit()
```

## Best Practices

### Keep Transactions Short

```python
# Good: Short transaction
backend.transaction.begin()
backend.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = 1")
backend.transaction.commit()

# Bad: Long transaction
backend.transaction.begin()
# Long operation...
# More operations...
backend.transaction.commit()
```

### Choose Appropriate Isolation

```python
# For read-only reports
backend.transaction.begin(isolation_level=IsolationLevel.READ_COMMITTED)

# For financial transactions
backend.transaction.begin(isolation_level=IsolationLevel.REPEATABLE_READ)

# For critical consistency
backend.transaction.begin(isolation_level=IsolationLevel.SERIALIZABLE)
```

💡 *AI Prompt:* "When should I use REPEATABLE READ vs READ COMMITTED for my application?"