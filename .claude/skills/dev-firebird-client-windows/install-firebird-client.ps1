# .claude/skills/dev-firebird-client-windows/install-firebird-client.ps1
#
# Installs the official Firebird Windows x64 client library into this
# repository's virtual environments, so `import firebird.driver` works on a
# machine that has no Firebird server and no system-wide client install.
# See SKILL.md in this directory for when to run it and how to read its output.
#
# Why this is needed
# ------------------
# firebird-driver talks to the server through the native `fbclient.dll`. When
# no explicit path is configured it locates that library with
# `ctypes.util.find_library('fbclient.dll')`, and on Windows `find_library`
# looks only at `PATH`. A fresh venv therefore fails with
#
#     Exception: The location of Firebird Client Library could not be determined.
#
# The upstream remedy is to install the client from an official kit and put it
# on `PATH`. This script does the venv-local version of that: it unpacks the
# client subset of the official Windows kit into `<venv>/firebird-client` and
# registers that directory at interpreter start through a `.pth` in the venv's
# site-packages. Nothing outside the venv is touched, no environment variable
# must be set, and the repository is left unmodified.
#
# What is installed, and why only this
# ------------------------------------
# The official Windows ZIP is a server kit; a client needs far less of it.
# The copied subset is the minimum that a remote connection actually resolves:
#
#   fbclient.dll, ib_util.dll, zlib1.dll   the client itself and its deps
#   firebird.msg                           server error text, not numeric codes
#   msvcp140*.dll, vcruntime140*.dll       the MSVC runtime the client links
#   intl/fbintl.dll                        character sets (UTF8 scenarios)
#   plugins/srp.dll                        SRP authentication (Firebird 3+)
#   plugins/legacy_auth.dll                legacy authentication (older servers)
#   plugins/chacha.dll                     wire encryption (Firebird 4+)
#   tzdata/*                               time zone data (session_time_zone)
#
# `firebird.exe`, the engine, the tooling and the debug symbols are not copied.
#
# Usage
# -----
#   pwsh -File .claude/skills/dev-firebird-client-windows/install-firebird-client.ps1
#   pwsh -File .claude/skills/dev-firebird-client-windows/install-firebird-client.ps1 -Check
#   pwsh -File .claude/skills/dev-firebird-client-windows/install-firebird-client.ps1 -Force
#   pwsh -File .claude/skills/dev-firebird-client-windows/install-firebird-client.ps1 -IncludeWorktrees
#   pwsh -File .claude/skills/dev-firebird-client-windows/install-firebird-client.ps1 -Venv .venv3.15
#   pwsh -File .claude/skills/dev-firebird-client-windows/install-firebird-client.ps1 `
#       -Package 5.0.4.1812-0 -Sha256 <hash>
#
# Parameters
# ----------
#   -Package      Firebird package version, as printed in the download file
#                 name (e.g. 5.0.4.1812-0). The release tag is derived from its
#                 first three components (v5.0.4).
#   -Sha256       Expected SHA256 of the ZIP. Pass an empty string to skip the
#                 check, at the cost of no longer knowing what was installed.
#   -Venv         Venv directories to install into. Default: every `.venv*`
#                 directory under the repository root that holds a Windows
#                 python.exe -- in this repository that means .venv3.14 and/or
#                 .venv3.15, whichever the checkout actually has. Names are not
#                 assumed: any `.venv*` with a Scripts\python.exe is used, so a
#                 checkout with only .venv3.15, or with both, works the same.
#   -IncludeWorktrees
#                 Also install into the venvs of every worktree under
#                 `.worktree/<branch>/`. Useful when running this from the main
#                 checkout, which may have no venv of its own: the branches are
#                 where the venvs usually live.
#   -CacheDir     Where the ZIP and the extraction are kept between runs.
#                 Default: %LOCALAPPDATA%\rhosocial\cache\firebird.
#   -Proxy        Proxy URL for the download. Default: whatever the current
#                 session or the system already provides.
#   -Force        Reinstall even when the client directory already looks right.
#   -Redownload   Fetch the ZIP again even when a cached copy exists.
#   -Check        Report the status of each venv; change nothing.
#
# A venv without firebird-driver still gets the client: the files do nothing on
# their own and are picked up as soon as the driver is installed, which saves a
# second run and avoids the "worked yesterday, broken today" of a venv that was
# recreated from a lock file.
#
# Exit codes: 0 success, 1 install or verification failure, 2 unusable
# environment (wrong platform, no venv, no Python).

