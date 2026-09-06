# Type Adapters

## Overview

Type adapters handle conversion between Python types and Firebird database types. The Firebird backend includes built-in adapters for common data types and supports custom adapters for specialized needs.

## Type Mapping

### Firebird to Python Type Conversion

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

### Built-in Adapters

#### FirebirdBlobAdapter

Handles binary BLOB data (SUB_TYPE 0):

```python
from rhosocial.activerecord.backend.impl.firebird.adapters import FirebirdBlobAdapter

adapter = FirebirdBlobAdapter()

# Python to Firebird
db_value = adapter.to_database(b"binary data", bytes)

# Firebird to Python
py_value = adapter.from_database(b"binary data", bytes)
# Returns: b"binary data"
```

#### FirebirdTextBlobAdapter

Handles text BLOB data (SUB_TYPE 1):

```python
from rhosocial.activerecord.backend.impl.firebird.adapters import FirebirdTextBlobAdapter

adapter = FirebirdTextBlobAdapter()

# Python to Firebird
db_value = adapter.to_database("text content", str)

# Firebird to Python
py_value = adapter.from_database(b"text content", str)
# Returns: "text content"
```

#### FirebirdBooleanAdapter

Handles BOOLEAN type (Firebird 3.0+):

```python
from rhosocial.activerecord.backend.impl.firebird.adapters import FirebirdBooleanAdapter

adapter = FirebirdBooleanAdapter()

# Python to Firebird (stores as integer 0/1)
db_value = adapter.to_database(True, bool)
# Returns: 1

# Firebird to Python
py_value = adapter.from_database(1, bool)
# Returns: True
```

#### FirebirdDecimalAdapter

Handles DECIMAL and NUMERIC types:

```python
from rhosocial.activerecord.backend.impl.firebird.adapters import FirebirdDecimalAdapter

adapter = FirebirdDecimalAdapter()

# Python to Firebird
db_value = adapter.to_database(Decimal("123.45"), Decimal)

# Firebird to Python
py_value = adapter.from_database(Decimal("123.45"), Decimal)
# Returns: Decimal("123.45")
```

## Custom Adapters

### Creating Custom Adapters

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

### Registering Custom Adapters

```python
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend

# Register adapter globally
FirebirdBackend.register_adapter(CustomEmailAdapter())

# Or register for specific backend instance
backend = FirebirdBackend(config=config)
backend.register_adapter(CustomEmailAdapter())
```

## Timezone Handling

### Timestamp Configuration

Firebird stores timestamps without timezone information. The backend can handle timezone conversion:

```python
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    timezone="America/New_York"  # Set session timezone
)
```

### UTC Timestamps

```python
from datetime import datetime, timezone

# Store as UTC
utc_now = datetime.now(timezone.utc)
backend.execute("INSERT INTO events (created_at) VALUES (?)", (utc_now,))

# Retrieve and convert
result = backend.execute("SELECT created_at FROM events WHERE id = ?", (1,))
local_time = result[0].replace(tzinfo=timezone.utc).astimezone()
```

## Type Conversion Examples

### Date and Time Types

```python
from datetime import date, time, datetime

# Date
backend.execute("INSERT INTO events (event_date) VALUES (?)", (date(2026, 1, 1),))

# Time
backend.execute("INSERT INTO events (event_time) VALUES (?)", (time(14, 30),))

# Timestamp
backend.execute("INSERT INTO events (event_timestamp) VALUES (?)", 
                (datetime(2026, 1, 1, 14, 30),))
```

### Numeric Types

```python
from decimal import Decimal

# Decimal
backend.execute("INSERT INTO products (price) VALUES (?)", (Decimal("19.99"),))

# Float
backend.execute("INSERT INTO measurements (value) VALUES (?)", (3.14159,))
```

### Boolean Type

```python
# Boolean (Firebird 3.0+)
backend.execute("INSERT INTO settings (enabled) VALUES (?)", (True,))

# For older Firebird versions, use CHAR(1) with 'T'/'F'
backend.execute("INSERT INTO settings (enabled) VALUES (?)", ("T",))
```

💡 *AI Prompt:* "How do I handle timezone conversions with Firebird timestamps?"