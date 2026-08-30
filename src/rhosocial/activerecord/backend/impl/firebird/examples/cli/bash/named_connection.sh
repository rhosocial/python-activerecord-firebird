#!/bin/bash
# named_connection.sh - Firebird CLI named-connection command example

set -e

FIREBIRD_HOST="${FIREBIRD_HOST:-localhost}"
FIREBIRD_PORT="${FIREBIRD_PORT:-3050}"
FIREBIRD_DATABASE="${FIREBIRD_DATABASE:-test.fdb}"
FIREBIRD_USER="${FIREBIRD_USER:-SYSDBA}"
FIREBIRD_PASSWORD="${FIREBIRD_PASSWORD:-masterkey}"

export FIREBIRD_HOST FIREBIRD_PORT FIREBIRD_DATABASE FIREBIRD_USER FIREBIRD_PASSWORD

PYTHON_CMD="python -m rhosocial.activerecord.backend.impl.firebird"

echo "=========================================="
echo "Firebird CLI - named-connection command examples"
echo "=========================================="

$PYTHON_CMD named-connection --list rhosocial.activerecord.backend.impl.firebird.examples.named_connections
$PYTHON_CMD named-connection --show rhosocial.activerecord.backend.impl.firebird.examples.named_connections.local_dev
$PYTHON_CMD named-connection --describe rhosocial.activerecord.backend.impl.firebird.examples.named_connections.local_dev