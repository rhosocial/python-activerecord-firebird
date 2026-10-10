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
        if Protocol not in getattr(obj, "__mro__", []) or not name.endswith("Support"):
            continue
        if name == "DDLTypeSupport":
            assert obj is dialect_protocols.DataTypeSupport
            continue
        assert name == obj.__name__, f"unexpected protocol alias: {name}"
        discovered[name] = obj
    return discovered


# Generic protocols FirebirdDialect implements.
#
# The core splits naming from rendering, so a DDL protocol is now one per
# statement (CreateTableSupport, DropTableSupport, AlterTableSupport) and a
# naming protocol is one per object kind (TableObjectSupport, ...). Firebird
# declares the per-statement protocols for the kinds it spells and the naming
# protocols for the kinds it persists; a naming protocol being present says the
# dialect can render that object's name, not that it can create one -- the
# capability switches answer that.
FIREBIRD_PROTOCOLS = [
    dialect_protocols.AdvancedGroupingSupport,
    dialect_protocols.AlterDomainSupport,
    dialect_protocols.AlterSequenceSupport,
    dialect_protocols.AlterTableModifierSupport,
    dialect_protocols.AlterTableSupport,
    dialect_protocols.AlterTypeSupport,
    dialect_protocols.ArraySupport,
    dialect_protocols.AutoIncrementColumnSupport,
    dialect_protocols.CTESupport,
    dialect_protocols.CollationSupport,
    dialect_protocols.ColumnAttributeSupport,
    # The column-type table: `FirebirdColumnTypeMixin` answers
    # `suggested_column_types()` for all eighteen common Python types -- five
    # of them deliberately `None`, a decision the partition of the protocol
    # still classifies as "implemented" -- and `suggested_extra_column_types()`
    # with nothing of Firebird's own. The dialect composes the mixin, so the
    # table the model layer reads for a field's annotation is declared here
    # rather than left for another dialect to answer.
    dialect_protocols.ColumnTypeSupport,
    dialect_protocols.CommentSupport,
    dialect_protocols.ConstraintSupport,
    dialect_protocols.CreateDomainSupport,
    dialect_protocols.CreateIndexSupport,
    dialect_protocols.CreateRoutineSupport,
    # CREATE SCHEMA / DROP SCHEMA are declared and every switch is False:
    # Firebird has no schemas, and saying so through the switch is how a
    # caller learns it without an AttributeError.
    dialect_protocols.CreateSchemaSupport,
    dialect_protocols.CreateSequenceSupport,
    dialect_protocols.CreateTableAsSupport,
    dialect_protocols.CreateTableCloneSupport,
    dialect_protocols.CreateTableLikeSupport,
    dialect_protocols.CreateTableSupport,
    dialect_protocols.CreateTableUsingTemplateSupport,
    dialect_protocols.CreateTriggerSupport,
    dialect_protocols.CreateTypeSupport,
    dialect_protocols.CreateViewSupport,
    dialect_protocols.DataTypeSupport,
    dialect_protocols.DateTimeSupport,
    dialect_protocols.DqlOrderSupport,
    dialect_protocols.DropDomainSupport,
    dialect_protocols.DropIndexSupport,
    dialect_protocols.DropRoutineSupport,
    dialect_protocols.DropSchemaSupport,
    dialect_protocols.DropSequenceSupport,
    dialect_protocols.DropTableSupport,
    dialect_protocols.DropTriggerSupport,
    dialect_protocols.DropTypeSupport,
    dialect_protocols.DropViewSupport,
    dialect_protocols.ExplainSupport,
    dialect_protocols.FilterClauseSupport,
    dialect_protocols.FulltextIndexSupport,
    dialect_protocols.GeneratedColumnSupport,
    # The two server-generated-column mechanisms, declared separately. The
    # identity clause is rendered through the core formatter with Firebird's
    # measured probes; the parameterless AUTO_INCREMENT marker is declared
    # with its switch False, so a caller learns the answer by name and the
    # formatter refuses rather than emitting a token the server rejects.
    dialect_protocols.IdentityColumnSupport,
    dialect_protocols.GraphSupport,
    dialect_protocols.ILIKESupport,
    dialect_protocols.IntrospectionSupport,
    dialect_protocols.JSONSupport,
    dialect_protocols.JoinSupport,
    dialect_protocols.LateralJoinSupport,
    dialect_protocols.LockingSupport,
    # Structurally satisfied through the core DDL mixins already in the MRO;
    # every switch answers False, so no materialized-view statement can render.
    dialect_protocols.MaterializedViewSupport,
    dialect_protocols.MergeSupport,
    # Sits at 0 of 3 by design: these are the naming switches, and Firebird
    # answers False for all of them because a database file is the whole
    # namespace. Declaring it is what makes that answer reachable by name.
    dialect_protocols.NamespaceSupport,
    dialect_protocols.OrderedSetAggregationSupport,
    dialect_protocols.PartitionSupport,
    dialect_protocols.QualifyClauseSupport,
    dialect_protocols.ReturningSupport,
    dialect_protocols.SQLFunctionSupport,
    dialect_protocols.SetOperationSupport,
    dialect_protocols.TemporalTableSupport,
    dialect_protocols.TransactionControlSupport,
    dialect_protocols.TruncateSupport,
    dialect_protocols.UpsertSupport,
    dialect_protocols.WildcardSupport,
    dialect_protocols.WindowFunctionSupport,
    # Naming: the object kinds Firebird persists. Materialized views, foreign
    # tables and synonyms are absent on purpose -- Firebird has none, so no
    # statement can reach their formatter.
    dialect_protocols.TypeObjectSupport,
    dialect_protocols.IndexObjectSupport,
    dialect_protocols.RoutineObjectSupport,
    dialect_protocols.SequenceObjectSupport,
    dialect_protocols.TableObjectSupport,
    dialect_protocols.TriggerObjectSupport,
    dialect_protocols.ViewObjectSupport,
]


