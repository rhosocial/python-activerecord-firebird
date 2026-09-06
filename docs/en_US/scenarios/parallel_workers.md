# Parallel Workers

## Overview

This section covers Firebird-specific concurrency characteristics and patterns for parallel processing.

## Firebird Concurrency Characteristics

### Multi-Version Concurrency Control (MVCC)

Firebird uses MVCC which provides:

- **Readers don't block writers**: SELECT queries don't lock rows
- **Writers don't block readers**: INSERT/UPDATE/DELETE don't block SELECT
- **Snapshot isolation**: Each transaction sees a consistent snapshot

### Transaction Lifetime

```python
# Long-running transactions may cause issues
backend.transaction.begin()
# Long operation...
backend.transaction.commit()

# Better: Use shorter transactions
backend.transaction.begin()
# Quick operation
backend.transaction.commit()
```

## Concurrent Access Patterns

### Read-Heavy Workloads

```python
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend
from concurrent.futures import ThreadPoolExecutor
import threading

def read_worker(backend, user_id):
    """Worker for read operations."""
    result = backend.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    return result

def parallel_reads(backend, user_ids):
    """Execute parallel reads."""
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(read_worker, backend, uid) for uid in user_ids]
        return [f.result() for f in futures]

# Usage
user_ids = [1, 2, 3, 4, 5]
results = parallel_reads(backend, user_ids)
```

### Write-Heavy Workloads

```python
def write_worker(backend, data):
    """Worker for write operations."""
    backend.transaction.begin()
    try:
        backend.execute(
            "INSERT INTO logs (message, timestamp) VALUES (?, ?)",
            (data['message'], data['timestamp'])
        )
        backend.transaction.commit()
    except Exception as e:
        backend.transaction.rollback()
        raise

def parallel_writes(backend, data_list):
    """Execute parallel writes with proper transaction isolation."""
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(write_worker, backend, data) for data in data_list]
        return [f.result() for f in futures]
```

## Connection Pooling for Workers

### Configure Pool

```python
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

# Configure connection pool for concurrent access
config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    pool_size=10,  # One connection per worker
    pool_timeout=30
)

backend = FirebirdBackend(config=config)
backend.connect()

# Workers will share the connection pool
```

### Pool Monitoring

```python
def monitor_pool(backend):
    """Monitor connection pool usage."""
    print(f"Connected: {backend.is_connected}")
    print(f"Pool size: {backend.config.pool_size}")
```

## FastAPI Integration

### Async Workers

```python
from fastapi import FastAPI, Depends
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

app = FastAPI()

config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey"
)

backend = FirebirdBackend(config=config)

@app.on_event("startup")
async def startup():
    await backend.connect()

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    result = await backend.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    )
    return result

@app.post("/users")
async def create_user(name: str, email: str):
    await backend.execute(
        "INSERT INTO users (name, email) VALUES (?, ?)",
        (name, email)
    )
    return {"status": "created"}
```

## Batch Processing

### Bulk Inserts

```python
def bulk_insert(backend, table, data_list):
    """Insert multiple rows efficiently."""
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

# Usage
data = [
    {"name": f"item_{i}", "value": i * 10}
    for i in range(1000)
]
bulk_insert(backend, "products", data)
```

### Bulk Updates

```python
def bulk_update(backend, table, updates):
    """Update multiple rows efficiently."""
    backend.transaction.begin()
    try:
        for update in updates:
            backend.execute(
                f"UPDATE {table} SET value = ? WHERE id = ?",
                (update['value'], update['id'])
            )
        backend.transaction.commit()
    except Exception as e:
        backend.transaction.rollback()
        raise

# Usage
updates = [
    {"id": i, "value": f"updated_{i}"}
    for i in range(1, 101)
]
bulk_update(backend, "products", updates)
```

## Best Practices

### Use Connection Pooling

```python
# Always use connection pooling for concurrent access
config = FirebirdConnectionConfig(
    pool_size=10,
    pool_timeout=30
)
```

### Keep Transactions Short

```python
# Good: Short transaction
backend.transaction.begin()
backend.execute("INSERT INTO logs (message) VALUES (?)", ("test",))
backend.transaction.commit()

# Bad: Long transaction
backend.transaction.begin()
# Long processing...
backend.transaction.commit()
```

### Handle Errors Gracefully

```python
def safe_worker(backend, data):
    """Worker with error handling."""
    try:
        backend.transaction.begin()
        backend.execute(
            "INSERT INTO logs (message) VALUES (?)",
            (data['message'],)
        )
        backend.transaction.commit()
    except Exception as e:
        backend.transaction.rollback()
        print(f"Error: {e}")
```

### Monitor Performance

```python
import time

def monitor_performance(backend, operations):
    """Monitor operation performance."""
    start_time = time.time()
    for op in operations:
        op()
    end_time = time.time()
    print(f"Total time: {end_time - start_time:.2f}s")
```

## Common Patterns

### Worker Pool

```python
from concurrent.futures import ThreadPoolExecutor
import threading

class WorkerPool:
    def __init__(self, backend, num_workers=5):
        self.backend = backend
        self.num_workers = num_workers
        self.executor = ThreadPoolExecutor(max_workers=num_workers)
    
    def submit(self, func, *args, **kwargs):
        return self.executor.submit(func, *args, **kwargs)
    
    def shutdown(self):
        self.executor.shutdown()
```

### Producer-Consumer

```python
import queue
import threading

def producer(backend, data_queue):
    """Producer thread."""
    for i in range(100):
        data_queue.put({"id": i, "value": f"item_{i}"})

def consumer(backend, data_queue):
    """Consumer thread."""
    while True:
        try:
            data = data_queue.get(timeout=1)
            backend.execute(
                "INSERT INTO products (id, value) VALUES (?, ?)",
                (data['id'], data['value'])
            )
        except queue.Empty:
            break
```

💡 *AI Prompt:* "How do I implement concurrent processing with Firebird?"