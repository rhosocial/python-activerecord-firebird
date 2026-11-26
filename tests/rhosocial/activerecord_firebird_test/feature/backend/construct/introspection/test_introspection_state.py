# tests/rhosocial/activerecord_firebird_test/feature/backend/construct/introspection/test_introspection_state.py
"""The neutral object-state API, answered from Firebird's catalogue.

Core's state API asks for shapes the catalogue families never had:
``TableState``, ``PartitionState``, ``IndexState``, ``ConstraintState``,
``SequenceState``, ``DerivedObjectState`` and ``item_exists``. Firebird owns
every row these are read from, so this module pins the two halves -- the
statement each question renders, and the parser that reads its rows.

The cases are offline: the executor is a stand-in returning a row set shaped
like the family's projection. That is deliberate, because every parser reads
a slot with ``row.get(...)`` and a projection that forgot an alias would
otherwise arrive as ``None`` rather than as an error. One family has no
question at all -- partitioning -- and the case for it asserts that no SQL is
executed.
"""

from __future__ import annotations

import asyncio

import pytest
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.introspection.cache import (
    InMemoryIntrospectionCache,
)
from rhosocial.activerecord.backend.introspection.errors import ObjectNotFoundError
from rhosocial.activerecord.backend.introspection.types import ItemKind

from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.introspection.async_introspector import (
    AsyncFirebirdIntrospector,
)
from rhosocial.activerecord.backend.impl.firebird.introspection.introspector import (
    FirebirdIntrospector,
)


class _Rows:
    """An executor that answers with a canned row set and records the SQL."""

    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        return list(self.rows)


class _FoldedOnlyRows(_Rows):
    """Answers only the folded catalogue spelling, as a real server does."""

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        return list(self.rows) if params == ("ORDERS",) else []


class _AsyncRows(_Rows):
    async def execute(self, sql, params=()):
        self.calls.append((sql, params))
        return list(self.rows)


class _Probe(FirebirdIntrospector):
    """The sync manager, with the catalogue and cache replaced by stand-ins."""

    def __init__(self, rows=None):
        self._backend = type(
            "_B",
            (),
            {
                "dialect": FirebirdDialect(version=(5, 0, 0)),
                "get_cached_server_version": staticmethod(lambda: None),
            },
        )()
        self._executor = _Rows(rows or [])
        self._cache = InMemoryIntrospectionCache()


class _AsyncProbe(AsyncFirebirdIntrospector):
    """The async manager, with the same stand-ins."""

    def __init__(self, rows=None):
        self._backend = type(
            "_B",
            (),
            {
                "dialect": FirebirdDialect(version=(5, 0, 0)),
                "get_cached_server_version": staticmethod(lambda: None),
            },
        )()
        self._executor = _AsyncRows(rows or [])
        self._cache = InMemoryIntrospectionCache()


class _StatementProbe(FirebirdIntrospector):
    """Only what the statement factories read: a dialect."""

    def __init__(self, dialect):
        self._backend = type("_B", (), {"dialect": dialect})()


def _relation(relation_type, description=None, name="ORDERS"):
    return {
        "RDB$RELATION_NAME": name,
        "RDB$VIEW_BLR": None,
        "RDB$RELATION_TYPE": relation_type,
        "RDB$DESCRIPTION": description,
        "RDB$SYSTEM_FLAG": 0,
    }


# ---------------------------------------------------------------------------
# The questions
# ---------------------------------------------------------------------------


class TestStateStatements:
    def test_table_state_asks_for_kind_comment_and_system_flag(self):
        sql, params = (
            _StatementProbe(FirebirdDialect(version=(5, 0, 0)))
            .table_state_statement("ORDERS")
            .to_sql()
        )
        for name in (
            '"RDB$RELATION_NAME"',
            '"RDB$RELATION_TYPE"',
            '"RDB$DESCRIPTION"',
            '"RDB$SYSTEM_FLAG"',
        ):
            assert name in sql
        assert params == ("ORDERS",)

    def test_index_state_reads_the_constraint_the_index_backs(self):
        sql, params = (
            _StatementProbe(FirebirdDialect(version=(5, 0, 0)))
            .index_state_statement("ORDERS")
            .to_sql()
        )
        assert 'AS "CONSTRAINT_NAME"' in sql
        assert params == ("ORDERS",)

    def test_sequence_state_does_not_read_a_value(self):
        """``SequenceState`` is the declaration; ``GEN_ID`` is another question."""
        sql, params = (
            _StatementProbe(FirebirdDialect(version=(5, 0, 0))).sequence_state_statement().to_sql()
        )
        assert '"RDB$GENERATORS"' in sql
        assert "GEN_ID" not in sql.upper()
        assert params == ()


