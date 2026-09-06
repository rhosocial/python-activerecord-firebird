# Deadlock Handling

## Overview

Firebird automatically detects deadlocks and raises error codes. The backend provides mechanisms for handling and retrying transactions.

## Deadlock Detection

### Firebird Error Codes

| Error Code | Description |
|------------|-------------|
| 335544336 | Lock conflict (isc_lock_conflict) |
| 335544349 | Foreign key violation |
| 335544350 | Primary key violation |

### Handling Deadlocks

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

## Retry Strategies

### Simple Retry

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
                time.sleep(delay)
            else:
                raise
    return False
```

### Exponential Backoff

```python
import time
from rhosocial.activerecord.backend import errors as exc

def execute_with_exponential_backoff(backend, max_retries=3, base_delay=0.1):
    for attempt in range(max_retries):
        try:
            backend.transaction.begin()
            # Perform operations
            backend.transaction.commit()
            return True
        except exc.LockConflictError:
            backend.transaction.rollback()
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
            else:
                raise
    return False
```

### Randomized Backoff

```python
import time
import random
from rhosocial.activerecord.backend import errors as exc

def execute_with_randomized_backoff(backend, max_retries=3, base_delay=0.1):
    for attempt in range(max_retries):
        try:
            backend.transaction.begin()
            # Perform operations
            backend.transaction.commit()
            return True
        except exc.LockConflictError:
            backend.transaction.rollback()
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt) * (0.5 + random.random())
                time.sleep(delay)
            else:
                raise
    return False
```

## Prevention Strategies

### Short Transactions

```python
# Good: Short transaction
backend.transaction.begin()
backend.execute("UPDATE accounts SET balance = balance - 100 WHERE user_id = 1")
backend.transaction.commit()

# Bad: Long transaction
backend.transaction.begin()
# Long operation...
# More operations...
backend.transaction.commit()
```

### Consistent Lock Order

```python
# Good: Consistent order
def transfer_funds(backend, from_id, to_id, amount):
    backend.transaction.begin()
    try:
        # Always lock in same order
        if from_id < to_id:
            backend.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, from_id))
            backend.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, to_id))
        else:
            backend.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, to_id))
            backend.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, from_id))
        backend.transaction.commit()
    except:
        backend.transaction.rollback()
        raise

# Bad: Inconsistent order
def bad_transfer(backend, from_id, to_id, amount):
    backend.transaction.begin()
    backend.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, from_id))
    backend.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, to_id))
    backend.transaction.commit()
```

### Use Lower Isolation

```python
# Use READ COMMITTED when possible
backend.transaction.begin(isolation_level=IsolationLevel.READ_COMMITTED)
try:
    # Operations
    backend.transaction.commit()
except:
    backend.transaction.rollback()
```

## Advanced Patterns

### Circuit Breaker

```python
import time
from rhosocial.activerecord.backend import errors as exc

class CircuitBreaker:
    def __init__(self, failure_threshold=5, reset_timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
    
    def call(self, func, *args, **kwargs):
        if self.state == "open":
            if time.time() - self.last_failure_time > self.reset_timeout:
                self.state = "half-open"
            else:
                raise Exception("Circuit breaker is open")
        
        try:
            result = func(*args, **kwargs)
            if self.state == "half-open":
                self.state = "closed"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = "open"
            raise

# Usage
circuit_breaker = CircuitBreaker()

def safe_operation():
    return circuit_breaker.call(
        lambda: backend.execute("SELECT 1 FROM rdb$database")
    )
```

### Deadlock Detection

```python
import time
from rhosocial.activerecord.backend import errors as exc

def detect_deadlock(backend, operation, timeout=5):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            return operation()
        except exc.LockConflictError:
            if time.time() - start_time >= timeout:
                raise
            time.sleep(0.1)
    raise Exception("Deadlock timeout exceeded")
```

## Monitoring

### Log Deadlocks

```python
import logging
from rhosocial.activerecord.backend import errors as exc

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def log_deadlocks(backend, operation):
    try:
        return operation()
    except exc.LockConflictError as e:
        logger.warning(f"Deadlock detected: {e}")
        raise
```

### Statistics

```python
class DeadlockStats:
    def __init__(self):
        self.total_attempts = 0
        self.deadlocks = 0
        self.successful = 0
    
    def record_attempt(self):
        self.total_attempts += 1
    
    def record_deadlock(self):
        self.deadlocks += 1
    
    def record_success(self):
        self.successful += 1
    
    def get_stats(self):
        return {
            'total_attempts': self.total_attempts,
            'deadlocks': self.deadlocks,
            'successful': self.successful,
            'deadlock_rate': self.deadlocks / self.total_attempts if self.total_attempts > 0 else 0
        }
```

## Best Practices

### Keep Transactions Short

```python
# Good
backend.transaction.begin()
backend.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = 1")
backend.transaction.commit()

# Bad
backend.transaction.begin()
# Long processing...
backend.transaction.commit()
```

### Use Appropriate Isolation

```python
# Use READ COMMITTED when possible
backend.transaction.begin(isolation_level=IsolationLevel.READ_COMMITTED)

# Use REPEATABLE READ when needed
backend.transaction.begin(isolation_level=IsolationLevel.REPEATABLE_READ)
```

### Implement Retry Logic

```python
def robust_operation(backend, operation):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return operation()
        except exc.LockConflictError:
            if attempt < max_retries - 1:
                time.sleep(0.1 * (2 ** attempt))
            else:
                raise
```

💡 *AI Prompt:* "How do I implement retry logic for Firebird deadlocks?"