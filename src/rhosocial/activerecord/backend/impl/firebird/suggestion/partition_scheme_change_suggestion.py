# src/rhosocial/activerecord/backend/impl/firebird/suggestion/partition_scheme_change_suggestion.py
"""Firebird's partition-scheme change answer.

Firebird has no table partitioning at all: the Firebird 5.0 Language Reference
``CREATE TABLE`` grammar has no ``PARTITION BY`` clause and ``ALTER TABLE`` has
no partition maintenance operation. Every ``supports_*_partition*`` probe on
this dialect is False, and all eight partition-lifecycle suggestions in this
package answer ``operations is False`` for the same reason.

A scheme change therefore has no real statement or node to return. The answer
is the explicit "unsupported" tri-state, never a fabricated build/drop/alter
chain and never silence that a caller could mistake for "no action".
"""
from __future__ import annotations

from rhosocial.activerecord.backend.suggestion import PartitionSchemeChangeSuggestion

from ._change_points import answer

__all__ = ["FirebirdPartitionSchemeChangeSuggestionMixin"]


class FirebirdPartitionSchemeChangeSuggestionMixin:
    """Answer the partition-scheme-change decision point as unsupported."""

    def suggest_partition_scheme_change(
        self, point: PartitionSchemeChangeSuggestion
    ) -> PartitionSchemeChangeSuggestion:
        """Return ``point`` with ``operations=False`` (unaddressable).

        Firebird's ``CREATE TABLE`` grammar has no ``PARTITION BY`` clause and
        its ``ALTER TABLE`` grammar has no partition maintenance operation. The
        point's old/new partition projections are deliberately not decoded:
        even a perfectly readable declaration has no DDL that could adopt,
        remove or switch a scheme. Delegating to the eight partition suggestions
        would give the same answer; stating it here makes the scheme point
        self-contained.
        """
        return answer(point, False)
