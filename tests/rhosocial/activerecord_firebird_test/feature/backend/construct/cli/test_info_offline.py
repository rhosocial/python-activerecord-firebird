# tests/rhosocial/activerecord_firebird_test/feature/backend/construct/cli/test_info_offline.py
"""Offline, mock-only unit tests for ``firebird.cli.info`` (synchronous paths).

The environment report is built from a simulated dialect (or a stub backend
when ``--database`` is given), and the rich-display helpers are driven with a
stub console.  No Firebird server, driver or real terminal is used.
"""

import argparse
import json
import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from rhosocial.activerecord.backend.errors import ConnectionError
from rhosocial.activerecord.backend.impl.firebird import backend as firebird_backend_mod
from rhosocial.activerecord.backend.impl.firebird.cli import info as mod
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect


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


class TestInfoParser:
    def test_defaults(self):
        args = parse(["info"])
        assert args.output == "table"
        assert args.verbose == 0
        assert args.version is None
        assert args.database is None
        assert args.rich_ascii is False

    @pytest.mark.parametrize("fmt", ["table", "json"])
    def test_output_choices(self, fmt):
        assert parse(["info", "-o", fmt]).output == fmt

    @pytest.mark.parametrize("fmt", ["csv", "tsv"])
    def test_flat_output_rejected(self, fmt):
        with pytest.raises(SystemExit) as exc:
            parse(["info", "-o", fmt])
        assert exc.value.code == 2

    def test_verbosity_is_counted(self):
        assert parse(["info"]).verbose == 0
        assert parse(["info", "-v"]).verbose == 1
        assert parse(["info", "-vvv"]).verbose == 3

    def test_version_and_rich_ascii(self):
        args = parse(["info", "--version", "3.0.0", "--rich-ascii"])
        assert args.version == "3.0.0"
        assert args.rich_ascii is True


class TestParseVersion:
    @pytest.mark.parametrize("text,expected", [
        ("4", (4, 0, 0)),
        ("3.1", (3, 1, 0)),
        ("2.5.9", (2, 5, 9)),
        ("5.0.2", (5, 0, 2)),
    ])
    def test_partial_and_full_versions(self, text, expected):
        assert mod.parse_version(text) == expected


class TestProtocolDiscovery:
    def test_support_methods_are_filtered_and_sorted(self):
        class Dummy:
            def supports_alpha(self):
                return True

            def is_beta_available(self):
                return True

            def format_gamma(self):
                return ""

        assert mod.get_protocol_support_methods(Dummy) == [
            "is_beta_available", "supports_alpha",
        ]

    def test_check_bool_and_parameterless_methods(self):
        class Proto:
            def supports_alpha(self):
                return True

            def supports_beta(self):
                return False

            def supports_blob_sub_type_binary(self):
                return True

            def supports_blob_sub_type_text(self):
                return True

            def is_gamma_available(self):
                return True

        dialect = SimpleNamespace(
            supports_alpha=lambda: True,
            supports_beta=lambda: False,
            supports_blob_sub_type_binary=lambda: True,
            supports_blob_sub_type_text=lambda: True,
            is_gamma_available=lambda: True,
        )
        result = mod.check_protocol_support(dialect, Proto)
        assert result["supports_alpha"] is True
        assert result["supports_beta"] is False
        assert result["is_gamma_available"] is True
        assert result["supports_blob_sub_type_binary"] is True
        assert result["supports_blob_sub_type_text"] is True

    def test_missing_method_is_false(self):
        class Proto:
            def supports_absent(self):
                return True

        assert mod.check_protocol_support(SimpleNamespace(), Proto) == {"supports_absent": False}

    def test_parameterized_method_is_not_a_support_switch(self):
        class Proto:
            def supports_needs_arg(self, value):
                return True

        dialect = SimpleNamespace(supports_needs_arg=lambda value: value)
        assert mod.check_protocol_support(dialect, Proto) == {"supports_needs_arg": False}

    def test_raising_method_is_false(self):
        class Proto:
            def supports_boom(self):
                return True

        def boom():
            raise RuntimeError("boom")

        assert mod.check_protocol_support(SimpleNamespace(supports_boom=boom), Proto) == {
            "supports_boom": False,
        }


