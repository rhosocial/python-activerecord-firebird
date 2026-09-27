# tests/rhosocial/activerecord_firebird_test/feature/backend/test_firebird_column_definition.py
"""Tests for the Firebird-specific column definition expressions."""

import pytest

from rhosocial.activerecord.backend.expression import ColumnDefinition
from rhosocial.activerecord.backend.expression.types import VarCharType
from rhosocial.activerecord.backend.impl.firebird import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.expression import (
    FirebirdColumnDefinition,
    FirebirdColumnOptions,
)


@pytest.fixture
def dialect():
    return FirebirdDialect((5, 0, 0))


def test_derives_generic_column_definition():
    assert ColumnDefinition in FirebirdColumnDefinition.__mro__


def test_character_set_and_collation(dialect):
    sql, _ = FirebirdColumnDefinition(
        dialect, "x", VarCharType(dialect, length=20),
        character_set="UTF8", collation="UNICODE",
    ).to_sql()
    assert sql == '"X" VARCHAR(20) CHARACTER SET UTF8 COLLATE UNICODE'


def test_computed_by(dialect):
    sql, _ = FirebirdColumnDefinition(
        dialect, "x", VarCharType(dialect, length=20), computed_by="UPPER(name)"
    ).to_sql()
    assert "COMPUTED BY (UPPER(name))" in sql


def test_generic_column_still_renders_on_firebird(dialect):
    generic = ColumnDefinition(dialect, "x", VarCharType(dialect, length=20))
    sql, _ = generic.to_sql()
    assert sql == '"X" VARCHAR(20)'


def test_options_select_firebird_column_class():
    assert FirebirdColumnOptions(character_set="UTF8").column_definition_class() is (
        FirebirdColumnDefinition
    )


def test_options_apply_to(dialect):
    options = FirebirdColumnOptions(character_set="UTF8", collation="UNICODE")
    col = FirebirdColumnDefinition(dialect, "c", VarCharType(dialect, length=10))
    options.apply_to(col)
    assert col.character_set == "UTF8"
    assert col.collation == "UNICODE"


def test_options_apply_to_rejects_generic_column(dialect):
    options = FirebirdColumnOptions(character_set="UTF8")
    generic = ColumnDefinition(dialect, "c", VarCharType(dialect, length=10))
    with pytest.raises(TypeError, match="FirebirdColumnDefinition"):
        options.apply_to(generic)
