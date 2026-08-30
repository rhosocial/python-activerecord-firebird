#!/bin/bash
# named_procedure.sh - Firebird CLI named-procedure command example

set -e

FIREBIRD_HOST="${FIREBIRD_HOST:-localhost}"
FIREBIRD_PORT="${FIREBIRD_PORT:-3050}"
FIREBIRD_DATABASE="${FIREBIRD_DATABASE:-test.fdb}"
FIREBIRD_USER="${FIREBIRD_USER:-SYSDBA}"
FIREBIRD_PASSWORD="${FIREBIRD_PASSWORD:-masterkey}"

export FIREBIRD_HOST FIREBIRD_PORT FIREBIRD_DATABASE FIREBIRD_USER FIREBIRD_PASSWORD

PYTHON_CMD="python -m rhosocial.activerecord.backend.impl.firebird"

echo "=========================================="
echo "Firebird CLI - named-procedure command examples"
echo "=========================================="

$PYTHON_CMD named-procedure --list rhosocial.activerecord.backend.impl.firebird.examples.named_procedures.order_workflow 2>/dev/null || echo "(No named procedures found)"
$PYTHON_CMD named-connection --list rhosocial.activerecord.backend.impl.firebird.examples.named_connections