class TestCalculateProtocolStats:
    @pytest.mark.parametrize("methods,expected", [
        ({}, (0, 0)),
        ({"a": True, "b": False}, (1, 2)),
        ({"a": True, "multi": {"supported": 2, "total": 5}}, (3, 6)),
    ])
    def test_counts(self, methods, expected):
        assert mod._calculate_protocol_stats(methods) == expected


class TestBuildProtocolInfo:
    def _protocol(self):
        class Proto:
            def supports_alpha(self):
                return True

        return Proto

    def test_summary_omits_methods(self):
        dialect = SimpleNamespace(supports_alpha=lambda: True)
        info = mod._build_protocol_info(dialect, "G", [self._protocol()], 0)
        assert info["Proto"] == {"supported": 1, "total": 1, "percentage": 100}

    def test_verbose_includes_methods(self):
        dialect = SimpleNamespace(supports_alpha=lambda: True)
        info = mod._build_protocol_info(dialect, "G", [self._protocol()], 2)
        assert info["Proto"] == {
            "supported": 1,
            "total": 1,
            "percentage": 100,
            "methods": {"supports_alpha": True},
        }

    def test_zero_total_has_zero_percentage(self):
        class Empty:
            pass

        info = mod._build_protocol_info(SimpleNamespace(), "G", [Empty], 0)
        assert info["Empty"]["percentage"] == 0


class TestDisplayStyles:
    @pytest.mark.parametrize("pct,expected", [
        (100, ("green", "[OK]")),
        (99, ("yellow", "[~]")),
        (50, ("yellow", "[~]")),
        (1, ("red", "[~]")),
        (0, ("red", "[X]")),
    ])
    def test_status_style(self, pct, expected):
        assert mod._get_status_style(pct) == expected

    @pytest.mark.parametrize("name,expected", [
        ("supports_window_functions", "window functions"),
        ("supports_blob_sub_type", "blob sub type"),
        ("is_beta_available", "is beta available"),
    ])
    def test_method_display(self, name, expected):
        assert mod._format_method_display(name) == expected


class TestInfoDisplayHelpers:
    def test_method_details_bool_and_dict(self):
        console = MagicMock()
        mod._display_method_details(console, "supports_alpha", True)
        mod._display_method_details(console, "supports_beta", False)
        mod._display_method_details(
            console, "supports_blob_sub_type", {"args": {"0": True, "1": False}}
        )
        text = " ".join(str(call) for call in console.print.call_args_list)
        assert "[OK]" in text
        assert "[X]" in text
        assert "alpha" in text
        assert "blob sub type" in text

    def test_protocol_item_renders_bar_and_percentage(self):
        console = MagicMock()
        stats = {"supported": 1, "total": 2, "percentage": 50}
        mod._display_protocol_item(console, "Proto", stats, 0)
        text = " ".join(str(call) for call in console.print.call_args_list)
        assert "Proto" in text
        assert "50%" in text
        assert "#" in text
        assert "-" in text

    def test_protocol_item_verbose_details(self):
        console = MagicMock()
        stats = {
            "supported": 1, "total": 1, "percentage": 100,
            "methods": {"supports_alpha": True},
        }
        with patch.object(mod, "_display_method_details") as details:
            mod._display_protocol_item(console, "Proto", stats, 2)
        details.assert_called_once_with(console, "supports_alpha", True)

    def test_protocol_group_marks_dialect_specific(self):
        console = MagicMock()
        protocols = {"Proto": {"supported": 1, "total": 1, "percentage": 100}}
        mod._display_protocol_group(console, "Firebird-specific", protocols, 0)
        mod._display_protocol_group(console, "Query Features", protocols, 0)
        text = " ".join(str(call) for call in console.print.call_args_list)
        assert "dialect-specific" in text
        assert "Query Features" in text

    @pytest.fixture
    def fake_console(self):
        console = MagicMock()
        console_mod = types.ModuleType("rich.console")
        console_mod.Console = MagicMock(return_value=console)
        rich_mod = types.ModuleType("rich")
        rich_mod.console = console_mod
        with patch.dict(sys.modules, {"rich": rich_mod, "rich.console": console_mod}):
            yield console

    def test_display_info_rich_connected_and_disconnected(self, fake_console):
        info = {
            "protocols": {
                "Query Features": {
                    "Proto": {"supported": 1, "total": 1, "percentage": 100},
                },
            },
        }
        mod._display_info_rich(info, 0, "5.0.2", True)
        connected_text = " ".join(str(c) for c in fake_console.print.call_args_list)
        assert "Firebird Environment Information" in connected_text
        assert "5.0.2" in connected_text
        assert "from actual connection" in connected_text
        assert "Query Features" in connected_text
        assert "Proto" in connected_text

        fake_console.print.reset_mock()
        mod._display_info_rich(info, 2, "4.0.0", False)
        default_text = " ".join(str(c) for c in fake_console.print.call_args_list)
        assert "default value" in default_text
        assert "Detailed" in default_text


