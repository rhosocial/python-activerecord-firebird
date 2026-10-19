# src/rhosocial/activerecord/backend/impl/firebird/mixins/collation.py
"""Firebird collation mixin."""

from typing import TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

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
        left for this hook to vet -- only the name, and the schema.

        The schema is refused by name rather than silently dropped: rendering
        ``COLLATE UNICODE_CI`` for a request that asked for ``PUBLIC.
        UNICODE_CI`` would answer a question the caller did not ask.
        Firebird's expression-level COLLATE takes a single collation
        identifier, so the qualified form is not a spelling this server
        parses -- the refusal names the feature and the alternative.
        """
        if expr.schema is not None:
            raise UnsupportedFeatureError(
                self.name,
                "COLLATE schema qualification",
                suggestion=(
                    "Firebird's COLLATE takes a single collation name, e.g. "
                    "COLLATE UNICODE_CI; a schema-qualified collation is not "
                    "part of this server's grammar"
                ),
            )
        return validate_firebird_collation_name(
            expr.collation_name, getattr(self, "version", None)
        )
