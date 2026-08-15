# rhosocial-activerecord-firebird ($\rho_{\mathbf{AR}\text{-firebird}}$)

[![PyPI version](https://badge.fury.io/py/rhosocial-activerecord-firebird.svg)](https://badge.fury.io/py/rhosocial-activerecord-firebird)
[![Python](https://img.shields.io/pypi/pyversions/rhosocial-activerecord-firebird.svg)](https://pypi.org/project/rhosocial-activerecord-firebird/)
[![Tests](https://github.com/rhosocial/python-activerecord-firebird/actions/workflows/test.yml/badge.svg)](https://github.com/rhosocial/python-activerecord-firebird/actions)
[![Coverage Status](https://codecov.io/gh/rhosocial/python-activerecord-firebird/branch/main/graph/badge.svg)](https://app.codecov.io/gh/rhosocial/python-activerecord-firebird/tree/main)
[![Apache 2.0 License](https://img.shields.io/github/license/rhosocial/python-activerecord-firebird.svg)](https://github.com/rhosocial/python-activerecord-firebird/blob/main/LICENSE)
[![Powered by vistart](https://img.shields.io/badge/Powered_by-vistart-blue.svg)](https://github.com/vistart)

<div align="center">
    <img src="https://raw.githubusercontent.com/rhosocial/python-activerecord/main/docs/images/logo.svg" alt="rhosocial ActiveRecord Logo" width="200"/>
    <h3>Firebird Backend for rhosocial-activerecord</h3>
    <p><b>Embedded & Server Modes · BLOB & Domains · Sync & Async</b></p>
</div>

> **Note**: This is a backend implementation for [rhosocial-activerecord](https://github.com/rhosocial/python-activerecord). It cannot be used standalone.

## Why This Backend?

### 1. Firebird-Specific Optimizations

| Feature | This Backend | Generic Solutions |
|---------|-------------|-------------------|
| **BLOB Types** | Native BLOB/CLOB handling | Application-level chunking |
| **Domains** | Reusable `CREATE DOMAIN` | Repetitive column definitions |
| **Sequences** | Native generators | Identity/application counters |
| **Stored Procedures** | Native PSQL support | Application-level orchestration |
| **External Functions** | `EXTERNAL FUNCTION` DDL | C/Python FFI glue |

### 2. True Sync-Async Parity

Same API surface for both sync and async operations:

```python
# Sync
users = User.query().where(User.c.age >= 18).all()

# Async - just add await
users = await User.query().where(User.c.age >= 18).all()
```

### 3. Built for Production

- **Connection pooling** with configurable pool sizes
- **Transaction support** with proper isolation levels
- **Error mapping** from Firebird error codes to Python exceptions
- **Type adapters** for Firebird-specific data types

## Quick Start

### Installation

```bash
pip install rhosocial-activerecord-firebird
```

### Basic Usage

```python
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig
from typing import Optional

class User(ActiveRecord):
    __table_name__ = "users"
    id: Optional[int] = None
    name: str
    email: str

# Configure
config = FirebirdConnectionConfig(
    host="localhost",
    port=3050,
    database="/var/lib/firebird/2.5/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey"
)
User.configure(config, FirebirdBackend)

# Use
user = User(name="Alice", email="alice@example.com")
user.save()

# Query with parameter binding
results = User.query().where("email = ?", ("alice@example.com",)).all()
```

> 💡 **AI Prompt**: "How do I configure connection pooling for Firebird?"

## Firebird-Specific Features

### BLOB & Text Types

Native handling of Firebird BLOB subtypes:

```python
class Document(ActiveRecord):
    __table_name__ = "documents"
    id: int
    title: str
    content: bytes  # BLOB SUB_TYPE 0
    body: str       # BLOB SUB_TYPE TEXT
```

### Domains

Reusable column type definitions:

```python
# DDL-level domain support
User.query().where(
    "CREATE DOMAIN EMAIL_ADDRESS AS VARCHAR(255)"
).all()
```

### Sequences (Generators)

Firebird's generator-based sequences:

```python
class Ticket(ActiveRecord):
    __table_name__ = "tickets"
    ticket_no: int  # NEXT VALUE FOR ticket_seq
```

### Stored Procedures

Native PSQL procedure execution:

```python
# Call a stored procedure
result = User.query().where(
    "SELECT * FROM get_user_stats(?)",
    (1,),
).all()
```

## Requirements

- **Python**: 3.11+ (including 3.13t/3.14t free-threaded builds)
- **Core**: `rhosocial-activerecord>=1.0.0`
- **Driver**: `firebird-driver>=2.0.0`

## Firebird Version Compatibility

| Feature | Min Version | Notes |
|---------|-------------|-------|
| Basic operations | 3.0+ | Core functionality |
| BLOB types | 1.0+ | Binary/text subtypes |
| Domains | 1.0+ | CREATE DOMAIN |
| Sequences | 1.0+ | Generators |
| Stored procedures | 1.0+ | PSQL |
| External functions | 2.5+ | EXTERNAL FUNCTION |
| Window functions | 3.0+ | ROW_NUMBER, RANK, etc. |
| EXECUTE BLOCK | 2.1+ | Anonymous PSQL |
| MERGE statement | 2.1+ | Upsert |
| BOOLEAN type | 3.0+ | Native boolean |
| Identity columns | 3.0+ | GENERATED BY DEFAULT AS IDENTITY |
| DBMS_OUTPUT | 2.1+ | Server-side output |

**Recommended**: Firebird 3.0+ for optimal feature support.

## Get Started with AI Code Agents

This project supports AI-assisted development. Clone and open in your preferred tool:

```bash
git clone https://github.com/rhosocial/python-activerecord-firebird.git
cd python-activerecord-firebird
```

### Example AI Prompts

- "How do I configure connection pooling for Firebird?"
- "Show me how to use BLOB fields"
- "How do I create and use domains?"
- "Call a stored procedure with parameters"

### For Any LLM

Feed the documentation files in `docs/` to your preferred LLM for context-aware assistance.

## Testing

> ⚠️ **CRITICAL**: Tests MUST run serially. Do NOT use `pytest -n auto` or parallel execution.

```bash
# Run all tests
PYTHONPATH=src pytest tests/

# Run specific feature tests
PYTHONPATH=src pytest tests/rhosocial/activerecord_firebird_test/feature/basic/
PYTHONPATH=src pytest tests/rhosocial/activerecord_firebird_test/feature/query/
```

See the [Testing Documentation](https://github.com/rhosocial/python-activerecord/blob/main/.claude/testing.md) for details.

## Documentation

- **[Getting Started](docs/en_US/getting_started/)** — Installation and configuration
- **[Firebird Features](docs/en_US/firebird_specific_features/)** — Firebird-specific capabilities
- **[Type Adapters](docs/en_US/type_adapters/)** — Data type handling
- **[Transaction Support](docs/en_US/transaction_support/)** — Transaction management

## Comparison with Other Backends

| Feature | Firebird | PostgreSQL | SQLite |
|---------|----------|------------|--------|
| **RETURNING** | ✅ RETURNING | ✅ RETURNING | ✅ RETURNING |
| **BLOB Types** | ✅ Native | ✅ BYTEA | ⚠️ BLOB |
| **Domains** | ✅ Native | ✅ CREATE DOMAIN | ❌ |
| **Arrays** | ❌ | ✅ Native | ❌ |
| **JSON Type** | ❌ | ✅ JSONB | ⚠️ JSON1 extension |

> 💡 **AI Prompt**: "When should I choose Firebird over PostgreSQL for my project?"

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

[Apache License 2.0](LICENSE) — Copyright © 2026 [vistart](https://github.com/vistart)

---

<div align="center">
    <p><b>Built with ❤️ by the rhosocial team</b></p>
    <p><a href="https://github.com/rhosocial/python-activerecord-firebird">GitHub</a> · <a href="https://docs.python-activerecord.dev.rho.social/backends/firebird.html">Documentation</a> · <a href="https://pypi.org/project/rhosocial-activerecord-firebird/">PyPI</a></p>
</div>