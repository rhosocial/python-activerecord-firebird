# src/rhosocial/activerecord/backend/impl/firebird/expression/alter_table.py
"""Firebird-specific ALTER TABLE ALTER COLUMN action expressions.

These action classes extend the core ``AlterTableAction`` hierarchy so the
generic ``AlterTableExpression`` / ``format_alter_table_statement`` renderer
can drive Firebird-only identity and column-ordering clauses:
  - SET GENERATED {ALWAYS | BY DEFAULT}
  - RESTART [WITH value]
  - SET INCREMENT [BY] n
  - DROP IDENTITY
  - POSITION n

Each action delegates SQL generation to the dialect's ``format_*_action``
method, following the Expression-Dialect separation pattern.
"""

from typing import TYPE_CHECKING, Any, Tuple

from rhosocial.activerecord.backend.expression.statements.ddl_alter import AlterTableAction

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class SetGenerated(AlterTableAction):
    """ALTER TABLE ... ALTER COLUMN ... SET GENERATED {ALWAYS | BY DEFAULT}."""

    action_type = "SET GENERATED"

    def __init__(self, dialect: "SQLDialectBase", column_name: str, generated: str = "BY DEFAULT"):
        super().__init__(dialect)
        self.column_name: str = column_name
        self.generated: str = generated

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_set_generated_action(self)


class RestartIdentity(AlterTableAction):
    """ALTER TABLE ... ALTER COLUMN ... RESTART [WITH value]."""

    action_type = "RESTART IDENTITY"

    def __init__(
        self, dialect: "SQLDialectBase", column_name: str, restart_with: Any = None
    ):
        super().__init__(dialect)
        self.column_name: str = column_name
        self.restart_with: Any = restart_with

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_restart_identity_action(self)


class SetIncrement(AlterTableAction):
    """ALTER TABLE ... ALTER COLUMN ... SET INCREMENT [BY] n."""

    action_type = "SET INCREMENT"

    def __init__(self, dialect: "SQLDialectBase", column_name: str, increment: Any):
        super().__init__(dialect)
        self.column_name: str = column_name
        self.increment: Any = increment

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_set_increment_action(self)


class DropIdentity(AlterTableAction):
    """ALTER TABLE ... ALTER COLUMN ... DROP IDENTITY."""

    action_type = "DROP IDENTITY"

    def __init__(self, dialect: "SQLDialectBase", column_name: str):
        super().__init__(dialect)
        self.column_name: str = column_name

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_drop_identity_action(self)


class SetPosition(AlterTableAction):
    """ALTER TABLE ... ALTER COLUMN ... POSITION n."""

    action_type = "SET POSITION"

    def __init__(self, dialect: "SQLDialectBase", column_name: str, position: Any):
        super().__init__(dialect)
        self.column_name: str = column_name
        self.position: Any = position

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_set_position_action(self)


__all__ = [
    "SetGenerated",
    "RestartIdentity",
    "SetIncrement",
    "DropIdentity",
    "SetPosition",
]
