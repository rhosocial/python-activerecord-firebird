# tests/rhosocial/activerecord_firebird_test/feature/backend/test_firebird_protocol_conformance.py
"""
Tests to verify FirebirdDialect conformance to the generic dialect protocols.

This test ensures:
1. FirebirdDialect implements every *generic* dialect protocol it claims to support.
2. The generic protocols Firebird intentionally does NOT implement are listed
   explicitly, so the omission is a deliberate, tested contract.
3. Every generic protocol is classified into exactly one of the two lists
   (positive / negative), so no protocol silently escapes coverage.

Only protocols defined in ``rhosocial.activerecord.backend.dialect.protocols``
(the generic, backend-agnostic contract) are considered here. Firebird-specific
protocols are covered elsewhere.
"""

import inspect
import sys

if sys.version_info >= (3, 13):
    from typing import get_protocol_members
elif sys.version_info >= (3, 12):
    from typing import _get_protocol_attrs as get_protocol_members

import pytest
from rhosocial.activerecord.backend.dialect import protocols as dialect_protocols
from rhosocial.activerecord.backend.impl.firebird import dialect as firebird_dialect


def get_all_protocol_methods(proto: type) -> set:
    """Extract all public method names from a protocol, including inherited."""
    members = set()
    if sys.version_info >= (3, 13):
        members = get_protocol_members(proto)
    elif sys.version_info >= (3, 12):
        members = get_protocol_members(proto)
    else:
        # Walk MRO to include methods from parent protocols
        for cls in proto.__mro__:
            if cls is object:
                continue
            for name in cls.__dict__:
                if name.startswith("_"):
                    continue
                val = cls.__dict__[name]
                if callable(val) or isinstance(val, (property, classmethod, staticmethod)):
                    members.add(name)
            members.update(k for k in getattr(cls, "__annotations__", {}) if not k.startswith("_"))
    return members


def get_all_generic_protocols() -> dict:
    """Discover every generic dialect protocol defined in protocols.py."""
    from typing import Protocol

    discovered = {}
    for name, obj in inspect.getmembers(dialect_protocols, inspect.isclass):
        if Protocol in getattr(obj, "__mro__", []) and name.endswith("Support"):
            discovered[name] = obj
    return discovered


# Generic protocols FirebirdDialect implements.
FIREBIRD_PROTOCOLS = [
    dialect_protocols.AdvancedGroupingSupport,
    dialect_protocols.AlterTableModifierSupport,
    dialect_protocols.ArraySupport,
    dialect_protocols.AutoIncrementSupport,
    dialect_protocols.CTESupport,
    dialect_protocols.CollationSupport,
    dialect_protocols.ConstraintSupport,
    dialect_protocols.DDLTypeSupport,
    dialect_protocols.ExplainSupport,
    dialect_protocols.FilterClauseSupport,
    dialect_protocols.FunctionSupport,
    dialect_protocols.GeneratedColumnSupport,
    dialect_protocols.GraphSupport,
    dialect_protocols.ILIKESupport,
    dialect_protocols.IndexSupport,
    dialect_protocols.IntrospectionSupport,
    dialect_protocols.JSONSupport,
    dialect_protocols.JoinSupport,
    dialect_protocols.LateralJoinSupport,
    dialect_protocols.LockingSupport,
    dialect_protocols.MergeSupport,
    dialect_protocols.OrderedSetAggregationSupport,
    dialect_protocols.PartitionSupport,
    dialect_protocols.QualifyClauseSupport,
    dialect_protocols.ReturningSupport,
    dialect_protocols.SQLFunctionSupport,
    dialect_protocols.SchemaSupport,
    dialect_protocols.SequenceSupport,
    dialect_protocols.SetOperationSupport,
    dialect_protocols.TableSupport,
    dialect_protocols.TemporalTableSupport,
    dialect_protocols.TransactionControlSupport,
    dialect_protocols.TriggerSupport,
    dialect_protocols.TruncateSupport,
    dialect_protocols.UpsertSupport,
    dialect_protocols.ViewSupport,
    dialect_protocols.WildcardSupport,
    dialect_protocols.WindowFunctionSupport,
]


# Generic protocols FirebirdDialect intentionally does NOT implement.
FIREBIRD_NOT_IMPLEMENTED = [
    # --- Intentional non-support ---
    # Firebird has no SQL/XML functions.
    dialect_protocols.SQLXMLSupport,
    dialect_protocols.SQLXMLParsingSupport,
    dialect_protocols.SQLXMLSerializationSupport,
    dialect_protocols.SQLXMLConstructionSupport,
    dialect_protocols.SQLXMLAggregationSupport,
    dialect_protocols.SQLXMLQueryingSupport,
    # Firebird has no SQL/PGQ property-graph tables (GRAPH_TABLE). It does
    # support the generic graph query/recursive capabilities (GraphSupport).
    dialect_protocols.GraphTableSupport,
]


class TestFirebirdDialectProtocolConformance:
    """Assert FirebirdDialect implements all generic protocols it claims to support."""

    @pytest.fixture
    def dialect(self):
        """Create a FirebirdDialect instance for testing."""
        return firebird_dialect.FirebirdDialect((4, 0, 0))

    @pytest.mark.parametrize("protocol", FIREBIRD_PROTOCOLS)
    def test_implements_protocol(self, dialect, protocol):
        """FirebirdDialect should implement each protocol in FIREBIRD_PROTOCOLS."""
        assert isinstance(dialect, protocol), (
            f"FirebirdDialect does not implement protocol {protocol.__name__}, "
            f"missing methods: {get_all_protocol_methods(protocol) - set(dir(dialect))}"
        )


class TestFirebirdDialectNegativeProtocolConformance:
    """Assert FirebirdDialect does not implement intentionally-unsupported protocols."""

    @pytest.fixture
    def dialect(self):
        return firebird_dialect.FirebirdDialect((4, 0, 0))

    @pytest.mark.parametrize("protocol", FIREBIRD_NOT_IMPLEMENTED)
    def test_does_not_implement_protocol(self, dialect, protocol):
        """FirebirdDialect must NOT implement any protocol in FIREBIRD_NOT_IMPLEMENTED."""
        assert not isinstance(dialect, protocol), (
            f"FirebirdDialect unexpectedly implements {protocol.__name__}. "
            f"If intentional, move it from FIREBIRD_NOT_IMPLEMENTED to FIREBIRD_PROTOCOLS "
            f"(and implement the behaviour fully)."
        )

    def test_positive_and_negative_lists_partition_all_protocols(self):
        """Every generic protocol must be classified for Firebird."""
        all_protos = set(get_all_generic_protocols())
        positive = {p.__name__ for p in FIREBIRD_PROTOCOLS if p.__module__ == dialect_protocols.__name__}
        negative = {p.__name__ for p in FIREBIRD_NOT_IMPLEMENTED}

        overlap = positive & negative
        assert not overlap, f"Protocols in BOTH lists: {sorted(overlap)}"

        unclassified = all_protos - positive - negative
        assert not unclassified, (
            f"Generic protocols not classified for Firebird: {sorted(unclassified)}. "
            f"Add each to FIREBIRD_PROTOCOLS or FIREBIRD_NOT_IMPLEMENTED."
        )
