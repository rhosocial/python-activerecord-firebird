# src/rhosocial/activerecord/backend/impl/firebird/introspection/status_introspector.py
"""
Firebird server status introspector.

Provides server status information by querying Firebird's RDB$ system
tables and MON$ monitoring tables.

Design principle: Sync and Async are separate and cannot coexist.
- SyncFirebirdStatusIntrospector: for synchronous backends
- AsyncFirebirdStatusIntrospector: for asynchronous backends

Every query below is built from expression nodes and rendered by the dialect
(org guide §16.2): this layer asks the catalogue a question, it does not spell
the SQL. The row shapes the parsers read -- the projection order and the
aliases -- are the ones the previous statement text produced, so the ``_exec_sql``
path and its key lower-casing are unchanged.
"""

from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.introspection.status import (
    StatusItem,
    StatusCategory,
    ServerOverview,
    DatabaseBriefInfo,
    UserInfo,
    ConnectionInfo,
    StorageInfo,
    SessionInfo,
    SyncAbstractStatusIntrospector,
    AsyncAbstractStatusIntrospector,
)

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class FirebirdStatusIntrospectorMixin:
    """Shared non-I/O logic for Firebird status introspectors."""

    @property
    def dialect(self) -> "SQLDialectBase":
        """The dialect these status queries are rendered by."""
        return self._backend.dialect

    def _get_vendor_name(self) -> str:
        """Get the database vendor name."""
        return "Firebird"

    def _create_status_item(
        self,
        name: str,
        value: Any,
        category: StatusCategory = StatusCategory.CONFIGURATION,
        description: Optional[str] = None,
        unit: Optional[str] = None,
        is_readonly: bool = False,
    ) -> StatusItem:
        """Create a StatusItem."""
        return StatusItem(
            name=name,
            value=value,
            category=category,
            description=description,
            unit=unit,
            is_readonly=is_readonly,
        )

    def _build_server_overview(
        self,
        configuration: List[StatusItem],
        performance: List[StatusItem],
        connections: ConnectionInfo,
        storage: StorageInfo,
        databases: List[DatabaseBriefInfo],
        users: List[UserInfo],
        version: str,
        session: Optional[SessionInfo] = None,
    ) -> ServerOverview:
        """Build ServerOverview from collected data."""
        return ServerOverview(
            server_version=version,
            server_vendor=self._get_vendor_name(),
            session=session,
            configuration=configuration,
            performance=performance,
            connections=connections,
            storage=storage,
            databases=databases,
            users=users,
        )

    # ------------------------------------------------------------------
    # The status queries, expressed once for both sync and async
    # ------------------------------------------------------------------

    def _version_string_sql(self) -> Tuple[str, tuple]:
        """The engine version, read from the system context."""
        from ..query_nodes import engine_version_sql

        return engine_version_sql(self.dialect)

    def _statement_count_sql(self) -> Tuple[str, tuple]:
        """How many statements this database is running."""
        from ..query_nodes import call, relation, row_count, select_sql

        d = self.dialect
        return select_sql(
            d,
            [call(d, "COUNT", row_count(d), alias="C")],
            from_=relation(d, "MON$STATEMENTS"),
        )

    def _attachment_count_sql(self) -> Tuple[str, tuple]:
        """How many attachments (sessions) this database has."""
        from ..query_nodes import call, relation, row_count, select_sql

        d = self.dialect
        return select_sql(
            d,
            [call(d, "COUNT", row_count(d), alias="C")],
            from_=relation(d, "MON$ATTACHMENTS"),
        )

    def _attachment_list_sql(self) -> Tuple[str, tuple]:
        """One row per attachment: its id, login, address and remote pid."""
        from ..query_nodes import column, relation, select_sql

        d = self.dialect
        return select_sql(
            d,
            [
                column(d, "MON$ATTACHMENT_ID", alias="ID"),
                column(d, "MON$USER", alias="USERNAME"),
                column(d, "MON$REMOTE_ADDRESS", alias="REMOTE_ADDR"),
                column(d, "MON$REMOTE_PID", alias="REMOTE_PID"),
            ],
            from_=relation(d, "MON$ATTACHMENTS"),
        )

    def _database_size_sql(self) -> Tuple[str, tuple]:
        """The database's size in bytes: page size times page count.

        The multiplication is stated as nodes because ``MON$PAGE_SIZE`` is a
        smallint on older engines and overflows a 16-bit product; the cast to
        ``BIGINT`` is what makes the arithmetic 64-bit, so it is part of the
        question rather than an incidental spelling.
        """
        from ..query_nodes import cast, column, multiply, relation, select_sql

        d = self.dialect
        return select_sql(
            d,
            [
                multiply(
                    d,
                    cast(d, column(d, "MON$PAGE_SIZE"), "BIGINT"),
                    column(d, "MON$PAGES"),
                ).as_("SIZE_BYTES")
            ],
            from_=relation(d, "MON$DATABASE"),
        )

    def _database_files_sql(self) -> Tuple[str, tuple]:
        """One row per database file with its page count and byte size."""
        from ..query_nodes import cast, column, multiply, relation, select_sql

        d = self.dialect
        return select_sql(
            d,
            [
                column(d, "MON$FILE_ID", alias="FILE_ID"),
                column(d, "MON$PAGES", alias="PAGES"),
                multiply(
                    d,
                    cast(d, column(d, "MON$PAGE_SIZE"), "BIGINT"),
                    column(d, "MON$PAGES"),
                ).as_("SIZE_BYTES"),
            ],
            from_=relation(d, "MON$DATABASE_FILES"),
        )

    def _database_name_sql(self) -> Tuple[str, tuple]:
        """The database's own name, as the attachment reports it."""
        from ..query_nodes import column, relation, select_sql

        d = self.dialect
        return select_sql(
            d,
            [column(d, "MON$DATABASE_NAME", alias="NAME")],
            from_=relation(d, "MON$DATABASE"),
        )

    def _rdb_users_sql(self) -> Tuple[str, tuple]:
        """Logins known to the security database, by name."""
        from ..query_nodes import (
            column,
            null_test,
            relation,
            select_sql,
        )

        d = self.dialect
        return select_sql(
            d,
            [column(d, "USER_NAME", alias="USERNAME")],
            from_=relation(d, "RDB$USERS"),
            where=null_test(d, column(d, "USER_NAME"), is_not=True),
            order_by=[column(d, "USER_NAME")],
        )

    def _attached_users_sql(self) -> Tuple[str, tuple]:
        """Distinct logins currently attached, for when ``RDB$USERS`` is empty.

        ``RDB$USERS`` exists only in a security database that carries it; an
        embedded or differently-secured database answers with no rows, and
        this is the fallback question.
        """
        from ..query_nodes import column, null_test, relation, select_sql

        d = self.dialect
        return select_sql(
            d,
            [column(d, "MON$USER", alias="USERNAME")],
            from_=relation(d, "MON$ATTACHMENTS"),
            where=null_test(d, column(d, "MON$USER"), is_not=True),
            distinct=True,
        )


