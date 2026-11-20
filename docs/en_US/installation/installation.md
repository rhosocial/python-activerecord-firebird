# Installation guide

## Requirements

- Python 3.11 or newer.
- A reachable Firebird server (3.0 or newer; CI exercises 5 and 6-snapshot).
- The native Firebird client library. On Debian/Ubuntu: `sudo apt-get install libfbclient2`.

## Install

```bash
pip install rhosocial-activerecord-firebird
```

This pulls in `rhosocial-activerecord>=1.0.0.dev30,<2.0.0` and
`firebird-driver>=2.0.0`. Until the required core version is published on PyPI,
install both from source instead:

```bash
pip install "rhosocial-activerecord @ git+https://github.com/rhosocial/python-activerecord.git@<branch>"
pip install -e .
```

For development and tests, install the extras and the test suite explicitly:

```bash
pip install -e ".[test,dev]"
pip install -e ../python-activerecord-testsuite
```

The testsuite must be installed from the local checkout: the bare name in the
extras can resolve to an older published release that lacks modules this backend
imports. See [Test configuration](../testing/README.md).

## Client library discovery

`firebird-driver` loads `libfbclient` through its engine layer. If the library is
not found on the default loader path, set the path before the first connection:

```powershell
$env:FIREBIRD_CLIENT_LIBRARY = 'C:\Program Files\Firebird\Firebird_5_0\bin\fbclient.dll'
```

```bash
export FIREBIRD_CLIENT_LIBRARY=/usr/lib/x86_64-linux-gnu/libfbclient.so.2
```

`FirebirdBackend.connect()` reads this variable and calls
`firebird.driver.fbapi.load_api()` with it when set.

## Verify the installation

```python
from rhosocial.activerecord.backend.impl.firebird.backend import FirebirdBackend
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

backend = FirebirdBackend(connection_config=FirebirdConnectionConfig(
    host="localhost", port=3050,
    database="/var/lib/firebird/data/test.fdb",
    username="SYSDBA", password="masterkey",
))
backend.connect()
print(".".join(str(v) for v in backend.get_server_version()))
backend.disconnect()
```

The same flow is available as [`examples/connection.py`](../../examples/connection.py).
Next: [Connection configuration](configuration.md).