# ---------------------------------------------------------------------------
# Table state
# ---------------------------------------------------------------------------


class TestTableState:
    def test_regular_table_carries_its_comment_and_no_storage_fact(self):
        probe = _Probe([_relation(0, description="orders comment")])
        state = probe.get_table_state("orders")

        assert state.name == "ORDERS"
        assert state.kind == "regular"
        assert state.traits == ()
        assert state.comment == "orders comment"
        assert state.storage.engine is None
        assert state.partitioning is None
        assert state.raw["relation_type"] == 0

    def test_global_temporary_tables_keep_the_on_commit_trait(self):
        for relation_type, trait in (
            (4, "on_commit_preserve_rows"),
            (5, "on_commit_delete_rows"),
        ):
            state = _Probe([_relation(relation_type)]).get_table_state("ORDERS")
            assert state.kind == "global_temporary"
            assert state.traits == (trait,)

    def test_other_relation_kinds_are_named_not_folded_into_regular(self):
        assert _Probe([_relation(1)]).get_table_state("V").kind == "view"
        assert _Probe([_relation(2)]).get_table_state("X").kind == "external"
        assert _Probe([_relation(3)]).get_table_state("M").kind == "monitoring"

    def test_a_missing_relation_is_refused_rather_than_defaulted(self):
        probe = _Probe([])
        with pytest.raises(ObjectNotFoundError):
            probe.get_table_state("ORDERS")

    def test_an_unquoted_name_is_tried_folded_as_well(self):
        """``orders`` must reach the catalogue's ``ORDERS``; a quoted name first."""
        probe = _Probe([_relation(0)])
        probe._executor = _FoldedOnlyRows([_relation(0)])
        state = probe.get_table_state("orders")
        assert state.name == "ORDERS"
        assert [call[1] for call in probe._executor.calls] == [
            ("orders",),
            ("ORDERS",),
        ]


# ---------------------------------------------------------------------------
# Partitioning: the one family with no question
# ---------------------------------------------------------------------------


class TestPartitionState:
    def test_scheme_none_is_the_explicit_unpartitioned_answer(self):
        probe = _Probe([])
        state = probe.get_partition_state("ORDERS")
        assert state.scheme is None
        assert state.bounds == ()
        # The answer is an engine fact, not a catalogue read.
        assert probe._executor.calls == []

    def test_a_named_namespace_is_still_refused(self):
        with pytest.raises(UnsupportedFeatureError, match="schema-scoped introspection"):
            _Probe([]).get_partition_state("ORDERS", schema="sales")


# ---------------------------------------------------------------------------
# Index states
# ---------------------------------------------------------------------------


class TestIndexStates:
    def test_segments_are_grouped_and_inactive_means_unusable(self):
        rows = [
            {
                "INDEX_NAME": "IDX_ORDERS_PLACED_AT",
                "UNIQUE_FLAG": 0,
                "INACTIVE": 1,
                "INDEX_TYPE": 0,
                "CONSTRAINT_NAME": None,
                "CONSTRAINT_TYPE": None,
                "FIELD_NAME": "PLACED_AT",
                "FIELD_POSITION": 1,
            },
            {
                "INDEX_NAME": "RDB$PRIMARY7",
                "UNIQUE_FLAG": 1,
                "INACTIVE": 0,
                "INDEX_TYPE": 0,
                "CONSTRAINT_NAME": "PK_ORDERS",
                "CONSTRAINT_TYPE": "PRIMARY KEY",
                "FIELD_NAME": "ID",
                "FIELD_POSITION": 1,
            },
        ]
        states = _Probe(rows).list_index_states("ORDERS")

        assert len(states) == 2
        by_name = {state.name: state for state in states}
        inactive = by_name["IDX_ORDERS_PLACED_AT"]
        primary = by_name["RDB$PRIMARY7"]
        assert inactive.usable is False
        assert inactive.backs_constraint is None
        assert primary.usable is True
        assert primary.unique is True
        assert primary.backs_constraint == "PK_ORDERS"
        assert primary.method == "btree"

    def test_two_segments_of_one_index_are_one_state(self):
        rows = [
            {"INDEX_NAME": "IDX_A", "FIELD_NAME": "A", "FIELD_POSITION": 1},
            {"INDEX_NAME": "IDX_A", "FIELD_NAME": "B", "FIELD_POSITION": 2},
        ]
        state = _Probe(rows).list_index_states("ORDERS")[0]
        assert state.name == "IDX_A"
        assert state.table == "ORDERS"


