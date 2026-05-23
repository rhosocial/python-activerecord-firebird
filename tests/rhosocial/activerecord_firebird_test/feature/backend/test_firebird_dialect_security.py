# tests/rhosocial/activerecord_firebird_test/feature/backend/test_firebird_dialect_security.py
"""
Tests for Firebird dialect SQL injection security.

This module verifies that identifier quoting properly escapes
double-quote characters and prevents SQL injection via breakout.
Firebird also uppercases identifiers to match its default behavior.
"""
import pytest

from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect


@pytest.fixture
def dialect():
    """Create a Firebird test dialect."""
    return FirebirdDialect(version=(4, 0, 0))


def test_format_identifier_normal(dialect):
    """Normal identifier is double-quoted and uppercased."""
    result = dialect.format_identifier("users")
    assert result == '"USERS"'


def test_format_identifier_already_upper(dialect):
    """Already-uppercase identifier is double-quoted."""
    result = dialect.format_identifier("USERS")
    assert result == '"USERS"'


def test_format_identifier_mixed_case(dialect):
    """Mixed-case identifier is uppercased and quoted."""
    result = dialect.format_identifier("UserOrders")
    assert result == '"USERORDERS"'


def test_format_identifier_with_quote(dialect):
    """Identifier with embedded double-quote is properly escaped and uppercased."""
    result = dialect.format_identifier('table"name')
    assert result == '"TABLE""NAME"'


def test_format_identifier_injection_payload(dialect):
    """Identifier with injection payload is safely contained (balanced quotes)."""
    payload = 'users"; DROP TABLE users--'
    result = dialect.format_identifier(payload)
    assert result.count('"') % 2 == 0, f"Unbalanced quotes: {result}"
    assert result == '"USERS""; DROP TABLE USERS--"'


def test_format_identifier_naive_vs_proper_safe(dialect):
    """For safe input with no special chars, naive and proper differ only by case."""
    names = ["users", "orders", "products", "table_1"]
    for name in names:
        naive = f'"{name}"'
        proper = dialect.format_identifier(name)
        # Proper uppercases, naive doesn't — but both have balanced quotes
        assert proper == f'"{name.upper()}"'
        assert proper.count('"') % 2 == 0
        assert naive.count('"') % 2 == 0


def test_format_identifier_naive_vs_proper_malicious(dialect):
    """For malicious input, proper quoting prevents breakout that naive allows."""
    payloads = [
        'x"; DROP TABLE users--',
        'y"; DELETE FROM t--',
    ]
    for payload in payloads:
        naive = f'"{payload}"'
        proper = dialect.format_identifier(payload)

        # Naive produces odd quote count => breakout
        assert naive.count('"') % 2 != 0, \
            f"Naive should unbalance quotes for '{payload}': {naive}"

        # Proper produces even quote count => contained
        assert proper.count('"') % 2 == 0, \
            f"Proper should balance quotes for '{payload}': {proper}"

        # Proper also uppercases
        assert proper == f'"{payload.upper().replace(chr(34), chr(34)+chr(34))}"'


def test_format_identifier_empty_string(dialect):
    """Empty identifier produces empty double quotes."""
    result = dialect.format_identifier("")
    # Firebird uppercases empty string to empty
    assert result == '""'


def test_escape_sql_string_inherited(dialect):
    """Test Firebird inherits _escape_sql_string from base dialect."""
    result = dialect._escape_sql_string("test's value")
    assert result == "test''s value"
