# tests/rhosocial/activerecord_firebird_test/feature/backend/construct/dialect/test_protocol_conformance.py
"""
Tests to verify FirebirdDialect conformance to the generic dialect protocols.

This test ensures:
1. FirebirdDialect implements every *generic* dialect protocol it claims to support.
2. The generic protocols Firebird intentionally does NOT implement are listed
   explicitly, so the omission is a deliberate, tested contract.
3. Every generic protocol is classified into exactly one of the three lists
   (positive / refused / negative), so no protocol silently escapes coverage.

The introspection surface is four families rather than one protocol. Firebird
answers structure and data profiles; the operational-statistics and
DDL-extraction families are genuinely absent. They are structurally reachable
because the core composition mixin supplies their defaults, so their absence is
recorded as an explicit refusal (every probe ``False``, every formatter raising
``UnsupportedFeatureError``) rather than as a missing attribute.

Protocols defined in ``rhosocial.activerecord.backend.dialect.protocols``
(the generic capability contract) and in
``rhosocial.activerecord.backend.suggestion.protocols`` (the suggestion
contract) are considered here. Firebird-specific protocols are covered elsewhere.
"""

import inspect
import sys
from pathlib import Path

if sys.version_info >= (3, 13):
    from typing import get_protocol_members
elif sys.version_info >= (3, 12):
    from typing import _get_protocol_attrs as get_protocol_members

import pytest
from rhosocial.activerecord.backend.dialect import protocols as dialect_protocols
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.suggestion import protocols as suggestion_protocols
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
        assert name == obj.__name__, f"unexpected protocol alias: {name}"
        discovered[name] = obj
    return discovered


# The four introspection families, split out of the old single
# ``IntrospectionSupport``. Firebird answers the two about declarations and
# rows; the two about measured behaviour and retained text stay absent.
#
# The families are enumerated rather than left implicit so each one is
# classified by name: a family that stops being answered has to move, and a
# family the core adds cannot fall through unnoticed.
FIREBIRD_INTROSPECTION_IMPLEMENTED = [
    dialect_protocols.StructureIntrospectionSupport,
    dialect_protocols.AsyncStructureIntrospectionSupport,
    dialect_protocols.DataProfileIntrospectionSupport,
    dialect_protocols.AsyncDataProfileIntrospectionSupport,
]

