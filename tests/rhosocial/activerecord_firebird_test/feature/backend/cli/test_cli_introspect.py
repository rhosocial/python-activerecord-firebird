# tests/rhosocial/activerecord_firebird_test/feature/backend/cli/test_cli_introspect.py
"""Offline black-box tests for the ``firebird introspect`` CLI subcommand.

``handle()`` runs against a fake backend whose introspector returns fixed
payloads; every INTROSPECT_TYPES value is exercised through capsys, and
ConnectionError/QueryError paths must exit non-zero.
"""
import argparse
import asyncio

import pytest

from rhosocial.activerecord.backend.errors import ConnectionError, QueryError
from rhosocial.activerecord.backend.impl.firebird.cli import introspect as introspect_mod
from rhosocial.activerecord.backend.impl.firebird.cli.introspect import INTROSPECT_TYPES


def parse_introspect_args(argv):
    parser = argparse.ArgumentParser(prog="firebird")
    subparsers = parser.add_subparsers(dest="command")
    introspect_mod.create_parser(subparsers)
    return parser.parse_args(argv)


class FakeIntrospector:
    def __init__(self):
        self.calls = []

    def list_tables(self, schema=None, include_system=False):
        self.calls.append(("list_tables", schema, include_system))
        return ["USERS", "ORDERS"]

    def list_views(self, schema=None):
        self.calls.append(("list_views", schema))
        return ["ACTIVE_USERS"]

    def get_view_info(self, name, schema=None):
        self.calls.append(("get_view_info", name))
        if name.upper() != "ACTIVE_USERS":
            return None
        return {
            "name": "ACTIVE_USERS",
            "definition": "SELECT ID, NAME FROM USERS WHERE ACTIVE = 1",
        }

    def list_columns(self, name, schema=None):
        self.calls.append(("list_columns", name, schema))
        return [{"name": "ID", "type": "INTEGER"}, {"name": "NAME", "type": "VARCHAR"}]

    def list_indexes(self, name, schema=None):
        self.calls.append(("list_indexes", name, schema))
        return [{"name": "IDX_USERS_NAME"}]

    def list_foreign_keys(self, name, schema=None):
        self.calls.append(("list_foreign_keys", name, schema))
        return [{"name": "FK_USERS_ROLE"}]

    def list_triggers(self, table_name=None, schema=None):
        self.calls.append(("list_triggers", table_name, schema))
        return [{"name": "TRG_AUDIT"}]

    def get_database_info(self):
        self.calls.append(("get_database_info",))
        return {"name": "/tmp/x.fdb", "page_size": 8192}

    # --- Firebird's own schema-object families -------------------------
    # One method per catalogue family, each recording the call so the test can
    # assert the CLI reached the manager rather than rendering something itself.

    def list_generators(self, include_system=False):
        self.calls.append(("list_generators", include_system))
        return [{"name": "GEN_SEQ"}]

    def list_domains(self, include_system=False):
        self.calls.append(("list_domains", include_system))
        return [{"name": "DOMAIN_MONEY"}]

    def list_exceptions(self, include_system=False):
        self.calls.append(("list_exceptions", include_system))
        return [{"name": "EXC_LIMIT"}]

    def list_procedures(self, include_system=False, include_source=False):
        self.calls.append(("list_procedures", include_system, include_source))
        return [{"name": "PROC_PING"}]

    def list_procedure_parameters(self, procedure_name):
        self.calls.append(("list_procedure_parameters", procedure_name))
        return [{"name": "PPARAM_I"}]

    def list_functions(self, include_system=False, include_source=False):
        self.calls.append(("list_functions", include_system, include_source))
        return [{"name": "FUNC_DOUBLE"}]

    def list_function_arguments(self, function_name):
        self.calls.append(("list_function_arguments", function_name))
        return [{"name": "FARG_X"}]

    def list_constraints(self, table_name=None, constraint_type=None, include_system=False):
        self.calls.append(
            ("list_constraints", table_name, constraint_type, include_system)
        )
        return [{"name": "CONS_PK"}]

    def list_roles(self, include_system=False):
        self.calls.append(("list_roles", include_system))
        return [{"name": "ROLE_READER"}]

    def list_privileges(self, object_name=None, user_name=None, include_system=False):
        self.calls.append(
            ("list_privileges", object_name, user_name, include_system)
        )
        return [{"name": "PRIV_SELECT"}]

    def list_charsets(self):
        self.calls.append(("list_charsets",))
        return [{"name": "CHARSET_UTF8"}]

    def list_collations(self, charset_name=None):
        self.calls.append(("list_collations", charset_name))
        return [{"name": "COLL_UCS_BASIC"}]

    def list_dependencies(self, object_name=None):
        self.calls.append(("list_dependencies", object_name))
        return [{"name": "DEP_VIEW"}]

    def list_view_relations(self, view_name=None):
        self.calls.append(("list_view_relations", view_name))
        return [{"name": "VREL_BASE"}]

    def list_publications(self, include_system=False):
        self.calls.append(("list_publications", include_system))
        return [{"name": "PUB_DEFAULT"}]


