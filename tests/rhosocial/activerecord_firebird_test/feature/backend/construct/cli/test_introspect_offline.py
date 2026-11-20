# tests/rhosocial/activerecord_firebird_test/feature/backend/construct/cli/test_introspect_offline.py
"""Offline, mock-only unit tests for ``firebird.cli.introspect`` (sync paths).

Covers parser shape, the validation/capability/serialization helpers and the
synchronous dispatch and error paths with a stub backend and provider.  No
Firebird server or driver is touched, and no async helper is exercised.
"""

import argparse
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from rhosocial.activerecord.backend.errors import ConnectionError, QueryError
from rhosocial.activerecord.backend.impl.firebird.cli import introspect as mod
from rhosocial.activerecord.backend.impl.firebird.cli.introspect import INTROSPECT_TYPES


def parse(argv):
    parser = argparse.ArgumentParser(prog="firebird")
    subparsers = parser.add_subparsers(dest="command")
    mod.create_parser(subparsers)
    return parser.parse_args(argv)


def ns(type="tables", name=None, **overrides):
    values = dict(
        type=type,
        name=name,
        output="json",
        rich_ascii=False,
        include_system=False,
        column=None,
        right_table=None,
        right_column=None,
        object=None,
        grantee=None,
        constraint_type=None,
        is_async=False,
    )
    values.update(overrides)
    return argparse.Namespace(**values)


@pytest.fixture(autouse=True)
def clean_fb_env(monkeypatch):
    for name in ("FIREBIRD_HOST", "FIREBIRD_PORT", "FIREBIRD_DATABASE",
                 "FIREBIRD_USER", "FIREBIRD_PASSWORD", "FIREBIRD_ROLE"):
        monkeypatch.delenv(name, raising=False)


class TestIntrospectParser:
    def test_defaults(self):
        args = parse(["introspect", "tables"])
        assert args.type == "tables"
        assert args.name is None
        assert args.output == "table"
        assert args.include_system is False
        assert args.rich_ascii is False
        assert args.column is None
        assert args.right_table is None
        assert args.right_column is None

    @pytest.mark.parametrize("introspect_type", INTROSPECT_TYPES)
    def test_every_type_accepted(self, introspect_type):
        assert parse(["introspect", introspect_type]).type == introspect_type

    def test_unknown_type_rejected(self):
        with pytest.raises(SystemExit) as exc:
            parse(["introspect", "stored-procs"])
        assert exc.value.code == 2

    def test_row_family_flags_parsed(self):
        args = parse([
            "introspect", "join-coverage", "orders",
            "--column", "customer_id", "--right-table", "customers",
            "--right-column", "id", "--include-system",
        ])
        assert args.name == "orders"
        assert args.column == "customer_id"
        assert args.right_table == "customers"
        assert args.right_column == "id"
        assert args.include_system is True

    def test_privilege_and_constraint_flags_parsed(self):
        args = parse([
            "introspect", "privileges", "--object", "USERS",
            "--grantee", "APP", "--constraint-type", "PRIMARY KEY",
        ])
        assert args.object == "USERS"
        assert args.grantee == "APP"
        assert args.constraint_type == "PRIMARY KEY"

    def test_no_schema_flag(self):
        with pytest.raises(SystemExit):
            parse(["introspect", "tables", "--schema", "PUBLIC"])


class TestMapConsistency:
    def test_name_rule_covers_every_type(self):
        assert set(mod._NAME_RULE) == set(INTROSPECT_TYPES)

    def test_specific_name_rules(self):
        for required in ("columns", "indexes", "foreign-keys", "procedure-parameters",
                         "function-arguments", "column-profiles", "value-samples", "join-coverage"):
            assert mod._NAME_RULE[required] == "required"
        for forbidden in ("tables", "database", "charsets", "roles", "privileges",
                          "publications", "unused-indexes", "table-stats", "runtime", "index-stats"):
            assert mod._NAME_RULE[forbidden] == "forbidden"
        assert mod._NAME_RULE["views"] == "optional"

    def test_capabilities_and_types_share_order(self):
        assert list(mod._TYPE_CAPABILITIES) == INTROSPECT_TYPES


