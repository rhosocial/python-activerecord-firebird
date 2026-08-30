#!/bin/bash
# named_expression.sh - Firebird CLI named-expression command example

set -e

FIREBIRD_HOST="${FIREBIRD_HOST:-localhost}"
FIREBIRD_PORT="${FIREBIRD_PORT:-3050}"
FIREBIRD_DATABASE="${FIREBIRD_DATABASE:-test.fdb}"
FIREBIRD_USER="${FIREBIRD_USER:-SYSDBA}"
FIREBIRD_PASSWORD="${FIREBIRD_PASSWORD:-masterkey}"

export FIREBIRD_HOST FIREBIRD_PORT FIREBIRD_DATABASE FIREBIRD_USER FIREBIRD_PASSWORD

PYTHON_CMD="python -m rhosocial.activerecord.backend.impl.firebird"

echo "=========================================="
echo "Firebird CLI - named-expression command examples"
echo "=========================================="

$PYTHON_CMD named-expression --list rhosocial.activerecord.backend.impl.firebird.examples.named_expressions.order_expressions 2>/dev/null || echo "(No named expressions found)"
$PYTHON_CMD named-connection --list rhosocial.activerecord.backend.impl.firebird.examples.named_connections