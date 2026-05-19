# rhosocial-activerecord-firebird

Firebird backend implementation for the `rhosocial-activerecord` Python ActiveRecord ORM.

## Installation

```bash
pip install rhosocial-activerecord-firebird
```

## Quick Start

```python
from rhosocial.activerecord import ActiveRecord
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend, FirebirdConnectionConfig

class User(ActiveRecord):
    __table_name__ = "users"

config = FirebirdConnectionConfig(
    host="localhost",
    port=3050,
    database="/path/to/database.fdb",
    user="SYSDBA",
    password="masterkey",
)

User.configure(config, FirebirdBackend)

# CRUD operations
user = User(name="Alice", email="alice@example.com")
user.save()
```

## Development

```bash
pip install -e ".[dev,test]"
pytest
```

## License

Apache License 2.0