class TestValueSampleArguments:
    def test_absent_limit_is_not_forwarded(self):
        assert mod._value_sample_arguments(ns()) == {}

    def test_limit_is_forwarded(self):
        assert mod._value_sample_arguments(ns(limit=25)) == {"limit": 25}


class TestRequireCapability:
    def test_unmapped_type_is_allowed(self):
        mod._require_capability(MagicMock(), ns(type="not-mapped"))

    def test_backend_without_dialect_is_allowed(self):
        backend = SimpleNamespace(dialect=None)
        mod._require_capability(backend, ns(type="publications"))

    def test_missing_switch_is_allowed(self):
        backend = SimpleNamespace(dialect=SimpleNamespace())
        mod._require_capability(backend, ns(type="publications"))

    def test_supported_switch_is_allowed(self):
        dialect = SimpleNamespace(supports_publication_introspection=lambda: True)
        mod._require_capability(SimpleNamespace(dialect=dialect), ns(type="publications"))

    def test_refusing_switch_exits_two(self, capsys):
        dialect = SimpleNamespace(supports_publication_introspection=lambda: False)
        with pytest.raises(SystemExit) as exc:
            mod._require_capability(SimpleNamespace(dialect=dialect), ns(type="publications"))
        assert exc.value.code == 2
        assert "publications introspection is not supported" in capsys.readouterr().err


class TestValidateName:
    @pytest.mark.parametrize("introspect_type", ["columns", "indexes", "column-profiles"])
    def test_missing_required_name_exits_one(self, capsys, introspect_type):
        with pytest.raises(SystemExit) as exc:
            mod._validate_name(ns(type=introspect_type))
        assert exc.value.code == 1
        assert "Table name is required" in capsys.readouterr().err

    def test_required_name_present_is_allowed(self):
        mod._validate_name(ns(type="columns", name="USERS"))

    @pytest.mark.parametrize("introspect_type", ["tables", "database", "roles"])
    def test_forbidden_name_exits_two(self, capsys, introspect_type):
        with pytest.raises(SystemExit) as exc:
            mod._validate_name(ns(type=introspect_type, name="USERS"))
        assert exc.value.code == 2
        assert "does not take an object name" in capsys.readouterr().err

    def test_forbidden_name_absent_is_allowed(self):
        mod._validate_name(ns(type="tables"))

    @pytest.mark.parametrize("introspect_type", ["views", "generators", "collations"])
    def test_optional_name_is_always_allowed(self, introspect_type):
        mod._validate_name(ns(type=introspect_type))
        mod._validate_name(ns(type=introspect_type, name="X"))


class TestRefuseUnusedArguments:
    def test_column_on_wrong_type_exits_two(self, capsys):
        with pytest.raises(SystemExit) as exc:
            mod._refuse_unused_arguments(ns(type="tables", column="ID"))
        assert exc.value.code == 2
        assert "does not take --column" in capsys.readouterr().err

    @pytest.mark.parametrize("introspect_type", ["value-samples", "join-coverage"])
    def test_column_on_row_family_is_allowed(self, introspect_type):
        mod._refuse_unused_arguments(ns(type=introspect_type, column="ID"))

    def test_right_table_on_wrong_type_exits_two(self, capsys):
        with pytest.raises(SystemExit) as exc:
            mod._refuse_unused_arguments(ns(type="tables", right_table="X"))
        assert exc.value.code == 2
        assert "does not take --right-table" in capsys.readouterr().err

    def test_right_column_on_wrong_type_exits_two(self, capsys):
        with pytest.raises(SystemExit) as exc:
            mod._refuse_unused_arguments(ns(type="tables", right_column="X"))
        assert exc.value.code == 2
        assert "does not take --right-table" in capsys.readouterr().err

    def test_right_names_on_join_coverage_allowed(self):
        mod._refuse_unused_arguments(
            ns(type="join-coverage", right_table="X", right_column="Y")
        )

    def test_absent_flags_allowed(self):
        mod._refuse_unused_arguments(ns(type="tables"))


