# Timezone Handling

## Overview

Firebird stores timestamps without timezone information. The backend provides timezone conversion support.

## Configuration

### Setting Session Timezone

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

### Common Timezones

| Timezone | Description |
|----------|-------------|
| `UTC` | Coordinated Universal Time |
| `America/New_York` | Eastern Time |
| `America/Chicago` | Central Time |
| `America/Denver` | Mountain Time |
| `America/Los_Angeles` | Pacific Time |
| `Europe/London` | Greenwich Mean Time |
| `Europe/Paris` | Central European Time |
| `Asia/Tokyo` | Japan Standard Time |

## Timezone Conversion

### Storing UTC Timestamps

```python
from datetime import datetime, timezone

# Store as UTC
utc_now = datetime.now(timezone.utc)
backend.execute("INSERT INTO events (created_at) VALUES (?)", (utc_now,))
```

### Retrieving Local Timestamps

```python
from datetime import datetime, timezone

# Retrieve and convert
result = backend.execute("SELECT created_at FROM events WHERE id = ?", (1,))
local_time = result[0].replace(tzinfo=timezone.utc).astimezone()
```

### Converting Between Timezones

```python
from datetime import datetime, timezone, timedelta

# Convert from UTC to local
utc_time = datetime.now(timezone.utc)
eastern = timezone(timedelta(hours=-5))
local_time = utc_time.astimezone(eastern)
```

## Python Examples

### Basic Timezone Operations

```python
from datetime import datetime, timezone, timedelta

# Create UTC timestamp
utc_time = datetime.now(timezone.utc)

# Convert to different timezones
eastern = timezone(timedelta(hours=-5))
pacific = timezone(timedelta(hours=-8))

eastern_time = utc_time.astimezone(eastern)
pacific_time = utc_time.astimezone(pacific)

print(f"UTC: {utc_time}")
print(f"Eastern: {eastern_time}")
print(f"Pacific: {pacific_time}")
```

### Database Operations

```python
# Store UTC timestamp
utc_now = datetime.now(timezone.utc)
backend.execute("INSERT INTO events (created_at) VALUES (?)", (utc_now,))

# Retrieve and convert
result = backend.execute("SELECT created_at FROM events WHERE id = 1")
stored_time = result[0][0]

# Convert to local timezone
if stored_time.tzinfo is None:
    stored_time = stored_time.replace(tzinfo=timezone.utc)
local_time = stored_time.astimezone(eastern)
```

### Timezone-Aware Queries

```python
# Query with timezone conversion
backend.execute("""
    INSERT INTO events (created_at, timezone)
    VALUES (?, ?)
""", (datetime.now(timezone.utc), "America/New_York"))

# Retrieve with timezone
result = backend.execute("""
    SELECT created_at, timezone FROM events WHERE id = 1
""")
```

## Best Practices

### Store UTC

```python
# Good: Store UTC
utc_time = datetime.now(timezone.utc)
backend.execute("INSERT INTO events (created_at) VALUES (?)", (utc_time,))

# Avoid: Store local time
local_time = datetime.now()  # No timezone info
backend.execute("INSERT INTO events (created_at) VALUES (?)", (local_time,))
```

### Convert on Display

```python
# Good: Convert on display
result = backend.execute("SELECT created_at FROM events WHERE id = 1")
utc_time = result[0][0].replace(tzinfo=timezone.utc)
local_time = utc_time.astimezone(eastern)
print(f"Event time: {local_time}")

# Avoid: Store converted time
backend.execute("INSERT INTO events (created_at) VALUES (?)", (local_time,))
```

### Handle DST

```python
from datetime import datetime, timezone, timedelta
import pytz

# Use pytz for DST handling
eastern = pytz.timezone('America/New_York')
utc_time = datetime.now(timezone.utc)
eastern_time = utc_time.astimezone(eastern)

# Handle DST transitions
try:
    eastern_time.normalize(eastern_time)
except pytz.exceptions.AmbiguousTimeError:
    # Handle ambiguous time (DST transition)
    pass
```

## Common Issues

### Timezone-Aware vs Naive

```python
from datetime import datetime, timezone

# Timezone-aware
aware_time = datetime.now(timezone.utc)

# Naive (no timezone)
naive_time = datetime.now()

# Cannot compare
try:
    if aware_time > naive_time:
        pass
except TypeError as e:
    print(f"Cannot compare: {e}")
```

### Missing Timezone

```python
# Handle missing timezone
result = backend.execute("SELECT created_at FROM events WHERE id = 1")
stored_time = result[0][0]

if stored_time.tzinfo is None:
    # Assume UTC
    stored_time = stored_time.replace(tzinfo=timezone.utc)

local_time = stored_time.astimezone(eastern)
```

## Advanced Usage

### Custom Timezone Adapter

```python
from rhosocial.activerecord.backend.type_adapter import SQLTypeAdapter
from datetime import datetime, timezone

class TimezoneAdapter(SQLTypeAdapter):
    def __init__(self, target_timezone):
        self.target_timezone = target_timezone
    
    @property
    def supported_types(self):
        return {datetime: [datetime]}
    
    def to_database(self, value, target_type, options=None):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    
    def from_database(self, value, target_type, options=None):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(self.target_timezone)

# Register adapter
FirebirdBackend.register_adapter(TimezoneAdapter(eastern))
```

### Timezone Conversion Function

```python
def convert_timezone(backend, table, column, from_tz, to_tz):
    """Convert timezone in database column."""
    backend.execute(f"""
        UPDATE {table}
        SET {column} = {column} AT TIME ZONE ?
    """, (to_tz,))
```

💡 *AI Prompt:* "How do I handle timezone conversions with Firebird timestamps?"