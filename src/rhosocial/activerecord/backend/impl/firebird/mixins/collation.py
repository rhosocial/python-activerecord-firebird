# src/rhosocial/activerecord/backend/impl/firebird/mixins/collation.py
"""Firebird collation mixin."""

from typing import TYPE_CHECKING

from ..collation import validate_firebird_collation_name

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.collation import CollateFunction


class FirebirdCollationMixin:

    def supports_collate_expression(self) -> bool:
        """Firebird supports expression-level COLLATE."""
        return True

    def validate_collation_name(self, expr: "CollateFunction") -> str:
        """Validate Firebird collation names and return their SQL representation.

        The options bag this used to reject no longer exists on the core
        class: schema-qualified COLLATE is the only option any backend reads,
        and it travels there as a named parameter, so there is no open set
        left for this hook to vet -- only the name.
        """
        return validate_firebird_collation_name(expr.collation_name, getattr(self, "version", None))