class RaisingIntrospector(FakeIntrospector):
    def __init__(self, exc):
        super().__init__()
        self._exc = exc

    def list_tables(self, schema=None, include_system=False):
        raise self._exc


def make_async_introspector(exc=None):
    if exc is not None:
        async def list_tables(schema=None, include_system=False):
            raise exc

        return type("AI", (), {"list_tables": staticmethod(list_tables)})()

    base = FakeIntrospector()

    class AsyncFakeIntrospector:
        def __init__(self):
            # The same list the sync fake records into: this wrapper exists to
            # make a method awaitable, not to hide which method was reached.
            self.calls = base.calls

        def __getattr__(self, name):
            attr = getattr(base, name)

            async def runner(*args, **kwargs):
                return attr(*args, **kwargs)

            return runner

        def track(self, name):
            return name

    return AsyncFakeIntrospector()


class FakeBackend:
    last_instance = None

    def __init__(self, connection_config=None):
        self.connection_config = connection_config
        self._connection = None
        self.disconnect_calls = 0
        self.introspector = FakeIntrospector()
        FakeBackend.last_instance = self

    def connect(self):
        self._connection = object()

    def introspect_and_adapt(self):
        """The real backend reads the server version here before rendering.

        Every formatter that branches on version needs it, which is why the CLI
        calls it after connecting; a stub without it would pass only while the
        CLI forgot to adapt -- which is exactly the defect it now covers.
        """
        self.adapt_calls = getattr(self, "adapt_calls", 0) + 1

    def disconnect(self):
        self.disconnect_calls += 1
        self._connection = None


class FakeAsyncBackend(FakeBackend):
    """The same fake, awaited.

    ``_handle_introspect_async`` connects, adapts and disconnects through
    coroutines, so the stub has to answer in kind; everything else -- the
    introspector it carries, the recording of that introspector's calls -- is
    the sync fake's, which is what keeps the two paths comparable.
    """

    async def connect(self):
        self._connection = object()

    async def introspect_and_adapt(self):
        self.adapt_calls = getattr(self, "adapt_calls", 0) + 1

    async def disconnect(self):
        self.disconnect_calls += 1
        self._connection = None


@pytest.fixture(autouse=True)
def clean_fb_env(monkeypatch):
    for name in ("FIREBIRD_HOST", "FIREBIRD_PORT", "FIREBIRD_DATABASE",
                 "FIREBIRD_USER", "FIREBIRD_PASSWORD", "FIREBIRD_ROLE"):
        monkeypatch.delenv(name, raising=False)


class TestIntrospectParserContract:
    def test_all_types_accepted(self):
        for introspect_type in INTROSPECT_TYPES:
            args = parse_introspect_args(["introspect", introspect_type])
            assert args.type == introspect_type

    def test_the_advertised_types_are_the_capability_mapping(self):
        """One source for the list: the mapping, not a second hand-written copy.

        The list used to be written out separately from the dialect's
        capability switches, so a family could be answerable and unaskable at
        the same time -- which is exactly what happened to the eleven
        schema-object families before they were wired up.
        """
        assert list(introspect_mod._TYPE_CAPABILITIES) == INTROSPECT_TYPES

    def test_every_type_names_a_switch_the_dialect_has(self):
        """A type whose switch does not exist would be un-gated, not gated."""
        from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect

        dialect = FirebirdDialect(version=(5, 0, 4))
        missing = [
            (cli_type, switch)
            for cli_type, switch in introspect_mod._TYPE_CAPABILITIES.items()
            if not hasattr(dialect, switch)
        ]
        assert missing == []

    def test_every_type_the_dialect_declares_is_askable(self):
        """The other direction: no family the dialect *answers for* lacks a type.

        A switch that returns False is a different statement -- Firebird
        declares ``supports_partition_metadata_introspection`` only because the
        protocol asks every dialect, and it answers False. Those are excluded;
        everything the dialect says it can answer must be reachable.
        """
        from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect

        dialect = FirebirdDialect(version=(5, 0, 4))
        answerable = {
            name
            for name in dir(FirebirdDialect)
            if name.startswith("supports_")
            and name.endswith("_introspection")
            and name != "supports_introspection"
            and getattr(dialect, name)()
        }
        used = set(introspect_mod._TYPE_CAPABILITIES.values())
        assert answerable - used == set()

    def test_name_and_flags(self):
        """The name and ``--include-system``; there is no namespace flag.

        Firebird has one unnamed namespace, so nothing here names a level.
        The case that a ``--schema`` flag is *absent* is pinned in
        ``test_cli.py``, which asserts the parser refuses it.
        """
        args = parse_introspect_args([
            "introspect", "columns", "users", "--include-system",
        ])
        assert args.name == "users"
        assert args.include_system is True

    def test_defaults(self):
        args = parse_introspect_args(["introspect", "tables"])
        assert args.name is None
        assert args.include_system is False
        assert args.output == "table"

    def test_invalid_type_rejected(self):
        with pytest.raises(SystemExit) as excinfo:
            parse_introspect_args(["introspect", "stored-procs"])
        assert excinfo.value.code == 2

    def test_no_dsn_form_exists(self):
        with pytest.raises(SystemExit) as excinfo:
            parse_introspect_args(["introspect", "--dsn", "x"])
        assert excinfo.value.code == 2


