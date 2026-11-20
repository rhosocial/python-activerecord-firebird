# tests/test_partition_suggestion_contract.py
"""Contract for Firebird's eight partition-lifecycle backend suggestions.

Firebird has no table partitioning and no partition-maintenance module. Every
``supports_*_partitioning`` probe is False, so each ``suggest_partition_<x>``
answers the explicit "unsupported" state (``operations is False``) rather than
staying silent. This module needs no live server -- it only instantiates the
dialect, so it runs with ``--noconftest`` if the root conftest lacks config.
"""

import pytest

from rhosocial.activerecord.backend.dialect.protocols import (
    PartitionAddSuggestionSupport,
    PartitionBuildSuggestionSupport,
    PartitionDropSuggestionSupport,
    PartitionMergeSuggestionSupport,
    PartitionRetentionSuggestionSupport,
    PartitionSplitSuggestionSupport,
    PartitionTableAlterSuggestionSupport,
    PartitionTableDropSuggestionSupport,
)
from rhosocial.activerecord.backend.expression.statements import PartitionStrategy
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.mixins import FirebirdPartitionSuggestionMixin

CASES = [
    ("build", PartitionBuildSuggestionSupport, "suggest_partition_build"),
    ("table_drop", PartitionTableDropSuggestionSupport, "suggest_partition_table_drop"),
    ("table_alter", PartitionTableAlterSuggestionSupport, "suggest_partition_table_alter"),
    ("add", PartitionAddSuggestionSupport, "suggest_partition_add"),
    ("drop", PartitionDropSuggestionSupport, "suggest_partition_drop"),
    ("split", PartitionSplitSuggestionSupport, "suggest_partition_split"),
    ("merge", PartitionMergeSuggestionSupport, "suggest_partition_merge"),
    ("retention", PartitionRetentionSuggestionSupport, "suggest_partition_retention"),
]


def test_dialect_carries_the_mixin():
    assert issubclass(FirebirdDialect, FirebirdPartitionSuggestionMixin)


def test_dialect_satisfies_all_eight_protocols():
    dialect = FirebirdDialect()
    for _name, protocol, _method in CASES:
        assert isinstance(dialect, protocol), protocol.__name__


@pytest.mark.parametrize("name,protocol,method", CASES, ids=[c[0] for c in CASES])
def test_suggestion_is_explicitly_unsupported(name, protocol, method):
    dialect = FirebirdDialect()
    suggestion = getattr(dialect, method)(PartitionStrategy.RANGE, None)
    assert suggestion.operations is False