# Generic protocols FirebirdDialect intentionally does NOT implement.
FIREBIRD_NOT_IMPLEMENTED = [
    # UUID value expressions (generation / nil-max constants / cast) are not
    # implemented yet on this dialect. Listed here so the omission is a
    # recorded decision rather than a gap; move it to the implemented list
    # when the mixin lands.
    dialect_protocols.UUIDSupport,
    # --- Intentional non-support ---
    # Firebird databases are created and dropped outside the connection, so the
    # per-statement database protocols are not composed; FirebirdDatabaseMixin
    # renders Firebird's own CREATE/DROP DATABASE expressions instead.
    dialect_protocols.CreateDatabaseSupport,
    dialect_protocols.AlterDatabaseSupport,
    dialect_protocols.DropDatabaseSupport,
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
    # No PIVOT / UNPIVOT.
    dialect_protocols.PivotSupport,
    # Naming for object kinds Firebird does not persist: no materialized views,
    # no foreign tables, no synonyms. Each of these protocols requires a
    # format_<kind>_object Firebird has no use for, and leaving it unimplemented
    # means a caller holding one of these objects is refused rather than handed
    # a name from a formatter nobody wrote.
    dialect_protocols.MaterializedViewObjectSupport,
    dialect_protocols.ForeignTableObjectSupport,
    dialect_protocols.SynonymObjectSupport,
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
        """Every generic protocol must be classified for Firebird.

        Membership is compared by object identity, not by ``__module__``. The
        filter that used to be here dropped any protocol not defined directly in
        the protocols package, which silently emptied the positive list once the
        core started defining protocols in submodules -- so the partition check
        reported seventy-one protocols as unclassified rather than as already
        listed, and classified nothing at all.
        """
        all_protos = set(get_all_generic_protocols().values())
        positive = set(FIREBIRD_PROTOCOLS)
        negative = set(FIREBIRD_NOT_IMPLEMENTED)
        positive_names = {p.__name__ for p in positive}
        negative_names = {p.__name__ for p in negative}

        overlap = positive_names & negative_names
        assert not overlap, f"Protocols in BOTH lists: {sorted(overlap)}"

        unclassified = all_protos - positive - negative
        assert not unclassified, (
            f"Generic protocols not classified for Firebird: {sorted(p.__name__ for p in unclassified)}. "
            f"Add each to FIREBIRD_PROTOCOLS or FIREBIRD_NOT_IMPLEMENTED."
        )
