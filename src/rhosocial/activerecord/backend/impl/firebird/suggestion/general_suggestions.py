# src/rhosocial/activerecord/backend/impl/firebird/suggestion/general_suggestions.py
"""Firebird's general (non-type) suggestion answers."""

from rhosocial.activerecord.backend.suggestion.definitions import (
    ConcatenationFunctionSuggestion,
    CreateTableLayoutSuggestion,
)


class FirebirdCreateTableLayoutSuggestionMixin:
    """Firebird renders neither inline indexes nor inline comments in CREATE TABLE.

    The answer is assembled from the dialect's own capability probes so it cannot
    drift from what the renderer actually accepts: both probes default to False
    on Firebird, which yields a split layout with separate statements.
    """

    def suggest_create_table_layout(self) -> CreateTableLayoutSuggestion:
        inline_index = self.supports_inline_index()
        inline_comment = self.supports_table_comment()
        return CreateTableLayoutSuggestion(
            strategy="single" if inline_index and inline_comment else "split",
            inline_index=inline_index,
            inline_comment=inline_comment,
            state="actions",
        )


class FirebirdStringConcatenationSuggestionMixin:
    """Firebird spells string concatenation with the ``||`` operator.

    ``function=None`` is the protocol's way of saying "use ``||``": the core
    formatter renders ``left || right`` and does not reach for a function name.
    """

    def suggest_concatenation_function(self) -> ConcatenationFunctionSuggestion:
        return ConcatenationFunctionSuggestion(function=None)


__all__ = [
    "FirebirdCreateTableLayoutSuggestionMixin",
    "FirebirdStringConcatenationSuggestionMixin",
]
