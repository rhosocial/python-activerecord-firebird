# tests/rhosocial/activerecord_firebird_test/feature/backend/introspection/test_status_introspector.py
"""Offline unit tests for Firebird status introspection.

Covers :class:`SyncFirebirdStatusIntrospector` and :class:`AsyncFirebirdStatusIntrospector`
using a scripted backend whose ``execute`` returns fake ``QueryResult``-like objects
with a ``data`` attribute. Both the happy paths and the defensive exception paths
of every status method are exercised without a live Firebird server.
"""
from types import SimpleNamespace

import pytest

from rhosocial.activerecord.backend.impl.firebird.introspection.status_introspector import (
    AsyncFirebirdStatusIntrospector,
    SyncFirebirdStatusIntrospector,
)
from rhosocial.activerecord.backend.introspection.status import (
    ServerOverview,
    StatusCategory,
    StatusItem,
)

DEFAULT_ROWS = {
    "RDB$GET_CONTEXT": [{"VERSION": "WI-V5.0.0"}],
    "MON$STATEMENTS": [{"C": 3}],
    "MON$ATTACHMENT_ID": [
        {"ID": 1, "USERNAME": "SYSDBA", "REMOTE_ADDR": "127.0.0.1", "REMOTE_PID": 1234}
    ],
    "MON$USER": [{"USERNAME": "SYSDBA"}],
    "MON$ATTACHMENTS": [{"C": 2}],
    "MON$DATABASE_FILES": [{"FILE_ID": 0, "PAGES": 100, "SIZE_BYTES": 819200}],
    "MON$PAGE_SIZE": [{"SIZE_BYTES": 409600}],
    "MON$DATABASE_NAME": [{"NAME": "/tmp/app.fdb"}],
    "RDB$USERS": [{"USERNAME": "SYSDBA"}, {"USERNAME": "APP_USER"}],
}


class FakeResult:
    """Minimal QueryResult stand-in exposing only the ``data`` attribute."""

    def __init__(self, data):
        self.data = data


class ScriptedStatusBackend:
    """Sync backend stub that answers SQL with fake row sets by keyword match."""

    def __init__(self, config=None, rows=None, raise_on=None):
        self.config = config or SimpleNamespace(
            charset="UTF8", username="SYSDBA", database="/tmp/app.fdb"
        )
        self._rows = rows or DEFAULT_ROWS
        self._raise_on = tuple(raise_on or ())
        self.calls = []

    def execute(self, sql):
        self.calls.append(sql)
        upper = (sql or "").upper()
        if self._raise_on and any(marker in upper for marker in self._raise_on):
            raise RuntimeError("boom")
        for marker, data in self._rows.items():
            if marker in upper:
                return FakeResult(data)
        return FakeResult([])


class ScriptedAsyncStatusBackend(ScriptedStatusBackend):
    """Async backend stub with the same row script as the sync variant."""

    async def execute(self, sql):
        return super().execute(sql)


@pytest.fixture
def sync_backend():
    """Return a scripted sync status backend with default rows."""
    return ScriptedStatusBackend()


@pytest.fixture
def async_backend():
    """Return a scripted async status backend with default rows."""
    return ScriptedAsyncStatusBackend()


@pytest.fixture
def sync_introspector(sync_backend):
    """Return a SyncFirebirdStatusIntrospector bound to the scripted backend."""
    return SyncFirebirdStatusIntrospector(sync_backend)


@pytest.fixture
def async_introspector(async_backend):
    """Return an AsyncFirebirdStatusIntrospector bound to the scripted backend."""
    return AsyncFirebirdStatusIntrospector(async_backend)


