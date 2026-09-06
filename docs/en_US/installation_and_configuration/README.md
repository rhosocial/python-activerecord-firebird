# Installation & Configuration

## Installation Guide

### Prerequisites

- Python 3.11 or later (including 3.13t/3.14t free-threaded builds)
- Firebird database server (3.0 or later recommended)
- `firebird-driver` Python package

### Installation

Install the Firebird backend using pip:

```bash
pip install rhosocial-activerecord-firebird
```

This will install:
- `rhosocial-activerecord-firebird` package
- `firebird-driver` dependency
- `rhosocial-activerecord` core library

### Optional Dependencies

For connection pooling, install with the pooling extra:

```bash
pip install rhosocial-activerecord-firebird[pooling]
```

This adds `DBUtils` for connection pool support.

### Development Installation

For development or testing:

```bash
pip install rhosocial-activerecord-firebird[dev,test]
```

## Connection Configuration

### Basic Configuration

```python
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

config = FirebirdConnectionConfig(
    host="localhost",
    port=3050,
    database="/var/lib/firebird/3.0/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey"
)

backend = FirebirdBackend(config=config)
backend.connect()
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `host` | str | `"localhost"` | Firebird server hostname |
| `port` | int | `3050` | Firebird server port |
| `database` | str | None | Database path or host:path connection string |
| `username` | str | None | Database username |
| `password` | str | None | Database password |
| `role` | str | None | SQL role name |
| `charset` | str | `"UTF8"` | Connection character set |
| `page_size` | int | None | Database page size |
| `wire_compression` | bool | `False` | Enable wire compression |
| `use_unicode` | bool | `True` | Use Unicode strings |
| `autocommit` | bool | `False` | Enable autocommit mode |
| `timeout` | int | None | Connection timeout in seconds |

### Environment Variables

You can configure the backend using environment variables with the `FIREBIRD_` prefix:

```bash
export FIREBIRD_HOST=localhost
export FIREBIRD_PORT=3050
export FIREBIRD_DATABASE=/data/myapp.fdb
export FIREBIRD_USERNAME=SYSDBA
export FIREBIRD_PASSWORD=masterkey
export FIREBIRD_CHARSET=UTF8
```

Then load from environment:

```python
config = FirebirdConnectionConfig.from_env()
```

## Connection Management

### Single Connection

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

### Connection Pool

For production use, enable connection pooling:

```python
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

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

# Connections are managed automatically
```

### FastAPI Integration

```python
from fastapi import FastAPI
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

@app.on_event("shutdown")
async def shutdown():
    await backend.disconnect()
```

## Character Set / Encoding

### Default Encoding

The Firebird backend uses UTF-8 encoding by default. You can change this:

```python
config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    charset="ISO8859_1"  # Use Latin-1 encoding
)
```

### Common Character Sets

| Charset | Description |
|---------|-------------|
| `UTF8` | Unicode UTF-8 (recommended) |
| `ISO8859_1` | Latin-1 |
| `WIN1252` | Windows Latin-1 |
| `ASCII` | ASCII |

💡 *AI Prompt:* "What character set should I use for international applications?"