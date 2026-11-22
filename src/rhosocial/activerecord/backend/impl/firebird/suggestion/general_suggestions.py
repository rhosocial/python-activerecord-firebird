# src/rhosocial/activerecord/backend/impl/firebird/suggestion/general_suggestions.py
"""Firebird's general (non-type) suggestion answers."""

from rhosocial.activerecord.backend.suggestion.definitions import (
    ConcatenationFunctionSuggestion,
)
from rhosocial.activerecord.backend.suggestion.protocols import (
    StringConcatenationSuggestionSupport,
)


class FirebirdStringConcatenationSuggestionMixin(StringConcatenationSuggestionSupport):
    """Firebird spells string concatenation with the ``||`` operator.

    ``function=None`` is the protocol's way of saying "use ``||``": the core
    formatter renders ``left || right`` and does not reach for a function name.
    """

    def suggest_concatenation_function(self) -> ConcatenationFunctionSuggestion:
        return ConcatenationFunctionSuggestion(function=None)


__all__ = ["FirebirdStringConcatenationSuggestionMixin"]
