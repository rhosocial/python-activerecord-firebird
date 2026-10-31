---
name: dev-firebird-client-windows
description: Prepare the Firebird client library for the Windows + PowerShell development environment, in the main checkout or in any worktree - download the official Firebird Windows x64 kit, install its client subset beside each venv, register it so firebird.driver loads it with no environment variable, and verify against the live scenarios in tests/config/firebird_scenarios.yaml
license: MIT
compatibility: opencode
metadata:
  category: environment
  level: intermediate
  audience: developers
  order: 20
---

# Firebird Client on Windows

Firebird is the one backend whose Python driver talks to a **native** library:
`firebird-driver` binds `fbclient.dll` through ctypes. Nothing is vendored and
nothing is on a typical Windows machine, so a fresh venv fails at the first
connection attempt with

```
Exception: The location of Firebird Client Library could not be determined.
```

This skill installs the official client into the venv and makes the driver find
it. Run it once per venv, or again after a venv is recreated.

## 1. When to run this

Run it when any of these is true:

| Symptom | Where |
| --- | --- |
| `The location of Firebird Client Library could not be determined.` | any `firebird.driver` call |
| `firebird.wrapper` / ctypes load error on connect | importing the backend |
| `tests/config/firebird_scenarios.yaml` exists but every Firebird test errors at connect | `pytest --scenarios firebird_5` |
| A venv was just created or recreated (`uv venv`, `uv sync`, deleting `.venv3.14`) | — |

Do **not** run it on Linux or inside the container: there the client comes from
the distribution package (`libfbclient2`), and the script refuses to run.

## 2. One command

From the checkout or worktree you are working in:

```powershell
pwsh -File .claude/skills/dev-firebird-client-windows/install-firebird-client.ps1
```

It discovers every `.venv*` in the current checkout that has a
`Scripts\python.exe` — in practice `.venv3.14`, `.venv3.15`, or both — and
installs into each. Names are not assumed, so a checkout with only one of them
behaves the same as one with both.

Useful variations:

```powershell
-Check              # report only, change nothing
-Force              # reinstall even if it already looks right
-Venv .venv3.15     # one venv, relative or absolute
-IncludeWorktrees   # also install into every .worktree/<branch>/.venv*
-Proxy http://host:port   # when the machine needs a proxy for GitHub
```

`-IncludeWorktrees` resolves the main checkout through `git rev-parse
--git-common-dir`, so running it **from inside a worktree** still reaches the
other branches' venvs (and the main checkout's, if it has any).

## 3. What it installs, and where

Never into the system, never into `PATH` globally, and never into git:

```
<venv>/firebird-client/                 the official client subset
<venv>/Lib/site-packages/firebird_client_path.py
<venv>/Lib/site-packages/_firebird_client.pth    one line: import firebird_client_path
```

The `.pth` runs at interpreter start and prepends that directory to `PATH`,
which is the only thing `ctypes.util.find_library` consults on Windows, and
registers it with `os.add_dll_directory` for the client's own dependencies. No
environment variable is needed, so `uv run`, `pytest`, and
`python -m rhosocial.activerecord.backend.impl.firebird` all inherit it.

The kit is the official **server** ZIP, but only the client subset is copied
(17 files, ~5.6 MB): `fbclient.dll`, `ib_util.dll`, `zlib1.dll`,
`firebird.msg`, the MSVC runtimes, `intl/fbintl.dll` (character sets),
`plugins/srp.dll` + `legacy_auth.dll` (authentication), `plugins/chacha.dll`
(wire encryption) and `tzdata/`. The engine, tools and debug symbols are not.

Downloads are cached in `%LOCALAPPDATA%\rhosocial\cache\firebird`, verified
against the SHA256 pinned in the script, and re-used on later runs.

## 4. Reading the output

| State | Meaning |
| --- | --- |
| `ok` | driver loaded the client from this venv's `firebird-client` |
| `unchanged` | already installed; nothing to do |
| `installed` | copied and verified in this run |
| `pending` | client in place, but `firebird-driver` is not installed in that venv yet — it will be used as soon as the driver is |
| `failed` | the interpreter could not run, or the client did not load; the detail says which |

Exit codes: `0` success, `1` install/verification failure, `2` wrong platform or
no venv to install into.

## 5. Verify against the live server

The scenarios users of this repository test against are in
`tests/config/firebird_scenarios.yaml` (`firebird_5` on port 19582, `firebird_6`
on 19583, user `SYSDBA`). That directory is gitignored, so a **worktree does not
have it** — copy it from the main checkout before running the suite:

```powershell
New-Item -ItemType Directory -Force <worktree>/tests/config | Out-Null
Copy-Item <main>/tests/config/firebird_scenarios.yaml <worktree>/tests/config/
```

Then a single live test is enough to prove the environment:

```powershell
$env:PYTHONPATH = "tests"
.venv3.14/Scripts/python.exe -m pytest `
  tests/rhosocial/activerecord_firebird_test/feature/backend/test_crud_backend.py::TestCRUDBackend::test_connect `
  --scenarios firebird_5 -q
```

Or, to check the library alone without pytest (this is what `-Check` runs
internally):

```powershell
.venv3.14/Scripts/python.exe -c "from firebird.driver import load_api, get_api; load_api(); print(get_api().client_library_name)"
```

A Firebird 5 client connects to the Firebird 6 server as well; the two sides
negotiate the protocol, so one client install serves both scenarios.

## 6. Troubleshooting

- **`SHA256 mismatch`** — the download was discarded, nothing was installed.
  Re-run; if it repeats, the pinned `-Sha256` and `-Package` disagree with what
  the release actually publishes. Check the file on the download page rather
  than disabling the check.
- **`download failed: 404`** — the `-Package` value must match the file name in
  the release (`5.0.4.1812-0` → `Firebird-5.0.4.1812-0-windows-x64.zip`, tag
  `v5.0.4`).
- **A `scripts/` install was suggested instead** — do not put this script under
  the repository's `scripts/` directory: that path is a whitelist in
  `.gitignore` and only two files are allowed through it. Living under
  `.claude/skills/` is what keeps it trackable.
- **`pending` never becomes `ok`** — `firebird-driver` is not installed in that
  venv; install the project there (`.venv3.14/Scripts/pip`, or `uv pip install
  --python .venv3.14 -e .`).
- **The venv was recreated** — the client lives inside the venv, so re-run this
  skill. That is the trade-off of keeping the repository untouched.
- **`-Check` reports `no-library` although `firebird-client` exists** — the
  `.pth` or `firebird_client_path.py` is missing from that venv; run with
  `-Force` to rewrite both.
