# tests/rhosocial/activerecord_firebird_test/feature/backend/test_identifier_quoting.py
"""
Tests for FirebirdDialect identifier quoting and reserved word detection.

Covers format_identifier with need_quote=True/False, internal quote escaping,
reserved word detection (case-insensitive), IdentifierQuotingWarning emission,
and balanced-quote security guarantees.
"""
import pytest

from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.warnings import IdentifierQuotingWarning


class TestFirebirdIdentifierQuoting:
    """Test FirebirdDialect format_identifier and reserved words."""

    def test_format_identifier_default_double_quote_and_uppercase(self):
        d = FirebirdDialect()
        assert d.format_identifier("users") == '"USERS"'

    def test_format_identifier_need_quote_false_no_uppercase(self):
        d = FirebirdDialect()
        assert d.format_identifier("users", need_quote=False) == "users"

    def test_format_identifier_escapes_internal_quotes(self):
        d = FirebirdDialect()
        assert d.format_identifier('my"table') == '"MY""TABLE"'

    def test_format_identifier_need_quote_false_no_escaping(self):
        d = FirebirdDialect()
        assert d.format_identifier('my"table', need_quote=False) == 'my"table'

    def test_reserved_words_is_frozenset(self):
        d = FirebirdDialect()
        assert isinstance(d.reserved_words, frozenset)

    def test_is_reserved_word_case_insensitive(self):
        d = FirebirdDialect()
        assert d.is_reserved_word("SELECT") is True
        assert d.is_reserved_word("select") is True

    def test_is_reserved_word_non_reserved(self):
        d = FirebirdDialect()
        assert d.is_reserved_word("users") is False

    def test_reserved_word_warning_emitted(self):
        d = FirebirdDialect()
        with pytest.warns(IdentifierQuotingWarning, match="select"):
            d.format_identifier("select", need_quote=False)

    def test_balanced_quotes_security(self):
        d = FirebirdDialect()
        for ident in ["users", 'my"table', 'a""b']:
            result = d.format_identifier(ident)
            assert result.count('"') % 2 == 0, f"Unbalanced quotes: {result}"
