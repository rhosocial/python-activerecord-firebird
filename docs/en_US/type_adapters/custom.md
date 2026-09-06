# Custom Adapters

## Overview

Custom type adapters allow you to define how Python types are converted to and from Firebird database types.

## Creating Custom Adapters

### Basic Adapter

```python
from rhosocial.activerecord.backend.type_adapter import SQLTypeAdapter
from typing import Any, Dict, List, Type, Optional

class CustomEmailAdapter(SQLTypeAdapter):
    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {str: [str]}
    
    def to_database(self, value: Any, target_type: Type, options: Optional[Dict] = None) -> Any:
        if value is None:
            return None
        # Validate email format
        if "@" not in value:
            raise ValueError(f"Invalid email format: {value}")
        return value.lower()
    
    def from_database(self, value: Any, target_type: Type, options: Optional[Dict] = None) -> Optional[str]:
        if value is None:
            return None
        return str(value)
```

### Adapter with Options

```python
class FirebirdCurrencyAdapter(SQLTypeAdapter):
    def __init__(self, decimal_places=2):
        self.decimal_places = decimal_places
    
    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {Decimal: [Decimal, float, int, str]}
    
    def to_database(self, value: Any, target_type: Type, options: Optional[Dict] = None) -> Any:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            value = Decimal(str(value))
        return round(value, self.decimal_places)
    
    def from_database(self, value: Any, target_type: Type, options: Optional[Dict] = None) -> Optional[Decimal]:
        if value is None:
            return None
        return Decimal(str(value))
```

## Registering Adapters

### Global Registration

```python
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend

# Register globally
FirebirdBackend.register_adapter(CustomEmailAdapter())
FirebirdBackend.register_adapter(FirebirdCurrencyAdapter(decimal_places=4))
```

### Instance Registration

```python
# Register for specific backend instance
backend = FirebirdBackend(config=config)
backend.register_adapter(CustomEmailAdapter())
```

## Adapter Examples

### Phone Number Adapter

```python
class PhoneNumberAdapter(SQLTypeAdapter):
    @property
    def supported_types(self):
        return {str: [str]}
    
    def to_database(self, value, target_type, options=None):
        if value is None:
            return None
        # Remove non-digit characters
        digits = ''.join(filter(str.isdigit, value))
        return f"+{digits}"
    
    def from_database(self, value, target_type, options=None):
        if value is None:
            return None
        # Remove formatting
        return ''.join(filter(str.isdigit, value))
```

### JSON Adapter

```python
import json

class JSONAdapter(SQLTypeAdapter):
    @property
    def supported_types(self):
        return {dict: [dict, list]}
    
    def to_database(self, value, target_type, options=None):
        if value is None:
            return None
        return json.dumps(value)
    
    def from_database(self, value, target_type, options=None):
        if value is None:
            return None
        if isinstance(value, str):
            return json.loads(value)
        return value
```

### UUID Adapter

```python
from uuid import UUID

class UUIDAdapter(SQLTypeAdapter):
    @property
    def supported_types(self):
        return {UUID: [UUID, str]}
    
    def to_database(self, value, target_type, options=None):
        if value is None:
            return None
        if isinstance(value, str):
            value = UUID(value)
        return str(value)
    
    def from_database(self, value, target_type, options=None):
        if value is None:
            return None
        return UUID(value)
```

### Enum Adapter

```python
import enum

class EnumAdapter(SQLTypeAdapter):
    def __init__(self, enum_class):
        self.enum_class = enum_class
    
    @property
    def supported_types(self):
        return {self.enum_class: [self.enum_class, str, int]}
    
    def to_database(self, value, target_type, options=None):
        if value is None:
            return None
        if isinstance(value, self.enum_class):
            return value.value
        return value
    
    def from_database(self, value, target_type, options=None):
        if value is None:
            return None
        if isinstance(value, self.enum_class):
            return value
        return self.enum_class(value)
```

## Using Custom Adapters

### Automatic Conversion

```python
# Custom adapter is used automatically
backend.execute("INSERT INTO users (email) VALUES (?)", ("TEST@EXAMPLE.COM",))
result = backend.execute("SELECT email FROM users WHERE id = 1")
# result[0][0] is "test@example.com"
```

### With Models

```python
from rhosocial.activerecord.model import ActiveRecord

class User(ActiveRecord):
    __table_name__ = "users"
    id: int
    email: str  # Uses CustomEmailAdapter automatically

# Create user
user = User(email="TEST@EXAMPLE.COM")
user.save()
# email is stored as "test@example.com"
```

## Best Practices

### Keep Adapters Simple

```python
# Good: Simple, focused adapter
class EmailAdapter(SQLTypeAdapter):
    def to_database(self, value, target_type, options=None):
        return value.lower() if value else None

# Avoid: Overly complex adapter
class ComplexAdapter(SQLTypeAdapter):
    def to_database(self, value, target_type, options=None):
        # Too much logic
```

### Handle None Values

```python
# Good: Always handle None
class SafeAdapter(SQLTypeAdapter):
    def to_database(self, value, target_type, options=None):
        if value is None:
            return None
        return value.lower()

# Avoid: Not handling None
class UnsafeAdapter(SQLTypeAdapter):
    def to_database(self, value, target_type, options=None):
        return value.lower()  # Will fail if value is None
```

### Validate Input

```python
# Good: Validate input
class ValidatingAdapter(SQLTypeAdapter):
    def to_database(self, value, target_type, options=None):
        if value is None:
            return None
        if "@" not in value:
            raise ValueError(f"Invalid email: {value}")
        return value.lower()

# Avoid: No validation
class UnvalidatingAdapter(SQLTypeAdapter):
    def to_database(self, value, target_type, options=None):
        return value.lower()  # No validation
```

💡 *AI Prompt:* "How do I create a custom adapter for a Firebird-specific data type?"