# One case per advertised type: the argv that asks, something the answer has to
# contain, and the introspector method the CLI must reach. Shared by the sync
# and the async path, so a type wired into one and not the other fails a test
# instead of being found by a user.
HAPPY_PATH_TYPES = [
    (["tables"], "ORDERS", "list_tables"),
    (["views"], "ACTIVE_USERS", "list_views"),
    (["columns", "USERS"], "VARCHAR", "list_columns"),
    (["indexes", "USERS"], "IDX_USERS_NAME", "list_indexes"),
    (["foreign-keys", "USERS"], "FK_USERS_ROLE", "list_foreign_keys"),
    (["triggers"], "TRG_AUDIT", "list_triggers"),
    (["database"], "page_size", "get_database_info"),
    (["generators"], "GEN_SEQ", "list_generators"),
    (["domains"], "DOMAIN_MONEY", "list_domains"),
    (["exceptions"], "EXC_LIMIT", "list_exceptions"),
    (["procedures"], "PROC_PING", "list_procedures"),
    (["procedure-parameters", "PING"], "PPARAM_I", "list_procedure_parameters"),
    (["functions"], "FUNC_DOUBLE", "list_functions"),
    (["function-arguments", "DOUBLE"], "FARG_X", "list_function_arguments"),
    (["constraints"], "CONS_PK", "list_constraints"),
    (["roles"], "ROLE_READER", "list_roles"),
    (["privileges"], "PRIV_SELECT", "list_privileges"),
    (["charsets"], "CHARSET_UTF8", "list_charsets"),
    (["collations"], "COLL_UCS_BASIC", "list_collations"),
    (["dependencies"], "DEP_VIEW", "list_dependencies"),
    (["view-relations"], "VREL_BASE", "list_view_relations"),
    (["publications"], "PUB_DEFAULT", "list_publications"),
]