class TestSyncStatusIntrospector:
    """Tests for the synchronous Firebird status introspector."""

    def test_get_overview_builds_complete_overview(self, sync_introspector):
        """get_overview must aggregate every status section into a ServerOverview."""
        overview = sync_introspector.get_overview()
        assert isinstance(overview, ServerOverview), "get_overview must return a ServerOverview"
        assert overview.server_version == "WI-V5.0.0", "server version must come from RDB$GET_CONTEXT"
        assert overview.server_vendor == "Firebird", "vendor must be Firebird"
        assert overview.configuration, "configuration items must be populated"
        assert overview.performance, "performance items must be populated"
        assert overview.connections.active_count == 2, "active connections must be counted"
        assert overview.storage.total_size_bytes == 409600, "storage size must be read from MON$PAGE_SIZE"
        assert overview.databases, "databases must be listed"
        assert overview.users, "users must be listed"
        assert overview.session.user == "SYSDBA", "session user must come from config"

    def test_get_version_string_from_row(self, sync_introspector):
        """_get_version_string must return the row version when present."""
        assert sync_introspector._get_version_string() == "WI-V5.0.0", (
            "version row must be returned verbatim"
        )

    def test_get_version_string_missing_key_returns_unknown(self):
        """A row without a version key must yield the fallback 'unknown'."""
        backend = ScriptedStatusBackend(rows={**DEFAULT_ROWS, "RDB$GET_CONTEXT": [{"OTHER": 1}]})
        introspector = SyncFirebirdStatusIntrospector(backend)
        assert introspector._get_version_string() == "unknown", "missing version key must fall back"

    def test_get_version_string_empty_rows_returns_unknown(self):
        """Empty rows from the version query must yield the fallback 'unknown'."""
        backend = ScriptedStatusBackend(rows={**DEFAULT_ROWS, "RDB$GET_CONTEXT": []})
        introspector = SyncFirebirdStatusIntrospector(backend)
        assert introspector._get_version_string() == "unknown", "empty version rows must fall back"

    def test_get_version_string_handles_exception(self):
        """A failing version query must be swallowed and yield 'unknown'."""
        backend = ScriptedStatusBackend(raise_on=("RDB$GET_CONTEXT",))
        introspector = SyncFirebirdStatusIntrospector(backend)
        assert introspector._get_version_string() == "unknown", "exception must not propagate"

    def test_list_configuration_all_and_filtered(self, sync_introspector):
        """list_configuration must honor the category filter."""
        all_items = sync_introspector.list_configuration()
        assert len(all_items) == 2, "server_version and client_charset must be present"
        assert all_items[0].name == "server_version", "first config item is server_version"
        assert all_items[0].is_readonly is True, "server_version must be marked read-only"
        assert all_items[1].name == "client_charset", "second config item is client_charset"
        assert all_items[1].value == "UTF8", "client_charset must come from backend config"
        assert sync_introspector.list_configuration(StatusCategory.CONFIGURATION) == all_items, (
            "CONFIGURATION filter must keep all config items"
        )
        assert sync_introspector.list_configuration(StatusCategory.PERFORMANCE) == [], (
            "PERFORMANCE filter must drop config items"
        )

    def test_list_configuration_charset_default_when_missing(self):
        """A config without a charset attribute must default to UTF8."""
        backend = ScriptedStatusBackend(config=SimpleNamespace())
        introspector = SyncFirebirdStatusIntrospector(backend)
        items = introspector.list_configuration()
        assert items[1].value == "UTF8", "charset must default to UTF8 when absent"

    def test_list_performance_metrics_all_and_filtered(self, sync_introspector):
        """list_performance_metrics must read MON$ counts and honor the filter."""
        items = sync_introspector.list_performance_metrics()
        by_name = {item.name: item for item in items}
        assert by_name["active_statements"].value == 3, "MON$STATEMENTS count must be exposed"
        assert by_name["attachments"].value == 2, "MON$ATTACHMENTS count must be exposed"
        assert sync_introspector.list_performance_metrics(StatusCategory.PERFORMANCE) == items, (
            "PERFORMANCE filter must keep all metric items"
        )
        assert sync_introspector.list_performance_metrics(StatusCategory.CONFIGURATION) == [], (
            "CONFIGURATION filter must drop metric items"
        )

    def test_list_performance_metrics_handles_partial_exception(self):
        """A failing statements query must still expose the attachments metric."""
        backend = ScriptedStatusBackend(raise_on=("MON$STATEMENTS",))
        introspector = SyncFirebirdStatusIntrospector(backend)
        items = introspector.list_performance_metrics()
        assert [item.name for item in items] == ["attachments"], (
            "statements failure must be swallowed, attachments kept"
        )

    def test_list_performance_metrics_handles_full_exception(self):
        """Failing both count queries must yield an empty metric list."""
        backend = ScriptedStatusBackend(raise_on=("MON$STATEMENTS", "MON$ATTACHMENTS"))
        introspector = SyncFirebirdStatusIntrospector(backend)
        assert introspector.list_performance_metrics() == [], (
            "all count failures must produce no metrics"
        )

    def test_list_performance_metrics_with_empty_rows(self):
        """Empty count rows must simply produce no metric items."""
        backend = ScriptedStatusBackend(
            rows={**DEFAULT_ROWS, "MON$STATEMENTS": [], "MON$ATTACHMENTS": []}
        )
        introspector = SyncFirebirdStatusIntrospector(backend)
        assert introspector.list_performance_metrics() == [], (
            "empty count rows must produce no metrics"
        )

    def test_get_connection_info_with_rows(self, sync_introspector):
        """get_connection_info must count attachments and expose the detail rows."""
        info = sync_introspector.get_connection_info()
        assert info.active_count == 2, "active count must come from the COUNT query"
        assert info.max_connections is None, "Firebird exposes no max connection limit"
        assert info.extra["attachments"][0]["username"] == "SYSDBA", (
            "attachment detail rows must be lowercased and exposed"
        )

    def test_get_connection_info_handles_exceptions(self):
        """Failing both queries must yield None counts and an empty extra dict."""
        backend = ScriptedStatusBackend(raise_on=("MON$ATTACHMENTS",))
        introspector = SyncFirebirdStatusIntrospector(backend)
        info = introspector.get_connection_info()
        assert info.active_count is None, "failed count query must leave active_count None"
        assert info.extra == {}, "failed detail query must yield an empty extra dict"

    def test_get_connection_info_empty_count_rows(self):
        """Empty count rows must leave active_count None while detail rows are kept."""
        backend = ScriptedStatusBackend(rows={**DEFAULT_ROWS, "MON$ATTACHMENTS": []})
        introspector = SyncFirebirdStatusIntrospector(backend)
        info = introspector.get_connection_info()
        assert info.active_count is None, "empty count rows must leave active_count None"
        assert info.extra["attachments"], "detail rows must still be exposed"

    def test_get_storage_info_with_size(self, sync_introspector):
        """get_storage_info must compute the size from page size times pages."""
        info = sync_introspector.get_storage_info()
        assert info.total_size_bytes == 409600, "total size must come from MON$DATABASE"
        assert info.data_size_bytes == 409600, "data size must mirror total size"
        assert info.extra["files"][0]["file_id"] == 0, "file rows must be exposed lowercased"

    def test_get_storage_info_handles_exceptions(self):
        """Failing both queries must yield None size and an empty file list."""
        backend = ScriptedStatusBackend(raise_on=("MON$PAGE_SIZE", "MON$DATABASE_FILES"))
        introspector = SyncFirebirdStatusIntrospector(backend)
        info = introspector.get_storage_info()
        assert info.total_size_bytes is None, "failed size query must leave total None"
        assert info.extra["files"] == [], "failed file query must yield an empty file list"

    def test_get_storage_info_empty_size_rows(self):
        """Empty size rows must leave total_size None while file rows are kept."""
        backend = ScriptedStatusBackend(rows={**DEFAULT_ROWS, "MON$PAGE_SIZE": []})
        introspector = SyncFirebirdStatusIntrospector(backend)
        info = introspector.get_storage_info()
        assert info.total_size_bytes is None, "empty size rows must leave total_size None"
        assert info.extra["files"], "file rows must still be exposed"

    def test_list_databases_with_rows(self, sync_introspector):
        """list_databases must map MON$DATABASE_NAME rows to DatabaseBriefInfo."""
        databases = sync_introspector.list_databases()
        assert len(databases) == 1, "one database row must yield one entry"
        assert databases[0].name == "/tmp/app.fdb", "database name must be carried through"

    def test_list_databases_handles_exception(self):
        """A failing query must yield an empty database list."""
        backend = ScriptedStatusBackend(raise_on=("MON$DATABASE_NAME",))
        introspector = SyncFirebirdStatusIntrospector(backend)
        assert introspector.list_databases() == [], "failed query must produce no databases"

    def test_list_users_from_rdb_users(self, sync_introspector):
        """list_users must prefer RDB$USERS rows when available."""
        users = sync_introspector.list_users()
        assert [user.name for user in users] == ["SYSDBA", "APP_USER"], (
            "RDB$USERS rows must be listed"
        )
        assert all(user.is_superuser is False for user in users), "Firebird users are not superusers"

    def test_list_users_falls_back_to_mon_attachments(self):
        """Empty RDB$USERS must fall back to distinct MON$ATTACHMENTS users."""
        backend = ScriptedStatusBackend(rows={**DEFAULT_ROWS, "RDB$USERS": []})
        introspector = SyncFirebirdStatusIntrospector(backend)
        assert [user.name for user in introspector.list_users()] == ["SYSDBA"], (
            "fallback must read MON$USER from attachments"
        )

    def test_list_users_falls_back_to_unknown(self):
        """Empty users everywhere must yield a single 'unknown' user."""
        backend = ScriptedStatusBackend(
            rows={**DEFAULT_ROWS, "RDB$USERS": [], "MON$USER": []}
        )
        introspector = SyncFirebirdStatusIntrospector(backend)
        assert [user.name for user in introspector.list_users()] == ["unknown"], (
            "both sources empty must yield 'unknown'"
        )

    def test_list_users_skips_unknown_mon_user(self):
        """MON$USER rows named 'unknown' must be dropped before the fallback kicks in."""
        backend = ScriptedStatusBackend(
            rows={**DEFAULT_ROWS, "RDB$USERS": [], "MON$USER": [{"USERNAME": "unknown"}]}
        )
        introspector = SyncFirebirdStatusIntrospector(backend)
        assert [user.name for user in introspector.list_users()] == ["unknown"], (
            "'unknown' attachment user must not be listed"
        )

    def test_list_users_skips_blank_rdb_usernames(self):
        """Blank RDB$USERS usernames must be skipped before the fallback source."""
        backend = ScriptedStatusBackend(
            rows={**DEFAULT_ROWS, "RDB$USERS": [{"USERNAME": ""}]}
        )
        introspector = SyncFirebirdStatusIntrospector(backend)
        assert [user.name for user in introspector.list_users()] == ["SYSDBA"], (
            "blank usernames must be skipped and the fallback used"
        )

    def test_list_users_handles_rdb_exception_then_fallback(self):
        """A failing RDB$USERS query must fall back to MON$ATTACHMENTS."""
        backend = ScriptedStatusBackend(raise_on=("RDB$USERS",))
        introspector = SyncFirebirdStatusIntrospector(backend)
        assert [user.name for user in introspector.list_users()] == ["SYSDBA"], (
            "fallback must be attempted after the RDB$USERS failure"
        )

    def test_list_users_handles_all_exceptions(self):
        """Failing both user sources must yield the 'unknown' placeholder."""
        backend = ScriptedStatusBackend(raise_on=("RDB$USERS", "MON$USER"))
        introspector = SyncFirebirdStatusIntrospector(backend)
        assert [user.name for user in introspector.list_users()] == ["unknown"], (
            "all user sources failing must yield 'unknown'"
        )

    def test_get_session_info_with_credentials(self, sync_introspector):
        """get_session_info must carry the configured user and database."""
        session = sync_introspector.get_session_info()
        assert session.user == "SYSDBA", "session user must come from config"
        assert session.database == "/tmp/app.fdb", "session database must come from config"
        assert session.password_used is True, "password must be reported as used"

    def test_get_session_info_without_credentials(self):
        """A config without credentials must yield None user and password_used."""
        backend = ScriptedStatusBackend(config=SimpleNamespace())
        introspector = SyncFirebirdStatusIntrospector(backend)
        session = introspector.get_session_info()
        assert session.user is None, "missing username must yield None"
        assert session.database is None, "missing database must yield None"
        assert session.password_used is None, "missing username must leave password_used None"

    def test_exec_lowercases_keys(self, sync_introspector):
        """_exec must lowercase row keys and return the data list."""
        rows = sync_introspector._exec("SELECT MON$DATABASE_NAME AS NAME FROM MON$DATABASE")
        assert rows == [{"name": "/tmp/app.fdb"}], "keys must be lowercased"

    def test_exec_none_result_returns_empty(self):
        """_exec must treat a None result as an empty row list."""
        backend = ScriptedStatusBackend()

        def none_result(sql):
            return None

        backend.execute = none_result
        introspector = SyncFirebirdStatusIntrospector(backend)
        assert introspector._exec("SELECT 1") == [], "None result must yield an empty list"

    def test_exec_result_without_data_returns_empty(self):
        """_exec must treat a result without a data attribute as empty."""
        backend = ScriptedStatusBackend()

        def bare_result(sql):
            return object()

        backend.execute = bare_result
        introspector = SyncFirebirdStatusIntrospector(backend)
        assert introspector._exec("SELECT 1") == [], "data-less result must yield an empty list"

    def test_vendor_name(self, sync_introspector):
        """_get_vendor_name must report Firebird."""
        assert sync_introspector._get_vendor_name() == "Firebird", "vendor name must be Firebird"

    def test_create_status_item_defaults(self, sync_introspector):
        """_create_status_item must populate defaults when only name/value are given."""
        item = sync_introspector._create_status_item("x", 1)
        assert isinstance(item, StatusItem), "helper must produce a StatusItem"
        assert item.category == StatusCategory.CONFIGURATION, "default category is CONFIGURATION"
        assert item.description is None, "description must default to None"
        assert item.is_readonly is False, "is_readonly must default to False"


