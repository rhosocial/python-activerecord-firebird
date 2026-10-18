# src/rhosocial/activerecord/backend/impl/firebird/mixins/ddl_alter_table_modifier.py
"""Firebird-specific ALTER TABLE handling.

Guards the vendor ``IF [NOT] EXISTS`` modifiers: Firebird <= 5.0.4 does
not support ``ADD COLUMN IF NOT EXISTS``, ``DROP COLUMN IF EXISTS`` or
``DROP CONSTRAINT IF EXISTS`` (native support only lands in the
unreleased Firebird 6.0 master). Requesting any of these modifiers
raises ``UnsupportedFeatureError``; applications should pre-check
``RDB$RELATION_FIELDS`` / ``RDB$RELATION_CONSTRAINTS`` instead.

Also renders the Firebird-only ``ALTER COLUMN`` identity / ordering
clauses that the core ``DDLColumnMixin`` does not know about:
``SET GENERATED``, ``RESTART [WITH]``, ``SET INCREMENT``, ``DROP
IDENTITY`` (Firebird 3.0+) and ``POSITION`` (Firebird 4.0+).
"""

from typing import Any, Tuple

from .version_boundaries import _norm_version
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


class FirebirdAlterTableModifierMixin:
    """Guards ALTER TABLE modifiers and renders identity ALTER COLUMN clauses."""

    def supports_add_column_if_not_exists(self) -> bool:
        return False

    def supports_drop_column_if_exists(self) -> bool:
        return False

    def supports_drop_constraint_if_exists(self) -> bool:
        """False: Firebird has no ``DROP CONSTRAINT IF EXISTS``.

        Measured on Firebird 5.0.4, against a real constraint on
        ``ALTER TABLE ... DROP CONSTRAINT IF EXISTS <name>``::

            -104: Token unknown - line 1, column 39 -EXISTS

        Refused at the ``EXISTS`` token, so there is nothing to catch and no
        idempotent spelling of the drop at all -- a caller that wants one has
        to pre-check ``RDB$RELATION_CONSTRAINTS`` or use ``EXECUTE STATEMENT``.

        Worth keeping in view next to the 2026-10-11 cross-backend table:
        MariaDB, PostgreSQL, SQL Server and ClickHouse all have this form and
        all turn a missing constraint into a silent success; MySQL has neither
        the form nor a catchable code.  Firebird is in the MySQL position -- the
        statement never parses -- which is why ``format_drop_table_constraint_
        action`` below raises by name instead of letting the statement fail at
        the server.

        The same value is repeated on
        :class:`~.FirebirdConstraintMixin.supports_drop_constraint_if_exists`, so
        the whole constraint contract can be read in one place; the two are
        asserted to agree in ``test_firebird_constraint_switches.py``.
        """
        return False

    def format_add_column_action(self, action: Any) -> Tuple[str, tuple]:
        """Format ALTER TABLE ADD COLUMN for Firebird.

        Firebird <= 5.0.4 does not support ``ADD COLUMN IF NOT EXISTS``.
        Guard the modifier and delegate the plain form to the base
        implementation.
        """
        # ``if_not_exists`` is AddColumnAction's declared field; the guard
        # reads it under its own name rather than probing for it.
        if action.if_not_exists is True:
            raise UnsupportedFeatureError(
                self.name,
                "ADD COLUMN IF NOT EXISTS",
                "Firebird <= 5.0.4 does not support IF NOT EXISTS on "
                "ADD COLUMN. Pre-check RDB$RELATION_FIELDS or use "
                "EXECUTE STATEMENT with WHEN ANY DO BEGIN END. Firebird "
                "6.0 (unreleased) will support it natively.",
            )
        return super().format_add_column_action(action)

    def format_drop_column_action(self, action: Any) -> Tuple[str, tuple]:
        """Format ALTER TABLE DROP COLUMN for Firebird.

        Firebird <= 5.0.4 does not support ``DROP COLUMN IF EXISTS``.
        Guard the modifier and delegate the plain form to the base
        implementation.
        """
        # ``if_exists`` is DropColumnAction's declared field; the guard
        # reads it under its own name rather than probing for it.
        if action.if_exists is True:
            raise UnsupportedFeatureError(
                self.name,
                "DROP COLUMN IF EXISTS",
                "Firebird <= 5.0.4 does not support IF EXISTS on "
                "DROP COLUMN. Pre-check RDB$RELATION_FIELDS.",
            )
        return super().format_drop_column_action(action)

    def format_drop_table_constraint_action(self, action: Any) -> Tuple[str, tuple]:
        """Format ALTER TABLE DROP CONSTRAINT for Firebird.

        Firebird <= 5.0.4 does not support ``DROP CONSTRAINT IF EXISTS``.
        Guard the modifier and delegate the plain form to the base
        implementation.
        """
        # ``if_exists`` is DropTableConstraintAction's declared field; the
        # guard reads it under its own name rather than probing for it.
        if action.if_exists is True:
            raise UnsupportedFeatureError(
                self.name,
                "DROP CONSTRAINT IF EXISTS",
                "Firebird <= 5.0.4 does not support IF EXISTS on "
                "DROP CONSTRAINT. Pre-check RDB$RELATION_CONSTRAINTS.",
            )
        return super().format_drop_table_constraint_action(action)

    def format_set_generated_action(self, action: Any) -> Tuple[str, tuple]:
        """Format ALTER COLUMN ... SET GENERATED {ALWAYS | BY DEFAULT}.

        Identity column clause, available since Firebird 3.0.
        """
        self._check_identity_version("SET GENERATED")
        return (
            f"ALTER COLUMN {self.format_identifier(action.column_name)} "
            f"SET GENERATED {action.generated}",
            (),
        )

    def format_restart_identity_action(self, action: Any) -> Tuple[str, tuple]:
        """Format ALTER COLUMN ... RESTART [WITH value].

        Resets the current value of an identity column; Firebird 3.0+.
        """
        self._check_identity_version("RESTART")
        col = self.format_identifier(action.column_name)
        # ``restart_with`` is RestartIdentity's declared field; the renderer
        # reads it under its own name rather than probing for it.
        if action.restart_with is not None:
            return f"ALTER COLUMN {col} RESTART WITH {action.restart_with}", ()
        return f"ALTER COLUMN {col} RESTART", ()

    def format_set_increment_action(self, action: Any) -> Tuple[str, tuple]:
        """Format ALTER COLUMN ... SET INCREMENT [BY] n.

        Changes the identity increment; Firebird 3.0+.
        """
        self._check_identity_version("SET INCREMENT")
        return (
            f"ALTER COLUMN {self.format_identifier(action.column_name)} "
            f"SET INCREMENT {action.increment}",
            (),
        )

    def format_drop_identity_action(self, action: Any) -> Tuple[str, tuple]:
        """Format ALTER COLUMN ... DROP IDENTITY.

        Converts an identity column to a plain column; Firebird 3.0+.
        """
        self._check_identity_version("DROP IDENTITY")
        return f"ALTER COLUMN {self.format_identifier(action.column_name)} DROP IDENTITY", ()

    def format_set_position_action(self, action: Any) -> Tuple[str, tuple]:
        """Format ALTER COLUMN ... POSITION n.

        Reorders a column within the table; Firebird 4.0+.
        """
        version = getattr(self, 'version', (4, 0, 0))
        if _norm_version(version) < (4, 0, 0):
            raise UnsupportedFeatureError(
                self.name,
                "ALTER COLUMN ... POSITION",
                "Firebird 4.0 or later is required for column POSITION reordering.",
            )
        return (
            f"ALTER COLUMN {self.format_identifier(action.column_name)} POSITION {action.position}",
            (),
        )

    def _check_identity_version(self, feature: str) -> None:
        """Raise unless the dialect targets Firebird 3.0 or later.

        Identity columns were introduced in Firebird 3.0, so all identity
        ALTER COLUMN clauses are gated on the same version boundary.
        """
        version = getattr(self, 'version', (3, 0, 0))
        if _norm_version(version) < (3, 0, 0):
            raise UnsupportedFeatureError(
                self.name,
                f"ALTER COLUMN ... {feature}",
                "Firebird identity columns require Firebird 3.0 or later.",
            )