class TestIntrospectHandleHappyPaths:
    @pytest.mark.parametrize("argv,marker,call_prefix", HAPPY_PATH_TYPES)
    def test_each_type_output(self, monkeypatch, capsys, argv, marker, call_prefix):
        monkeypatch.setattr(introspect_mod, "FirebirdBackend", FakeBackend)
        args = parse_introspect_args(["introspect", *argv, "--database", "/tmp/x.fdb", "-o", "json"])
        introspect_mod.handle(args)
        out = capsys.readouterr().out
        assert marker in out
        assert FakeBackend.last_instance.introspector.calls[0][0] == call_prefix
        assert FakeBackend.last_instance.disconnect_calls == 1

    def test_one_view_answered_by_name(self, monkeypatch, capsys):
        """``views NAME`` asks for that one view instead of listing the family."""
        monkeypatch.setattr(introspect_mod, "FirebirdBackend", FakeBackend)
        args = parse_introspect_args([
            "introspect", "views", "ACTIVE_USERS", "--database", "/tmp/x.fdb", "-o", "json",
        ])
        introspect_mod.handle(args)
        out = capsys.readouterr().out
        assert "ACTIVE_USERS" in out
        assert "SELECT ID, NAME FROM USERS" in out
        assert FakeBackend.last_instance.introspector.calls[0][0] == "get_view_info"

    def test_an_unknown_view_exits_one(self, monkeypatch, capsys):
        monkeypatch.setattr(introspect_mod, "FirebirdBackend", FakeBackend)
        args = parse_introspect_args([
            "introspect", "views", "NO_SUCH_VIEW", "--database", "/tmp/x.fdb",
        ])
        with pytest.raises(SystemExit) as excinfo:
            introspect_mod.handle(args)
        assert excinfo.value.code == 1
        assert "not found" in capsys.readouterr().err

    def test_include_system_forwarded(self, monkeypatch):
        monkeypatch.setattr(introspect_mod, "FirebirdBackend", FakeBackend)
        args = parse_introspect_args([
            "introspect", "tables", "--database", "/tmp/x.fdb", "--include-system",
        ])
        introspect_mod.handle(args)
        call = FakeBackend.last_instance.introspector.calls[0]
        assert call == ("list_tables", None, True)

    def test_the_connection_database_is_the_only_scope(self, monkeypatch):
        """What the run asks about is the database it connected to.

        There is no namespace flag, so the schema each question receives is
        the introspector's own default -- which for Firebird is nothing at
        all, because nothing qualifies a name above the table.
        """
        monkeypatch.setattr(introspect_mod, "FirebirdBackend", FakeBackend)
        args = parse_introspect_args([
            "introspect", "columns", "USERS", "--database", "/tmp/x.fdb",
        ])
        introspect_mod.handle(args)
        call = FakeBackend.last_instance.introspector.calls[0]
        assert call == ("list_columns", "USERS", None)

    def test_default_table_output_emits_rows_via_fallback_provider(self, monkeypatch, capsys):
        monkeypatch.setattr(introspect_mod, "FirebirdBackend", FakeBackend)
        args = parse_introspect_args(["introspect", "tables", "--database", "/tmp/x.fdb"])
        introspect_mod.handle(args)
        assert "USERS" in capsys.readouterr().out


class _RefusingDialect:
    """A server one release older than the family being asked about.

    Publications are Firebird 4; on 3 the switch answers False, and the CLI is
    expected to say so rather than let the statement reach the server and come
    back as a "table unknown" the caller has to translate.
    """

    def supports_publication_introspection(self):
        return False


class TestCapabilityGate:
    def test_a_family_the_server_cannot_answer_exits_two(self, monkeypatch, capsys):
        """Exit 2: the request does not hold *here*, which is not a failure of the run.

        The distinction is what lets a caller script around it: 1 means "it did
        not run", 2 means "this server cannot answer that", and the sentence on
        stderr names the family rather than the statement.
        """

        class OldServer(FakeBackend):
            dialect = _RefusingDialect()

        monkeypatch.setattr(introspect_mod, "FirebirdBackend", OldServer)
        args = parse_introspect_args(
            ["introspect", "publications", "--database", "/tmp/x.fdb"]
        )
        with pytest.raises(SystemExit) as excinfo:
            introspect_mod.handle(args)
        assert excinfo.value.code == 2
        assert "publications introspection is not supported by this server" in (
            capsys.readouterr().err
        )

    def test_the_async_path_refuses_the_same_way(self, capsys):
        """The gate is asked after adaptation on both paths, so both refuse alike."""
        backend = FakeAsyncBackend()
        backend.dialect = _RefusingDialect()
        args = parse_introspect_args(
            ["introspect", "publications", "--database", "/tmp/x.fdb"]
        )
        with pytest.raises(SystemExit) as excinfo:
            asyncio.run(
                introspect_mod._handle_introspect_async(
                    args, backend, introspect_mod.create_provider("json")
                )
            )
        assert excinfo.value.code == 2
        assert "publications introspection is not supported by this server" in (
            capsys.readouterr().err
        )


class TestIntrospectArgumentValidation:
    @pytest.mark.parametrize("introspect_type", ["columns", "indexes", "foreign-keys"])
    def test_missing_name_exits_nonzero(self, monkeypatch, capsys, introspect_type):
        monkeypatch.setattr(introspect_mod, "FirebirdBackend", FakeBackend)
        args = parse_introspect_args(["introspect", introspect_type, "--database", "/tmp/x.fdb"])
        with pytest.raises(SystemExit) as excinfo:
            introspect_mod.handle(args)
        assert excinfo.value.code == 1
        assert "Table name is required" in capsys.readouterr().err

    def test_the_aggregate_table_type_is_gone(self):
        """``table`` was the one type that answered three catalogue questions.

        One catalogue item is one dimension: a table's own row, its columns,
        its indexes and its foreign keys are four questions, and each has its
        own type. The aggregate also could not be rendered as one JSON
        document, which is how the split became visible.
        """
        assert "table" not in INTROSPECT_TYPES
        with pytest.raises(SystemExit) as excinfo:
            parse_introspect_args(["introspect", "table", "USERS"])
        assert excinfo.value.code == 2