class TestAsyncStatusIntrospector:
    """Tests for the asynchronous Firebird status introspector."""

    async def test_get_overview_builds_complete_overview(self, async_introspector):
        """get_overview must aggregate every status section into a ServerOverview."""
        overview = await async_introspector.get_overview()
        assert isinstance(overview, ServerOverview), "get_overview must return a ServerOverview"
        assert overview.server_version == "WI-V5.0.0", "server version must come from RDB$GET_CONTEXT"
        assert overview.server_vendor == "Firebird", "vendor must be Firebird"
        assert overview.configuration, "configuration items must be populated"
        assert overview.performance, "performance items must be populated"
        assert overview.connections.active_count == 2, "active connections must be counted"
        assert overview.storage.total_size_bytes == 409600, "storage size must be read from MON$PAGE_SIZE"
        assert overview.databases, "databases must be listed"
        assert overview.users, "users must be listed"
        assert overview.session.user == "SYSDBA", "session user must come from config"

    async def test_get_version_string_from_row(self, async_introspector):
        """_get_version_string must return the row version when present."""
        assert await async_introspector._get_version_string() == "WI-V5.0.0", (
            "version row must be returned verbatim"
        )

    async def test_get_version_string_missing_key_returns_unknown(self):
        """A row without a version key must yield the fallback 'unknown'."""
        backend = ScriptedAsyncStatusBackend(
            rows={**DEFAULT_ROWS, "RDB$GET_CONTEXT": [{"OTHER": 1}]}
        )
        introspector = AsyncFirebirdStatusIntrospector(backend)
        assert await introspector._get_version_string() == "unknown", (
            "missing version key must fall back"
        )

    async def test_get_version_string_handles_exception(self):
        """A failing version query must be swallowed and yield 'unknown'."""
        backend = ScriptedAsyncStatusBackend(raise_on=("RDB$GET_CONTEXT",))
        introspector = AsyncFirebirdStatusIntrospector(backend)
        assert await introspector._get_version_string() == "unknown", (
            "exception must not propagate"
        )

    async def test_list_configuration_all_and_filtered(self, async_introspector):
        """list_configuration must honor the category filter."""
        all_items = await async_introspector.list_configuration()
        assert len(all_items) == 2, "server_version and client_charset must be present"
        assert all_items[0].name == "server_version", "first config item is server_version"
        assert all_items[1].value == "UTF8", "client_charset must come from backend config"
        assert await async_introspector.list_configuration(StatusCategory.CONFIGURATION) == all_items, (
            "CONFIGURATION filter must keep all config items"
        )
        assert await async_introspector.list_configuration(StatusCategory.PERFORMANCE) == [], (
            "PERFORMANCE filter must drop config items"
        )

    async def test_list_performance_metrics_all_and_filtered(self, async_introspector):
        """list_performance_metrics must read MON$ counts and honor the filter."""
        items = await async_introspector.list_performance_metrics()
        by_name = {item.name: item for item in items}
        assert by_name["active_statements"].value == 3, "MON$STATEMENTS count must be exposed"
        assert by_name["attachments"].value == 2, "MON$ATTACHMENTS count must be exposed"
        assert await async_introspector.list_performance_metrics(StatusCategory.PERFORMANCE) == items, (
            "PERFORMANCE filter must keep all metric items"
        )
        assert await async_introspector.list_performance_metrics(StatusCategory.CONFIGURATION) == [], (
            "CONFIGURATION filter must drop metric items"
        )

    async def test_list_performance_metrics_handles_full_exception(self):
        """Failing both count queries must yield an empty metric list."""
        backend = ScriptedAsyncStatusBackend(raise_on=("MON$STATEMENTS", "MON$ATTACHMENTS"))
        introspector = AsyncFirebirdStatusIntrospector(backend)
        assert await introspector.list_performance_metrics() == [], (
            "all count failures must produce no metrics"
        )

    async def test_list_performance_metrics_with_empty_rows(self):
        """Empty count rows must simply produce no metric items."""
        backend = ScriptedAsyncStatusBackend(
            rows={**DEFAULT_ROWS, "MON$STATEMENTS": [], "MON$ATTACHMENTS": []}
        )
        introspector = AsyncFirebirdStatusIntrospector(backend)
        assert await introspector.list_performance_metrics() == [], (
            "empty count rows must produce no metrics"
        )

    async def test_get_connection_info_with_rows(self, async_introspector):
        """get_connection_info must count attachments and expose the detail rows."""
        info = await async_introspector.get_connection_info()
        assert info.active_count == 2, "active count must come from the COUNT query"
        assert info.max_connections is None, "Firebird exposes no max connection limit"
        assert info.extra["attachments"][0]["username"] == "SYSDBA", (
            "attachment detail rows must be lowercased and exposed"
        )

    async def test_get_connection_info_handles_exceptions(self):
        """Failing both queries must yield None counts and an empty extra dict."""
        backend = ScriptedAsyncStatusBackend(raise_on=("MON$ATTACHMENTS",))
        introspector = AsyncFirebirdStatusIntrospector(backend)
        info = await introspector.get_connection_info()
        assert info.active_count is None, "failed count query must leave active_count None"
        assert info.extra == {}, "failed detail query must yield an empty extra dict"

    async def test_get_connection_info_empty_count_rows(self):
        """Empty count rows must leave active_count None while detail rows are kept."""
        backend = ScriptedAsyncStatusBackend(rows={**DEFAULT_ROWS, "MON$ATTACHMENTS": []})
        introspector = AsyncFirebirdStatusIntrospector(backend)
        info = await introspector.get_connection_info()
        assert info.active_count is None, "empty count rows must leave active_count None"
        assert info.extra["attachments"], "detail rows must still be exposed"

    async def test_get_storage_info_with_size(self, async_introspector):
        """get_storage_info must compute the size from page size times pages."""
        info = await async_introspector.get_storage_info()
        assert info.total_size_bytes == 409600, "total size must come from MON$DATABASE"
        assert info.extra["files"][0]["file_id"] == 0, "file rows must be exposed lowercased"

    async def test_get_storage_info_handles_exceptions(self):
        """Failing both queries must yield None size and an empty file list."""
        backend = ScriptedAsyncStatusBackend(raise_on=("MON$PAGE_SIZE", "MON$DATABASE_FILES"))
        introspector = AsyncFirebirdStatusIntrospector(backend)
        info = await introspector.get_storage_info()
        assert info.total_size_bytes is None, "failed size query must leave total None"
        assert info.extra["files"] == [], "failed file query must yield an empty file list"

    async def test_get_storage_info_empty_size_rows(self):
        """Empty size rows must leave total_size None while file rows are kept."""
        backend = ScriptedAsyncStatusBackend(rows={**DEFAULT_ROWS, "MON$PAGE_SIZE": []})
        introspector = AsyncFirebirdStatusIntrospector(backend)
        info = await introspector.get_storage_info()
        assert info.total_size_bytes is None, "empty size rows must leave total_size None"
        assert info.extra["files"], "file rows must still be exposed"

    async def test_list_databases_with_rows(self, async_introspector):
        """list_databases must map MON$DATABASE_NAME rows to DatabaseBriefInfo."""
        databases = await async_introspector.list_databases()
        assert len(databases) == 1, "one database row must yield one entry"
        assert databases[0].name == "/tmp/app.fdb", "database name must be carried through"

    async def test_list_databases_handles_exception(self):
        """A failing query must yield an empty database list."""
        backend = ScriptedAsyncStatusBackend(raise_on=("MON$DATABASE_NAME",))
        introspector = AsyncFirebirdStatusIntrospector(backend)
        assert await introspector.list_databases() == [], "failed query must produce no databases"

    async def test_list_users_from_rdb_users(self, async_introspector):
        """list_users must prefer RDB$USERS rows when available."""
        users = await async_introspector.list_users()
        assert [user.name for user in users] == ["SYSDBA", "APP_USER"], (
            "RDB$USERS rows must be listed"
        )
        assert all(user.is_superuser is False for user in users), "Firebird users are not superusers"

    async def test_list_users_falls_back_to_mon_attachments(self):
        """Empty RDB$USERS must fall back to distinct MON$ATTACHMENTS users."""
        backend = ScriptedAsyncStatusBackend(rows={**DEFAULT_ROWS, "RDB$USERS": []})
        introspector = AsyncFirebirdStatusIntrospector(backend)
        assert [user.name for user in await introspector.list_users()] == ["SYSDBA"], (
            "fallback must read MON$USER from attachments"
        )

    async def test_list_users_falls_back_to_unknown(self):
        """Empty users everywhere must yield a single 'unknown' user."""
        backend = ScriptedAsyncStatusBackend(
            rows={**DEFAULT_ROWS, "RDB$USERS": [], "MON$USER": []}
        )
        introspector = AsyncFirebirdStatusIntrospector(backend)
        assert [user.name for user in await introspector.list_users()] == ["unknown"], (
            "both sources empty must yield 'unknown'"
        )

    async def test_list_users_skips_blank_rdb_usernames(self):
        """Blank RDB$USERS usernames must be skipped before the fallback source."""
        backend = ScriptedAsyncStatusBackend(
            rows={**DEFAULT_ROWS, "RDB$USERS": [{"USERNAME": ""}]}
        )
        introspector = AsyncFirebirdStatusIntrospector(backend)
        assert [user.name for user in await introspector.list_users()] == ["SYSDBA"], (
            "blank usernames must be skipped and the fallback used"
        )

    async def test_list_users_skips_unknown_mon_user(self):
        """MON$USER rows named 'unknown' must be dropped before the fallback kicks in."""
        backend = ScriptedAsyncStatusBackend(
            rows={**DEFAULT_ROWS, "RDB$USERS": [], "MON$USER": [{"USERNAME": "unknown"}]}
        )
        introspector = AsyncFirebirdStatusIntrospector(backend)
        assert [user.name for user in await introspector.list_users()] == ["unknown"], (
            "'unknown' attachment user must not be listed"
        )

    async def test_list_users_handles_all_exceptions(self):
        """Failing both user sources must yield the 'unknown' placeholder."""
        backend = ScriptedAsyncStatusBackend(raise_on=("RDB$USERS", "MON$USER"))
        introspector = AsyncFirebirdStatusIntrospector(backend)
        assert [user.name for user in await introspector.list_users()] == ["unknown"], (
            "all user sources failing must yield 'unknown'"
        )

    async def test_get_session_info_with_credentials(self, async_introspector):
        """get_session_info must carry the configured user and database."""
        session = await async_introspector.get_session_info()
        assert session.user == "SYSDBA", "session user must come from config"
        assert session.database == "/tmp/app.fdb", "session database must come from config"
        assert session.password_used is True, "password must be reported as used"

    async def test_exec_lowercases_keys(self, async_introspector):
        """_exec must lowercase row keys and return the data list."""
        rows = await async_introspector._exec("SELECT MON$DATABASE_NAME AS NAME FROM MON$DATABASE")
        assert rows == [{"name": "/tmp/app.fdb"}], "keys must be lowercased"

    async def test_exec_none_result_returns_empty(self):
        """_exec must treat a None result as an empty row list."""
        backend = ScriptedAsyncStatusBackend()

        async def none_execute(sql):
            return None

        backend.execute = none_execute
        introspector = AsyncFirebirdStatusIntrospector(backend)
        assert await introspector._exec("SELECT 1") == [], "None result must yield an empty list"

    async def test_exec_result_without_data_returns_empty(self):
        """_exec must treat a result without a data attribute as empty."""
        backend = ScriptedAsyncStatusBackend()

        async def bare_execute(sql):
            return object()

        backend.execute = bare_execute
        introspector = AsyncFirebirdStatusIntrospector(backend)
        assert await introspector._exec("SELECT 1") == [], (
            "data-less result must yield an empty list"
        )