class FakeInfoBackend:
    last_instance = None

    def __init__(self, connection_config=None):
        self.connection_config = connection_config
        self.dialect = FirebirdDialect((5, 0, 0))
        self.disconnect_calls = 0
        FakeInfoBackend.last_instance = self

    def connect(self):
        pass

    def introspect_and_adapt(self):
        pass

    def get_server_version(self):
        return (5, 0, 2)

    def disconnect(self):
        self.disconnect_calls += 1


class TestInfoHandle:
    def test_default_report_shape(self, capsys):
        mod.handle(parse(["info", "-o", "json"]))
        payload = json.loads(capsys.readouterr().out)
        assert payload["database"] == {
            "type": "firebird",
            "version": "4.0.0",
            "version_tuple": [4, 0, 0],
            "connected": False,
        }
        assert "Firebird-specific" in payload["protocols"]
        assert "Query Features" in payload["protocols"]

    def test_version_override(self, capsys):
        mod.handle(parse(["info", "-o", "json", "--version", "3.0.7"]))
        payload = json.loads(capsys.readouterr().out)
        assert payload["database"]["version"] == "3.0.7"
        assert payload["database"]["version_tuple"] == [3, 0, 7]

    def test_verbose_json_contains_methods(self, capsys):
        mod.handle(parse(["info", "-o", "json", "-vv"]))
        payload = json.loads(capsys.readouterr().out)
        for stats in payload["protocols"]["Firebird-specific"].values():
            assert "methods" in stats

    def test_connected_report_uses_backend(self, monkeypatch, capsys):
        monkeypatch.setattr(firebird_backend_mod, "FirebirdBackend", FakeInfoBackend)
        monkeypatch.setattr(mod, "resolve_connection_config_from_args", lambda args: "cfg")
        mod.handle(parse(["info", "-o", "json", "--database", "/x.fdb"]))
        payload = json.loads(capsys.readouterr().out)
        assert payload["database"]["connected"] is True
        assert payload["database"]["version"] == "5.0.2"
        assert FakeInfoBackend.last_instance.disconnect_calls == 1

    def test_connection_failure_falls_back_to_defaults(self, monkeypatch, capsys):
        class Refused(FakeInfoBackend):
            def connect(self):
                raise ConnectionError("down")

        monkeypatch.setattr(firebird_backend_mod, "FirebirdBackend", Refused)
        monkeypatch.setattr(mod, "resolve_connection_config_from_args", lambda args: "cfg")
        mod.handle(parse(["info", "-o", "json", "--database", "/x.fdb"]))
        payload = json.loads(capsys.readouterr().out)
        assert payload["database"]["connected"] is False
        assert payload["database"]["version"] == "4.0.0"