class TestNoteUnmeasuredProfiles:
    @pytest.mark.parametrize("profiles", [[], [SimpleNamespace(
        column_name="A", distinct_count=1, min_value=0, max_value=9
    )]])
    def test_measured_profiles_emit_nothing(self, capsys, profiles):
        mod._note_unmeasured_profiles(profiles, "T")
        assert capsys.readouterr().err == ""

    def test_blind_profile_is_reported(self, capsys):
        profiles = [
            SimpleNamespace(column_name="BLOB_A", distinct_count=None, min_value=None, max_value=None),
            SimpleNamespace(column_name="OK", distinct_count=1, min_value=0, max_value=9),
        ]
        mod._note_unmeasured_profiles(profiles, "ORDERS")
        err = capsys.readouterr().err
        assert "1 column(s) of ORDERS" in err
        assert "BLOB_A" in err
        assert "OK" not in err

    def test_none_entries_are_ignored(self, capsys):
        mod._note_unmeasured_profiles([None], "T")
        assert capsys.readouterr().err == ""


def introspect_backend():
    backend = MagicMock()
    backend._connection = object()
    introspector = backend.introspector
    payload = [{"name": "X", "value": 1}]
    for name in (
        "list_tables", "list_views", "list_columns", "list_indexes", "list_foreign_keys",
        "list_triggers", "get_database_info", "list_generators", "list_domains",
        "list_exceptions", "list_procedures", "list_procedure_parameters", "list_functions",
        "list_function_arguments", "list_constraints", "list_roles", "list_privileges",
        "list_charsets", "list_collations", "list_dependencies", "list_view_relations",
        "list_publications", "list_unused_indexes", "list_table_usage_stats",
        "list_runtime_metrics", "list_index_usage_stats", "list_column_data_profiles",
        "sample_column_values", "estimate_join_coverage",
    ):
        getattr(introspector, name).return_value = payload
    # Single-object getters must return plain data: a bare MagicMock exposes a
    # synthetic ``model_dump`` which would recurse forever in serialization.
    for getter in (
        "get_view_info", "get_domain_info", "get_exception_info",
        "get_procedure_info", "get_function_info",
    ):
        getattr(introspector, getter).return_value = payload
    # The one-object generator branch reads ``generator.name`` for its title.
    introspector.get_generator_info.return_value = SimpleNamespace(name="GEN")
    return backend