[CmdletBinding()]
param(
    [string] $Package = '5.0.4.1812-0',
    [string] $Sha256 = '01E844FCE4D5F53272A76205DBC3A1BA4B782AB8E8EADCD808CDBCCD9CE13B72',
    [string[]] $Venv,
    [string] $CacheDir = (Join-Path $env:LOCALAPPDATA 'rhosocial\cache\firebird'),
    [string] $Proxy,
    [switch] $Force,
    [switch] $Redownload,
    [switch] $Check,
    [switch] $IncludeWorktrees
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Write-Step([string] $Message) { Write-Host "==> $Message" }
function Write-Info([string] $Message) { Write-Host "    $Message" }
function Write-Warn([string] $Message) { Write-Host "    $Message" -ForegroundColor Yellow }
function Fail([string] $Message, [int] $Code = 1) {
    [Console]::Error.WriteLine("install-firebird-client: $Message")
    exit $Code
}

# --------------------------------------------------------------------------
# Preconditions
# --------------------------------------------------------------------------
if ($env:OS -ne 'Windows_NT') {
    Fail "this script installs the Windows client; on other platforms use the system package manager (e.g. libfbclient2)" 2
}
if (-not [Environment]::Is64BitOperatingSystem) {
    Fail "the official x64 client cannot be loaded by a 32-bit Windows" 2
}

# The script lives in <repo>/.claude/skills/<skill>/, and the repository root is
# found by walking up rather than by counting `..`: the same file is run from the
# main checkout and from <repo>/.worktree/<branch>/, which sit at different
# depths relative to it.
$RepositoryRoot = $PSScriptRoot
while ($RepositoryRoot -and -not (Test-Path (Join-Path $RepositoryRoot 'pyproject.toml'))) {
    $parent = Split-Path -Parent $RepositoryRoot
    if ($parent -eq $RepositoryRoot) { $RepositoryRoot = $null; break }
    $RepositoryRoot = $parent
}
if (-not $RepositoryRoot -or -not (Test-Path (Join-Path $RepositoryRoot 'src'))) {
    Fail "could not locate the repository root above $PSScriptRoot (expected a pyproject.toml and src/)" 2
}

# --------------------------------------------------------------------------
# Which venvs
#
# Discovery is by shape, not by name: any `.venv*` holding a Scripts\python.exe.
# The checkout may have .venv3.14, .venv3.15, both, or a future name; the script
# must not care. Worktree venvs are only reached with -IncludeWorktrees, because
# writing into another branch's environment is a side effect the caller should
# ask for.
# --------------------------------------------------------------------------
function Get-MainCheckoutRoot {
    # From a worktree, `.worktree/` belongs to the main checkout, which git can
    # name even though the path differs: --git-common-dir points at the shared
    # .git of the repository the worktree was cut from.
    $common = & git -C $RepositoryRoot rev-parse --path-format=absolute --git-common-dir 2>$null
    if ($LASTEXITCODE -eq 0 -and $common) {
        $candidate = Split-Path -Parent ([string]$common).Trim()
        if ($candidate -and (Test-Path (Join-Path $candidate 'pyproject.toml'))) { return $candidate }
    }
    return $RepositoryRoot
}

function Get-DefaultVenvs {
    $roots = @($RepositoryRoot)
    if ($IncludeWorktrees) {
        $mainRoot = Get-MainCheckoutRoot
        if ($mainRoot -ne $RepositoryRoot) { $roots += $mainRoot }
        $worktreeRoot = Join-Path $mainRoot '.worktree'
        if (Test-Path $worktreeRoot) {
            $roots += @(Get-ChildItem -Path $worktreeRoot -Directory | ForEach-Object { $_.FullName })
        }
    }

    $found = foreach ($root in $roots) {
        Get-ChildItem -Path $root -Directory -Filter '.venv*' -ErrorAction SilentlyContinue |
            Where-Object { Test-Path (Join-Path $_.FullName 'Scripts\python.exe') } |
            ForEach-Object { $_.FullName }
    }
    return @($found | Sort-Object -Unique)
}

if (-not $Venv) {
    # @() matters: a function that finds nothing returns $null through the
    # pipeline, and $null.Count is an error under Set-StrictMode.
    $Venv = @(Get-DefaultVenvs)
    if ($Venv.Count -eq 0) {
        $where = if ($IncludeWorktrees) { "this checkout or any of its worktrees" } else { $RepositoryRoot }
        Fail "no .venv* directory with Scripts\python.exe under $where; create one first (uv venv .venv3.14 --python 3.14 or .venv3.15 --python 3.15)" 2
    }
}
else {
    $Venv = $Venv | ForEach-Object {
        $resolved = if ([IO.Path]::IsPathRooted($_)) { $_ } else { Join-Path $RepositoryRoot $_ }
        if (-not (Test-Path (Join-Path $resolved 'Scripts\python.exe'))) {
            Fail "not a Windows venv (no Scripts\python.exe): $resolved" 2
        }
        (Resolve-Path $resolved).Path
    }
}

# --------------------------------------------------------------------------
# The client subset, and the loader that makes it visible to the venv
#
# The loader is written rather than merely a `.pth` pointing at a path,
# because `.pth` files can only extend sys.path; they cannot put a directory on
# PATH, which is the one thing find_library consults on Windows.
# --------------------------------------------------------------------------
$ClientFiles = @(
    'fbclient.dll', 'ib_util.dll', 'zlib1.dll', 'firebird.msg',
    'msvcp140.dll', 'msvcp140_1.dll', 'vcruntime140.dll', 'vcruntime140_1.dll'
)
$ClientSubdirs = @{
    'intl'    = @('fbintl.dll')
    'plugins' = @('srp.dll', 'legacy_auth.dll', 'chacha.dll')
    'tzdata'  = @('ids.dat', 'metaZones.res', 'timezoneTypes.res', 'windowsZones.res', 'zoneinfo64.res')
}

$LoaderModule = @'
"""Make the Firebird client library visible to this virtual environment.

The official Firebird client kit is unpacked next to this venv in
``<venv>/firebird-client``. ``ctypes.util.find_library`` -- which
``firebird-driver`` uses to locate ``fbclient.dll`` when no explicit path is
configured -- searches ``PATH`` on Windows, so putting the directory on
``PATH`` at interpreter start is enough to make ``import firebird.driver``
work with no environment variables and no per-project settings.

``os.add_dll_directory`` is registered as well, so the client's own
dependencies (the MSVC runtime, ``intl/fbintl.dll``, ``plugins/*.dll``) are
resolved from the same directory.

This module is imported by ``_firebird_client.pth`` in ``site-packages``; it
is inert when the directory is absent.
"""

import os
import sys

CLIENT_DIR = os.path.join(sys.prefix, "firebird-client")


def _activate() -> None:
    if not os.path.isdir(CLIENT_DIR):
        return
    path = os.environ.get("PATH", "")
    if CLIENT_DIR not in path.split(os.pathsep):
        os.environ["PATH"] = CLIENT_DIR + os.pathsep + path
    if hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(CLIENT_DIR)
        except OSError:
            pass


_activate()
'@

$ProbeScript = @'
import ctypes.util
import importlib.util

try:
    # A dotted name whose parent package is absent raises ModuleNotFoundError
    # instead of returning None, which is exactly the "driver not installed"
    # case this probe exists to report.
    spec = importlib.util.find_spec("firebird.driver")
except (ImportError, ValueError):
    spec = None
if spec is None:
    print("NO_DRIVER")
    raise SystemExit(0)
found = ctypes.util.find_library("fbclient.dll")
if not found:
    print("NO_LIBRARY")
    raise SystemExit(0)
import firebird.driver

firebird.driver.load_api()
print("OK " + str(firebird.driver.get_api().client_library_name))
'@

function Get-VenvStatus([string] $VenvPath) {
    $python = Join-Path $VenvPath 'Scripts\python.exe'
    $clientDir = Join-Path $VenvPath 'firebird-client'
    $probe = Join-Path ([IO.Path]::GetTempPath()) ('fbclient_probe_{0}.py' -f ([guid]::NewGuid().ToString('N')))
    try {
        [IO.File]::WriteAllText($probe, ($ProbeScript -replace "`r`n", "`n"))
        $output = & $python $probe 2>&1
        $text = ($output | Out-String).Trim()
        if ($text -like 'OK *') {
            return [pscustomobject]@{ Venv = $VenvPath; State = 'ok'; Detail = $text.Substring(3) }
        }
        if ($text -like 'NO_DRIVER*') {
            return [pscustomobject]@{ Venv = $VenvPath; State = 'no-driver'; Detail = 'firebird-driver is not installed here' }
        }
        if ($text -like 'NO_LIBRARY*') {
            $hint = if (Test-Path $clientDir) { 'client directory present but not on PATH' } else { 'client directory missing' }
            return [pscustomobject]@{ Venv = $VenvPath; State = 'no-library'; Detail = $hint }
        }
        # A traceback: keep the last line, which is the exception itself, so the
        # summary table stays readable and still says what went wrong.
        $lastLine = ($text -split "`r?`n" | Where-Object { $_.Trim() } | Select-Object -Last 1)
        return [pscustomobject]@{ Venv = $VenvPath; State = 'error'; Detail = $lastLine.Trim() }
    }
    finally {
        Remove-Item $probe -Force -ErrorAction SilentlyContinue
    }
}

function Install-Into([string] $VenvPath, [string] $SourceDir, [string] $ClientDir) {
    $sitePackages = Join-Path $VenvPath 'Lib\site-packages'
    if (-not (Test-Path $sitePackages)) {
        Fail "site-packages not found in $VenvPath" 1
    }

    if (Test-Path $ClientDir) { Remove-Item $ClientDir -Recurse -Force }
    New-Item -ItemType Directory -Path $ClientDir -Force | Out-Null

    $copied = 0
    foreach ($name in $ClientFiles) {
        $from = Join-Path $SourceDir $name
        if (-not (Test-Path $from)) { Fail "the kit does not contain $name; is -Package correct?" 1 }
        Copy-Item $from (Join-Path $ClientDir $name) -Force
        $copied++
    }
    foreach ($subdir in $ClientSubdirs.Keys) {
        $target = Join-Path $ClientDir $subdir
        New-Item -ItemType Directory -Path $target -Force | Out-Null
        foreach ($name in $ClientSubdirs[$subdir]) {
            $from = Join-Path (Join-Path $SourceDir $subdir) $name
            if (-not (Test-Path $from)) { Fail "the kit does not contain $subdir/$name; is -Package correct?" 1 }
            Copy-Item $from (Join-Path $target $name) -Force
            $copied++
        }
    }

    # LF regardless of host default: the repository normalises *.py to LF and
    # these files are read by the interpreter, not by a Windows tool.
    [IO.File]::WriteAllText(
        (Join-Path $sitePackages 'firebird_client_path.py'),
        ($LoaderModule -replace "`r`n", "`n"))
    [IO.File]::WriteAllText(
        (Join-Path $sitePackages '_firebird_client.pth'),
        "import firebird_client_path`n")

    return $copied
}

# --------------------------------------------------------------------------
# -Check: report and stop
# --------------------------------------------------------------------------
if ($Check) {
    Write-Step "client status per venv"
    $failed = 0
    foreach ($path in $Venv) {
        $status = Get-VenvStatus $path
        $relative = $path.Replace($RepositoryRoot + '\', '')
        switch ($status.State) {
            'ok' {
                Write-Host ("    {0,-40} ok         {1}" -f $relative, $status.Detail)
            }
            'no-driver' {
                # Not a failure: the client may already be in place and simply
                # have nothing to load it yet.
                $state = if (Test-Path (Join-Path $path 'firebird-client')) { 'pending' } else { 'no-driver' }
                Write-Host ("    {0,-40} {1,-10} {2}" -f $relative, $state, $status.Detail)
            }
            default {
                Write-Host ("    {0,-40} {1,-10} {2}" -f $relative, $status.State, $status.Detail) -ForegroundColor Yellow
                $failed++
            }
        }
    }
    if ($failed -gt 0) { exit 1 }
    exit 0
}

# --------------------------------------------------------------------------
# Acquire the official kit
# --------------------------------------------------------------------------
$ReleaseTag = 'v' + (($Package -split '\.')[0..2] -join '.')
$ZipName = "Firebird-$Package-windows-x64.zip"
$ZipUrl = "https://github.com/FirebirdSQL/firebird/releases/download/$ReleaseTag/$ZipName"
$ZipPath = Join-Path $CacheDir $ZipName
$ExtractDir = Join-Path $CacheDir "extracted-$Package"

New-Item -ItemType Directory -Path $CacheDir -Force | Out-Null

$needDownload = $Redownload -or -not (Test-Path $ZipPath)
if (-not $needDownload -and $Sha256) {
    $actual = (Get-FileHash $ZipPath -Algorithm SHA256).Hash
    if ($actual -ne $Sha256.ToUpperInvariant()) {
        Write-Warn "cached ZIP does not match the expected hash; fetching it again"
        $needDownload = $true
    }
}

if ($needDownload) {
    Write-Step "downloading $ZipName"
    Write-Info $ZipUrl
    # Windows PowerShell 5.1 defaults to TLS 1.0, which GitHub refuses.
    try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch { }
    $splat = @{ Uri = $ZipUrl; OutFile = $ZipPath; UseBasicParsing = $true }
    if ($Proxy) { $splat['Proxy'] = $Proxy }
    $ProgressPreference = 'SilentlyContinue'
    try {
        Invoke-WebRequest @splat
    }
    catch {
        Fail "download failed: $($_.Exception.Message)`n    If the machine needs a proxy, pass -Proxy http://host:port" 1
    }
}
else {
    Write-Step "using cached $ZipName"
}

if ($Sha256) {
    $actual = (Get-FileHash $ZipPath -Algorithm SHA256).Hash
    if ($actual -ne $Sha256.ToUpperInvariant()) {
        Remove-Item $ZipPath -Force -ErrorAction SilentlyContinue
        Fail "SHA256 mismatch for $ZipName`n    expected $($Sha256.ToUpperInvariant())`n    actual   $actual`n    the download was discarded; verify -Package/-Sha256 before retrying" 1
    }
    Write-Info "sha256 verified: $actual"
}
else {
    Write-Warn "no -Sha256 given; the download was not verified"
}

if ($Force -or -not (Test-Path (Join-Path $ExtractDir 'fbclient.dll'))) {
    Write-Step "extracting"
    if (Test-Path $ExtractDir) { Remove-Item $ExtractDir -Recurse -Force }
    New-Item -ItemType Directory -Path $ExtractDir -Force | Out-Null
    Expand-Archive -Path $ZipPath -DestinationPath $ExtractDir -Force
}

# --------------------------------------------------------------------------
# Install
# --------------------------------------------------------------------------
$results = @()
foreach ($path in $Venv) {
    $relative = $path.Replace($RepositoryRoot + '\', '')
    $clientDir = Join-Path $path 'firebird-client'

    $status = Get-VenvStatus $path

    if ($status.State -eq 'ok' -and -not $Force) {
        Write-Step "$relative"
        Write-Info "already installed: $($status.Detail)"
        $results += [pscustomobject]@{ Venv = $relative; State = 'unchanged'; Detail = $status.Detail }
        continue
    }

    if ($status.State -eq 'error') {
        # The interpreter itself did not answer; installing files would only
        # produce a second, less informative failure.
        Write-Step "$relative"
        Write-Warn "the interpreter could not be run: $($status.Detail)"
        $results += [pscustomobject]@{ Venv = $relative; State = 'failed'; Detail = $status.Detail }
        continue
    }

    Write-Step "$relative"
    $count = Install-Into $path $ExtractDir $clientDir
    Write-Info "installed $count client files into firebird-client"

    $after = Get-VenvStatus $path
    if ($after.State -eq 'ok') {
        Write-Info "verified: $($after.Detail)"
        $results += [pscustomobject]@{ Venv = $relative; State = 'installed'; Detail = $after.Detail }
    }
    elseif ($after.State -eq 'no-driver') {
        # Expected for a venv that has the project but not the driver yet: the
        # files are in place and take effect the moment the driver arrives.
        Write-Warn "client installed; firebird-driver is not installed here yet"
        $results += [pscustomobject]@{ Venv = $relative; State = 'pending'; Detail = 'waiting for firebird-driver' }
    }
    else {
        Write-Warn "verification failed: $($after.State) $($after.Detail)"
        $results += [pscustomobject]@{ Venv = $relative; State = 'failed'; Detail = $after.Detail }
    }
}

# --------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------
Write-Step "summary"
foreach ($row in $results) {
    Write-Host ("    {0,-44} {1,-10} {2}" -f $row.Venv, $row.State, $row.Detail)
}

$failed = @($results | Where-Object { $_.State -eq 'failed' })
if ($failed.Count -gt 0) {
    Fail "$($failed.Count) venv(s) failed verification" 1
}
exit 0
