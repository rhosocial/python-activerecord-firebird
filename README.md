<!-- README.md -->
# rhosocial-activerecord-firebird ($\rho_{\mathbf{AR}\text{-firebird}}$)

[![PyPI version](https://badge.fury.io/py/rhosocial-activerecord-firebird.svg)](https://badge.fury.io/py/rhosocial-activerecord-firebird)
[![Python](https://img.shields.io/pypi/pyversions/rhosocial-activerecord-firebird.svg)](https://pypi.org/project/rhosocial-activerecord-firebird/)
[![Tests](https://github.com/rhosocial/python-activerecord-firebird/actions/workflows/test.yml/badge.svg)](https://github.com/rhosocial/python-activerecord-firebird/actions)
[![Coverage Status](https://codecov.io/gh/rhosocial/python-activerecord-firebird/branch/main/graph/badge.svg)](https://app.codecov.io/gh/rhosocial/python-activerecord-firebird/tree/main)
[![Supported Firebird versions](https://img.shields.io/badge/Firebird-3%7C4%7C5%7C6-blue?logo=firebird)](https://github.com/rhosocial/python-activerecord/blob/main/docs/en_US/README.md)
[![Apache 2.0 License](https://img.shields.io/github/license/rhosocial/python-activerecord-firebird.svg)](https://github.com/rhosocial/python-activerecord-firebird/blob/main/LICENSE)

<div align="center">
    <img src="https://raw.githubusercontent.com/rhosocial/python-activerecord/main/docs/images/logo.svg" alt="rhosocial ActiveRecord Logo" width="200"/>
    <h3>Firebird Backend for rhosocial-activerecord</h3>
    <p><b>Domains &amp; generators · BLOB subtypes · PSQL · Firebird 3–6</b></p>
</div>

This is a backend implementation for [rhosocial-activerecord](https://github.com/rhosocial/python-activerecord).
It cannot be used standalone.

**Keywords:** orm, activerecord, pydantic, python, firebird, firebird-driver, backend

## Why This Project?

### 1. Firebird deserves a native ActiveRecord backend

Firebird has capabilities that generic ORMs flatten or ignore — domains, generators as
sequences, BLOB subtypes, PSQL stored procedures, and a version-gated feature surface.
This backend exposes them as ordinary expressions, so you use them from the same model
and query API as the rest of your application.

### 2. No wrapper, no hidden layer

The backend sits directly on the core library's expression and dialect system and talks
to the server through `firebird-driver`. There is no second ORM in the middle: nothing is
rendered to Firebird SQL until an explicit `.to_sql()` call, and the statements the
backend emits are the statements Firebird executes.

## Quick Start

### Installation

```bash
pip install rhosocial-activerecord-firebird
```

Requires Python 3.11+ (through 3.15) and a reachable Firebird 3+ server. The core
library is installed as a dependency.

### End-to-End Example

```python
"""Save as demo.py and run with: python demo.py"""
from typing import Annotated, ClassVar

from rhosocial.activerecord.base import FieldProxy, UseSqlType
from rhosocial.activerecord.backend.impl.firebird.backend import FirebirdBackend
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig
from rhosocial.activerecord.backend.expression.types import VarCharType
from rhosocial.activerecord.field import DefaultTimestampMixin, IntegerPKMixin
from rhosocial.activerecord.model import ActiveRecord


class User(
    IntegerPKMixin,         # auto-increment integer primary key (`id`)
    DefaultTimestampMixin,  # injects `created_at` / `updated_at` timestamps
    ActiveRecord,           # persistence, query builder, relations
):
    name: Annotated[str, UseSqlType(VarCharType(length=100))]
    email: Annotated[str, UseSqlType(VarCharType(length=255))]
    age: int = 0

    c: ClassVar[FieldProxy] = FieldProxy()  # enables User.c.<field> expressions

    @classmethod
    def table_name(cls) -> str:
        return "users"


# Firebird connects to a physical .fdb file — create it before running.
User.configure(
    FirebirdConnectionConfig(
        host="localhost",
        port=3050,
        database="/var/lib/firebird/data/myapp.fdb",
        username="SYSDBA",
        password="masterkey",
    ),
    FirebirdBackend,
)
User.create_table()  # DDL derived from the model declaration

alice = User(name="Alice", email="alice@example.com", age=30)
alice.save()
print(alice.id)  # database-assigned integer primary key

adults = User.query().where(User.c.age >= 18).all()
print([user.name for user in adults])

sql, params = User.query().where(User.c.age >= 18).to_sql()
print(sql, params)  # preview the statement before it runs
```

> **Async (experimental — not for production):** `AsyncActiveRecord` with
> `AsyncFirebirdBackend` keeps the same method names — just add `await`. The
> `firebird-driver` has no native async support, so this is a thread-pool wrapper kept
> for API-shape parity only; use the synchronous `FirebirdBackend` in production.

## Project Architecture

This package is a backend layer on top of `rhosocial-activerecord`: your models and
queries flow through the core's expression and dialect machinery, and this package binds
them to Firebird SQL and the `firebird-driver`. It contributes the Firebird dialect, DDL
extensions (domains, generators, PSQL), version-gated capability switches, introspection,
and transaction handling.

For the full picture, start with the [Documentation](https://github.com/rhosocial/python-activerecord/blob/main/docs/en_US/README.md).

## Backend Support & Progress

This package ships separately from the core library and adds Firebird support to any
application built on `rhosocial-activerecord`; the core does not bundle it. Firebird 3 or
newer is required in practice — `IDENTITY`, native `BOOLEAN`, CTEs, window functions and
generators-as-sequences all switch on at 3.0. CI runs against Firebird 5 and a
6-snapshot build.

> **⚠️ Development Stage:** This project is under active development. APIs may change,
> and some features are not yet production-ready. The asynchronous API is experimental
> (see Quick Start).

## Documentation

### Contributing

We welcome contributions! Please see [CONTRIBUTING.md](https://github.com/rhosocial/python-activerecord/blob/main/CONTRIBUTING.md) for guidelines.

### License

[Apache License 2.0](LICENSE) — Copyright © 2026 [vistart](https://github.com/vistart)

### Documentation

* **[Documentation Home](https://github.com/rhosocial/python-activerecord/blob/main/docs/en_US/README.md)** — the full documentation table of contents
* **[Introspection](docs/introspection.md)** — what this backend answers and what it declines
* **[Datetime](docs/datetime.md)** — `seconds_between`, resolution and bind order
* **[Backend code style](.claude/code_style.md)** — conventions for this backend
* **[Version control](.claude/version_control.md)** — branching and changelog rules
* **[Core library documentation](https://github.com/rhosocial/python-activerecord/tree/main/docs)** — ActiveRecord and query reference

---

<div align="center">
    <p><b>Built with ❤️ by the rhosocial team</b></p>
    <p><a href="https://github.com/rhosocial/python-activerecord-firebird">GitHub</a> · <a href="https://pypi.org/project/rhosocial-activerecord-firebird/">PyPI</a></p>
</div>
