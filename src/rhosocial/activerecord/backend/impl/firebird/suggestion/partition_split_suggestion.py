# src/rhosocial/activerecord/backend/impl/firebird/suggestion/partition_split_suggestion.py
"""Firebird's partition split suggestion.

Firebird has no table partitioning, so there is no split-partition mechanism to
suggest for any strategy. The answer is the explicit "unsupported" state
(``operations is False``), not silence: the caller can report it as unavailable
rather than guessing at SQL the server rejects. Unconditional, consults no probe.
"""

from typing import TYPE_CHECKING

from rhosocial.activerecord.backend.suggestion import PartitionSplitSuggestion

from ._common import FirebirdPartitionSuggestionBase

if TYPE_CHECKING:  # pragma: no cover
    from ._common import PartitionStrategy


class FirebirdPartitionSplitSuggestionMixin(FirebirdPartitionSuggestionBase):
    """Answer Firebird's lack of partitioning explicitly at partition split."""

    def suggest_partition_split(
        self, strategy: "PartitionStrategy", plan: object
    ) -> PartitionSplitSuggestion:
        return PartitionSplitSuggestion(False)
