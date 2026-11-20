# tests/rhosocial/activerecord_firebird_test/feature/backend/construct/cli/test_named_expression_offline.py
"""Offline, mock-only unit tests for ``firebird.cli.named_expression``.

This module is a thin adapter over the shared named-expression helper.  The
helper call, the connection/output parser and the injected closures are all
exercised with mocks; no connection is ever opened.  Only the synchronous
``handle`` branch is covered.
"""

import argparse
from unittest.mock import MagicMock

import pytest

from rhosocial.activerecord.backend.impl.firebird import dialect as dialect_mod
from rhosocial.activerecord.backend.impl.firebird.cli import named_expression as mod
from rhosocial.activerecord.backend.named_expression import cli as ne_mod


def parse(argv):
    parser = argparse.ArgumentParser(prog="firebird")
    subparsers = parser.add_subparsers(dest="command")
    mod.create_parser(subparsers)
    return parser.parse_args(argv)


def capture(monkeypatch, argv, backend=None):
    """Run ``handle`` with every seam replaced and return its closures."""
    backend = backend if backend is not None else MagicMock()
    provider = MagicMock()
    resolve = MagicMock(return_value="cfg")
    backend_cls = MagicMock(return_value=backend)
    dialect_cls = MagicMock()
    captured = {}

    def fake_handle_ne(args, provider_arg, **kwargs):
        captured["args"] = args
        captured["provider"] = provider_arg
        captured["kwargs"] = kwargs

    monkeypatch.setattr(mod, "create_provider", MagicMock(return_value=provider))
    monkeypatch.setattr(mod, "resolve_connection_config_from_args", resolve)
    monkeypatch.setattr(mod, "FirebirdBackend", backend_cls)
    monkeypatch.setattr(dialect_mod, "FirebirdDialect", dialect_cls)
    monkeypatch.setattr(ne_mod, "handle_named_expression", fake_handle_ne)

    args = parse(argv)
    mod.handle(args)
    return args, provider, backend, resolve, backend_cls, dialect_cls, captured


@pytest.fixture(autouse=True)
def clean_fb_env(monkeypatch):
    for name in ("FIREBIRD_HOST", "FIREBIRD_PORT", "FIREBIRD_DATABASE",
                 "FIREBIRD_USER", "FIREBIRD_PASSWORD", "FIREBIRD_ROLE"):
        monkeypatch.delenv(name, raising=False)


class TestNamedExpressionParser:
    def test_defaults(self):
        args = parse(["named-expression"])
        assert args.qualified_name is None
        assert args.dialect_version is None
        assert args.output == "table"
        assert args.rich_ascii is False
        assert args.is_async is False
        assert args.list_queries is False
        assert args.describe is False
        assert args.dry_run is False

    def test_connection_output_and_version_flags(self):
        args = parse([
            "named-expression", "app.queries.orders",
            "--database", "/x.fdb", "--host", "h", "--port", "3055",
            "-o", "json", "--rich-ascii", "--dialect-version", "4.0.1",
        ])
        assert args.qualified_name == "app.queries.orders"
        assert args.database == "/x.fdb"
        assert args.host == "h"
        assert args.port == 3055
        assert args.output == "json"
        assert args.rich_ascii is True
        assert args.dialect_version == "4.0.1"

    def test_shared_helper_flags_available(self):
        args = parse([
            "named-expression", "app.queries", "--list", "--describe",
            "--dry-run", "--force", "--explain", "--param", "x=1",
        ])
        assert args.list_queries is True
        assert args.describe is True
        assert args.dry_run is True
        assert args.force is True
        assert args.explain is True
        assert args.params == ["x=1"]


