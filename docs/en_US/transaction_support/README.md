# Transaction Support

## Overview

Firebird provides robust transaction support with multiple isolation levels and savepoint capabilities. The Firebird backend implements a transaction manager that leverages Firebird's native transaction API.

## Transaction Manager API

### Basic Transaction Usage

```python
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend

backend = FirebirdBackend(config=config)
backend.connect()

# Begin transaction
backend.transaction.begin()

try:
    # Perform operations
    backend.execute("INSERT INTO users (name, email) VALUES (?, ?)", 
                    ("Alice", "alice@example.com"))
    backend.execute("UPDATE accounts SET balance = balance - ? WHERE user_id = ?", 
                    (100, 1))
    
    # Commit transaction
    backend.transaction.commit()
except Exception as e:
    # Rollback on error
    backend.transaction.rollback()
    raise
```

### Context Manager

```python
# Using context manager for automatic commit/rollback
with backend.transaction:
    backend.execute("INSERT INTO users (name, email) VALUES (?, ?)", 
                    ("Alice", "alice@example.com"))
    backend.execute("UPDATE accounts SET balance = balance - ? WHERE user_id = ?", 
                    (100, 1))
# Automatically commits if no exception, rolls back if exception occurs
```

## Isolation Levels

Firebird supports four isolation levels:

### Read Committed (Default)

```python
from rhosocial.activerecord.backend.transaction import IsolationLevel

# Read Committed - only sees committed data
backend.transaction.begin(isolation_level=IsolationLevel.READ_COMMITTED)
try:
    # Operations here
    backend.transaction.commit()
except:
    backend.transaction.rollback()
```

### Repeatable Read

```python
# Repeatable Read - consistent view within transaction
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

### Serializable

```python
# Serializable - highest isolation level
backend.transaction.begin(isolation_level=IsolationLevel.SERIALIZABLE)
try:
    # Transactions are fully serialized
    backend.execute("UPDATE accounts SET balance = balance - 100 WHERE user_id = 1")
    backend.execute("UPDATE accounts SET balance = balance + 100 WHERE user_id = 2")
    backend.transaction.commit()
except:
    backend.transaction.rollback()
```

## Savepoint

### Creating Savepoints

```python
# Create savepoint
backend.transaction.begin()
try:
    backend.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))
    
    # Create savepoint
    backend.transaction.savepoint("after_insert")
    
    backend.execute("INSERT INTO orders (user_id, amount) VALUES (?, ?)", (1, 100))
    
    # Rollback to savepoint if needed
    backend.transaction.rollback_savepoint("after_insert")
    
    # Only Alice remains, order is rolled back
    backend.transaction.commit()
except:
    backend.transaction.rollback()
```

### Nested Transactions with Savepoints

```python
# Simulate nested transactions
backend.transaction.begin()
try:
    backend.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))
    
    # Create savepoint for nested operation
    backend.transaction.savepoint("nested")
    try:
        backend.execute("INSERT INTO orders (user_id, amount) VALUES (?, ?)", (1, 100))
        backend.transaction.release_savepoint("nested")
    except:
        backend.transaction.rollback_savepoint("nested")
        # Continue with outer transaction
    
    backend.transaction.commit()
except:
    backend.transaction.rollback()
```

## Deadlock Handling

### Firebird Deadlock Detection

Firebird automatically detects deadlocks and raises error code 335544336 (isc_lock_conflict).

```python
from rhosocial.activerecord.backend import errors as exc

try:
    backend.transaction.begin()
    backend.execute("UPDATE accounts SET balance = balance - 100 WHERE user_id = 1")
    backend.transaction.commit()
except exc.LockConflictError as e:
    # Handle deadlock
    backend.transaction.rollback()
    # Retry logic here
except exc.DatabaseError as e:
    if "lock conflict" in str(e).lower():
        # Handle lock conflict
        backend.transaction.rollback()
```

### Retry Strategy

```python
import time
from rhosocial.activerecord.backend import errors as exc

def execute_with_retry(backend, max_retries=3, delay=0.1):
    for attempt in range(max_retries):
        try:
            backend.transaction.begin()
            # Perform operations
            backend.transaction.commit()
            return True
        except exc.LockConflictError:
            backend.transaction.rollback()
            if attempt < max_retries - 1:
                time.sleep(delay * (2 ** attempt))  # Exponential backoff
            else:
                raise
    return False
```

## Transaction Modes

### Read-Only Transactions

```python
# Read-only transaction for reporting
backend.transaction.begin(mode="read_only")
try:
    result = backend.execute("SELECT * FROM large_table")
    # Process results
    backend.transaction.commit()
except:
    backend.transaction.rollback()
```

### Read-Write Transactions

```python
# Read-write transaction (default)
backend.transaction.begin(mode="read_write")
try:
    backend.execute("INSERT INTO audit_log (action) VALUES (?)", ("login",))
    backend.transaction.commit()
except:
    backend.transaction.rollback()
```

💡 *AI Prompt:* "When should I use REPEATABLE READ vs READ COMMITTED for my application?"