# Absent families are *refused*, not unimplemented-by-attribute: core's
# composition mixin still gives the dialect every member, so ``isinstance``
# passes. What makes absence honest is the answer -- ``False`` from each probe
# and an ``UnsupportedFeatureError`` from each formatter -- and that is what
# ``TestIntrospectionFamiliesAreClassifiedHonestly`` holds them to.
FIREBIRD_INTROSPECTION_REFUSED = [
    dialect_protocols.OperationalStatsIntrospectionSupport,
    dialect_protocols.AsyncOperationalStatsIntrospectionSupport,
    dialect_protocols.DdlExtractionIntrospectionSupport,
    dialect_protocols.AsyncDdlExtractionIntrospectionSupport,
]


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
    # The four migration change points: Firebird has native POSITION for one,
    # real ALTER TABLE constraint actions and standalone index statements for
    # two, and no partitioning at all for the last (an explicit False answer).
    suggestion_protocols.ColumnReorderSuggestionSupport,
    suggestion_protocols.TableConstraintChangeSuggestionSupport,
    suggestion_protocols.TableIndexChangeSuggestionSupport,
    suggestion_protocols.PartitionSchemeChangeSuggestionSupport,
    suggestion_protocols.PartitionBuildSuggestionSupport,
    suggestion_protocols.PartitionTableDropSuggestionSupport,
    suggestion_protocols.PartitionTableAlterSuggestionSupport,
    suggestion_protocols.PartitionAddSuggestionSupport,
    suggestion_protocols.PartitionDropSuggestionSupport,
    suggestion_protocols.PartitionSplitSuggestionSupport,
    suggestion_protocols.PartitionMergeSuggestionSupport,
    suggestion_protocols.PartitionRetentionSuggestionSupport,
    dialect_protocols.AdvancedGroupingSupport,
    dialect_protocols.AlterDomainSupport,
    dialect_protocols.AlterSequenceSupport,
    dialect_protocols.AlterTableModifierSupport,
    dialect_protocols.AlterTableSupport,
    dialect_protocols.AlterTypeSupport,
    dialect_protocols.ArraySupport,
    dialect_protocols.AutoIncrementColumnSupport,
    dialect_protocols.DatabaseAssignedColumnSupport,
    *FIREBIRD_INTROSPECTION_IMPLEMENTED,
    dialect_protocols.DDLColumnSupport,
    dialect_protocols.DMLSupport,
    dialect_protocols.DQLSupport,
    dialect_protocols.DatabaseNameSupport,
    dialect_protocols.DateTimeSupport,
    dialect_protocols.ExpressionSupport,
    dialect_protocols.FunctionCallSupport,
    dialect_protocols.LpadSupport,
    dialect_protocols.PredicateSupport,
    dialect_protocols.RelationSourceSupport,
    dialect_protocols.RpadSupport,
    dialect_protocols.SchemaNameSupport,
    dialect_protocols.TrimSupport,
    dialect_protocols.CTESupport,
    dialect_protocols.CollationSupport,
    dialect_protocols.ColumnAttributeSupport,
    # The column-type table: `FirebirdColumnTypeMixin` answers
    # `suggest_column_types().table` for every framework-committed type -- five
    # of them deliberately `None`, a decision the partition of the protocol
    # still classifies as "implemented" -- and `suggest_extra_column_types().table`
    # with nothing of Firebird's own. The dialect composes the mixin, so the
    # table the model layer reads for a field's annotation is declared here
    # rather than left for another dialect to answer.
    suggestion_protocols.ColumnTypeSuggestionSupport,
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
    dialect_protocols.TimestampSupport,
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
    suggestion_protocols.GeneratedValueSuggestionSupport,
    dialect_protocols.GraphSupport,
    dialect_protocols.ILIKESupport,
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
    # The SQL-function catalogue is a suggestion value rather than a switch:
    # ``suggest_functions()`` answers which functions this dialect renders,
    # with the per-name availability built from Firebird's version floors.
    suggestion_protocols.FunctionSuggestionSupport,
    dialect_protocols.SetOperationSupport,
    dialect_protocols.TemporalTableSupport,
    dialect_protocols.TransactionControlSupport,
    dialect_protocols.TruncateSupport,
    dialect_protocols.TransactionalDDLSupport,
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
    # No SQL/PGQ property-graph table naming, and no REPEAT function.
    dialect_protocols.PropertyGraphNameSupport,
    dialect_protocols.RepeatSupport,
    # Naming for object kinds Firebird does not persist: no materialized views,
    # no foreign tables, no synonyms. Each of these protocols requires a
    # format_<kind>_object Firebird has no use for, and leaving it unimplemented
    # means a caller holding one of these objects is refused rather than handed
    # a name from a formatter nobody wrote.
    dialect_protocols.MaterializedViewObjectSupport,
    dialect_protocols.ForeignTableObjectSupport,
    dialect_protocols.SynonymObjectSupport,
]


class TestDialectProtocolConformance:
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


class TestDialectNegativeProtocolConformance:
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

    def test_the_classification_lists_partition_all_protocols(self):
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
        refused = set(FIREBIRD_INTROSPECTION_REFUSED)
        positive_names = {p.__name__ for p in positive}
        negative_names = {p.__name__ for p in negative}
        refused_names = {p.__name__ for p in refused}

        overlap = positive_names & (negative_names | refused_names)
        assert not overlap, f"Protocols in BOTH lists: {sorted(overlap)}"
        assert not (negative_names & refused_names), (
            f"Protocols in both refused and negative lists: "
            f"{sorted(negative_names & refused_names)}"
        )

        unclassified = all_protos - positive - negative - refused
        assert not unclassified, (
            f"Generic protocols not classified for Firebird: {sorted(p.__name__ for p in unclassified)}. "
            f"Add each to FIREBIRD_PROTOCOLS, FIREBIRD_INTROSPECTION_REFUSED or FIREBIRD_NOT_IMPLEMENTED."
        )


