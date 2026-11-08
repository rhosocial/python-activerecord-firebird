# tests/rhosocial/activerecord_firebird_test/feature/backend/introspection/test_introspect_families_cli.py
"""The nine families, as the CLI asks for them.

No server is needed here. What is checked is the wiring the CLI owns: that
each type reaches its introspector method, that NAME and the type-specific
flags arrive as arguments rather than being parsed and dropped, that a
family the connected server refuses is refused, and that a figure the
engine will not compute stays visible instead of being smoothed into a
zero. Whether the answer is right is the introspector's question, and the
live tests carry it.

The stub introspector records one call per run, so a branch that calls two
methods, or calls the right one with a dropped argument, fails here rather
than showing up as a plausible-looking listing.

Six of the nine are gated, not answered: Firebird's catalogue describes
objects rather than a statistics collector, so ``unused-indexes``,
``table-stats``, ``runtime`` and ``index-stats`` -- plus ``ddl`` and the
``dependencies`` family's common switch -- are refused at the capability
question. Their branches are still asserted here, by holding the gate
open, because "the CLI can ask this and is told no" and "the CLI cannot
ask this" are different contracts and only one of them is true.
"""

import argparse
import json
from typing import Optional

import pytest

from rhosocial.activerecord.backend.impl.firebird.cli import introspect as introspect_cli
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.cli.introspect import (
    INTROSPECT_TYPES,
    _TYPE_CAPABILITIES,
)
from rhosocial.activerecord.backend.introspection.types import (
    ColumnDataProfile,
    ColumnValueFrequency,
    DDLStatement,
    JoinCoverage,
)

#: The nine families this change wires, and the switch that gates each.
#: The dialect declares three of them; the rest it declines, and the
#: refusal is the answer this backend gives rather than an empty row.
NEW_FAMILIES = {
    "unused-indexes": "supports_unused_indexes_detection",
    "table-stats": "supports_table_stats",
    "runtime": "supports_runtime_stats",
    "index-stats": "supports_index_stats",
    "rdb-dependencies": "supports_dependency_introspection",
    "ddl": "supports_ddl_extraction",
    "column-profiles": "supports_column_data_profile",
    "value-samples": "supports_column_value_sample",
    "join-coverage": "supports_join_coverage",
}

#: The families that answer for the whole database and take no NAME.
WHOLE_DATABASE_FAMILIES = (
    "unused-indexes",
    "table-stats",
    "runtime",
    "index-stats",
)

#: The version the stub's ``introspect_and_adapt()`` claims. A modern one,
#: so the value sample's row bound renders rather than raising
#: ``DialectNotAdaptedException``.
STUB_SERVER_VERSION = (4, 0, 0)


