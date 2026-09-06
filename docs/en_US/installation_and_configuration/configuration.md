# Connection Configuration

## Basic Configuration

### Configuration Class

```python
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

config = FirebirdConnectionConfig(
    host="localhost",
    port=3050,
    database="/var/lib/firebird/3.0/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey"
)
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `host` | str | `"localhost"` | Firebird server hostname |
| `port` | int | `3050` | Firebird server port |
| `database` | str | None | Database path or connection string |
| `username` | str | None | Database username |
| `password` | str | None | Database password |
| `role` | str | None | SQL role name |
| `charset` | str | `"UTF8"` | Connection character set |
| `page_size` | int | None | Database page size |
| `wire_compression` | bool | `False` | Enable wire compression |
| `use_unicode` | bool | `True` | Use Unicode strings |
| `autocommit` | bool | `False` | Enable autocommit mode |
| `timeout` | int | None | Connection timeout in seconds |

## Connection Strings

### Host:Port Format

```python
config = FirebirdConnectionConfig(
    host="localhost",
    port=3050,
    database="/data/myapp.fdb"
)
```

### Full DSN

```python
# For remote databases
config = FirebirdConnectionConfig(
    database="localhost/3050:/data/myapp.fdb"
)
```

### Embedded Mode

```python
# For embedded Firebird
config = FirebirdConnectionConfig(
    database="/data/myapp.fdb"
)
```

## Environment Variables

### From Environment

```python
config = FirebirdConnectionConfig.from_env()
```

### Environment Variable Mapping

| Environment Variable | Config Option |
|----------------------|---------------|
| `FIREBIRD_HOST` | `host` |
| `FIREBIRD_PORT` | `port` |
| `FIREBIRD_DATABASE` | `database` |
| `FIREBIRD_USERNAME` | `username` |
| `FIREBIRD_PASSWORD` | `password` |
| `FIREBIRD_ROLE` | `role` |
| `FIREBIRD_CHARSET` | `charset` |
| `FIREBIRD_PAGE_SIZE` | `page_size` |
| `FIREBIRD_POOL_SIZE` | `pool_size` |
| `FIREBIRD_POOL_TIMEOUT` | `pool_timeout` |
| `FIREBIRD_AUTOCOMMIT` | `autocommit` |
| `FIREBIRD_WIRE_COMPRESSION` | `wire_compression` |
| `FIREBIRD_TIMEOUT` | `timeout` |

## Advanced Configuration

### Connection Pool

```python
config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    pool_size=5,
    pool_timeout=30
)
```

### SSL/TLS

```python
config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    ssl=True,
    ssl_ca="/path/to/ca.pem",
    ssl_cert="/path/to/client-cert.pem",
    ssl_key="/path/to/client-key.pem"
)
```

### Timezone

```python
config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    timezone="America/New_York"
)
```

## Configuration Validation

### Test Configuration

```python
config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey"
)

# Validate configuration
print(config.to_dict())
```

### Load from File

```python
import json

with open("config.json") as f:
    config_data = json.load(f)

config = FirebirdConnectionConfig(**config_data)
```

💡 *AI Prompt:* "How do I configure Firebird connection pooling for production?"