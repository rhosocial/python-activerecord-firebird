# src/rhosocial/activerecord/backend/impl/firebird/suggestion/_common.py
"""Shared base for Firebird's partition-lifecycle suggestion mixins.

Firebird has no native table partitioning and no partition-maintenance
mechanism; every ``supports_*_partitioning`` / ``supports_add_partition`` /
``supports_drop_partition`` probe is False (see :class:`FirebirdPartitionMixin`).
Each of the eight ``suggest_partition_<x>`` mixins in this package therefore
answers the explicit "unsupported" state (``operations is False``) rather than
staying silent, so a caller can report partitioning as unavailable instead of
guessing at SQL Firebird would reject.

The one shared type (``PartitionStrategy``) and the common base class live here;
each concrete mixin contributes exactly one ``suggest_partition_<x>`` method and
inherits :class:`FirebirdPartitionSuggestionBase` so the contract is stated in a
single place. Firebird is a pseudo-async backend (firebird-driver has no real
async), so only synchronous suggestions are meaningful; there is no async
counterpart.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from ....expression import PartitionStrategy as PartitionStrategy


class FirebirdPartitionSuggestionBase:
    """Common base for Firebird's eight partition-lifecycle suggestion mixins."""

    __slots__ = ()
