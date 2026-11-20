# tests/rhosocial/activerecord_firebird_test/feature/backend/construct/cli/test_status_offline.py
"""Offline, mock-only unit tests for ``firebird.cli.status`` (synchronous paths).

No Firebird server or driver is used.  Parser shape and the pure helpers are
exercised directly; ``handle`` / ``_handle_status_sync`` run against a stub
backend and a stub provider.  The async helpers are deliberately out of scope
(the official driver is synchronous only).
"""

import argparse
import json
import sys
import types
from dataclasses import dataclass
from enum import Enum
from unittest.mock import MagicMock, patch

import pytest

from rhosocial.activerecord.backend.errors import ConnectionError, QueryError
from rhosocial.activerecord.backend.impl.firebird.cli import status as mod
from rhosocial.activerecord.backend.impl.firebird.cli.status import STATUS_TYPES
from rhosocial.activerecord.backend.introspection.status import (
    ConnectionInfo,
    DatabaseBriefInfo,
    ServerOverview,
    SessionInfo,
    StatusItem,
    StorageInfo,
    UserInfo,
)


def parse(argv):
    parser = argparse.ArgumentParser(prog="firebird")
    subparsers = parser.add_subparsers(dest="command")
    mod.create_parser(subparsers)
    return parser.parse_args(argv)


@pytest.fixture(autouse=True)
def clean_fb_env(monkeypatch):
    for name in ("FIREBIRD_HOST", "FIREBIRD_PORT", "FIREBIRD_DATABASE",
                 "FIREBIRD_USER", "FIREBIRD_PASSWORD", "FIREBIRD_ROLE"):
        monkeypatch.delenv(name, raising=False)


class TestStatusParser:
    def test_defaults(self):
        args = parse(["status"])
        assert args.type == "all"
        assert args.output == "table"
        assert args.verbose == 0
        assert args.rich_ascii is False
        assert args.is_async is False

    @pytest.mark.parametrize("status_type", STATUS_TYPES)
    def test_every_status_type_accepted(self, status_type):
        assert parse(["status", status_type]).type == status_type

    def test_verbosity_is_counted(self):
        assert parse(["status", "-v"]).verbose == 1
        assert parse(["status", "-vvv"]).verbose == 3
        assert parse(["status", "--verbose", "--verbose"]).verbose == 2

    def test_rich_ascii_flag(self):
        assert parse(["status", "--rich-ascii"]).rich_ascii is True

    @pytest.mark.parametrize("fmt", ["table", "json", "csv", "tsv"])
    def test_output_choices(self, fmt):
        assert parse(["status", "-o", fmt]).output == fmt

    def test_unknown_output_rejected(self):
        with pytest.raises(SystemExit) as exc:
            parse(["status", "-o", "yaml"])
        assert exc.value.code == 2

    def test_unknown_type_rejected(self):
        with pytest.raises(SystemExit) as exc:
            parse(["status", "bogus"])
        assert exc.value.code == 2


class Colour(Enum):
    RED = "red"


@dataclass
class Point:
    x: int
    y: int


class ModelDump:
    def model_dump(self, mode="python"):
        return {"mode": mode, "colour": Colour.RED}


class StrictModelDump:
    def model_dump(self):
        return {"ok": True}


class TestSerializeForOutput:
    def test_none_and_primitives(self):
        assert mod._serialize_for_output(None) is None
        assert mod._serialize_for_output("x") == "x"
        assert mod._serialize_for_output(3) == 3
        assert mod._serialize_for_output(1.5) == 1.5
        assert mod._serialize_for_output(True) is True

    def test_enum_dataclass_tuple(self):
        assert mod._serialize_for_output(Colour.RED) == "red"
        assert mod._serialize_for_output(Point(1, 2)) == {"x": 1, "y": 2}
        assert mod._serialize_for_output((Colour.RED, 2)) == ["red", 2]

    def test_nested_dict_and_list(self):
        obj = {"p": Point(1, 2), "c": Colour.RED, "items": [Colour.RED, Point(3, 4)]}
        assert mod._serialize_for_output(obj) == {
            "p": {"x": 1, "y": 2},
            "c": "red",
            "items": ["red", {"x": 3, "y": 4}],
        }

    def test_model_dump_json_mode_recurses(self):
        assert mod._serialize_for_output(ModelDump()) == {"mode": "json", "colour": "red"}

    def test_model_dump_typeerror_falls_back(self):
        assert mod._serialize_for_output(StrictModelDump()) == {"ok": True}

    def test_unknown_object_falls_back_to_str(self):
        class Weird:
            def __str__(self):
                return "weird"

        assert mod._serialize_for_output(Weird()) == "weird"


