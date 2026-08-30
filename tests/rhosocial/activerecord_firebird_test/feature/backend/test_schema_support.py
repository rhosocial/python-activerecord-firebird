# tests/rhosocial/activerecord_firebird_test/feature/backend/test_schema_support.py
"""Tests for the SchemaSupport capability declared on the Firebird dialect.

Firebird has no schema namespaces: the database file is the entire namespace,
so the umbrella ``supports_schema()`` flag must be False (explicitly declared,
not inherited from the core default).
"""
from rhosocial.activerecord.backend.dialect.protocols import SchemaSupport
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect


class TestSchemaCapability:
    """Umbrella flag and granular schema DDL capability bits."""

    def _dialect(self) -> FirebirdDialect:
        return FirebirdDialect()

    def test_supports_schema_is_false(self):
        assert self._dialect().supports_schema() is False

    def test_implements_schema_support_protocol(self):
        assert isinstance(self._dialect(), SchemaSupport)

    def test_no_schema_ddl_capabilities(self):
        d = self._dialect()
        assert d.supports_create_schema() is False
        assert d.supports_drop_schema() is False
        assert d.supports_schema_if_not_exists() is False
        assert d.supports_schema_if_exists() is False