# ---------------------------------------------------------------------------
# Constraint states and the indexes they own
# ---------------------------------------------------------------------------


def _constraint(name, kind, index_name=None, deferred=None, check_source=None):
    return {
        "CONSTRAINT_NAME": name,
        "CONSTRAINT_TYPE": kind,
        "RELATION_NAME": "ORDERS",
        "DEFERRABLE": "DEFERRABLE" if deferred else "NOT DEFERRABLE",
        "INITIALLY_DEFERRED": deferred or "IMMEDIATE",
        "INDEX_NAME": index_name,
        "CHECK_TRIGGER": "CHECK_" + name if check_source else None,
        "CHECK_SOURCE": check_source,
    }


class TestConstraintStates:
    def test_a_deferred_primary_key_keeps_its_index(self):
        state = _Probe(
            [_constraint("PK_ORDERS", "PRIMARY KEY", "RDB$PRIMARY7", "DEFERRED")]
        ).list_constraint_states("ORDERS")[0]

        assert state.kind == "primary_key"
        assert state.deferred is True
        assert state.backing_index == "RDB$PRIMARY7"
        assert state.validated is True
        assert state.enforced is True
        assert state.disabled is False

    def test_a_check_constraint_has_no_backing_index(self):
        state = _Probe(
            [_constraint("CHK_TOTAL", "CHECK", None, None, "CHECK_SOURCE")]
        ).list_constraint_states("ORDERS")[0]

        assert state.kind == "check"
        assert state.backing_index is None
        assert state.raw["check_source"] == "CHECK_SOURCE"

    def test_duplicate_constraint_states_become_the_owned_indexes(self):
        rows = [
            _constraint("PK_ORDERS", "PRIMARY KEY", "RDB$PRIMARY7"),
            _constraint("CHK_TOTAL", "CHECK", None, None, "CHECK_SOURCE"),
            _constraint("FK_CUSTOMER", "FOREIGN KEY", "IDX_FK_CUSTOMER"),
        ]
        derived = _Probe(rows).list_derived_objects("ORDERS")

        assert [item.name for item in derived] == ["RDB$PRIMARY7", "IDX_FK_CUSTOMER"]
        assert derived[0].kind == "backing_index"
        assert derived[0].owned_by == "PK_ORDERS"
        assert derived[1].owned_by == "FK_CUSTOMER"


# ---------------------------------------------------------------------------
# Sequence states
# ---------------------------------------------------------------------------


class TestSequenceStates:
    def test_an_identity_generator_names_its_owning_column(self):
        rows = [
            {
                "GENERATOR_NAME": "GEN_ORDERS_ID",
                "SYSTEM_FLAG": 1,
                "OWNER_TABLE": "ORDERS",
                "OWNER_COLUMN": "ID",
                "IDENTITY_TYPE": 0,
            },
            {
                "GENERATOR_NAME": "GEN_INVOICE_NO",
                "SYSTEM_FLAG": 0,
                "OWNER_TABLE": None,
                "OWNER_COLUMN": None,
                "IDENTITY_TYPE": None,
            },
        ]
        states = _Probe(rows).list_sequence_states()

        by_name = {state.name: state for state in states}
        assert by_name["GEN_ORDERS_ID"].owned_by == "ORDERS.ID"
        assert by_name["GEN_INVOICE_NO"].owned_by is None
        # RDB$GENERATORS records neither clause; None is "not recorded".
        assert by_name["GEN_INVOICE_NO"].start is None
        assert by_name["GEN_INVOICE_NO"].increment is None


# ---------------------------------------------------------------------------
# item_exists
# ---------------------------------------------------------------------------


