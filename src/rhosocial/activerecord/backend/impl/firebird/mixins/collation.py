# src/rhosocial/activerecord/backend/impl/firebird/mixins/collation.py
"""Firebird collation mixin."""

from typing import TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from ..collation import validate_firebird_collation_name

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.collation import CollateExpression


class FirebirdCollationMixin:

    def supports_collate_expression(self) -> bool:
        """Firebird supports expression-level COLLATE."""
        return True

    def validate_collation_name(self, expr: "CollateExpression") -> str:
        """Validate Firebird collation names and return their SQL representation."""
        if expr.collation_options:
            unsupported = ", ".join(sorted(expr.collation_options))
            raise UnsupportedFeatureError(self.name, f"COLLATE options: {unsupported}")
        return validate_firebird_collation_name(expr.collation_name, getattr(self, "version", None))
