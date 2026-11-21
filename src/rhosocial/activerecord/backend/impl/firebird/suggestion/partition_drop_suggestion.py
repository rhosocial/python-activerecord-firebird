# src/rhosocial/activerecord/backend/impl/firebird/suggestion/partition_drop_suggestion.py
"""Firebird's partition drop suggestion.

Firebird has no table partitioning, so there is no drop-partition mechanism to
suggest for any strategy. The answer is the explicit "unsupported" state
(``operations is False``), not silence: the caller can report it as unavailable
rather than guessing at SQL the server rejects. Unconditional, consults no probe.
"""

from typing import TYPE_CHECKING

from rhosocial.activerecord.backend.suggestion import PartitionDropSuggestion

from ._common import FirebirdPartitionSuggestionBase

if TYPE_CHECKING:  # pragma: no cover
    from ._common import PartitionByClause


class FirebirdPartitionDropSuggestionMixin(FirebirdPartitionSuggestionBase):
    """Answer Firebird's lack of partitioning explicitly at partition drop."""

    def suggest_partition_drop(
        self, strategy: "PartitionByClause", plan: object
    ) -> PartitionDropSuggestion:
        return PartitionDropSuggestion(False)
