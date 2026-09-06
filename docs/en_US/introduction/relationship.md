# Relationship with Core Library

## Overview

The `rhosocial-activerecord-firebird` backend integrates with the `rhosocial-activerecord` core library to provide Firebird database support while maintaining the ActiveRecord pattern interface.

## Architecture

```
rhosocial-activerecord (Core)
├── ActiveRecord base class
├── Query builder
├── Transaction management
└── Type system

rhosocial-activerecord-firebird (Backend)
├── FirebirdBackend implementation
├── Firebird-specific types
├── Firebird dialect
└── Firebird adapters
```

## Integration Points

### Model Registration

```python
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

class User(ActiveRecord):
    __table_name__ = "users"
    id: int
    name: str
    email: str

# Configure with Firebird backend
config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey"
)
User.configure(config, FirebirdBackend)
```

### Query Execution

The backend implements the core storage interface:

```python
from rhosocial.activerecord.backend.expression import Column
from rhosocial.activerecord.backend.expression.core import Literal
from rhosocial.activerecord.backend.expression.operators import BinaryExpression

# Core query builder using expressions
expr = BinaryExpression(dialect, "=", Column(dialect, "active"), Literal(dialect, True))
users = User.query().where(expr).all()
sql, params = expr.to_sql()
# sql: "active" = %s
# params: (True,)

# Backend executes against Firebird
# Uses Firebird-specific SQL dialect
```

### Transaction Management

```python
# Core transaction API
with User.transaction():
    user = User(name="Alice")
    user.save()
    
    order = Order(user_id=user.id, amount=100)
    order.save()
```

## Feature Mapping

| Core Feature | Firebird Implementation |
|--------------|------------------------|
| Model | FirebirdBackend handles storage |
| Query | Firebird SQL dialect |
| Transaction | FirebirdTransactionManager |
| Type System | FirebirdTypeAdapter |
| DDL | FirebirdDialect extensions |

## Compatibility

- **Core Version**: Requires `rhosocial-activerecord>=1.0.0`
- **Python**: 3.11+
- **API Surface**: Full sync/async parity

💡 *AI Prompt:* "How does the Firebird backend extend the core ActiveRecord functionality?"