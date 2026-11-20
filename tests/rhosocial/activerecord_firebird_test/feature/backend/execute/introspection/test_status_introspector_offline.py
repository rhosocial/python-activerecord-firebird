# tests/rhosocial/activerecord_firebird_test/feature/backend/execute/introspection/test_status_introspector_offline.py
"""DB-free unit tests for Firebird's synchronous status introspector.

Every test drives :class:`FirebirdStatusIntrospector` with mocks and a real
(but connection-less) :class:`FirebirdDialect`, so this module runs without a
live Firebird server or the optional ``firebird-driver``.  The pseudo-async
introspector is deliberately not exercised: project policy tests only the
synchronous paths.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from rhosocial.activerecord.backend.introspection.status import (
    ConnectionInfo,
    DatabaseBriefInfo,
    ServerOverview,
    SessionInfo,
    StatusCategory,
    StatusItem,
    StorageInfo,
    UserInfo,
)

from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.introspection.status_introspector import (
    FirebirdStatusIntrospector,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SQL_MARKERS = {
    "_version_string_sql": "VERSION",
    "_statement_count_sql": "STMT_COUNT",
    "_attachment_count_sql": "ATT_COUNT",
    "_attachment_list_sql": "ATT_LIST",
    "_database_size_sql": "DB_SIZE",
    "_database_files_sql": "DB_FILES",
    "_database_name_sql": "DB_NAME",
    "_rdb_users_sql": "RDB_USERS",
    "_attached_users_sql": "ATT_USERS",
}


def _make_introspector(charset="UTF8", username=None, database=None):
    """Build a sync introspector over a MagicMock backend with a real dialect."""
    backend = MagicMock()
    backend.dialect = FirebirdDialect()
    backend.config = SimpleNamespace(charset=charset, username=username, database=database)
    return FirebirdStatusIntrospector(backend), backend


def _result(rows):
    """Minimal stand-in for the backend execution result (carries ``.data``)."""
    return SimpleNamespace(data=rows)


def _wire_sql(introspector, rows_by_marker):
    """Replace every ``*_sql`` builder with a unique marker and route ``_exec_sql``.

    ``rows_by_marker`` maps a marker (e.g. ``"ATT_COUNT"``) to the list of row
    dicts that the corresponding query should yield.  Missing markers yield an
    empty list, which keeps the method under test on its "no rows" path.
    """
    for method_name, marker in _SQL_MARKERS.items():
        setattr(introspector, method_name, MagicMock(return_value=(marker, ())))

    def fake_exec_sql(statement):
        return rows_by_marker.get(statement[0], [])

    introspector._exec_sql = MagicMock(side_effect=fake_exec_sql)


# ---------------------------------------------------------------------------
# Pure mixin helpers
# ---------------------------------------------------------------------------


class TestMixinHelpers:
    def test_get_vendor_name(self):
        introspector, _ = _make_introspector()
        assert introspector._get_vendor_name() == "Firebird"

    def test_dialect_property_returns_backend_dialect(self):
        introspector, backend = _make_introspector()
        assert introspector.dialect is backend.dialect

    def test_create_status_item_defaults(self):
        introspector, _ = _make_introspector()
        item = introspector._create_status_item("server_version", "FB-3.0")
        assert isinstance(item, StatusItem)
        assert item.name == "server_version"
        assert item.value == "FB-3.0"
        assert item.category is StatusCategory.CONFIGURATION
        assert item.description is None
        assert item.unit is None
        assert item.is_readonly is False
        assert item.extra == {}

    def test_create_status_item_custom_fields(self):
        introspector, _ = _make_introspector()
        item = introspector._create_status_item(
            "active_statements",
            7,
            category=StatusCategory.PERFORMANCE,
            description="Active statements",
            unit="statements",
            is_readonly=True,
        )
        assert item.category is StatusCategory.PERFORMANCE
        assert item.description == "Active statements"
        assert item.unit == "statements"
        assert item.is_readonly is True
        assert item.value == 7

    def test_build_server_overview_populates_all_fields(self):
        introspector, _ = _make_introspector()
        config = [introspector._create_status_item("cfg", "v")]
        perf = [introspector._create_status_item("perf", 1, StatusCategory.PERFORMANCE)]
        conn = ConnectionInfo(active_count=3)
        storage = StorageInfo(total_size_bytes=4096)
        dbs = [DatabaseBriefInfo(name="emp.fdb")]
        users = [UserInfo(name="SYSDBA")]
        session = SessionInfo(user="SYSDBA", database="emp.fdb", password_used=True)

        overview = introspector._build_server_overview(
            configuration=config,
            performance=perf,
            connections=conn,
            storage=storage,
            databases=dbs,
            users=users,
            version="FB-3.0",
            session=session,
        )

        assert isinstance(overview, ServerOverview)
        assert overview.server_version == "FB-3.0"
        assert overview.server_vendor == "Firebird"
        assert overview.configuration == config
        assert overview.performance == perf
        assert overview.connections is conn
        assert overview.storage is storage
        assert overview.databases == dbs
        assert overview.users == users
        assert overview.session is session

    def test_build_server_overview_session_is_optional(self):
        introspector, _ = _make_introspector()
        overview = introspector._build_server_overview(
            [], [], ConnectionInfo(), StorageInfo(), [], [], "v"
        )
        assert overview.session is None
        assert overview.server_vendor == "Firebird"

    @pytest.mark.parametrize(
        "method_name, fragment",
        [
            ("_version_string_sql", "ENGINE_VERSION"),
            ("_statement_count_sql", "MON$STATEMENTS"),
            ("_attachment_count_sql", "MON$ATTACHMENTS"),
            ("_attachment_list_sql", "MON$REMOTE_PID"),
            ("_database_size_sql", "SIZE_BYTES"),
            ("_database_files_sql", "MON$DATABASE_FILES"),
            ("_database_name_sql", "MON$DATABASE_NAME"),
            ("_rdb_users_sql", "RDB$USERS"),
            ("_attached_users_sql", "MON$USER"),
        ],
    )
    def test_sql_helpers_render_statement_tuples(self, method_name, fragment):
        introspector, _ = _make_introspector()
        statement = getattr(introspector, method_name)()
        assert isinstance(statement, tuple)
        assert len(statement) == 2
        sql, params = statement
        assert isinstance(sql, str)
        assert fragment in sql
        assert isinstance(params, tuple)


# ---------------------------------------------------------------------------
# _exec_sql
# ---------------------------------------------------------------------------


class TestExecSql:
    def test_exec_sql_lowercases_row_keys(self):
        introspector, backend = _make_introspector()
        backend.execute.return_value = _result([{"ATTACHMENT_ID": 1, "USERNAME": "SYSDBA"}])
        rows = introspector._exec_sql(("SELECT ...", (7,)))
        assert rows == [{"attachment_id": 1, "username": "SYSDBA"}]
        backend.execute.assert_called_once_with("SELECT ...", (7,))

    def test_exec_sql_passes_none_for_empty_params(self):
        introspector, backend = _make_introspector()
        backend.execute.return_value = _result([])
        introspector._exec_sql(("SELECT 1", ()))
        backend.execute.assert_called_once_with("SELECT 1", None)

    def test_exec_sql_none_result_returns_empty(self):
        introspector, backend = _make_introspector()
        backend.execute.return_value = None
        assert introspector._exec_sql(("SELECT 1", ())) == []

    def test_exec_sql_result_without_data_returns_empty(self):
        introspector, backend = _make_introspector()
        backend.execute.return_value = object()
        assert introspector._exec_sql(("SELECT 1", ())) == []

    def test_exec_sql_none_data_returns_empty(self):
        introspector, backend = _make_introspector()
        backend.execute.return_value = _result(None)
        assert introspector._exec_sql(("SELECT 1", ())) == []


# ---------------------------------------------------------------------------
# Version string + configuration
# ---------------------------------------------------------------------------


class TestVersionAndConfiguration:
    def test_get_version_string_from_rows(self):
        introspector, _ = _make_introspector()
        _wire_sql(introspector, {"VERSION": [{"version": "Firebird 3.0.7"}]})
        assert introspector._get_version_string() == "Firebird 3.0.7"

    def test_get_version_string_coerces_to_str(self):
        introspector, _ = _make_introspector()
        _wire_sql(introspector, {"VERSION": [{"version": 4}]})
        assert introspector._get_version_string() == "4"

    def test_get_version_string_unknown_when_no_rows(self):
        introspector, _ = _make_introspector()
        _wire_sql(introspector, {})
        assert introspector._get_version_string() == "unknown"

    def test_get_version_string_unknown_when_key_empty(self):
        introspector, _ = _make_introspector()
        _wire_sql(introspector, {"VERSION": [{"version": None}]})
        assert introspector._get_version_string() == "unknown"

    def test_get_version_string_unknown_on_exception(self):
        introspector, _ = _make_introspector()
        introspector._exec_sql = MagicMock(side_effect=RuntimeError("boom"))
        assert introspector._get_version_string() == "unknown"

    def test_list_configuration_defaults(self):
        introspector, _ = _make_introspector(charset="WIN1252")
        introspector._get_version_string = MagicMock(return_value="FB-3.0")
        items = introspector.list_configuration()
        assert [item.name for item in items] == ["server_version", "client_charset"]
        version_item, charset_item = items
        assert version_item.value == "FB-3.0"
        assert version_item.category is StatusCategory.CONFIGURATION
        assert version_item.description == "Firebird server version"
        assert version_item.is_readonly is True
        assert charset_item.value == "WIN1252"
        assert charset_item.description == "Connection character set"
        assert charset_item.is_readonly is False

    def test_list_configuration_charset_default_when_missing(self):
        backend = MagicMock()
        backend.dialect = FirebirdDialect()
        backend.config = SimpleNamespace()  # no charset attribute
        introspector = FirebirdStatusIntrospector(backend)
        introspector._get_version_string = MagicMock(return_value="FB")
        items = introspector.list_configuration()
        assert items[1].value == "UTF8"

    @pytest.mark.parametrize(
        "category, expected_count",
        [
            (StatusCategory.CONFIGURATION, 2),
            (StatusCategory.PERFORMANCE, 0),
            (StatusCategory.SECURITY, 0),
        ],
    )
    def test_list_configuration_category_filter(self, category, expected_count):
        introspector, _ = _make_introspector()
        introspector._get_version_string = MagicMock(return_value="FB")
        items = introspector.list_configuration(category=category)
        assert len(items) == expected_count
        assert all(item.category is category for item in items)


# ---------------------------------------------------------------------------
# Performance metrics
# ---------------------------------------------------------------------------


class TestPerformanceMetrics:
    def test_list_performance_metrics_with_rows(self):
        introspector, _ = _make_introspector()
        _wire_sql(
            introspector,
            {
                "STMT_COUNT": [{"c": 5}],
                "ATT_COUNT": [{"c": 2}],
            },
        )
        items = introspector.list_performance_metrics()
        assert [item.name for item in items] == ["active_statements", "attachments"]
        assert items[0].value == 5
        assert items[1].value == 2
        assert all(item.category is StatusCategory.PERFORMANCE for item in items)
        assert items[0].description == "Active statements"
        assert items[1].description == "Database attachments"

    def test_list_performance_metrics_missing_key_defaults_zero(self):
        introspector, _ = _make_introspector()
        _wire_sql(introspector, {"STMT_COUNT": [{}], "ATT_COUNT": [{}]})
        items = introspector.list_performance_metrics()
        assert [item.value for item in items] == [0, 0]

    def test_list_performance_metrics_empty_when_queries_return_no_rows(self):
        introspector, _ = _make_introspector()
        _wire_sql(introspector, {})
        assert introspector.list_performance_metrics() == []

    def test_list_performance_metrics_empty_when_queries_fail(self):
        introspector, _ = _make_introspector()
        introspector._exec_sql = MagicMock(side_effect=RuntimeError("boom"))
        assert introspector.list_performance_metrics() == []

    def test_list_performance_metrics_category_filter(self):
        introspector, _ = _make_introspector()
        _wire_sql(introspector, {"STMT_COUNT": [{"c": 1}], "ATT_COUNT": [{"c": 1}]})
        assert introspector.list_performance_metrics(StatusCategory.PERFORMANCE) != []
        assert introspector.list_performance_metrics(StatusCategory.STORAGE) == []


# ---------------------------------------------------------------------------
# Connection info
# ---------------------------------------------------------------------------


class TestConnectionInfo:
    def test_get_connection_info_with_counts_and_attachments(self):
        introspector, _ = _make_introspector()
        attachments = [{"id": 1, "username": "SYSDBA"}]
        _wire_sql(introspector, {"ATT_COUNT": [{"c": 3}], "ATT_LIST": attachments})
        info = introspector.get_connection_info()
        assert isinstance(info, ConnectionInfo)
        assert info.active_count == 3
        assert info.max_connections is None
        assert info.idle_count is None
        assert info.extra == {"attachments": attachments}

    def test_get_connection_info_active_count_coerced_to_int(self):
        introspector, _ = _make_introspector()
        _wire_sql(introspector, {"ATT_COUNT": [{"c": "4"}]})
        assert introspector.get_connection_info().active_count == 4

    def test_get_connection_info_empty_when_no_rows(self):
        introspector, _ = _make_introspector()
        _wire_sql(introspector, {})
        info = introspector.get_connection_info()
        assert info.active_count is None
        assert info.extra == {"attachments": []}

    def test_get_connection_info_attachment_list_failure_gives_empty_extra(self):
        introspector, _ = _make_introspector()
        _wire_sql(introspector, {})

        def fake_exec_sql(statement):
            if statement[0] == "ATT_COUNT":
                return [{"c": 2}]
            raise RuntimeError("no monitor")

        introspector._exec_sql = MagicMock(side_effect=fake_exec_sql)
        info = introspector.get_connection_info()
        assert info.active_count == 2
        assert info.extra == {}

    def test_get_connection_info_count_failure_gives_none(self):
        introspector, _ = _make_introspector()
        introspector._exec_sql = MagicMock(side_effect=RuntimeError("boom"))
        info = introspector.get_connection_info()
        assert info.active_count is None


# ---------------------------------------------------------------------------
# Storage info
# ---------------------------------------------------------------------------


class TestStorageInfo:
    def test_get_storage_info_with_size_and_files(self):
        introspector, _ = _make_introspector()
        files = [{"file_id": 0, "pages": 512, "size_bytes": 2097152}]
        _wire_sql(introspector, {"DB_SIZE": [{"size_bytes": "2097152"}], "DB_FILES": files})
        info = introspector.get_storage_info()
        assert isinstance(info, StorageInfo)
        assert info.total_size_bytes == 2097152
        assert info.data_size_bytes == 2097152
        assert info.index_size_bytes is None
        assert info.log_size_bytes is None
        assert info.free_space_bytes is None
        assert info.extra == {"files": files}

    def test_get_storage_info_none_size(self):
        introspector, _ = _make_introspector()
        _wire_sql(introspector, {"DB_SIZE": [{"size_bytes": None}]})
        info = introspector.get_storage_info()
        assert info.total_size_bytes is None
        assert info.data_size_bytes is None
        assert info.extra == {"files": []}

    def test_get_storage_info_size_failure_still_returns_files(self):
        introspector, _ = _make_introspector()
        _wire_sql(introspector, {})

        def fake_exec_sql(statement):
            if statement[0] == "DB_SIZE":
                raise RuntimeError("no size")
            return [{"file_id": 0}]

        introspector._exec_sql = MagicMock(side_effect=fake_exec_sql)
        info = introspector.get_storage_info()
        assert info.total_size_bytes is None
        assert info.extra == {"files": [{"file_id": 0}]}

    def test_get_storage_info_files_failure_gives_empty_files(self):
        introspector, _ = _make_introspector()
        introspector._exec_sql = MagicMock(side_effect=RuntimeError("boom"))
        info = introspector.get_storage_info()
        assert info.extra == {"files": []}


# ---------------------------------------------------------------------------
# Databases
# ---------------------------------------------------------------------------


class TestListDatabases:
    def test_list_databases_parses_names(self):
        introspector, _ = _make_introspector()
        _wire_sql(introspector, {"DB_NAME": [{"name": "employee.fdb"}, {"name": "test.fdb"}]})
        dbs = introspector.list_databases()
        assert [db.name for db in dbs] == ["employee.fdb", "test.fdb"]
        assert all(isinstance(db, DatabaseBriefInfo) for db in dbs)
        assert dbs[0].schema is None
        assert dbs[0].size_bytes is None

    def test_list_databases_stringifies_non_string_name(self):
        introspector, _ = _make_introspector()
        _wire_sql(introspector, {"DB_NAME": [{"name": 123}]})
        assert introspector.list_databases()[0].name == "123"

    def test_list_databases_unknown_fallback_for_empty_name(self):
        introspector, _ = _make_introspector()
        _wire_sql(introspector, {"DB_NAME": [{"name": None}, {}]})
        assert [db.name for db in introspector.list_databases()] == ["unknown", "unknown"]

    def test_list_databases_empty_on_query_failure(self):
        introspector, _ = _make_introspector()
        introspector._exec_sql = MagicMock(side_effect=RuntimeError("boom"))
        assert introspector.list_databases() == []


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


class TestListUsers:
    def test_list_users_from_rdb_users(self):
        introspector, _ = _make_introspector()
        _wire_sql(introspector, {"RDB_USERS": [{"username": "SYSDBA"}, {"username": "ALICE"}]})
        users = introspector.list_users()
        assert [user.name for user in users] == ["SYSDBA", "ALICE"]
        assert all(isinstance(user, UserInfo) for user in users)
        assert all(user.is_superuser is False for user in users)

    def test_list_users_skips_empty_names(self):
        introspector, _ = _make_introspector()
        _wire_sql(
            introspector, {"RDB_USERS": [{"username": ""}, {"username": None}, {"username": "BOB"}]}
        )
        assert [user.name for user in introspector.list_users()] == ["BOB"]

    def test_list_users_falls_back_to_attached_users(self):
        introspector, _ = _make_introspector()
        _wire_sql(introspector, {"ATT_USERS": [{"username": "SYSDBA"}, {"username": "GUEST"}]})
        users = introspector.list_users()
        assert [user.name for user in users] == ["SYSDBA", "GUEST"]

    def test_list_users_fallback_filters_unknown(self):
        introspector, _ = _make_introspector()
        _wire_sql(introspector, {"ATT_USERS": [{"username": "unknown"}, {"username": "SYSDBA"}]})
        assert [user.name for user in introspector.list_users()] == ["SYSDBA"]

    def test_list_users_unknown_when_all_sources_empty(self):
        introspector, _ = _make_introspector()
        _wire_sql(introspector, {})
        users = introspector.list_users()
        assert [user.name for user in users] == ["unknown"]
        assert users[0].is_superuser is False

    def test_list_users_unknown_when_queries_fail(self):
        introspector, _ = _make_introspector()
        introspector._exec_sql = MagicMock(side_effect=RuntimeError("boom"))
        assert [user.name for user in introspector.list_users()] == ["unknown"]


# ---------------------------------------------------------------------------
# Session info
# ---------------------------------------------------------------------------


class TestSessionInfo:
    def test_get_session_info_with_credentials(self):
        introspector, _ = _make_introspector(username="SYSDBA", database="employee.fdb")
        session = introspector.get_session_info()
        assert isinstance(session, SessionInfo)
        assert session.user == "SYSDBA"
        assert session.database == "employee.fdb"
        assert session.password_used is True
        assert session.schema is None
        assert session.ssl_enabled is None

    def test_get_session_info_without_user(self):
        introspector, _ = _make_introspector(username=None, database=None)
        session = introspector.get_session_info()
        assert session.user is None
        assert session.database is None
        assert session.password_used is None

    def test_get_session_info_stringifies_database(self):
        introspector, _ = _make_introspector(username="U", database=42)
        session = introspector.get_session_info()
        assert session.database == "42"


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


class TestGetOverview:
    def test_get_overview_assembles_all_sub_results(self):
        introspector, _ = _make_introspector()
        config = [StatusItem(name="cfg", value="v")]
        perf = [StatusItem(name="perf", value=1, category=StatusCategory.PERFORMANCE)]
        conn = ConnectionInfo(active_count=2)
        storage = StorageInfo(total_size_bytes=1024)
        dbs = [DatabaseBriefInfo(name="emp.fdb")]
        users = [UserInfo(name="SYSDBA")]
        session = SessionInfo(user="SYSDBA")

        introspector.list_configuration = MagicMock(return_value=config)
        introspector.list_performance_metrics = MagicMock(return_value=perf)
        introspector.get_connection_info = MagicMock(return_value=conn)
        introspector.get_storage_info = MagicMock(return_value=storage)
        introspector.list_databases = MagicMock(return_value=dbs)
        introspector.list_users = MagicMock(return_value=users)
        introspector.get_session_info = MagicMock(return_value=session)
        introspector._get_version_string = MagicMock(return_value="FB-3.0")

        overview = introspector.get_overview()

        assert isinstance(overview, ServerOverview)
        assert overview.server_version == "FB-3.0"
        assert overview.server_vendor == "Firebird"
        assert overview.configuration == config
        assert overview.performance == perf
        assert overview.connections is conn
        assert overview.storage is storage
        assert overview.databases == dbs
        assert overview.users == users
        assert overview.session is session
        for mocked in (
            introspector.list_configuration,
            introspector.list_performance_metrics,
            introspector.get_connection_info,
            introspector.get_storage_info,
            introspector.list_databases,
            introspector.list_users,
            introspector.get_session_info,
            introspector._get_version_string,
        ):
            mocked.assert_called_once_with()