class TestIntrospectAsyncPath:
    @pytest.mark.parametrize("argv,marker,call_prefix", HAPPY_PATH_TYPES)
    def test_each_type_answers(self, capsys, argv, marker, call_prefix):
        """The async path offers every type the sync one does.

        Only ``tables`` was exercised before, so the other branches of the
        async handler could have reached a method by the wrong name and passed:
        the fake records which one was called, and this asserts it is the same
        one the sync path asks for.
        """
        backend = FakeAsyncBackend()
        backend.introspector = make_async_introspector()
        args = parse_introspect_args(
            ["introspect", *argv, "--database", "/tmp/x.fdb", "-o", "json"]
        )
        asyncio.run(
            introspect_mod._handle_introspect_async(args, backend, introspect_mod.create_provider("json"))
        )
        out = capsys.readouterr().out
        assert marker in out
        assert backend.introspector.calls[0][0] == call_prefix
        assert backend.disconnect_calls == 1

    def test_async_tables_json(self, capsys):
        backend = FakeAsyncBackend()
        backend.introspector = make_async_introspector()
        args = parse_introspect_args(["introspect", "tables", "--database", "/tmp/x.fdb", "-o", "json"])
        asyncio.run(
            introspect_mod._handle_introspect_async(args, backend, introspect_mod.create_provider("json"))
        )
        assert "ORDERS" in capsys.readouterr().out
        assert backend.disconnect_calls == 1

    def test_async_query_error_exits_nonzero(self):
        backend = FakeAsyncBackend()
        backend.introspector = make_async_introspector(exc=QueryError("no such table"))
        args = parse_introspect_args(["introspect", "tables", "--database", "/tmp/x.fdb"])
        with pytest.raises(SystemExit) as excinfo:
            asyncio.run(
                introspect_mod._handle_introspect_async(args, backend, introspect_mod.create_provider("json"))
            )
        assert excinfo.value.code == 1


class TestIntrospectErrorPaths:
    def test_missing_database_exits_with_stderr_message(self, capsys):
        args = parse_introspect_args(["introspect", "tables"])
        with pytest.raises(SystemExit) as excinfo:
            introspect_mod.handle(args)
        assert excinfo.value.code == 1
        assert "--database is required" in capsys.readouterr().err

    def test_connection_error_exits_nonzero(self, monkeypatch):
        class RefusedBackend(FakeBackend):
            def connect(self):
                raise ConnectionError("unavailable")

        monkeypatch.setattr(introspect_mod, "FirebirdBackend", RefusedBackend)
        args = parse_introspect_args(["introspect", "tables", "--database", "/tmp/x.fdb"])
        with pytest.raises(SystemExit) as excinfo:
            introspect_mod.handle(args)
        assert excinfo.value.code == 1

    def test_query_error_exits_nonzero(self, monkeypatch):
        monkeypatch.setattr(introspect_mod, "FirebirdBackend", FakeBackend)
        original_init = FakeBackend.__init__

        def patched_init(self, connection_config=None):
            original_init(self, connection_config)
            self.introspector = RaisingIntrospector(QueryError("malformed"))

        monkeypatch.setattr(FakeBackend, "__init__", patched_init)
        args = parse_introspect_args(["introspect", "tables", "--database", "/tmp/x.fdb"])
        with pytest.raises(SystemExit) as excinfo:
            introspect_mod.handle(args)
        assert excinfo.value.code == 1

    def test_unexpected_error_prints_to_stderr_and_exits(self, monkeypatch, capsys):
        monkeypatch.setattr(introspect_mod, "FirebirdBackend", FakeBackend)

        class BrokenIntrospector(FakeIntrospector):
            def list_tables(self, schema=None, include_system=False):
                raise RuntimeError("boom")

        original_init = FakeBackend.__init__

        def patched_init(self, connection_config=None):
            original_init(self, connection_config)
            self.introspector = BrokenIntrospector()

        monkeypatch.setattr(FakeBackend, "__init__", patched_init)
        args = parse_introspect_args(["introspect", "tables", "--database", "/tmp/x.fdb"])
        with pytest.raises(SystemExit) as excinfo:
            introspect_mod.handle(args)
        assert excinfo.value.code == 1
        assert "Error during introspection" in capsys.readouterr().err