class TestIntrospectionFamiliesAreClassifiedHonestly:
    """The four families split out of ``IntrospectionSupport``, classified.

    Structure and data profiles are answered: Firebird reads the ``RDB$``
    catalogue for the first and aggregates the table's rows for the second.
    Operational statistics and DDL extraction are *refused*: there is no
    collector relation on this engine and no statement text to return. Because
    core's composition mixin supplies their members either way, ``isinstance``
    cannot tell those two states apart -- so absence is pinned to the answers
    instead of to the attribute's existence.
    """

    @pytest.fixture
    def dialect(self):
        return firebird_dialect.FirebirdDialect((4, 0, 0))

    @pytest.mark.parametrize("protocol", FIREBIRD_INTROSPECTION_IMPLEMENTED)
    def test_implemented_family_is_structurally_present(self, dialect, protocol):
        assert isinstance(dialect, protocol), (
            f"FirebirdDialect does not answer {protocol.__name__}; missing methods: "
            f"{get_all_protocol_methods(protocol) - set(dir(dialect))}"
        )

    @pytest.mark.parametrize("protocol", FIREBIRD_INTROSPECTION_REFUSED)
    def test_refused_family_says_false_and_refuses_every_formatter(self, dialect, protocol):
        """Absence is explicit: every probe answers ``False``, every formatter refuses."""
        members = get_all_protocol_methods(protocol)
        probes = sorted(name for name in members if name.startswith("supports_"))
        formatters = sorted(name for name in members if name.startswith("format_"))
        assert probes, f"{protocol.__name__} declares no support probe"
        assert formatters, f"{protocol.__name__} declares no formatter"

        for probe in probes:
            assert getattr(dialect, probe)() is False, (
                f"{protocol.__name__}.{probe} must answer False: Firebird does not answer that family"
            )
        for formatter in formatters:
            with pytest.raises(UnsupportedFeatureError):
                getattr(dialect, formatter)(None)


class TestTheBackendOwnAnswersAreTheEffectiveOnes:
    """A backend mixin's method must resolve to a backend class.

    The other checks in this file are about the *declaration*: the mixin
    declares the method, and the protocol declares it too. This one is
    about the *resolution*. A core class that wins the MRO makes the
    backend's implementation dead code, and the answer a caller gets is
    core's rather than the backend's -- so the backend never says what it
    means about itself, and nothing else in the suite notices: the
    declaration is there either way.

    A protocol class is a declaration rather than an implementation (its
    body is ``...``), so a core class may legitimately precede it; only
    the mixins are held to this.
    """

    def test_no_backend_method_is_shadowed_by_a_core_class(self):
        mro = type(firebird_dialect.FirebirdDialect((4, 0, 0))).__mro__
        own = "rhosocial.activerecord.backend.impl.firebird"
        shadowed = []
        for klass in mro:
            if not klass.__module__.startswith(own):
                continue
            if not klass.__name__.endswith("Mixin"):
                continue
            for name in vars(klass):
                if not name.startswith(("format_", "supports_", "get_", "suggest_")):
                    continue
                if not callable(vars(klass)[name]):
                    continue
                winner = next((k for k in mro if name in k.__dict__), None)
                if winner is None or winner.__module__.startswith(own):
                    continue
                shadowed.append(f"{klass.__name__}.{name} -> {winner.__name__}")
        assert not shadowed, (
            "a core class wins these backend methods, so the backend's "
            f"implementation is dead code: {shadowed}"
        )


