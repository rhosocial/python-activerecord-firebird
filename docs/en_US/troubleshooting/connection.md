# Connection Errors

## Overview

This section covers common connection errors and their solutions.

## Common Connection Issues

### Error: Connection refused

```
Error: Connection refused
```

**Causes:**
- Firebird server not running
- Wrong host or port
- Firewall blocking connection

**Solutions:**

```bash
# Check if Firebird is running
sudo systemctl status firebird3.0

# Test connection with isql
isql-fb -user SYSDBA -password masterkey -host localhost -port 3050

# Check firewall
sudo ufw status
sudo ufw allow 3050/tcp
```

### Error: Unable to complete network request

```
Error: Unable to complete network request to host "localhost"
```

**Causes:**
- Wrong port number
- Network configuration issue
- Firebird not listening on network interface

**Solutions:**

```python
# Verify configuration
config = FirebirdConnectionConfig(
    host="localhost",  # or IP address
    port=3050,         # default Firebird port
    database="/data/myapp.fdb"
)

# Check Firebird configuration
# Edit /etc/firebird/3.0/firebird.conf
# Ensure RemoteServiceName = gds_db (port 3050)
```

### Error: Cannot attach to database

```
Error: Cannot attach to database file "/data/myapp.fdb"
```

**Causes:**
- Database file doesn't exist
- Wrong permissions
- Database path incorrect

**Solutions:**

```bash
# Check database file exists
ls -la /data/myapp.fdb

# Check permissions
sudo chown firebird:firebird /data/myapp.fdb
sudo chmod 660 /data/myapp.fdb

# Create database if needed
isql-fb -user SYSDBA -password masterkey
> CREATE DATABASE '/data/myapp.fdb';
> EXIT;
```

### Error: Login mismatch

```
Error: login mismatch
```

**Causes:**
- Wrong username or password
- User doesn't exist
- Authentication method mismatch

**Solutions:**

```bash
# Reset SYSDBA password
isql-fb -user SYSDBA -password masterkey
> ALTER USER SYSDBA SET PASSWORD 'new_password';
> EXIT;

# Create new user
isql-fb -user SYSDBA -password masterkey
> CREATE USER app_user PASSWORD 'app_password';
> EXIT;
```

## Automatic Recovery

### Connection Retry

```python
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    pool_size=5,
    pool_timeout=30
)

backend = FirebirdBackend(config=config)

# Backend will attempt automatic reconnection on connection loss
try:
    backend.connect()
    # Use backend
except Exception as e:
    # Handle permanent failures
    print(f"Connection failed: {e}")
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

## Error Codes

### Common Firebird Error Codes

| Error Code | Description | Solution |
|------------|-------------|----------|
| 335544336 | Lock conflict | Retry transaction or use shorter transactions |
| 335544349 | Foreign key violation | Check referenced table |
| 335544350 | Primary key violation | Check for duplicate key |
| 335544558 | Connection rejected | Check Firebird server status |
| 335544569 | Cannot attach to database | Check database path and permissions |

### Error Handling

```python
from rhosocial.activerecord.backend import errors as exc

try:
    backend.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")
except exc.IntegrityError as e:
    print(f"Integrity error: {e}")
except exc.DatabaseError as e:
    print(f"Database error: {e}")
except exc.ConnectionError as e:
    print(f"Connection error: {e}")
```

## Troubleshooting Steps

### 1. Check Server Status

```bash
# Check if Firebird is running
sudo systemctl status firebird3.0

# Check port
netstat -tlnp | grep 3050
```

### 2. Verify Configuration

```python
# Print configuration
print(config.to_dict())
```

### 3. Test Connection

```python
# Simple connection test
try:
    backend.connect()
    print("Connection successful!")
except Exception as e:
    print(f"Connection failed: {e}")
finally:
    backend.disconnect()
```

### 4. Check Logs

```bash
# Check Firebird logs
tail -f /var/log/firebird3.0/*.log
```

## Prevention

### Use Connection Pooling

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

### Set Timeouts

```python
config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    timeout=30
)
```

### Handle Errors Gracefully

```python
try:
    backend.execute("SELECT * FROM users")
except exc.ConnectionError:
    backend.connect()
    backend.execute("SELECT * FROM users")
```

💡 *AI Prompt:* "How do I troubleshoot Firebird connection timeout issues?"