class TestNamedExpressionHandleSync:
    def test_delegates_to_shared_helper_with_sync_closures(self, monkeypatch):
        args, provider, _, _, _, _, captured = capture(
            monkeypatch, ["named-expression", "app.q.x", "--database", "/x.fdb"]
        )
        assert captured["args"] is args
        assert captured["provider"] is provider
        kwargs = captured["kwargs"]
        for key in ("backend_factory", "get_dialect", "execute_query", "disconnect", "create_dialect"):
            assert key in kwargs
        for key in ("backend_async_factory", "get_dialect_async", "execute_query_async", "disconnect_async"):
            assert key not in kwargs

    def test_create_dialect_without_version(self, monkeypatch):
        *_, dialect_cls, captured = capture(
            monkeypatch, ["named-expression", "app.q.x", "--database", "/x.fdb"]
        )
        captured["kwargs"]["create_dialect"]()
        dialect_cls.assert_called_once_with(version=None)

    def test_create_dialect_with_requested_version(self, monkeypatch):
        *_, dialect_cls, captured = capture(
            monkeypatch,
            ["named-expression", "app.q.x", "--database", "/x.fdb", "--dialect-version", "3.0.0"],
        )
        captured["kwargs"]["create_dialect"]()
        dialect_cls.assert_called_once_with(version=(3, 0, 0))

    def test_backend_factory_connects_and_adapts(self, monkeypatch):
        args, _, backend, resolve, backend_cls, _, captured = capture(
            monkeypatch, ["named-expression", "app.q.x", "--database", "/x.fdb"]
        )
        result = captured["kwargs"]["backend_factory"]()
        assert result is backend
        resolve.assert_called_once_with(args)
        backend_cls.assert_called_once_with(connection_config="cfg")
        backend.connect.assert_called_once_with()
        backend.introspect_and_adapt.assert_called_once_with()

    def test_backend_factory_applies_requested_version(self, monkeypatch):
        _, _, backend, _, _, _, captured = capture(
            monkeypatch,
            ["named-expression", "app.q.x", "--database", "/x.fdb", "--dialect-version", "2.5.9"],
        )
        captured["kwargs"]["backend_factory"]()
        assert backend.dialect.version == (2, 5, 9)

    def test_get_dialect_returns_backend_dialect(self, monkeypatch):
        _, _, backend, _, _, _, captured = capture(
            monkeypatch, ["named-expression", "app.q.x", "--database", "/x.fdb"]
        )
        captured["kwargs"]["backend_factory"]()
        assert captured["kwargs"]["get_dialect"](backend) is backend.dialect

    def test_execute_query_by_name_builds_execution_options(self, monkeypatch):
        _, _, backend, _, _, _, captured = capture(
            monkeypatch, ["named-expression", "app.q.x", "--database", "/x.fdb"]
        )
        captured["kwargs"]["backend_factory"]()
        stmt_type = object()
        captured["kwargs"]["execute_query"]("SELECT 1", (1,), stmt_type)
        backend.execute.assert_called_once()
        call = backend.execute.call_args
        assert call.args == ("SELECT 1", (1,))
        assert call.kwargs["options"].stmt_type is stmt_type

    def test_disconnect_when_connected(self, monkeypatch):
        _, _, backend, _, _, _, captured = capture(
            monkeypatch, ["named-expression", "app.q.x", "--database", "/x.fdb"]
        )
        captured["kwargs"]["backend_factory"]()
        backend._connection = object()
        captured["kwargs"]["disconnect"]()
        backend.disconnect.assert_called_once_with()

    def test_disconnect_without_connection_is_noop(self, monkeypatch):
        _, _, backend, _, _, _, captured = capture(
            monkeypatch, ["named-expression", "app.q.x", "--database", "/x.fdb"]
        )
        captured["kwargs"]["backend_factory"]()
        backend._connection = None
        captured["kwargs"]["disconnect"]()
        backend.disconnect.assert_not_called()

    def test_async_flag_is_rejected_before_delegation(self, monkeypatch, capsys):
        handle_ne = MagicMock()
        monkeypatch.setattr(ne_mod, "handle_named_expression", handle_ne)
        args = parse([
            "named-expression", "app.q.x", "--database", "/x.fdb", "--async",
        ])
        with pytest.raises(SystemExit) as exc:
            mod.handle(args)
        assert exc.value.code == 1
        assert "does not support" in capsys.readouterr().err
        handle_ne.assert_not_called()