class SyncFirebirdStatusIntrospector(FirebirdStatusIntrospectorMixin, SyncAbstractStatusIntrospector):
    """Synchronous Firebird status introspector.

    Uses RDB$ system tables and MON$ monitoring tables to gather server
    information.

    Usage::

        backend = FirebirdBackend(connection_config=config)
        backend.connect()
        status = backend.introspector.status.get_overview()
        print(status.server_version)
    """

    def __init__(self, backend: Any) -> None:
        super().__init__(backend)

    def get_overview(self) -> ServerOverview:
        """Get complete Firebird server status overview."""
        configuration = self.list_configuration()
        performance = self.list_performance_metrics()
        connections = self.get_connection_info()
        storage = self.get_storage_info()
        databases = self.list_databases()
        users = self.list_users()
        session = self.get_session_info()

        version = self._get_version_string()

        return self._build_server_overview(
            configuration=configuration,
            performance=performance,
            connections=connections,
            storage=storage,
            databases=databases,
            users=users,
            version=version,
            session=session,
        )

    def _get_version_string(self) -> str:
        """Get the Firebird server version string."""
        try:
            rows = self._exec_sql(self._version_string_sql())
            if rows and rows[0].get("version"):
                return str(rows[0]["version"])
        except Exception:
            pass
        return "unknown"

    def list_configuration(self, category: Optional[StatusCategory] = None) -> List[StatusItem]:
        """List configuration parameters."""
        items = [
            self._create_status_item(
                "server_version",
                self._get_version_string(),
                StatusCategory.CONFIGURATION,
                "Firebird server version",
                None,
                True,
            ),
            self._create_status_item(
                "client_charset",
                getattr(self._backend.config, "charset", "UTF8"),
                StatusCategory.CONFIGURATION,
                "Connection character set",
                None,
                False,
            ),
        ]
        if category is not None:
            return [item for item in items if item.category == category]
        return items

    def list_performance_metrics(self, category: Optional[StatusCategory] = None) -> List[StatusItem]:
        """List performance metrics from MON$ tables."""
        items: List[StatusItem] = []
        try:
            rows = self._exec_sql(self._statement_count_sql())
            if rows:
                items.append(
                    self._create_status_item(
                        "active_statements",
                        rows[0].get("c", 0),
                        StatusCategory.PERFORMANCE,
                        "Active statements",
                    )
                )
        except Exception:
            pass
        try:
            rows = self._exec_sql(self._attachment_count_sql())
            if rows:
                items.append(
                    self._create_status_item(
                        "attachments",
                        rows[0].get("c", 0),
                        StatusCategory.PERFORMANCE,
                        "Database attachments",
                    )
                )
        except Exception:
            pass
        if category is not None:
            return [item for item in items if item.category == category]
        return items

    def get_connection_info(self) -> ConnectionInfo:
        """Get connection information."""
        active_count = None
        max_connections = None
        try:
            rows = self._exec_sql(self._attachment_count_sql())
            if rows:
                active_count = int(rows[0].get("c", 0))
        except Exception:
            pass
        try:
            rows = self._exec_sql(self._attachment_list_sql())
            extra = {"attachments": rows}
        except Exception:
            extra = {}
        return ConnectionInfo(
            active_count=active_count,
            max_connections=max_connections,
            idle_count=None,
            extra=extra,
        )

    def get_storage_info(self) -> StorageInfo:
        """Get storage information."""
        total_size = None
        try:
            rows = self._exec_sql(self._database_size_sql())
            if rows and rows[0].get("size_bytes") is not None:
                total_size = int(rows[0]["size_bytes"])
        except Exception:
            pass
        try:
            rows = self._exec_sql(self._database_files_sql())
        except Exception:
            rows = []
        return StorageInfo(
            total_size_bytes=total_size,
            data_size_bytes=total_size,
            index_size_bytes=None,
            log_size_bytes=None,
            free_space_bytes=None,
            extra={"files": rows},
        )

    def list_databases(self) -> List[DatabaseBriefInfo]:
        """List databases/schemas."""
        try:
            rows = self._exec_sql(self._database_name_sql())
        except Exception:
            rows = []
        result = []
        for row in rows:
            name = row.get("name") or "unknown"
            result.append(
                DatabaseBriefInfo(
                    name=str(name),
                    schema=None,
                    owner=None,
                    encoding=None,
                    size_bytes=None,
                    table_count=None,
                    view_count=None,
                )
            )
        return result

    def list_users(self) -> List[UserInfo]:
        """List users from RDB$USERS."""
        users: List[UserInfo] = []
        try:
            rows = self._exec_sql(self._rdb_users_sql())
            for row in rows:
                name = str(row.get("username", "") or "")
                if name:
                    users.append(
                        UserInfo(
                            name=name,
                            is_superuser=False,
                        )
                    )
        except Exception:
            pass
        if not users:
            try:
                rows = self._exec_sql(self._attached_users_sql())
                for row in rows:
                    name = str(row.get("username", "") or "")
                    if name and name != "unknown":
                        users.append(
                            UserInfo(
                                name=name,
                                is_superuser=False,
                            )
                        )
            except Exception:
                pass
        if not users:
            users.append(UserInfo(name="unknown", is_superuser=False))
        return users

    def get_session_info(self) -> SessionInfo:
        """Get current session/connection information."""
        user = getattr(self._backend.config, "username", None)
        database = getattr(self._backend.config, "database", None)
        return SessionInfo(
            user=user,
            database=str(database) if database else None,
            schema=None,
            host=None,
            ssl_enabled=None,
            ssl_version=None,
            ssl_cipher=None,
            password_used=True if user else None,
        )

    def _exec_sql(self, statement: Tuple[str, tuple]) -> List[Dict[str, Any]]:
        """Execute a rendered statement and return rows as lowercased dicts."""
        sql, params = statement
        result = self._backend.execute(sql, params or None)
        if result is None or not hasattr(result, "data"):
            return []
        rows = result.data or []
        return [{str(k).lower(): v for k, v in row.items()} for row in rows]


