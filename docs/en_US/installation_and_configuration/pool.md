# Connection Management

## Overview

The Firebird backend supports connection pooling for efficient resource management.

## Single Connection

### Basic Usage

```python
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey"
)

backend = FirebirdBackend(config=config)
backend.connect()

# Use the connection
try:
    result = backend.execute("SELECT * FROM users")
    # Process results
finally:
    backend.disconnect()
```

## Connection Pool

### Enabling Pooling

```python
config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    pool_size=5,  # Enable pooling with 5 connections
    pool_timeout=30
)

backend = FirebirdBackend(config=config)
backend.connect()
```

### Pool Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `pool_size` | int | 0 | Number of connections in pool (0 = disabled) |
| `pool_timeout` | int | 30 | Timeout for getting connection from pool |
| `pool_recycle` | int | 3600 | Recycle connections after this many seconds |

### Pool Usage

```python
# Connections are automatically managed
backend = FirebirdBackend(config=config)
backend.connect()

# Multiple operations use pool connections
for i in range(10):
    result = backend.execute("SELECT * FROM users WHERE id = ?", (i,))
    # Connection is returned to pool after each operation

backend.disconnect()
```

## FastAPI Integration

### Application Setup

```python
from fastapi import FastAPI
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

app = FastAPI()

config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    pool_size=10
)

backend = FirebirdBackend(config=config)

@app.on_event("startup")
async def startup():
    await backend.connect()

@app.on_event("shutdown")
async def shutdown():
    await backend.disconnect()

@app.get("/users")
async def get_users():
    result = await backend.execute("SELECT * FROM users")
    return result
```

## Connection Lifecycle

### Connect/Disconnect

```python
# Explicit connection management
backend = FirebirdBackend(config=config)
backend.connect()

# Use connection
result = backend.execute("SELECT 1 FROM rdb$database")

# Cleanup
backend.disconnect()
```

### Automatic Reconnection

```python
# Backend handles reconnection on connection loss
try:
    backend.execute("SELECT * FROM users")
except ConnectionError:
    # Backend will attempt reconnection
    backend.execute("SELECT * FROM users")
```

## Best Practices

### Connection Timeout

```python
config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    timeout=30  # 30 second timeout
)
```

### Connection Validation

```python
# Test connection before use
if backend.is_connected:
    result = backend.execute("SELECT 1 FROM rdb$database")
else:
    backend.connect()
    result = backend.execute("SELECT 1 FROM rdb$database")
```

### Resource Cleanup

```python
# Always disconnect when done
try:
    backend.connect()
    # Use backend
finally:
    backend.disconnect()
```

💡 *AI Prompt:* "How do I manage Firebird connections in a multi-threaded application?"