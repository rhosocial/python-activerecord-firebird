# Custom Data Types

## Overview

Custom data types allow you to define new DataType subclasses for custom column types.

## Creating Custom Data Types

### Basic Data Type

```python
from rhosocial.activerecord.backend.data_type import DataType

class FirebirdJSONType(DataType):
    """Firebird JSON type using BLOB SUB_TYPE 1."""
    
    def __init__(self, charset="UTF8"):
        self.charset = charset
    
    def to_sql(self):
        return f"BLOB SUB_TYPE 1 SEGMENT SIZE 16384 CHARACTER SET {self.charset}"
    
    def to_python(self, value):
        if value is None:
            return None
        import json
        if isinstance(value, bytes):
            value = value.decode(self.charset)
        return json.loads(value)
    
    def to_database(self, value):
        if value is None:
            return None
        import json
        return json.dumps(value).encode(self.charset)

# Usage in model
class Document(ActiveRecord):
    __table_name__ = "documents"
    id: int
    metadata: FirebirdJSONType = FirebirdJSONType()
```

### Domain Type

```python
class FirebirdEmailDomain(DataType):
    """Email domain type with validation."""
    
    def to_sql(self):
        return "VARCHAR(255) NOT NULL CHECK (VALUE LIKE '%@%.%')"
    
    def to_python(self, value):
        if value is None:
            return None
        if "@" not in value:
            raise ValueError(f"Invalid email: {value}")
        return value.lower()
    
    def to_database(self, value):
        if value is None:
            return None
        return value.lower()

# Usage
class User(ActiveRecord):
    __table_name__ = "users"
    id: int
    email: FirebirdEmailDomain
```

### Array Type

```python
class FirebirdArrayDataType(DataType):
    """Firebird array type."""
    
    def __init__(self, base_type, dimensions):
        self.base_type = base_type
        self.dimensions = dimensions
    
    def to_sql(self):
        dim_strs = []
        for dim in self.dimensions:
            if isinstance(dim, tuple):
                dim_strs.append(f"{dim[0]}:{dim[1]}")
            else:
                dim_strs.append(str(dim))
        return f"{self.base_type}[{' AND '.join(dim_strs)}]"
    
    def to_python(self, value):
        if value is None:
            return None
        return value
    
    def to_database(self, value):
        if value is None:
            return None
        return value

# Usage
class Product(ActiveRecord):
    __table_name__ = "products"
    id: int
    tags: FirebirdArrayDataType = FirebirdArrayDataType('VARCHAR(50)', [10])
```

## Type Conversion

### to_sql Method

```python
class CustomDataType(DataType):
    def to_sql(self):
        """Return SQL type definition."""
        return "VARCHAR(255)"
```

### to_python Method

```python
class CustomDataType(DataType):
    def to_python(self, value):
        """Convert database value to Python value."""
        if value is None:
            return None
        return str(value).lower()
```

### to_database Method

```python
class CustomDataType(DataType):
    def to_database(self, value):
        """Convert Python value to database value."""
        if value is None:
            return None
        return str(value).upper()
```

## Using Custom Types

### In Models

```python
from rhosocial.activerecord.model import ActiveRecord

class User(ActiveRecord):
    __table_name__ = "users"
    id: int
    email: FirebirdEmailDomain
    metadata: FirebirdJSONType = FirebirdJSONType()

# Create user
user = User(email="TEST@EXAMPLE.COM", metadata={"key": "value"})
user.save()
# email is stored as "test@example.com"
# metadata is stored as JSON string
```

### In Queries

```python
from rhosocial.activerecord.backend.expression import Column
from rhosocial.activerecord.backend.expression.core import Literal
from rhosocial.activerecord.backend.expression.operators import BinaryExpression

# Query with custom type using expression
expr = BinaryExpression(dialect, "=", Column(dialect, "email"), Literal(dialect, "test@example.com"))
user = User.query().where(expr).one()
sql, params = expr.to_sql()
# sql: "email" = %s
# params: ('test@example.com',)
print(user.email)  # "test@example.com"
print(user.metadata)  # {"key": "value"}
```

## Type Validation

### Validating Input

```python
class ValidatingDataType(DataType):
    def to_database(self, value):
        if value is None:
            return None
        # Validate before storing
        if not isinstance(value, str):
            raise ValueError(f"Expected string, got {type(value)}")
        return value.lower()
```

### Validating Output

```python
class ValidatingDataType(DataType):
    def to_python(self, value):
        if value is None:
            return None
        # Validate when reading
        if not isinstance(value, str):
            raise ValueError(f"Expected string, got {type(value)}")
        return value.lower()
```

## Best Practices

### Keep Types Simple

```python
# Good: Simple, focused type
class SimpleType(DataType):
    def to_sql(self):
        return "VARCHAR(255)"
    
    def to_python(self, value):
        return value.lower() if value else None

# Avoid: Overly complex type
class ComplexType(DataType):
    def to_sql(self):
        # Too much logic
```

### Handle None Values

```python
# Good: Always handle None
class SafeType(DataType):
    def to_python(self, value):
        if value is None:
            return None
        return value.lower()

# Avoid: Not handling None
class UnsafeType(DataType):
    def to_python(self, value):
        return value.lower()  # Will fail if value is None
```

### Validate Input

```python
# Good: Validate input
class ValidatingType(DataType):
    def to_database(self, value):
        if value is None:
            return None
        if "@" not in value:
            raise ValueError(f"Invalid email: {value}")
        return value.lower()

# Avoid: No validation
class UnvalidatingType(DataType):
    def to_database(self, value):
        return value.lower()  # No validation
```

💡 *AI Prompt:* "How do I create a custom data type for Firebird arrays?"