class AsyncFirebirdStatusIntrospector(FirebirdStatusIntrospectorMixin, AsyncAbstractStatusIntrospector):
    """Asynchronous Firebird status introspector.

    Uses RDB$ system tables and MON$ monitoring tables to gather server
    information. All I/O is delegated to the async backend.
    """

    def __init__(self, backend: Any) -> None:
        super().__init__(backend)

    async def get_overview(self) -> ServerOverview:
        """Get complete Firebird server status overview."""
        configuration = await self.list_configuration()
        performance = await self.list_performance_metrics()
        connections = await self.get_connection_info()
        storage = await self.get_storage_info()
        databases = await self.list_databases()
        users = await self.list_users()
        session = await self.get_session_info()

        version = await self._get_version_string()

        return self._build_server_overview(
            configuration=configuration,
            performance=performance,
            connections=connections,
            storage=storage,
            databases=databases,
            users=users,
            version=version,
            session=session,
        )

    async def _get_version_string(self) -> str:
        """Get the Firebird server version string."""
        try:
            rows = await self._exec_sql(self._version_string_sql())
            if rows and rows[0].get("version"):
                return str(rows[0]["version"])
        except Exception:
            pass
        return "unknown"

    async def list_configuration(self, category: Optional[StatusCategory] = None) -> List[StatusItem]:
        """List configuration parameters."""
        items = [
            self._create_status_item(
                "server_version",
                await self._get_version_string(),
                StatusCategory.CONFIGURATION,
                "Firebird server version",
                None,
                True,
            ),
            self._create_status_item(
                "client_charset",
                getattr(self._backend.config, "charset", "UTF8"),
                StatusCategory.CONFIGURATION,
                "Connection character set",
                None,
                False,
            ),
        ]
        if category is not None:
            return [item for item in items if item.category == category]
        return items

    async def list_performance_metrics(self, category: Optional[StatusCategory] = None) -> List[StatusItem]:
        """List performance metrics from MON$ tables."""
        items: List[StatusItem] = []
        try:
            rows = await self._exec_sql(self._statement_count_sql())
            if rows:
                items.append(
                    self._create_status_item(
                        "active_statements",
                        rows[0].get("c", 0),
                        StatusCategory.PERFORMANCE,
                        "Active statements",
                    )
                )
        except Exception:
            pass
        try:
            rows = await self._exec_sql(self._attachment_count_sql())
            if rows:
                items.append(
                    self._create_status_item(
                        "attachments",
                        rows[0].get("c", 0),
                        StatusCategory.PERFORMANCE,
                        "Database attachments",
                    )
                )
        except Exception:
            pass
        if category is not None:
            return [item for item in items if item.category == category]
        return items

    async def get_connection_info(self) -> ConnectionInfo:
        """Get connection information."""
        active_count = None
        try:
            rows = await self._exec_sql(self._attachment_count_sql())
            if rows:
                active_count = int(rows[0].get("c", 0))
        except Exception:
            pass
        try:
            rows = await self._exec_sql(self._attachment_list_sql())
            extra = {"attachments": rows}
        except Exception:
            extra = {}
        return ConnectionInfo(
            active_count=active_count,
            max_connections=None,
            idle_count=None,
            extra=extra,
        )

    async def get_storage_info(self) -> StorageInfo:
        """Get storage information."""
        total_size = None
        try:
            rows = await self._exec_sql(self._database_size_sql())
            if rows and rows[0].get("size_bytes") is not None:
                total_size = int(rows[0]["size_bytes"])
        except Exception:
            pass
        try:
            rows = await self._exec_sql(self._database_files_sql())
        except Exception:
            rows = []
        return StorageInfo(
            total_size_bytes=total_size,
            data_size_bytes=total_size,
            index_size_bytes=None,
            log_size_bytes=None,
            free_space_bytes=None,
            extra={"files": rows},
        )

    async def list_databases(self) -> List[DatabaseBriefInfo]:
        """List databases/schemas."""
        try:
            rows = await self._exec_sql(self._database_name_sql())
        except Exception:
            rows = []
        result = []
        for row in rows:
            name = row.get("name") or "unknown"
            result.append(
                DatabaseBriefInfo(
                    name=str(name),
                    schema=None,
                    owner=None,
                    encoding=None,
                    size_bytes=None,
                    table_count=None,
                    view_count=None,
                )
            )
        return result

    async def list_users(self) -> List[UserInfo]:
        """List users from RDB$USERS."""
        users: List[UserInfo] = []
        try:
            rows = await self._exec_sql(self._rdb_users_sql())
            for row in rows:
                name = str(row.get("username", "") or "")
                if name:
                    users.append(
                        UserInfo(
                            name=name,
                            is_superuser=False,
                        )
                    )
        except Exception:
            pass
        if not users:
            try:
                rows = await self._exec_sql(self._attached_users_sql())
                for row in rows:
                    name = str(row.get("username", "") or "")
                    if name and name != "unknown":
                        users.append(
                            UserInfo(
                                name=name,
                                is_superuser=False,
                            )
                        )
            except Exception:
                pass
        if not users:
            users.append(UserInfo(name="unknown", is_superuser=False))
        return users

    async def get_session_info(self) -> SessionInfo:
        """Get current session/connection information."""
        user = getattr(self._backend.config, "username", None)
        database = getattr(self._backend.config, "database", None)
        return SessionInfo(
            user=user,
            database=str(database) if database else None,
            schema=None,
            host=None,
            ssl_enabled=None,
            ssl_version=None,
            ssl_cipher=None,
            password_used=True if user else None,
        )

    async def _exec_sql(self, statement: Tuple[str, tuple]) -> List[Dict[str, Any]]:
        """Execute a rendered statement and return rows as lowercased dicts."""
        sql, params = statement
        result = await self._backend.execute(sql, params or None)
        if result is None or not hasattr(result, "data"):
            return []
        rows = result.data or []
        return [{str(k).lower(): v for k, v in row.items()} for row in rows]


__all__ = [
    "SyncFirebirdStatusIntrospector",
    "AsyncFirebirdStatusIntrospector",
]
