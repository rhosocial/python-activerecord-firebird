---
name: dev-firebird-client
description: Prepare the native Firebird client library for the Python firebird-driver on Windows 11 (PowerShell) and Ubuntu 26.04 (apt) - install fbclient.dll beside the Windows venv or libfbclient2 from the distribution, then verify against the live Firebird scenarios
license: MIT
compatibility: opencode
metadata:
  category: environment
  level: intermediate
  audience: developers
  order: 20
---

# Firebird Client Library

Firebird is the one backend whose Python driver talks to a **native** library:
`firebird-driver` binds `fbclient.dll` on Windows and `libfbclient` on Linux
through ctypes. The driver wheel does not contain that library, and a fresh
machine or venv therefore fails at the first connection attempt with:

```text
Exception: The location of Firebird Client Library could not be determined.
```

This skill prepares the client dependency on the two development platforms
this repository uses: **Windows 11 + PowerShell** and **Ubuntu 26.04**. Both
paths are local-only: the Windows script installs the official client subset
beside each venv, while Ubuntu installs the distribution package system-wide.

## 1. When to run this

Run it when any of these is true:

| Symptom | Where |
| --- | --- |
| `The location of Firebird Client Library could not be determined.` | any `firebird.driver` call |
| `firebird.wrapper` / ctypes load error on connect | importing the backend |
| `tests/config/firebird_scenarios.yaml` exists but every Firebird test errors at connect | `pytest --scenarios firebird_5` |
| A venv was just created or recreated on Windows | after `uv venv`, `uv sync`, or deleting `.venv3.14` |
| A new Ubuntu machine or container image has no `libfbclient2` | first `firebird.driver` import |

The Python package alone is never enough:

```bash
pip install "rhosocial-activerecord-firebird"
```

That installs `firebird-driver`, but not the native client.

## 2. Windows 11 (PowerShell, primary local path)

The skill ships a script that downloads the official Firebird Windows x64
kit, copies only the client subset into each venv, and registers it through a
site-packages `.pth` so no environment variable or global `PATH` edit is
needed.

Run it from the checkout or worktree root:

```powershell
pwsh -File .claude/skills/dev-firebird-client/install-firebird-client.ps1
```

Windows PowerShell 5.1 also works:

```powershell
powershell -ExecutionPolicy Bypass -File .claude/skills/dev-firebird-client/install-firebird-client.ps1
```

### What it installs

```text
<venv>\firebird-client\                 official client subset
<venv>\Lib\site-packages\firebird_client_path.py
<venv>\Lib\site-packages\_firebird_client.pth    one line: import firebird_client_path
```

The copied subset is about 5.6 MB and contains `fbclient.dll`, its MSVC
runtimes, `firebird.msg`, `intl\fbintl.dll`, authentication plugins and
`tzdata`. The Firebird engine, tools and debug symbols are not copied. No
system directory, no machine-wide `PATH`, and no repository file is changed.

### Useful variations

```powershell
-Check              # report status, change nothing
-Force              # reinstall even when it already looks right
-Venv .venv3.15     # one venv, relative or absolute
-IncludeWorktrees   # also install into every .worktree/<branch>/.venv*
-Proxy http://host:port   # when GitHub downloads need a proxy
-Redownload         # ignore the cached ZIP
```

Venv discovery is by shape, not name: any `.venv*` with
`Scripts\python.exe`. A checkout with only `.venv3.15`, or with both
`.venv3.14` and `.venv3.15`, behaves the same.

Downloads are cached in `%LOCALAPPDATA%\rhosocial\cache\firebird` and checked
against the SHA256 pinned in the script.

### Manual Windows fallback

If the script cannot be used, download the official Windows x64 ZIP from
<https://www.firebirdsql.org/en/firebird-5-0/> and copy at least:

```text
fbclient.dll
ib_util.dll
zlib1.dll
firebird.msg
msvcp140.dll, msvcp140_1.dll
vcruntime140.dll, vcruntime140_1.dll
intl\fbintl.dll
plugins\srp.dll, plugins\legacy_auth.dll, plugins\chacha.dll
tzdata\ids.dat, tzdata\metaZones.res, tzdata\timezoneTypes.res,
tzdata\windowsZones.res, tzdata\zoneinfo64.res
```

into a directory, then set it for the current PowerShell session only:

```powershell
$client = "C:\path\to\firebird-client"
$env:PATH = "$client;$env:PATH"
```

The script is preferable because the venv keeps the setting across shells
without modifying the machine environment.

## 3. Ubuntu 26.04 (apt, primary local path)

Only the client library is needed when tests connect to a remote Firebird
server (the scenarios in `tests/config/firebird_scenarios.yaml` do):

```bash
sudo apt-get update
sudo apt-get install -y libfbclient2
```

`libfbclient2` is in the Ubuntu `universe` component. If the package is not
found, enable it first:

```bash
sudo add-apt-repository universe
sudo apt-get update
sudo apt-get install -y libfbclient2
```

