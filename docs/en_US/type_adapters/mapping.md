# Type Mapping

## Firebird to Python Type Conversion

| Firebird Type | Python Type | Adapter |
|---------------|-------------|---------|
| INTEGER | int | Default |
| BIGINT | int | Default |
| SMALLINT | int | Default |
| FLOAT | float | Default |
| DOUBLE PRECISION | float | Default |
| DECIMAL(p,s) | Decimal | FirebirdDecimalAdapter |
| NUMERIC(p,s) | Decimal | FirebirdDecimalAdapter |
| VARCHAR(n) | str | Default |
| CHAR(n) | str | Default |
| BLOB SUB_TYPE 0 | bytes | FirebirdBlobAdapter |
| BLOB SUB_TYPE 1 | str | FirebirdTextBlobAdapter |
| DATE | date | Default |
| TIME | time | Default |
| TIMESTAMP | datetime | Default |
| BOOLEAN | bool | FirebirdBooleanAdapter |

## Detailed Mapping

### Numeric Types

| Firebird Type | Python Type | Notes |
|---------------|-------------|-------|
| SMALLINT | int | -32,768 to 32,767 |
| INTEGER | int | -2,147,483,648 to 2,147,483,647 |
| BIGINT | int | -9,223,372,036,854,775,808 to 9,223,372,036,854,775,807 |
| FLOAT | float | ~7 decimal digits |
| DOUBLE PRECISION | float | ~15 decimal digits |
| DECIMAL(p,s) | Decimal | Exact precision |
| NUMERIC(p,s) | Decimal | Exact precision |

### String Types

| Firebird Type | Python Type | Notes |
|---------------|-------------|-------|
| VARCHAR(n) | str | Variable length |
| CHAR(n) | str | Fixed length |
| BLOB SUB_TYPE 1 | str | Text BLOB |
| CLOB | str | Character Large Object |

### Binary Types

| Firebird Type | Python Type | Notes |
|---------------|-------------|-------|
| BLOB SUB_TYPE 0 | bytes | Binary BLOB |
| BLOB SUB_TYPE 2-7 | bytes | Application-defined |

### Date/Time Types

| Firebird Type | Python Type | Notes |
|---------------|-------------|-------|
| DATE | date | Calendar date |
| TIME | time | Time of day |
| TIMESTAMP | datetime | Date and time |

### Boolean Type

| Firebird Type | Python Type | Notes |
|---------------|-------------|-------|
| BOOLEAN | bool | TRUE/FALSE (Firebird 3.0+) |

## Type Conversion Examples

### Numeric Conversion

```python
from decimal import Decimal

# Integer
value = 42
db_value = value  # No conversion needed

# Decimal
value = Decimal("123.45")
db_value = value  # No conversion needed

# Float
value = 3.14159
db_value = value  # No conversion needed
```

### String Conversion

```python
# String
value = "Hello, World!"
db_value = value  # No conversion needed

# Unicode
value = "测试"
db_value = value  # No conversion needed
```

### Binary Conversion

```python
# Bytes
value = b"binary data"
db_value = value  # No conversion needed

# bytearray
value = bytearray(b"binary data")
db_value = bytes(value)  # Convert to bytes
```

### Date/Time Conversion

```python
from datetime import date, time, datetime

# Date
value = date(2026, 1, 1)
db_value = value  # No conversion needed

# Time
value = time(14, 30)
db_value = value  # No conversion needed

# Datetime
value = datetime(2026, 1, 1, 14, 30)
db_value = value  # No conversion needed
```

### Boolean Conversion

```python
# Boolean
value = True
db_value = 1  # Converted to integer for Firebird

value = False
db_value = 0  # Converted to integer for Firebird
```

## Custom Type Mapping

### Defining Custom Mappings

```python
from rhosocial.activerecord.backend.type_adapter import SQLTypeAdapter

class CustomEmailAdapter(SQLTypeAdapter):
    @property
    def supported_types(self):
        return {str: [str]}
    
    def to_database(self, value, target_type, options=None):
        if value is None:
            return None
        return value.lower()
    
    def from_database(self, value, target_type, options=None):
        if value is None:
            return None
        return str(value)

# Register custom adapter
FirebirdBackend.register_adapter(CustomEmailAdapter())
```

### Using Custom Mappings

```python
# Custom mapping is used automatically
backend.execute("INSERT INTO users (email) VALUES (?)", ("TEST@EXAMPLE.COM",))
result = backend.execute("SELECT email FROM users WHERE id = 1")
# result[0][0] is "test@example.com"
```

## Type Validation

### Validating Input

```python
def validate_email(value):
    if "@" not in value:
        raise ValueError(f"Invalid email: {value}")
    return value.lower()

# Use in adapter
class EmailAdapter(SQLTypeAdapter):
    def to_database(self, value, target_type, options=None):
        return validate_email(value)
```

### Validating Output

```python
def validate_date(value):
    if value is None:
        return None
    if not isinstance(value, date):
        raise ValueError(f"Invalid date: {value}")
    return value

# Use in adapter
class DateAdapter(SQLTypeAdapter):
    def from_database(self, value, target_type, options=None):
        return validate_date(value)
```

💡 *AI Prompt:* "How do I handle custom data types in Firebird?"