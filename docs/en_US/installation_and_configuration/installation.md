# Installation Guide

## Prerequisites

- Python 3.11 or later
- Firebird database server (3.0+ recommended)
- `firebird-driver` Python package

## Installation

### Basic Installation

```bash
pip install rhosocial-activerecord-firebird
```

### With Optional Dependencies

```bash
# With connection pooling support
pip install rhosocial-activerecord-firebird[pooling]

# For development
pip install rhosocial-activerecord-firebird[dev,test]
```

## Driver Setup

### firebird-driver

The backend uses `firebird-driver` for database connectivity. This is automatically installed as a dependency.

### Client Library

Firebird client library is required. On Linux:

```bash
# Ubuntu/Debian
sudo apt-get install firebird3.0-client

# CentOS/RHEL
sudo yum install firebird-client
```

On Windows, the client library is included with the Firebird installation.

## Environment Variables

### Client Library Path

If the client library is not in the standard path:

```bash
export FIREBIRD_CLIENT_LIBRARY=/path/to/libfbclient.so
```

### Database Configuration

```bash
export FIREBIRD_HOST=localhost
export FIREBIRD_PORT=3050
export FIREBIRD_DATABASE=/data/myapp.fdb
export FIREBIRD_USERNAME=SYSDBA
export FIREBIRD_PASSWORD=masterkey
```

## Verification

### Test Installation

```python
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

config = FirebirdConnectionConfig(
    host="localhost",
    database="/tmp/test.fdb",
    username="SYSDBA",
    password="masterkey"
)

backend = FirebirdBackend(config=config)
backend.connect()
print("Installation successful!")
backend.disconnect()
```

### Check Version

```python
import firebird.driver
print(f"firebird-driver version: {firebird.driver.__version__}")
```

💡 *AI Prompt:* "How do I install Firebird on different operating systems?"