class _RecordingIntrospector:
    """Records each introspection call, and returns what the test declared.

    ``__getattr__`` is the whole implementation: a test names the method
    once, in the assertion, and a branch that reaches a different one
    fails on the recorded name rather than on an attribute error that
    would hide the typo.
    """

    def __init__(self, results: Optional[dict] = None) -> None:
        self.results = results or {}
        self.calls = []

    def __getattr__(self, name: str):
        def call(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return self.results.get(name)

        return call


class _AsyncRecordingIntrospector(_RecordingIntrospector):
    """The async shape of the same recorder: methods are awaited, calls are not."""

    def __getattr__(self, name: str):
        async def call(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return self.results.get(name)

        return call


def _args(type_: str, name: Optional[str] = None, **overrides) -> argparse.Namespace:
    """The attributes a parsed invocation carries, with sane defaults."""
    values = dict(
        output="json",
        rich_ascii=False,
        type=type_,
        name=name,
        database="/tmp/test_db",
        is_async=False,
        named_connection=None,
        include_system=False,
        column=None,
        right_table=None,
        right_column=None,
        object=None,
        grantee=None,
        constraint_type=None,
    )
    values.update(overrides)
    return argparse.Namespace(**values)


class _BackendStub:
    """A backend that connects, adapts and records nothing else.

    ``dialect`` is the real one so a capability switch answers the way it
    does against a server; ``introspect_and_adapt`` installs a versioned
    copy the way the real backend does, because several formatters raise
    ``DialectNotAdaptedException`` on an unadapted dialect rather than
    guessing a floor.
    """

    dialect = FirebirdDialect()
    _connection = None

    def __init__(self, introspector) -> None:
        self.introspector = introspector

    def connect(self) -> None:
        pass

    def introspect_and_adapt(self) -> None:
        self.dialect = FirebirdDialect(version=STUB_SERVER_VERSION)

    def disconnect(self) -> None:
        pass


class _AsyncBackendStub(_BackendStub):
    async def connect(self) -> None:
        pass

    async def introspect_and_adapt(self) -> None:
        self.dialect = FirebirdDialect(version=STUB_SERVER_VERSION)

    async def disconnect(self) -> None:
        pass


def _run_sync(monkeypatch, introspector, args, gate_open: bool = False) -> None:
    monkeypatch.setattr(
        introspect_cli, "FirebirdBackend", lambda **kw: _BackendStub(introspector)
    )
    monkeypatch.setattr(
        introspect_cli, "resolve_connection_config_from_args", lambda _args: None
    )
    if gate_open:
        # The branch is asserted without the server's answer: the gate is
        # what refuses these families, and it is tested on its own below.
        monkeypatch.setattr(introspect_cli, "_require_capability", lambda *a: None)
    introspect_cli.handle(args)


def _run_async(monkeypatch, introspector, args, gate_open: bool = False) -> None:
    backend = _AsyncBackendStub(introspector)
    monkeypatch.setattr(
        introspect_cli, "resolve_connection_config_from_args", lambda _args: None
    )
    if gate_open:
        monkeypatch.setattr(introspect_cli, "_require_capability", lambda *a: None)

    import asyncio

    asyncio.run(
        introspect_cli._handle_introspect_async(
            args, backend, introspect_cli.create_provider("json")
        )
    )


class TestTheSchemaWideFamilies:
    """The counters and listings describe the database, so NAME is refused."""

    @pytest.mark.parametrize(
        "type_, method",
        [
            ("unused-indexes", "list_unused_indexes"),
            ("table-stats", "list_table_usage_stats"),
            ("runtime", "list_runtime_metrics"),
            ("index-stats", "list_index_usage_stats"),
        ],
    )
    def test_the_family_asks_its_method_for_the_whole_schema(
        self, type_, method, monkeypatch
    ):
        introspector = _RecordingIntrospector({method: []})

        # The gate open because these four are refused by this backend;
        # what is asserted is the branch behind the refusal.
        _run_sync(monkeypatch, introspector, _args(type_), gate_open=True)

        assert introspector.calls == [(method, (), {"schema": None})]

    @pytest.mark.parametrize("type_", WHOLE_DATABASE_FAMILIES)
    def test_a_name_is_refused(self, type_, capsys):
        with pytest.raises(SystemExit) as excinfo:
            introspect_cli._validate_name(_args(type_, "orders"))

        assert excinfo.value.code == 2
        assert "does not take an object name" in capsys.readouterr().err


class TestTheDdlBranch:
    """The schema object, not a name, is what a caller parses."""

    def _statement(self) -> DDLStatement:
        return DDLStatement(
            schema=None,
            object_type="TABLE",
            object_name="ORDERS",
            ddl="CREATE TABLE ORDERS (ID INTEGER)",
            native=True,
        )

    def test_the_table_is_asked_for_by_name(self, monkeypatch):
        introspector = _RecordingIntrospector({"get_ddl_statement": self._statement()})

        _run_sync(monkeypatch, introspector, _args("ddl", "ORDERS"), gate_open=True)

        assert introspector.calls == [
            ("get_ddl_statement", ("ORDERS",), {"object_type": None, "schema": None})
        ]

    def test_a_missing_name_is_an_incomplete_invocation(self, monkeypatch, capsys):
        """A missing required NAME exits 1, like a missing ``--database``.

        ``ddl`` is refused by this backend's gate, so the gate is held open
        to reach the branch's own check: the exit code is the difference
        between "you did not finish the invocation" (1) and "this server
        will not answer that" (2), and only one of them is a defect in the
        request.
        """
        with pytest.raises(SystemExit) as excinfo:
            _run_sync(
                monkeypatch, _RecordingIntrospector({}), _args("ddl"), gate_open=True
            )

        assert excinfo.value.code == 1
        assert "required" in capsys.readouterr().err

    def test_no_ddl_is_an_error_not_an_empty_listing(self, monkeypatch, capsys):
        introspector = _RecordingIntrospector({"get_ddl_statement": None})

        with pytest.raises(SystemExit) as excinfo:
            _run_sync(monkeypatch, introspector, _args("ddl", "ORDERS"), gate_open=True)

        assert excinfo.value.code == 1
        assert "no DDL available" in capsys.readouterr().err


class TestTheColumnProfilesBranch:
    """A column the engine refuses to measure stays in the answer."""

    def _blob_profile(self) -> ColumnDataProfile:
        """The shape a BLOB answers with: nulls and rows, no other figures.

        Firebird refuses ``MIN``, ``MAX`` and ``COUNT(DISTINCT ...)`` on a
        type it cannot compare, at prepare time, so the three slots stay
        ``None``. That is "this engine will not measure that about this
        type", which must not be smoothed into a zero.
        """
        return ColumnDataProfile(
            schema=None,
            table_name="ORDERS",
            column_name="DOC",
            null_fraction=0.6,
            row_count=100,
            source="aggregate",
        )

    def test_the_table_is_asked_for_by_name(self, monkeypatch):
        introspector = _RecordingIntrospector(
            {"list_column_data_profiles": [self._blob_profile()]}
        )

        _run_sync(monkeypatch, introspector, _args("column-profiles", "ORDERS"))

        assert introspector.calls == [
            ("list_column_data_profiles", ("ORDERS",), {"schema": None})
        ]

    def test_the_blob_column_is_not_hidden(self, monkeypatch, capsys):
        introspector = _RecordingIntrospector(
            {"list_column_data_profiles": [self._blob_profile()]}
        )

        _run_sync(monkeypatch, introspector, _args("column-profiles", "ORDERS"))

        rows = json.loads(capsys.readouterr().out)
        assert [row["column_name"] for row in rows] == ["DOC"]

    def test_the_refused_figures_are_null_not_zero(self, monkeypatch, capsys):
        introspector = _RecordingIntrospector(
            {"list_column_data_profiles": [self._blob_profile()]}
        )

        _run_sync(monkeypatch, introspector, _args("column-profiles", "ORDERS"))

        row = json.loads(capsys.readouterr().out)[0]
        assert row["distinct_count"] is None
        assert row["min_value"] is None
        assert row["max_value"] is None

    def test_the_run_says_which_figures_are_not_measured(self, monkeypatch, capsys):
        introspector = _RecordingIntrospector(
            {"list_column_data_profiles": [self._blob_profile()]}
        )

        _run_sync(monkeypatch, introspector, _args("column-profiles", "ORDERS"))

        err = capsys.readouterr().err
        assert "not measured" in err
        assert "DOC" in err

    def test_the_note_is_not_mistaken_for_a_result_row(self, monkeypatch, capsys):
        """The note belongs on stderr; a line on stdout would break every parser."""
        introspector = _RecordingIntrospector(
            {"list_column_data_profiles": [self._blob_profile()]}
        )

        _run_sync(monkeypatch, introspector, _args("column-profiles", "ORDERS"))

        out = capsys.readouterr().out
        assert out.lstrip().startswith("[")

    def test_a_fully_measured_column_says_nothing(self, monkeypatch, capsys):
        measured = ColumnDataProfile(
            table_name="ORDERS",
            column_name="ID",
            null_fraction=0.0,
            distinct_count=100,
            min_value=1,
            max_value=100,
            row_count=100,
            source="aggregate",
        )
        introspector = _RecordingIntrospector(
            {"list_column_data_profiles": [measured]}
        )

        _run_sync(monkeypatch, introspector, _args("column-profiles", "ORDERS"))

        assert "not measured" not in capsys.readouterr().err


class TestTheValueSamplesBranch:
    """A table and a column, and a limit that is not sent unasked."""

    def test_the_table_column_and_limit_reach_the_introspector(self, monkeypatch):
        introspector = _RecordingIntrospector(
            {"sample_column_values": [ColumnValueFrequency(value="a", count=7)]}
        )

        _run_sync(
            monkeypatch,
            introspector,
            _args("value-samples", "ORDERS", column="STATUS"),
        )

        assert introspector.calls == [
            ("sample_column_values", ("ORDERS", "STATUS"), {"schema": None})
        ]

    def test_no_limit_is_sent_when_the_flag_is_omitted(self, monkeypatch):
        introspector = _RecordingIntrospector({"sample_column_values": []})

        _run_sync(
            monkeypatch,
            introspector,
            _args("value-samples", "ORDERS", column="STATUS"),
        )

        # Absent ``--limit`` means absent from the call: the introspector's own
        # signature answers with its own default, and the CLI does not restate
        # it. A number here would fail the day the signature's default moved.
        assert "limit" not in introspector.calls[0][2]

    def test_a_limit_is_forwarded_only_when_the_flag_names_one(self, monkeypatch):
        """The discipline's other half, driven by a hand-built namespace.

        This parser declares no ``--limit``, so the flag cannot reach the CLI
        here; the namespace override is how the five backends that do declare
        it drive the same helper, and it keeps the forwarder honest on this
        backend too rather than leaving the branch permanently one-sided.
        """
        introspector = _RecordingIntrospector({"sample_column_values": []})

        _run_sync(
            monkeypatch,
            introspector,
            _args("value-samples", "ORDERS", column="STATUS", limit=3),
        )

        assert introspector.calls == [
            (
                "sample_column_values",
                ("ORDERS", "STATUS"),
                {"schema": None, "limit": 3},
            )
        ]

    def test_a_missing_table_is_an_incomplete_invocation(self, monkeypatch, capsys):
        with pytest.raises(SystemExit) as excinfo:
            _run_sync(monkeypatch, _RecordingIntrospector({}), _args("value-samples"))

        assert excinfo.value.code == 1
        assert "Table name is required" in capsys.readouterr().err

    def test_a_missing_column_is_an_incomplete_invocation(self, monkeypatch, capsys):
        """The flag check passes (nothing to refuse) and the branch refuses."""
        introspect_cli._refuse_unused_arguments(_args("value-samples", "ORDERS"))

        with pytest.raises(SystemExit) as excinfo:
            _run_sync(
                monkeypatch, _RecordingIntrospector({}), _args("value-samples", "ORDERS")
            )

        assert excinfo.value.code == 1
        assert "--column is required" in capsys.readouterr().err

    def test_the_most_frequent_values_are_printed(self, monkeypatch, capsys):
        introspector = _RecordingIntrospector(
            {"sample_column_values": [ColumnValueFrequency(value="a", count=7)]}
        )

        _run_sync(
            monkeypatch,
            introspector,
            _args("value-samples", "ORDERS", column="STATUS"),
        )

        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["value"] == "a"
        assert payload[0]["count"] == 7


class TestTheJoinCoverageBranch:
    """Four names, both sides of the measurement, in the order they are asked."""

    def _coverage(self) -> JoinCoverage:
        return JoinCoverage(
            left_table="ORDERS",
            left_column="CUSTOMER_ID",
            right_table="CUSTOMERS",
            right_column="ID",
            left_coverage=1.0,
            right_coverage=0.75,
        )

    def test_the_four_names_reach_the_introspector(self, monkeypatch):
        introspector = _RecordingIntrospector(
            {"estimate_join_coverage": self._coverage()}
        )

        _run_sync(
            monkeypatch,
            introspector,
            _args(
                "join-coverage",
                "ORDERS",
                column="CUSTOMER_ID",
                right_table="CUSTOMERS",
                right_column="ID",
            ),
        )

        assert introspector.calls == [
            (
                "estimate_join_coverage",
                ("ORDERS", "CUSTOMER_ID", "CUSTOMERS", "ID"),
                {"schema": None},
            )
        ]

    def test_both_fractions_are_reported(self, monkeypatch, capsys):
        introspector = _RecordingIntrospector(
            {"estimate_join_coverage": self._coverage()}
        )

        _run_sync(
            monkeypatch,
            introspector,
            _args(
                "join-coverage",
                "ORDERS",
                column="CUSTOMER_ID",
                right_table="CUSTOMERS",
                right_column="ID",
            ),
        )

        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["left_coverage"] == 1.0
        assert payload[0]["right_coverage"] == 0.75

    def test_a_missing_right_table_is_an_incomplete_invocation(self, monkeypatch, capsys):
        """One run names every absent flag, rather than the first it met."""
        introspect_cli._refuse_unused_arguments(
            _args("join-coverage", "ORDERS", column="CUSTOMER_ID")
        )

        with pytest.raises(SystemExit) as excinfo:
            _run_sync(
                monkeypatch,
                _RecordingIntrospector({}),
                _args("join-coverage", "ORDERS", column="CUSTOMER_ID"),
            )

        assert excinfo.value.code == 1
        err = capsys.readouterr().err
        assert "--right-table" in err
        assert "--right-column" in err

    def test_an_unmeasurable_pair_is_an_error(self, monkeypatch, capsys):
        """``None`` is "not measured", which is not a zero-overlap answer."""
        introspector = _RecordingIntrospector({"estimate_join_coverage": None})

        with pytest.raises(SystemExit) as excinfo:
            _run_sync(
                monkeypatch,
                introspector,
                _args(
                    "join-coverage",
                    "ORDERS",
                    column="CUSTOMER_ID",
                    right_table="CUSTOMERS",
                    right_column="ID",
                ),
            )

        assert excinfo.value.code == 1
        assert "no coverage could be measured" in capsys.readouterr().err


class TestTheDependenciesBranch:
    """One optional NAME narrows the graph; omitting it asks for all of it."""

    def test_a_named_object_is_asked_for_by_name(self, monkeypatch):
        introspector = _RecordingIntrospector({"list_dependencies": []})

        _run_sync(monkeypatch, introspector, _args("rdb-dependencies", "ORDERS"))

        assert introspector.calls == [("list_dependencies", ("ORDERS",), {})]

    def test_an_unnamed_run_asks_for_the_whole_graph(self, monkeypatch):
        introspector = _RecordingIntrospector({"list_dependencies": []})

        _run_sync(monkeypatch, introspector, _args("rdb-dependencies"))

        assert introspector.calls == [("list_dependencies", (None,), {})]


class TestTheArgumentRules:
    def test_a_flag_the_type_does_not_read_is_refused(self, capsys):
        with pytest.raises(SystemExit) as excinfo:
            introspect_cli._refuse_unused_arguments(_args("tables", column="STATUS"))

        assert excinfo.value.code == 2
        assert "does not take --column" in capsys.readouterr().err

    def test_the_right_hand_flags_belong_to_join_coverage_only(self, capsys):
        with pytest.raises(SystemExit) as excinfo:
            introspect_cli._refuse_unused_arguments(
                _args("value-samples", "ORDERS", column="STATUS", right_table="CUSTOMERS")
            )

        assert excinfo.value.code == 2
        assert "--right-table" in capsys.readouterr().err

    def test_both_families_that_read_a_column_may_be_given_one(self):
        for type_ in ("value-samples", "join-coverage"):
            introspect_cli._refuse_unused_arguments(_args(type_, column="STATUS"))

    def test_a_required_name_is_required_for_the_new_families(self, monkeypatch, capsys):
        for type_ in ("ddl", "column-profiles", "value-samples"):
            with pytest.raises(SystemExit) as excinfo:
                _run_sync(
                    monkeypatch,
                    _RecordingIntrospector({}),
                    _args(type_),
                    gate_open=True,
                )
            assert excinfo.value.code == 1


class TestTheCapabilityGate:
    @pytest.mark.parametrize("type_, switch", list(NEW_FAMILIES.items()))
    def test_a_family_the_server_refuses_exits_two(self, type_, switch, capsys):
        """The gate, not a failed statement, is what answers for a refusal."""
        class _Dialect:
            pass

        setattr(_Dialect, switch, staticmethod(lambda: False))

        class _Backend:
            dialect = _Dialect()

        # Firebird's gate reads (backend, args) -- the reverse of the
        # MySQL spelling -- and a swapped pair fails loudly here rather
        # than silently passing on an unrelated attribute.
        with pytest.raises(SystemExit) as excinfo:
            introspect_cli._require_capability(_Backend(), _args(type_))

        assert excinfo.value.code == 2
        assert "not supported by this server" in capsys.readouterr().err

    @pytest.mark.parametrize(
        "type_",
        ["column-profiles", "value-samples", "join-coverage"],
    )
    def test_the_row_families_are_not_refused(self, type_):
        """These three answer True, so the gate must not refuse them."""
        introspect_cli._require_capability(
            _BackendStub(_RecordingIntrospector()), _args(type_)
        )

    def test_a_stub_without_a_dialect_is_not_refused(self):
        introspect_cli._require_capability(object(), _args("triggers"))

    def test_the_four_operational_families_are_refused_by_this_dialect(self, capsys):
        """Firebird has no statistics collector, and says so at the question."""
        for type_ in WHOLE_DATABASE_FAMILIES:
            with pytest.raises(SystemExit) as excinfo:
                introspect_cli._require_capability(
                    _BackendStub(_RecordingIntrospector()), _args(type_)
                )
            assert excinfo.value.code == 2
            assert "not supported by this server" in capsys.readouterr().err


class TestTheAsyncPath:
    """The second dispatch chain must ask the same question the first one does."""

    @pytest.mark.parametrize(
        "type_, method, args_kwargs, result, expected",
        [
            ("unused-indexes", "list_unused_indexes", {}, [], ((), {"schema": None})),
            ("table-stats", "list_table_usage_stats", {}, [], ((), {"schema": None})),
            ("runtime", "list_runtime_metrics", {}, [], ((), {"schema": None})),
            ("index-stats", "list_index_usage_stats", {}, [], ((), {"schema": None})),
            (
                "ddl",
                "get_ddl_statement",
                {"name": "ORDERS"},
                DDLStatement(
                    object_type="TABLE",
                    object_name="ORDERS",
                    ddl="CREATE TABLE ORDERS (ID INTEGER)",
                    native=True,
                ),
                (("ORDERS",), {"object_type": None, "schema": None}),
            ),
            (
                "column-profiles",
                "list_column_data_profiles",
                {"name": "ORDERS"},
                [],
                (("ORDERS",), {"schema": None}),
            ),
            (
                "value-samples",
                "sample_column_values",
                {"name": "ORDERS", "column": "STATUS"},
                [],
                (("ORDERS", "STATUS"), {"schema": None}),
            ),
            (
                "join-coverage",
                "estimate_join_coverage",
                {
                    "name": "ORDERS",
                    "column": "CUSTOMER_ID",
                    "right_table": "CUSTOMERS",
                    "right_column": "ID",
                },
                [],
                (("ORDERS", "CUSTOMER_ID", "CUSTOMERS", "ID"), {"schema": None}),
            ),
            ("rdb-dependencies", "list_dependencies", {"name": "ORDERS"}, [], (("ORDERS",), {})),
        ],
    )
    def test_the_async_branch_calls_the_same_method_with_the_same_arguments(
        self, type_, method, args_kwargs, result, expected, monkeypatch
    ):
        # ``result`` is not ``[]`` everywhere: ``ddl`` answers ``None`` for
        # "no statement", and a stub that returned an empty list there would
        # send the branch down the display path instead of the call it is
        # being asked to reach.
        introspector = _AsyncRecordingIntrospector({method: result})

        _run_async(monkeypatch, introspector, _args(type_, **args_kwargs), gate_open=True)

        assert introspector.calls == [(method, expected[0], expected[1])]

    def test_the_async_blob_note_reaches_stderr(self, monkeypatch, capsys):
        blob = ColumnDataProfile(
            table_name="ORDERS", column_name="DOC", null_fraction=0.6, row_count=100
        )
        introspector = _AsyncRecordingIntrospector(
            {"list_column_data_profiles": [blob]}
        )

        _run_async(
            monkeypatch,
            introspector,
            _args("column-profiles", "ORDERS"),
        )

        err = capsys.readouterr().err
        assert "not measured" in err
        assert "DOC" in err


class TestTheTypeSurfaceExtension:
    def test_the_type_list_is_the_capability_table(self):
        assert list(_TYPE_CAPABILITIES) == INTROSPECT_TYPES

    def test_each_new_family_has_an_entry_naming_a_probe(self):
        for type_, switch in NEW_FAMILIES.items():
            assert _TYPE_CAPABILITIES[type_] == switch
            assert hasattr(FirebirdDialect, switch), type_

    def test_every_advertised_type_has_a_name_rule(self):
        """A type without a rule is a type whose NAME decision nobody made."""
        assert set(introspect_cli._NAME_RULE) == set(INTROSPECT_TYPES)

    def test_the_name_rule_says_what_each_types_name_means(self):
        """The table, pinned as data: a change is a visible edit, not a drift.

        A table nobody asserts is text nobody guarantees, which is the
        cross-repository clause of ``.claude/rules/constants.md`` -- the
        private name is legitimate because one validator reads it, and this
        is what makes the reading checkable.
        """
        assert introspect_cli._NAME_RULE == {
            "tables": "forbidden",
            "views": "optional",
            "columns": "required",
            "indexes": "required",
            "foreign-keys": "required",
            "triggers": "optional",
            "database": "forbidden",
            "generators": "optional",
            "domains": "optional",
            "exceptions": "optional",
            "procedures": "optional",
            "procedure-parameters": "required",
            "functions": "optional",
            "function-arguments": "required",
            "constraints": "optional",
            "roles": "forbidden",
            "privileges": "forbidden",
            "charsets": "forbidden",
            "collations": "optional",
            "rdb-dependencies": "optional",
            "view-relations": "optional",
            "publications": "forbidden",
            "unused-indexes": "forbidden",
            "table-stats": "forbidden",
            "runtime": "forbidden",
            "index-stats": "forbidden",
            "ddl": "required",
            "column-profiles": "required",
            "value-samples": "required",
            "join-coverage": "required",
        }

    @pytest.mark.parametrize(
        "type_",
        [
            "tables",
            "database",
            "roles",
            "privileges",
            "charsets",
            "publications",
            "unused-indexes",
            "table-stats",
            "runtime",
            "index-stats",
        ],
    )
    def test_a_refused_type_is_refused_by_the_table(self, type_, capsys):
        with pytest.raises(SystemExit) as excinfo:
            introspect_cli._validate_name(_args(type_, "ORDERS"))

        assert excinfo.value.code == 2
        assert f"'{type_}' does not take an object name" in capsys.readouterr().err

    @pytest.mark.parametrize(
        "type_",
        [
            "columns",
            "indexes",
            "foreign-keys",
            "procedure-parameters",
            "function-arguments",
            "ddl",
            "column-profiles",
            "value-samples",
            "join-coverage",
        ],
    )
    def test_a_required_name_is_required_by_the_table(self, type_, capsys):
        """Exit 1 like a missing ``--database``: the invocation is incomplete."""
        with pytest.raises(SystemExit) as excinfo:
            introspect_cli._validate_name(_args(type_))

        assert excinfo.value.code == 1
        assert f"Table name is required for '{type_}'" in capsys.readouterr().err

    @pytest.mark.parametrize(
        "type_",
        [
            "views",
            "triggers",
            "generators",
            "domains",
            "exceptions",
            "procedures",
            "functions",
            "constraints",
            "collations",
            "rdb-dependencies",
            "view-relations",
        ],
    )
    def test_an_optional_name_may_be_given_or_not(self, type_):
        introspect_cli._validate_name(_args(type_))
        introspect_cli._validate_name(_args(type_, "ORDERS"))

    def test_every_type_has_a_branch_in_both_paths(self):
        """A type with no branch prints nothing and exits 0 -- the worst shape."""
        import inspect

        sync_source = inspect.getsource(introspect_cli._handle_introspect_sync)
        async_source = inspect.getsource(introspect_cli._handle_introspect_async)
        for name in INTROSPECT_TYPES:
            assert f'args.type == "{name}"' in sync_source, name
            assert f'args.type == "{name}"' in async_source, name

    def test_help_lists_every_type(self, capsys):
        parser = introspect_cli.create_parser(
            argparse.ArgumentParser().add_subparsers()
        )
        with pytest.raises(SystemExit):
            parser.parse_args(["--help"])
        out = capsys.readouterr().out
        for name in INTROSPECT_TYPES:
            assert name in out
