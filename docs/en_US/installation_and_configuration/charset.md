# Character Set / Encoding

## Overview

Firebird supports various character sets for data storage and retrieval.

## Configuration

### Setting Character Set

```python
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    charset="UTF8"  # Default character set
)
```

### Common Character Sets

| Charset | Description |
|---------|-------------|
| `UTF8` | Unicode UTF-8 (recommended) |
| `ISO8859_1` | Latin-1 |
| `WIN1252` | Windows Latin-1 |
| `ASCII` | ASCII |
| `UNICODE_FSS` | Unicode Fractional Space Filling |

## Character Set Operations

### Query with Character Set

```sql
-- Specify character set in query
SELECT * FROM users WHERE name = 'Alice' CHARACTER SET UTF8
```

### Column Character Set

```sql
-- Create table with character set
CREATE TABLE users (
    id INTEGER,
    name VARCHAR(100) CHARACTER SET UTF8,
    email VARCHAR(255) CHARACTER SET UTF8
)
```

### BLOB Character Set

```sql
-- Text BLOB with character set
CREATE TABLE documents (
    id INTEGER,
    content BLOB SUB_TYPE TEXT SEGMENT SIZE 16384 CHARACTER SET UTF8
)
```

## Character Set Conversion

### Automatic Conversion

The backend handles character set conversion automatically:

```python
# Data is converted between Python strings and Firebird character set
backend.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))
result = backend.execute("SELECT name FROM users WHERE id = 1")
# result[0][0] is a Python string
```

### Manual Conversion

```python
# Explicit character set conversion
backend.execute("""
    INSERT INTO users (name) 
    VALUES (? CHARACTER SET UTF8)
""", ("Alice",))
```

## Best Practices

### Use UTF-8

```python
# Recommended: Use UTF-8 for maximum compatibility
config = FirebirdConnectionConfig(
    charset="UTF8"
)
```

### Consistent Character Sets

```python
# Ensure consistent character sets across application
config = FirebirdConnectionConfig(
    charset="UTF8"
)

# All operations use the same character set
backend.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))
```

### Character Set Validation

```python
# Validate character set support
try:
    backend.execute("INSERT INTO users (name) VALUES (?)", ("测试",))
except Exception as e:
    print(f"Character set error: {e}")
```

## Troubleshooting

### Common Character Set Issues

1. **Data truncation**
   - Check column length
   - Verify character set supports the data

2. **Conversion errors**
   - Ensure client and server use compatible character sets
   - Check for invalid characters

3. **Display issues**
   - Verify terminal supports the character set
   - Check font support

### Error Messages

```
Invalid character set
```

**Solution**: Check if the character set is supported by Firebird.

```
Character set conversion error
```

**Solution**: Ensure source and target character sets are compatible.

💡 *AI Prompt:* "How do I handle international characters in Firebird?"