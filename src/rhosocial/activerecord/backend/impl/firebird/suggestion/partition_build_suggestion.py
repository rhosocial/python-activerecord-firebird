# src/rhosocial/activerecord/backend/impl/firebird/suggestion/partition_build_suggestion.py
"""Firebird's partition build suggestion.

Firebird has no table partitioning, so there is no mechanism to suggest for any
strategy. The answer is the explicit "unsupported" state (``operations is
False``), not silence: the caller can report it as unavailable rather than
guessing at SQL the server rejects. Unconditional, consults no probe.
"""

from typing import TYPE_CHECKING

from rhosocial.activerecord.backend.suggestion import PartitionBuildSuggestion

from ._common import FirebirdPartitionSuggestionBase

if TYPE_CHECKING:  # pragma: no cover
    from ._common import PartitionByClause


class FirebirdPartitionBuildSuggestionMixin(FirebirdPartitionSuggestionBase):
    """Answer Firebird's lack of partitioning explicitly at partition build."""

    def suggest_partition_build(
        self, strategy: "PartitionByClause", plan: object
    ) -> PartitionBuildSuggestion:
        return PartitionBuildSuggestion(False)
