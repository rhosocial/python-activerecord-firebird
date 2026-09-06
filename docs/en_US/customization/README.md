# Customization

## Overview

The Firebird backend supports extensive customization through custom expressions, data types, and type adapters. This section covers how to extend the backend for specific use cases.

## Custom Expressions

### Creating Custom Expression Classes

Custom expressions allow you to define Firebird-specific SQL syntax:

```python
from rhosocial.activerecord.backend.dialect.base import Expression

class ExecuteBlockExpression(Expression):
    """Custom expression for EXECUTE BLOCK."""
    
    def __init__(self, declarations=None, statements=None):
        self.declarations = declarations or []
        self.statements = statements or []
    
    def to_sql(self, dialect):
        sql = "EXECUTE BLOCK"
        
        if self.declarations:
            declarations_sql = "; ".join(self.declarations)
            sql += f" AS\nDECLARE {declarations_sql}"
        
        if self.statements:
            statements_sql = "\n    ".join(self.statements)
            sql += f"\nBEGIN\n    {statements_sql}\nEND"
        
        return sql

# Usage
expr = ExecuteBlockExpression(
    declarations=["cnt INTEGER"],
    statements=[
        "SELECT COUNT(*) INTO cnt FROM users",
        "INSERT INTO stats (count_value) VALUES (cnt)"
    ]
)
```

### Registering Custom Expressions

```python
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend

# Register expression globally
FirebirdBackend.register_expression("execute_block", ExecuteBlockExpression)

# Or use in dialect
class CustomFirebirdDialect(FirebirdDialect):
    def execute_block(self, declarations=None, statements=None):
        return ExecuteBlockExpression(declarations, statements)
```

## Custom Data Types

### Defining New DataType Subclasses

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

### Custom Domain Types

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

## Custom Type Adapters

### Registering Custom Converters

```python
from rhosocial.activerecord.backend.type_adapter import SQLTypeAdapter

class FirebirdPhoneNumberAdapter(SQLTypeAdapter):
    """Custom adapter for phone numbers."""
    
    @property
    def supported_types(self):
        return {str: [str]}
    
    def to_database(self, value, target_type, options=None):
        if value is None:
            return None
        # Remove non-digit characters
        digits = ''.join(filter(str.isdigit, value))
        # Format as Firebird-friendly string
        return f"+{digits}"
    
    def from_database(self, value, target_type, options=None):
        if value is None:
            return None
        # Remove formatting
        return ''.join(filter(str.isdigit, value))

# Register adapter
FirebirdBackend.register_adapter(FirebirdPhoneNumberAdapter())
```

### Type Adapter with Options

```python
class FirebirdCurrencyAdapter(SQLTypeAdapter):
    """Currency adapter with decimal places option."""
    
    def __init__(self, decimal_places=2):
        self.decimal_places = decimal_places
    
    @property
    def supported_types(self):
        return {Decimal: [Decimal, float, int, str]}
    
    def to_database(self, value, target_type, options=None):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            value = Decimal(str(value))
        return round(value, self.decimal_places)
    
    def from_database(self, value, target_type, options=None):
        if value is None:
            return None
        return Decimal(str(value))

# Usage with options
adapter = FirebirdCurrencyAdapter(decimal_places=4)
FirebirdBackend.register_adapter(adapter)
```

## Dialect Customization

### Extending Firebird Dialect

```python
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect

class CustomFirebirdDialect(FirebirdDialect):
    """Custom Firebird dialect with additional features."""
    
    def custom_function(self, *args):
        """Add custom function support."""
        return f"CUSTOM_FUNC({', '.join(str(a) for a in args)})"
    
    def upsert(self, table, data, conflict_columns):
        """Custom UPSERT implementation using MERGE."""
        merge_sql = f"""
            MERGE INTO {table} t
            USING (SELECT ? AS id, ? AS name) s
            ON t.id = s.id
            WHEN MATCHED THEN
                UPDATE SET t.name = s.name
            WHEN NOT MATCHED THEN
                INSERT (id, name) VALUES (s.id, s.name)
        """
        return merge_sql

# Register custom dialect
FirebirdBackend.dialect_class = CustomFirebirdDialect
```

## Model Customization

### Custom Model Base Class

```python
from rhosocial.activerecord.model import ActiveRecord

class FirebirdModel(ActiveRecord):
    """Custom model base class for Firebird."""
    
    __abstract__ = True
    
    @classmethod
    def find_by_email(cls, email):
        """Find user by email (case-insensitive)."""
        return cls.query().where(
            "LOWER(email) = LOWER(?)", (email,)
        ).one()
    
    def soft_delete(self):
        """Soft delete with timestamp."""
        self.deleted_at = datetime.now()
        self.save()
    
    @classmethod
    def active(cls):
        """Get only active (non-deleted) records."""
        from rhosocial.activerecord.backend.expression import Column
        expr = Column(dialect, "deleted_at").is_null()
        return cls.query().where(expr)
```

### Custom Query Builder

```python
class FirebirdQuery:
    """Custom query builder with Firebird-specific features."""
    
    def __init__(self, backend, model):
        self.backend = backend
        self.model = model
    
    def with_row_number(self, partition_by=None, order_by=None):
        """Add ROW_NUMBER() window function."""
        sql = f"SELECT *, ROW_NUMBER() OVER ("
        if partition_by:
            sql += f"PARTITION BY {partition_by} "
        if order_by:
            sql += f"ORDER BY {order_by}"
        sql += f") as row_num FROM {self.model.__table_name__}"
        return self.backend.execute(sql)
    
    def execute_block(self, declarations, statements):
        """Execute EXECUTE BLOCK."""
        expr = ExecuteBlockExpression(declarations, statements)
        return self.backend.execute(expr.to_sql(None))
```

## Configuration Customization

### Custom Configuration Mixin

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class FirebirdExtendedConfig(FirebirdConnectionConfig):
    """Extended configuration with additional options."""
    
    # Connection options
    connection_timeout: int = 30
    query_timeout: int = 60
    
    # Logging options
    log_queries: bool = False
    log_slow_queries: bool = True
    slow_query_threshold: float = 1.0  # seconds
    
    # Performance options
    fetch_size: int = 100
    array_size: int = 100

# Usage
config = FirebirdExtendedConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    log_queries=True,
    slow_query_threshold=0.5
)
```

## Plugin System

### Creating Plugins

```python
class FirebirdPlugin:
    """Base class for Firebird plugins."""
    
    def __init__(self, backend):
        self.backend = backend
    
    def on_connect(self):
        """Called when connection is established."""
        pass
    
    def on_disconnect(self):
        """Called when connection is closed."""
        pass
    
    def on_query(self, query, params):
        """Called before query execution."""
        pass

class LoggingPlugin(FirebirdPlugin):
    """Plugin for query logging."""
    
    def on_query(self, query, params):
        print(f"Executing: {query}")
        print(f"Parameters: {params}")

# Register plugin
backend = FirebirdBackend(config=config)
backend.register_plugin(LoggingPlugin(backend))
```

💡 *AI Prompt:* "How do I create a custom expression for Firebird's EXECUTE BLOCK?"