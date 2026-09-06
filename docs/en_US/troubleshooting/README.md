# Troubleshooting

## Connection Errors

### Common Connection Issues

#### Error: Connection refused

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

#### Error: Unable to complete network request

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

#### Error: Cannot attach to database

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

#### Error: Login mismatch

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

### Automatic Recovery

The backend includes automatic reconnection for transient errors:

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

## Performance Issues

### Slow Query Analysis

#### Enable Query Logging

```python
import logging

# Enable query logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('rhosocial.activerecord')
logger.setLevel(logging.DEBUG)
```

#### Use EXPLAIN

```python
# Analyze query execution plan
result = backend.execute("""
    EXPLAIN SELECT * FROM users 
    WHERE email LIKE '%@example.com' 
    ORDER BY created_at DESC
""")
print(result)
```

### Common Performance Issues

#### Missing Indexes

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

#### Large Result Sets

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

#### Connection Pool Exhaustion

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

#### Detecting Lock Conflicts

```python
from rhosocial.activerecord.backend import errors as exc

try:
    backend.transaction.begin()
    # Long-running operation
    backend.transaction.commit()
except exc.LockConflictError as e:
    print(f"Lock conflict detected: {e}")
    backend.transaction.rollback()
```

#### Reducing Lock Conflicts

```python
# Use shorter transactions
backend.transaction.begin()
try:
    # Quick operations only
    backend.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (100, 1))
    backend.transaction.commit()
except:
    backend.transaction.rollback()

# Use explicit locking when needed
backend.execute("""
    SELECT * FROM accounts 
    WHERE id = 1 
    WITH LOCK
""")
```

## SQL Standard Compliance

### Firebird SQL Dialect

Firebird uses SQL dialect 3 by default. Some SQL standard features differ:

```python
# Firebird uses double quotes for identifiers
backend.execute('SELECT * FROM "users" WHERE "email" = ?', ('test@example.com',))

# String concatenation uses ||
backend.execute("SELECT first_name || ' ' || last_name AS full_name FROM users")

# Boolean values use 1/0 or TRUE/FALSE (Firebird 3.0+)
backend.execute("SELECT * FROM users WHERE active = TRUE")
```

### Date/Time Functions

```python
# Firebird date functions
backend.execute("SELECT CURRENT_DATE FROM rdb$database")
backend.execute("SELECT CURRENT_TIMESTAMP FROM rdb$database")
backend.execute("SELECT CAST('2026-01-01' AS DATE) FROM rdb$database")
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

💡 *AI Prompt:* "How do I troubleshoot Firebird connection timeout issues?"