class TestFormatSize:
    @pytest.mark.parametrize("size,expected", [
        (None, "N/A"),
        (0, "0.0 B"),
        (1023, "1023.0 B"),
        (1024, "1.0 KB"),
        (1536, "1.5 KB"),
        (1024 ** 2, "1.0 MB"),
        (1024 ** 3, "1.0 GB"),
        (1024 ** 4, "1.0 TB"),
        (1024 ** 5, "1.0 PB"),
    ])
    def test_units(self, size, expected):
        assert mod._format_size(size) == expected


class _FakeTable:
    def __init__(self, *args, **kwargs):
        self.columns = []
        self.rows = []

    def add_column(self, *args, **kwargs):
        self.columns.append((args, kwargs))

    def add_row(self, *args, **kwargs):
        self.rows.append((args, kwargs))


class _FakeConsole:
    printed = []

    def __init__(self, *args, **kwargs):
        pass

    def print(self, *args, **kwargs):
        for item in args:
            if isinstance(item, _FakeTable):
                for call_args, _ in item.columns:
                    _FakeConsole.printed.extend(str(x) for x in call_args)
                for call_args, _ in item.rows:
                    _FakeConsole.printed.extend(str(x) for x in call_args)
            else:
                _FakeConsole.printed.append(str(item))


@pytest.fixture
def fake_rich():
    console_mod = types.ModuleType("rich.console")
    console_mod.Console = _FakeConsole
    table_mod = types.ModuleType("rich.table")
    table_mod.Table = _FakeTable
    rich_mod = types.ModuleType("rich")
    rich_mod.console = console_mod
    rich_mod.table = table_mod
    with patch.dict(sys.modules, {
        "rich": rich_mod,
        "rich.console": console_mod,
        "rich.table": table_mod,
    }):
        _FakeConsole.printed = []
        yield


class TestDisplayStatusRich:
    def test_every_optional_section_renders(self, fake_rich):
        overview = ServerOverview(
            server_version="WI-V5",
            server_vendor="Firebird",
            session=SessionInfo(user="SYSDBA", database="/data/app.fdb"),
            connections=ConnectionInfo(active_count=4),
            configuration=[StatusItem(name="MaxBuffers", value=1024, description="cache")],
            performance=[StatusItem(name="Reads", value=7)],
            storage=StorageInfo(total_size_bytes=2048, free_space_bytes=512),
            databases=[DatabaseBriefInfo(name="employees.fdb")],
            users=[UserInfo(name="SYSDBA")],
        )
        mod._display_status_rich(overview)
        out = " ".join(_FakeConsole.printed)
        for token in (
            "Server Status", "WI-V5", "Firebird", "Session", "SYSDBA", "/data/app.fdb",
            "Active Connections", "4", "Configuration", "MaxBuffers", "Performance", "Reads",
            "Storage", "Total size", "2.0 KB", "Free space", "512.0 B", "Databases",
            "employees.fdb", "Users",
        ):
            assert token in out

    def test_missing_optional_sections_do_not_crash(self, fake_rich):
        overview = ServerOverview(server_version="v", server_vendor="v")
        mod._display_status_rich(overview)
        out = " ".join(_FakeConsole.printed)
        assert "Server Status" in out
        assert "Session" not in out
        assert "Configuration" not in out

    def test_verbose_adds_description_column(self, fake_rich):
        overview = ServerOverview(
            server_version="v",
            server_vendor="v",
            configuration=[StatusItem(name="P", value=1, description="a description")],
        )
        mod._display_status_rich(overview, verbose=1)
        assert "Description" in _FakeConsole.printed
        assert "a description" in _FakeConsole.printed


def status_backend():
    backend = MagicMock()
    backend._connection = object()
    si = backend.introspector.status
    overview = MagicMock()
    overview.to_dict.return_value = {"server_version": "v", "configuration": []}
    si.get_overview.return_value = overview
    si.list_configuration.return_value = [{"name": "P", "value": 1}]
    si.list_performance_metrics.return_value = [{"name": "R", "value": 2}]
    si.get_connection_info.return_value = {"user": "SYSDBA"}
    si.get_storage_info.return_value = {"total_size_bytes": 10}
    si.list_databases.return_value = ["db.fdb"]
    si.list_users.return_value = ["SYSDBA"]
    return backend


def status_args(status_type, output="json", verbose=0):
    return argparse.Namespace(type=status_type, output=output, verbose=verbose, rich_ascii=False)


