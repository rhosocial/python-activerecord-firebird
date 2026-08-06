# src/rhosocial/activerecord/backend/impl/firebird/mixins/alter_table_modifier.py
"""Firebird-specific ALTER TABLE IF [NOT] EXISTS handling.

Firebird <= 5.0.4 does not support the vendor extensions ``ADD COLUMN
IF NOT EXISTS``, ``DROP COLUMN IF EXISTS`` or ``DROP CONSTRAINT
IF EXISTS`` (native support only lands in the unreleased Firebird 6.0
master). Requesting any of these modifiers raises
``UnsupportedFeatureError``; applications should pre-check
``RDB$RELATION_FIELDS`` / ``RDB$RELATION_CONSTRAINTS`` instead.
"""

from typing import Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


class FirebirdAlterTableModifierMixin:
    """Guards the IF [NOT] EXISTS ALTER TABLE modifiers for Firebird."""

    def supports_add_column_if_not_exists(self) -> bool:
        return False

    def supports_drop_column_if_exists(self) -> bool:
        return False

    def supports_drop_constraint_if_exists(self) -> bool:
        return False

    def format_add_column_action(self, action) -> Tuple[str, tuple]:
        """Format ALTER TABLE ADD COLUMN for Firebird.

        Firebird <= 5.0.4 does not support ``ADD COLUMN IF NOT EXISTS``.
        Guard the modifier and delegate the plain form to the base
        implementation.
        """
        if getattr(action, "if_not_exists", None) is True:
            raise UnsupportedFeatureError(
                self.name,
                "ADD COLUMN IF NOT EXISTS",
                "Firebird <= 5.0.4 does not support IF NOT EXISTS on "
                "ADD COLUMN. Pre-check RDB$RELATION_FIELDS or use "
                "EXECUTE STATEMENT with WHEN ANY DO BEGIN END. Firebird "
                "6.0 (unreleased) will support it natively.",
            )
        return super().format_add_column_action(action)

    def format_drop_column_action(self, action) -> Tuple[str, tuple]:
        """Format ALTER TABLE DROP COLUMN for Firebird.

        Firebird <= 5.0.4 does not support ``DROP COLUMN IF EXISTS``.
        Guard the modifier and delegate the plain form to the base
        implementation.
        """
        if getattr(action, "if_exists", None) is True:
            raise UnsupportedFeatureError(
                self.name,
                "DROP COLUMN IF EXISTS",
                "Firebird <= 5.0.4 does not support IF EXISTS on "
                "DROP COLUMN. Pre-check RDB$RELATION_FIELDS.",
            )
        return super().format_drop_column_action(action)

    def format_drop_table_constraint_action(self, action) -> Tuple[str, tuple]:
        """Format ALTER TABLE DROP CONSTRAINT for Firebird.

        Firebird <= 5.0.4 does not support ``DROP CONSTRAINT IF EXISTS``.
        Guard the modifier and delegate the plain form to the base
        implementation.
        """
        if getattr(action, "if_exists", None) is True:
            raise UnsupportedFeatureError(
                self.name,
                "DROP CONSTRAINT IF EXISTS",
                "Firebird <= 5.0.4 does not support IF EXISTS on "
                "DROP CONSTRAINT. Pre-check RDB$RELATION_CONSTRAINTS.",
            )
        return super().format_drop_table_constraint_action(action)