If `apt-cache` still cannot find it, search for the current package name:

```bash
apt-cache search firebird
apt-cache search libfbclient
```

The package installs the shared library under the loader path, for example:

```text
/usr/lib/x86_64-linux-gnu/libfbclient.so.2
```

`ctypes.util.find_library('fbclient')` finds it through `ldconfig`; no
`PATH`, no `LD_LIBRARY_PATH`, and no per-venv copy is needed. Every venv on
the machine uses the same library.

### Optional local server or message catalog

The client package is sufficient for remote connections, which is what the
test suite uses. If you need a local Firebird server, install the server
package matching the Ubuntu release:

```bash
apt-cache search '^firebird.*server$'
sudo apt-get install -y firebird3.0-server   # or firebird4.0-server, if offered
```

If connection errors show numeric codes instead of readable messages, install
the matching common package that provides `firebird.msg`:

```bash
apt-cache search '^firebird.*common$'
sudo apt-get install -y firebird3.0-common     # or firebird4.0-common
```

The CLI and test suite do not require either package for remote scenarios.

### Custom Linux client location

If you use an official Linux kit instead of the distribution package, point
`firebird-driver` at the library explicitly for the current process:

```bash
export FIREBIRD_CLIENT_LIBRARY=/opt/firebird/lib/libfbclient.so
python -c "from firebird.driver import load_api; load_api('$FIREBIRD_CLIENT_LIBRARY')"
```

For the test suite, set `LD_LIBRARY_PATH` for that shell instead:

```bash
export LD_LIBRARY_PATH=/opt/firebird/lib:${LD_LIBRARY_PATH:-}
```

## 4. Verify the library

The quickest check does not need a server:

Windows PowerShell:

```powershell
.venv3.14\Scripts\python.exe -c "from firebird.driver import load_api, get_api; load_api(); print(get_api().client_library_name)"
```

Ubuntu:

```bash
.venv3.14/bin/python -c "from firebird.driver import load_api, get_api; load_api(); print(get_api().client_library_name)"
```

The script's `-Check` mode runs the same check for every Windows venv.

### Verify against the live scenarios

`tests/config/firebird_scenarios.yaml` is gitignored, so a worktree does not
have it. Copy it from the main checkout first:

Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force <worktree>\tests\config | Out-Null
Copy-Item <main>\tests\config\firebird_scenarios.yaml <worktree>\tests\config\
```

Ubuntu:

```bash
mkdir -p <worktree>/tests/config
cp <main>/tests/config/firebird_scenarios.yaml <worktree>/tests/config/
```

Then run one live CLI test:

Windows PowerShell:

```powershell
$env:PYTHONPATH = "tests"
.venv3.14\Scripts\python.exe -m pytest `
  tests\rhosocial\activerecord_firebird_test\feature\cli\test_cli_dml.py `
  --scenarios firebird_5 -q
```

Ubuntu:

```bash
PYTHONPATH=tests .venv3.14/bin/python -m pytest \
  tests/rhosocial/activerecord_firebird_test/feature/cli/test_cli_dml.py \
  --scenarios firebird_5 -q
```

A Firebird 5 client connects to the Firebird 6 server as well; the two sides
negotiate the protocol.

## 5. Troubleshooting

| Symptom | Fix |
| --- | --- |
| `The location of Firebird Client Library could not be determined.` | Windows: rerun the script with `-Force`. Ubuntu: install `libfbclient2`. |
| `wrong architecture` or a 32-bit load error | The official Windows kit is x64; use a 64-bit Python and Windows 11 x64. |
| `SHA256 mismatch` on Windows | The download was discarded. Re-run; if it repeats, check the pinned package and hash against the release page. |
| `download failed: 404` on Windows | The `-Package` value must match the release file name, for example `5.0.4.1812-0`. |
| Script reports `pending` | The venv has the client but not `firebird-driver`; install the project into that venv. |
| Script reports `no-library` although `firebird-client` exists | Re-run with `-Force` to rewrite the `.pth` and loader module. |
| Windows venv was recreated | The client lives inside the venv, so re-run the script. |
| Ubuntu `apt` cannot find `libfbclient2` | Enable `universe`, run `apt-get update`, then search `firebird` / `libfbclient`. |
| Ubuntu import fails although `libfbclient.so.2` exists | Check `ldconfig -p \| grep fbclient`; refresh the loader cache with `sudo ldconfig`. |
| Custom Linux install is not found | Set `LD_LIBRARY_PATH` or call `firebird.driver.load_api('/path/libfbclient.so')`. |
| Error text is numeric only | Install the matching `firebird*-common` package for `firebird.msg`. |
| Charset/`intl` errors | Install the package that provides `intl/fbintl.dll` on Windows or the matching `firebird*-common` / server package on Ubuntu. |
| Firebird tests connect locally but not remotely | Check `tests/config/firebird_scenarios.yaml`; this file is not tracked and must be copied into worktrees. |

Do not commit the downloaded client, the venv directories, or a cache
directory into the repository.
