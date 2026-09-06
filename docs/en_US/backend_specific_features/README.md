# Firebird Specific Features

## Overview

Firebird provides several unique features that distinguish it from other databases. This section covers Firebird-specific data types, SQL dialect extensions, and special capabilities.

## Field Types

### BLOB Types

Firebird supports multiple BLOB subtypes for different data storage needs:

```python
from rhosocial.activerecord.backend.impl.firebird.types import FirebirdBlobType

# Binary BLOB (SUB_TYPE 0)
binary_blob = FirebirdBlobType(sub_type=0, segment_size=16384)

# Text BLOB (SUB_TYPE 1)
text_blob = FirebirdBlobType(sub_type=1, segment_size=16384, character_set='UTF8')
```

### Array Types

Firebird supports multi-dimensional arrays:

```python
from rhosocial.activerecord.backend.impl.firebird.types import FirebirdArrayType

# 1D array of integers
arr = FirebirdArrayType(base_type='INTEGER', dimensions=[5])

# 2D array of strings
arr = FirebirdArrayType('VARCHAR(30)', dimensions=[3, 4])
```

### Domain Types

Reusable column type definitions:

```python
from rhosocial.activerecord.backend.impl.firebird.types import FirebirdDomainType

# Create a domain for email addresses
email_domain = FirebirdDomainType(
    'VARCHAR(255)',
    not_null=True,
    check="VALUE LIKE '%@%.%'"
)
```

## Dialect Expressions

### EXECUTE BLOCK

Firebird supports anonymous PSQL blocks for complex operations:

```python
# Execute multiple statements in a single block
backend.execute("""
    EXECUTE BLOCK AS
    BEGIN
        INSERT INTO audit_log (action, timestamp) VALUES ('LOGIN', CURRENT_TIMESTAMP);
        UPDATE user_stats SET login_count = login_count + 1 WHERE user_id = 1;
    END
""")
```

### RETURNING Clause

Firebird supports RETURNING for INSERT, UPDATE, and DELETE:

```python
# INSERT with RETURNING
result = backend.execute(
    "INSERT INTO users (name, email) VALUES (?, ?) RETURNING id",
    ("Alice", "alice@example.com")
)

# UPDATE with RETURNING
result = backend.execute(
    "UPDATE users SET name = ? WHERE id = ? RETURNING name, email",
    ("Alice Smith", 1)
)
```

### MERGE Statement

Firebird 2.1+ supports MERGE for upsert operations:

```python
backend.execute("""
    MERGE INTO target_table t
    USING source_table s ON t.id = s.id
    WHEN MATCHED THEN
        UPDATE SET t.name = s.name, t.value = s.value
    WHEN NOT MATCHED THEN
        INSERT (id, name, value) VALUES (s.id, s.name, s.value)
""")
```

### Window Functions

Firebird 3.0+ supports window functions:

```python
backend.execute("""
    SELECT 
        name,
        department,
        salary,
        ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC) as rank
    FROM employees
""")
```

## Indexing

### Standard Indexes

```python
# Create a standard index
backend.execute("CREATE INDEX idx_users_email ON users (email)")

# Create a unique index
backend.execute("CREATE UNIQUE INDEX idx_users_username ON users (username)")
```

### Expression Indexes

Firebird supports expression-based indexes:

```python
# Index on expression
backend.execute("CREATE INDEX idx_users_lower_email ON users (LOWER(email))")
```

## EXPLAIN

### Query Execution Plans

Firebird provides EXPLAIN for query analysis:

```python
# Get execution plan
result = backend.execute("EXPLAIN SELECT * FROM users WHERE email = 'alice@example.com'")
print(result)
```

## Introspection

### Database Metadata

```python
# List all tables
tables = backend.introspect.tables()

# Get table columns
columns = backend.introspect.columns("users")

# Get table indexes
indexes = backend.introspect.indexes("users")
```

## EXECUTE BLOCK

### Anonymous PSQL Blocks

EXECUTE BLOCK allows executing multiple statements as a single unit:

```python
# Complex data manipulation
backend.execute("""
    EXECUTE BLOCK AS
    DECLARE variable total DECIMAL(10,2);
    BEGIN
        SELECT SUM(amount) INTO total FROM orders WHERE user_id = CURRENT_USER_ID;
        INSERT INTO user_reports (user_id, total_orders, report_date)
        VALUES (CURRENT_USER_ID, total, CURRENT_DATE);
    END
""")
```

### Dynamic SQL in EXECUTE BLOCK

```python
# Dynamic SQL with input parameters
backend.execute("""
    EXECUTE BLOCK (user_id INTEGER = ?) AS
    BEGIN
        UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = :user_id;
        INSERT INTO login_history (user_id, login_time) VALUES (:user_id, CURRENT_TIMESTAMP);
    END
""", (1,))
```

💡 *AI Prompt:* "When should I use EXECUTE BLOCK instead of multiple separate queries?"