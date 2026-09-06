# Scenarios

## Overview

This section covers common usage scenarios and patterns for the Firebird backend, including concurrency characteristics and best practices.

## Parallel Workers

### Firebird Concurrency Characteristics

Firebird uses Multi-Version Concurrency Control (MVCC) which provides:

- **Readers don't block writers**: SELECT queries don't lock rows
- **Writers don't block readers**: INSERT/UPDATE/DELETE don't block SELECT
- **Snapshot isolation**: Each transaction sees a consistent snapshot

### Concurrent Access Patterns

#### Read-Heavy Workloads

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

#### Write-Heavy Workloads

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

### Connection Pooling for Workers

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

### FastAPI with Firebird

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

## Data Migration

### Migrating Data Between Tables

```python
def migrate_data(backend, source_table, target_table, transform_func):
    """Migrate data from source to target table."""
    # Read source data
    source_data = backend.execute(f"SELECT * FROM {source_table}")
    
    # Transform and insert
    backend.transaction.begin()
    try:
        for row in source_data:
            transformed = transform_func(row)
            backend.execute(
                f"INSERT INTO {target_table} (col1, col2) VALUES (?, ?)",
                (transformed['col1'], transformed['col2'])
            )
        backend.transaction.commit()
    except Exception as e:
        backend.transaction.rollback()
        raise

# Usage
def transform_user(row):
    return {
        'col1': row[1].upper(),  # name to uppercase
        'col2': row[2]           # email unchanged
    }

migrate_data(backend, "users_old", "users_new", transform_user)
```

## Reporting and Analytics

### Complex Aggregation Queries

```python
def get_sales_report(backend, start_date, end_date):
    """Generate sales report with aggregations."""
    return backend.execute("""
        SELECT 
            product_name,
            SUM(quantity) as total_quantity,
            SUM(amount) as total_amount,
            AVG(amount) as avg_amount
        FROM sales
        WHERE sale_date BETWEEN ? AND ?
        GROUP BY product_name
        ORDER BY total_amount DESC
    """, (start_date, end_date))

# Usage
report = get_sales_report(backend, "2026-01-01", "2026-12-31")
```

### Window Functions for Analytics

```python
def get_ranked_products(backend):
    """Get products ranked by sales using window functions."""
    return backend.execute("""
        SELECT 
            product_name,
            total_sales,
            RANK() OVER (ORDER BY total_sales DESC) as sales_rank,
            PERCENT_RANK() OVER (ORDER BY total_sales DESC) as percentile
        FROM (
            SELECT 
                product_name,
                SUM(amount) as total_sales
            FROM sales
            GROUP BY product_name
        ) ranked
        ORDER BY sales_rank
    """)
```

## Error Recovery Patterns

### Retry with Exponential Backoff

```python
import time
from rhosocial.activerecord.backend import errors as exc

def execute_with_retry(backend, operation, max_retries=3, base_delay=0.1):
    """Execute operation with retry logic."""
    for attempt in range(max_retries):
        try:
            return operation()
        except exc.LockConflictError:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
            else:
                raise

# Usage
def insert_operation():
    backend.transaction.begin()
    try:
        backend.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))
        backend.transaction.commit()
    except:
        backend.transaction.rollback()
        raise

execute_with_retry(backend, insert_operation)
```

### Circuit Breaker Pattern

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

💡 *AI Prompt:* "How do I implement idempotent operations with Firebird?"