class TestHandleStatusSync:
    @pytest.mark.parametrize("status_type,method,title", [
        ("config", "list_configuration", "Configuration"),
        ("performance", "list_performance_metrics", "Performance"),
        ("connections", "get_connection_info", "Connections"),
        ("storage", "get_storage_info", "Storage"),
        ("databases", "list_databases", "Databases"),
        ("users", "list_users", "Users"),
    ])
    def test_each_type_dispatches_and_disconnects(self, status_type, method, title):
        backend = status_backend()
        provider = MagicMock()
        mod._handle_status_sync(status_args(status_type), backend, provider)
        backend.connect.assert_called_once_with()
        backend.introspect_and_adapt.assert_called_once_with()
        getattr(backend.introspector.status, method).assert_called_once()
        provider.display_results.assert_called_once()
        assert provider.display_results.call_args.kwargs["title"] == title
        backend.disconnect.assert_called_once_with()

    def test_all_json(self, capsys):
        backend = status_backend()
        mod._handle_status_sync(status_args("all"), backend, MagicMock())
        assert json.loads(capsys.readouterr().out)["server_version"] == "v"

    @pytest.mark.parametrize("fmt", ["csv", "tsv"])
    def test_all_flat_output_falls_back_to_json(self, capsys, fmt):
        backend = status_backend()
        mod._handle_status_sync(status_args("all", output=fmt), backend, MagicMock())
        assert json.loads(capsys.readouterr().out)["server_version"] == "v"

    def test_all_table_uses_rich_display(self):
        backend = status_backend()
        args = status_args("all", output="table", verbose=2)
        with patch.object(mod, "_display_status_rich") as display:
            mod._handle_status_sync(args, backend, MagicMock())
        overview = backend.introspector.status.get_overview.return_value
        display.assert_called_once_with(overview, 2)

    def test_connection_error_uses_provider(self):
        backend = status_backend()
        backend.connect.side_effect = ConnectionError("down")
        provider = MagicMock()
        with pytest.raises(SystemExit) as exc:
            mod._handle_status_sync(status_args("config"), backend, provider)
        assert exc.value.code == 1
        provider.display_connection_error.assert_called_once()

    def test_query_error_uses_provider(self):
        backend = status_backend()
        backend.introspector.status.list_configuration.side_effect = QueryError("bad")
        provider = MagicMock()
        with pytest.raises(SystemExit) as exc:
            mod._handle_status_sync(status_args("config"), backend, provider)
        assert exc.value.code == 1
        provider.display_query_error.assert_called_once()

    def test_unexpected_error_goes_to_stderr(self, capsys):
        backend = status_backend()
        backend.introspector.status.list_configuration.side_effect = RuntimeError("boom")
        with pytest.raises(SystemExit) as exc:
            mod._handle_status_sync(status_args("config"), backend, MagicMock())
        assert exc.value.code == 1
        assert "Error during status retrieval" in capsys.readouterr().err

    def test_no_disconnect_without_connection(self):
        backend = status_backend()
        backend._connection = None
        mod._handle_status_sync(status_args("users"), backend, MagicMock())
        backend.disconnect.assert_not_called()


class TestStatusHandle:
    def test_missing_database_guard(self, capsys):
        with pytest.raises(SystemExit) as exc:
            mod.handle(parse(["status", "config"]))
        assert exc.value.code == 1
        assert "--database is required" in capsys.readouterr().err

    def test_async_flag_is_rejected_before_connection(self, capsys):
        with patch.object(mod, "FirebirdBackend") as backend_cls:
            with pytest.raises(SystemExit) as exc:
                mod.handle(parse(["status", "config", "--database", "/x.fdb", "--async"]))
        assert exc.value.code == 1
        assert "does not support" in capsys.readouterr().err
        backend_cls.assert_not_called()

    def test_sync_dispatch(self):
        args = parse(["status", "config", "--database", "/x.fdb", "-o", "json"])
        backend = MagicMock()
        with patch.object(mod, "create_provider") as provider_factory, \
                patch.object(mod, "resolve_connection_config_from_args", return_value="cfg") as resolve, \
                patch.object(mod, "FirebirdBackend", return_value=backend) as backend_cls, \
                patch.object(mod, "_handle_status_sync") as sync:
            mod.handle(args)
        provider_factory.assert_called_once_with("json", ascii_borders=False)
        resolve.assert_called_once_with(args)
        backend_cls.assert_called_once_with(connection_config="cfg")
        sync.assert_called_once_with(args, backend, provider_factory.return_value)