class TestHandleIntrospectSync:
    @pytest.mark.parametrize("introspect_type,method", [
        ("tables", "list_tables"),
        ("views", "list_views"),
        ("columns", "list_columns"),
        ("indexes", "list_indexes"),
        ("foreign-keys", "list_foreign_keys"),
        ("triggers", "list_triggers"),
        ("database", "get_database_info"),
        ("generators", "list_generators"),
        ("roles", "list_roles"),
        ("charsets", "list_charsets"),
        ("publications", "list_publications"),
        ("table-stats", "list_table_usage_stats"),
        ("runtime", "list_runtime_metrics"),
    ])
    def test_family_dispatch(self, introspect_type, method):
        backend = introspect_backend()
        provider = MagicMock()
        name = "USERS" if mod._NAME_RULE[introspect_type] == "required" else None
        mod._handle_introspect_sync(ns(type=introspect_type, name=name), backend, provider)
        backend.connect.assert_called_once_with()
        backend.introspect_and_adapt.assert_called_once_with()
        getattr(backend.introspector, method).assert_called_once()
        provider.display_results.assert_called_once()
        backend.disconnect.assert_called_once_with()

    def test_optional_single_view_is_fetched_by_name(self):
        backend = introspect_backend()
        provider = MagicMock()
        mod._handle_introspect_sync(ns(type="views", name="V1"), backend, provider)
        backend.introspector.get_view_info.assert_called_once_with("V1")
        assert provider.display_results.call_args.kwargs["title"] == "View V1"

    def test_optional_single_generator_is_fetched_by_name(self):
        backend = introspect_backend()
        provider = MagicMock()
        mod._handle_introspect_sync(ns(type="generators", name="G1"), backend, provider)
        backend.introspector.get_generator_info.assert_called_once_with("G1")
        assert provider.display_results.call_args.kwargs["title"] == "Generator GEN"

    def test_missing_column_for_value_samples_exits_one(self, capsys):
        backend = introspect_backend()
        with pytest.raises(SystemExit) as exc:
            mod._handle_introspect_sync(ns(type="value-samples", name="T"), backend, MagicMock())
        assert exc.value.code == 1
        assert "--column is required" in capsys.readouterr().err

    def test_missing_right_names_for_join_coverage_exits_one(self, capsys):
        backend = introspect_backend()
        args = ns(type="join-coverage", name="T", column="A")
        with pytest.raises(SystemExit) as exc:
            mod._handle_introspect_sync(args, backend, MagicMock())
        assert exc.value.code == 1
        assert "--right-table and --right-column are required" in capsys.readouterr().err

    def test_unmeasurable_join_coverage_exits_one(self, capsys):
        backend = introspect_backend()
        backend.introspector.estimate_join_coverage.return_value = None
        args = ns(type="join-coverage", name="T", column="A", right_table="R", right_column="B")
        with pytest.raises(SystemExit) as exc:
            mod._handle_introspect_sync(args, backend, MagicMock())
        assert exc.value.code == 1
        assert "no coverage could be measured" in capsys.readouterr().err

    def test_column_profiles_notes_unmeasured_figures(self):
        backend = introspect_backend()
        profiles = [SimpleNamespace(
            column_name="BLOB_A", distinct_count=None, min_value=None, max_value=None
        )]
        backend.introspector.list_column_data_profiles.return_value = profiles
        with patch.object(mod, "_note_unmeasured_profiles") as note:
            mod._handle_introspect_sync(ns(type="column-profiles", name="T"), backend, MagicMock())
        note.assert_called_once_with(profiles, "T")

    def test_connection_error_uses_provider(self):
        backend = introspect_backend()
        backend.connect.side_effect = ConnectionError("down")
        provider = MagicMock()
        with pytest.raises(SystemExit) as exc:
            mod._handle_introspect_sync(ns(type="tables"), backend, provider)
        assert exc.value.code == 1
        provider.display_connection_error.assert_called_once()

    def test_query_error_uses_provider(self):
        backend = introspect_backend()
        backend.introspector.list_tables.side_effect = QueryError("bad")
        provider = MagicMock()
        with pytest.raises(SystemExit) as exc:
            mod._handle_introspect_sync(ns(type="tables"), backend, provider)
        assert exc.value.code == 1
        provider.display_query_error.assert_called_once()

    def test_unexpected_error_goes_to_stderr(self, capsys):
        backend = introspect_backend()
        backend.introspector.list_tables.side_effect = RuntimeError("boom")
        with pytest.raises(SystemExit) as exc:
            mod._handle_introspect_sync(ns(type="tables"), backend, MagicMock())
        assert exc.value.code == 1
        assert "Error during introspection" in capsys.readouterr().err

    def test_no_disconnect_without_connection(self):
        backend = introspect_backend()
        backend._connection = None
        mod._handle_introspect_sync(ns(type="tables"), backend, MagicMock())
        backend.disconnect.assert_not_called()


class TestIntrospectHandle:
    def test_missing_database_guard(self, capsys):
        with pytest.raises(SystemExit) as exc:
            mod.handle(parse(["introspect", "tables"]))
        assert exc.value.code == 1
        assert "--database is required" in capsys.readouterr().err

    def test_async_flag_is_rejected_before_connection(self, capsys):
        with patch.object(mod, "FirebirdBackend") as backend_cls:
            with pytest.raises(SystemExit) as exc:
                mod.handle(parse(["introspect", "tables", "--database", "/x.fdb", "--async"]))
        assert exc.value.code == 1
        assert "does not support" in capsys.readouterr().err
        backend_cls.assert_not_called()

    def test_sync_dispatch(self):
        args = parse(["introspect", "tables", "--database", "/x.fdb"])
        backend = MagicMock()
        with patch.object(mod, "create_provider") as provider_factory, \
                patch.object(mod, "resolve_connection_config_from_args", return_value="cfg") as resolve, \
                patch.object(mod, "FirebirdBackend", return_value=backend) as backend_cls, \
                patch.object(mod, "_handle_introspect_sync") as sync:
            mod.handle(args)
        provider_factory.assert_called_once_with("table", ascii_borders=False)
        resolve.assert_called_once_with(args)
        backend_cls.assert_called_once_with(connection_config="cfg")
        sync.assert_called_once_with(args, backend, provider_factory.return_value)