class TestIntrospectionSplitIsTheCoreOne:
    """Guard the four-family split from this backend's side.

    Three things can regress silently: the old single name can come back as an
    alias, the partition probe can be repointed at the deleted
    ``supports_partition_info``, or this backend can import a local
    re-declaration instead of the core family. Each check below names the
    contract rather than the symptom.
    """

    @pytest.fixture
    def dialect(self):
        return firebird_dialect.FirebirdDialect((4, 0, 0))

    def test_the_old_partition_probe_is_absent(self, dialect):
        assert not hasattr(dialect, "supports_partition_info")
        assert "supports_partition_info" not in dir(type(dialect))

    def test_no_cli_family_map_names_the_old_partition_probe(self):
        from rhosocial.activerecord.backend.impl.firebird.cli import info, introspect

        assert "partitions" not in introspect._TYPE_CAPABILITIES
        assert "supports_partition_info" not in inspect.getsource(introspect)
        assert "supports_partition_info" not in inspect.getsource(info)
        for probe in introspect._TYPE_CAPABILITIES.values():
            assert probe != "supports_partition_info"

    def test_the_partition_switch_resolves_to_the_metadata_probe(self, dialect):
        protocol = dialect_protocols.PartitionSupport
        assert "supports_partition_metadata_introspection" in get_all_protocol_methods(protocol)
        assert "supports_partition_info" not in get_all_protocol_methods(protocol)

        # The answer comes from Firebird's own mixin, not from core's default:
        # a dialect whose switch merely exists would let an implementation of
        # the old probe masquerade as an answer to the metadata question.
        owner = next(
            klass
            for klass in type(dialect).__mro__
            if "supports_partition_metadata_introspection" in klass.__dict__
        )
        assert owner.__module__.startswith("rhosocial.activerecord.backend.impl.firebird")
        assert dialect.supports_partition_metadata_introspection() is False

    def test_the_four_families_import_from_the_new_core_modules(self):
        from rhosocial.activerecord.backend.dialect.protocols.introspect.data_profile import (
            AsyncDataProfileIntrospectionSupport,
            DataProfileIntrospectionSupport,
        )
        from rhosocial.activerecord.backend.dialect.protocols.introspect.ddl_extraction import (
            AsyncDdlExtractionIntrospectionSupport,
            DdlExtractionIntrospectionSupport,
        )
        from rhosocial.activerecord.backend.dialect.protocols.introspect.operational_stats import (
            AsyncOperationalStatsIntrospectionSupport,
            OperationalStatsIntrospectionSupport,
        )
        from rhosocial.activerecord.backend.dialect.protocols.introspect.structure import (
            AsyncStructureIntrospectionSupport,
            StructureIntrospectionSupport,
        )

        expected = [
            (StructureIntrospectionSupport, "structure"),
            (AsyncStructureIntrospectionSupport, "structure"),
            (OperationalStatsIntrospectionSupport, "operational_stats"),
            (AsyncOperationalStatsIntrospectionSupport, "operational_stats"),
            (DataProfileIntrospectionSupport, "data_profile"),
            (AsyncDataProfileIntrospectionSupport, "data_profile"),
            (DdlExtractionIntrospectionSupport, "ddl_extraction"),
            (AsyncDdlExtractionIntrospectionSupport, "ddl_extraction"),
        ]
        for cls, module in expected:
            assert cls is getattr(dialect_protocols, cls.__name__)
            assert cls.__module__ == (
                f"rhosocial.activerecord.backend.dialect.protocols.introspect.{module}"
            ), f"{cls.__name__} must come from core's {module} module, not a local re-declaration"

    def test_the_old_aggregate_names_are_not_exported(self):
        from rhosocial.activerecord.backend.impl.firebird import protocols as firebird_protocols

        for name in ("IntrospectionSupport", "AsyncIntrospectionSupport"):
            assert not hasattr(dialect_protocols, name), f"core still exports the old {name}"
            assert not hasattr(firebird_protocols, name), f"Firebird re-exports the old {name}"

    def test_no_table_state_is_built_with_a_null_partitioning(self):
        """``TableState.partitioning`` is a shape, never ``None``.

        An unpartitioned table must carry an empty ``PartitionState`` whose
        ``scheme`` is ``None`` -- the same answer ``get_partition_state``
        gives. A null ``partitioning`` argument would make the slot say
        "unknown" at the table-state level even though this engine can answer
        it. The needle is assembled so this guard does not match itself.
        """
        root = next(
            parent
            for parent in Path(__file__).resolve().parents
            if (parent / "pyproject.toml").is_file()
        )
        needle = "partitioning=" + "None"
        offenders = []
        for directory in ("src", "tests"):
            for path in sorted((root / directory).rglob("*.py")):
                text = path.read_text(encoding="utf-8")
                for lineno, line in enumerate(text.splitlines(), 1):
                    if needle in line:
                        offenders.append(f"{path}:{lineno}: {line.strip()}")
        assert not offenders, (
            "TableState.partitioning must be a PartitionState (scheme=None for "
            "an unpartitioned table), never None:\n" + "\n".join(offenders)
        )
