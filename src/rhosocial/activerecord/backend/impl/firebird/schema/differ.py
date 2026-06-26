# src/rhosocial/activerecord/backend/impl/firebird/schema/differ.py
"""Firebird schema differ — type-name-based comparison."""

from rhosocial.activerecord.backend.schema.differ import SchemaDiffer


class FirebirdSchemaDiffer(SchemaDiffer):
    """Firebird schema differ.

    Firebird uses BLOB SUB_TYPE, VARCHAR(n) CHAR(n) type names with
    ordinal position sensitivity via RDB$FIELD_POSITION.
    """

    def _columns_equivalent(self, old_col, new_col) -> bool:
        if not super()._columns_equivalent(old_col, new_col):
            return False
        return old_col.ordinal_position == new_col.ordinal_position