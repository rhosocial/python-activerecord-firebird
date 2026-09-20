# src/rhosocial/activerecord/backend/impl/firebird/expression/column.py
"""Firebird-specific column definition expressions.

Firebird extends the standard column definition with per-column clauses that
have no generic equivalent:

* ``COMPUTED BY (<expr>)`` — a computed (stored-expression) column.
* ``CHARACTER SET <name>`` — column character set.
* ``COLLATE <name>`` — column collation (Firebird spelling at column level).

These live on ``FirebirdColumnDefinition`` (deriving the generic
``ColumnDefinition``) and are rendered by the Firebird
``format_column_definition`` override; they are declared through
``FirebirdColumnOptions`` (deriving the generic ``ColumnOptions``).
"""

from typing import Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.statements import ColumnDefinition
from rhosocial.activerecord.base.ddl.options import ColumnOptions

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


__all__ = [
    "FirebirdColumnDefinition",
    "FirebirdColumnOptions",
]


class FirebirdColumnDefinition(ColumnDefinition):
    """A Firebird column definition extending the generic one.

    Adds Firebird-only typed attributes: ``computed_by``, ``character_set``
    and ``collation``.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        name: str,
        data_type,
        constraints=None,
        comment: Optional[str] = None,
        generated_expression=None,
        identity: Optional[str] = None,
        identity_start: Optional[int] = None,
        identity_increment: Optional[int] = None,
        identity_clause=None,
        *,
        computed_by: Optional[str] = None,
        character_set: Optional[str] = None,
        collation: Optional[str] = None,
    ):
        super().__init__(
            dialect,
            name,
            data_type,
            constraints=constraints,
            comment=comment,
            generated_expression=generated_expression,
            identity=identity,
            identity_start=identity_start,
            identity_increment=identity_increment,
            identity_clause=identity_clause,
        )
        self.computed_by = computed_by
        self.character_set = character_set
        self.collation = collation


class FirebirdColumnOptions(ColumnOptions):
    """Firebird per-column options declaration."""

    def __init__(
        self,
        *,
        identity_start: Optional[int] = None,
        identity_increment: Optional[int] = None,
        computed_by: Optional[str] = None,
        character_set: Optional[str] = None,
        collation: Optional[str] = None,
    ):
        super().__init__(
            identity_start=identity_start,
            identity_increment=identity_increment,
        )
        self.computed_by = computed_by
        self.character_set = character_set
        self.collation = collation

    def column_definition_class(self):
        """Build a ``FirebirdColumnDefinition`` for these options."""
        return FirebirdColumnDefinition

    def apply_to(self, column) -> None:
        """Transfer the Firebird-only fields onto the column definition."""
        if not isinstance(column, FirebirdColumnDefinition):
            raise TypeError(
                "FirebirdColumnOptions.apply_to requires a FirebirdColumnDefinition, "
                f"got {type(column).__name__}"
            )
        column.computed_by = self.computed_by
        column.character_set = self.character_set
        column.collation = self.collation
