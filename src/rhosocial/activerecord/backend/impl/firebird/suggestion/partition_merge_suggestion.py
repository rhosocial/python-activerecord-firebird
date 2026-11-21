# src/rhosocial/activerecord/backend/impl/firebird/suggestion/partition_merge_suggestion.py
"""Firebird's partition merge suggestion.

Firebird has no table partitioning, so there is no merge-partition mechanism to
suggest for any strategy. The answer is the explicit "unsupported" state
(``operations is False``), not silence: the caller can report it as unavailable
rather than guessing at SQL the server rejects. Unconditional, consults no probe.
"""

from typing import TYPE_CHECKING

from rhosocial.activerecord.backend.suggestion import PartitionMergeSuggestion

from ._common import FirebirdPartitionSuggestionBase

if TYPE_CHECKING:  # pragma: no cover
    from ._common import PartitionStrategy


class FirebirdPartitionMergeSuggestionMixin(FirebirdPartitionSuggestionBase):
    """Answer Firebird's lack of partitioning explicitly at partition merge."""

    def suggest_partition_merge(
        self, strategy: "PartitionStrategy", plan: object
    ) -> PartitionMergeSuggestion:
        return PartitionMergeSuggestion(False)