class TestItemExists:
    def test_the_one_unnamed_namespace_is_the_empty_name(self):
        assert _Probe([]).item_exists(ItemKind.SCHEMA, "") is True
        assert _Probe([]).item_exists(ItemKind.SCHEMA, "PUBLIC") is False

    def test_a_domain_is_asked_through_its_own_family(self):
        rows = [
            {
                "DOMAIN_NAME": "POSITIVE_INT",
                "FIELD_TYPE": 8,
                "FIELD_SUB_TYPE": 0,
                "NULL_FLAG": 1,
                "SYSTEM_FLAG": 0,
            }
        ]
        probe = _Probe(rows)
        assert probe.item_exists(ItemKind.DOMAIN, "POSITIVE_INT") is True
        assert probe.item_exists(ItemKind.DOMAIN, "NOPE") is False

    def test_a_sequence_is_the_user_generator_the_family_lists(self):
        rows = [
            {
                "GENERATOR_NAME": "GEN_INVOICE_NO",
                "SYSTEM_FLAG": 0,
                "OWNER_TABLE": None,
                "OWNER_COLUMN": None,
                "IDENTITY_TYPE": None,
            }
        ]
        probe = _Probe(rows)
        assert probe.item_exists(ItemKind.SEQUENCE, "GEN_INVOICE_NO") is True
        assert probe.item_exists(ItemKind.SEQUENCE, "NOPE") is False

    def test_a_kind_with_no_catalogue_is_refused_not_answered_false(self):
        with pytest.raises(UnsupportedFeatureError, match="item_exists"):
            _Probe([]).item_exists(ItemKind.TABLESPACE, "USER_SPACE")


# ---------------------------------------------------------------------------
# The family that deliberately has no member
# ---------------------------------------------------------------------------


class TestNoPartitionsFamily:
    def test_the_managers_have_no_legacy_list_partitions(self):
        """``list_partitions`` is gone; ``get_partition_state`` replaced it."""
        from rhosocial.activerecord.backend.introspection.base import (
            AbstractIntrospector,
            AsyncAbstractIntrospector,
        )

        for manager in (
            AbstractIntrospector,
            AsyncAbstractIntrospector,
            FirebirdIntrospector,
            AsyncFirebirdIntrospector,
        ):
            assert not hasattr(manager, "list_partitions")

    def test_the_cli_offers_no_partitions_type(self):
        """Firebird has no partitions, and no CLI type may claim otherwise."""
        from rhosocial.activerecord.backend.impl.firebird.cli.introspect import (
            INTROSPECT_TYPES,
        )

        assert "partitions" not in INTROSPECT_TYPES


# ---------------------------------------------------------------------------
# The async twin
# ---------------------------------------------------------------------------


class TestAsyncState:
    def test_async_answers_are_the_sync_answers(self):
        probe = _AsyncProbe([_relation(5)])
        state = asyncio.run(probe.get_table_state("orders"))
        assert state.kind == "global_temporary"
        assert state.traits == ("on_commit_delete_rows",)

    def test_async_partition_state_runs_no_query(self):
        probe = _AsyncProbe([])
        state = asyncio.run(probe.get_partition_state("ORDERS"))
        assert state.scheme is None
        assert probe._executor.calls == []

    def test_async_twins_share_the_names_and_the_answers(self):
        rows = [
            {
                "INDEX_NAME": "IDX_A",
                "UNIQUE_FLAG": 1,
                "INACTIVE": 0,
                "INDEX_TYPE": 0,
                "CONSTRAINT_NAME": "PK_A",
                "CONSTRAINT_TYPE": "PRIMARY KEY",
                "FIELD_NAME": "A",
                "FIELD_POSITION": 1,
            },
        ]
        probe = _AsyncProbe(rows)
        indexes = asyncio.run(probe.list_index_states("ORDERS"))
        constraints = asyncio.run(probe.list_constraint_states("ORDERS"))
        derived = asyncio.run(probe.list_derived_objects("ORDERS"))
        assert indexes[0].backs_constraint == "PK_A"
        assert constraints[0].kind == "primary_key"
        assert derived[0].name == "IDX_A"

    def test_async_sequence_item_exists(self):
        rows = [
            {
                "GENERATOR_NAME": "GEN_INVOICE_NO",
                "SYSTEM_FLAG": 0,
                "OWNER_TABLE": None,
                "OWNER_COLUMN": None,
                "IDENTITY_TYPE": None,
            }
        ]
        probe = _AsyncProbe(rows)
        assert asyncio.run(probe.item_exists(ItemKind.SEQUENCE, "GEN_INVOICE_NO")) is True
        assert asyncio.run(probe.item_exists(ItemKind.SEQUENCE, "NOPE")) is False
