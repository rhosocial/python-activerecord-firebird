# src/rhosocial/activerecord/backend/impl/firebird/introspection/status_introspector.py
"""
Firebird server status introspector.

Provides server status information by querying Firebird's RDB$ system
tables and MON$ monitoring tables.

Design principle: Sync and Async are separate and cannot coexist.
- SyncFirebirdStatusIntrospector: for synchronous backends
- AsyncFirebirdStatusIntrospector: for asynchronous backends
"""

from typing import Any, Dict, List, Optional

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


class FirebirdStatusIntrospectorMixin:
    """Shared non-I/O logic for Firebird status introspectors."""

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
            rows = self._exec(
                "SELECT rdb$get_context('SYSTEM', 'ENGINE_VERSION') AS VERSION FROM rdb$database"
            )
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
            rows = self._exec("SELECT COUNT(*) AS C FROM MON$STATEMENTS")
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
            rows = self._exec("SELECT COUNT(*) AS C FROM MON$ATTACHMENTS")
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
            rows = self._exec("SELECT COUNT(*) AS C FROM MON$ATTACHMENTS")
            if rows:
                active_count = int(rows[0].get("c", 0))
        except Exception:
            pass
        try:
            rows = self._exec(
                "SELECT MON$ATTACHMENT_ID AS ID, MON$USER AS USERNAME, "
                "MON$REMOTE_ADDRESS AS REMOTE_ADDR, MON$REMOTE_PID AS REMOTE_PID "
                "FROM MON$ATTACHMENTS"
            )
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
            rows = self._exec(
                "SELECT CAST(MON$PAGE_SIZE AS BIGINT) * MON$PAGES AS SIZE_BYTES "
                "FROM MON$DATABASE"
            )
            if rows and rows[0].get("size_bytes") is not None:
                total_size = int(rows[0]["size_bytes"])
        except Exception:
            pass
        try:
            rows = self._exec(
                "SELECT MON$FILE_ID AS FILE_ID, MON$PAGES AS PAGES, "
                "CAST(MON$PAGE_SIZE AS BIGINT) * MON$PAGES AS SIZE_BYTES "
                "FROM MON$DATABASE_FILES"
            )
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
            rows = self._exec(
                "SELECT MON$DATABASE_NAME AS NAME FROM MON$DATABASE"
            )
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
            rows = self._exec(
                "SELECT USER_NAME AS USERNAME FROM RDB$USERS "
                "WHERE USER_NAME IS NOT NULL ORDER BY USER_NAME"
            )
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
                rows = self._exec(
                    "SELECT DISTINCT MON$USER AS USERNAME FROM MON$ATTACHMENTS "
                    "WHERE MON$USER IS NOT NULL"
                )
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

    def _exec(self, sql: str) -> List[Dict[str, Any]]:
        """Execute a query and return list of row dicts (lowercased keys)."""
        result = self._backend.execute(sql)
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
            rows = await self._exec(
                "SELECT rdb$get_context('SYSTEM', 'ENGINE_VERSION') AS VERSION FROM rdb$database"
            )
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
            rows = await self._exec("SELECT COUNT(*) AS C FROM MON$STATEMENTS")
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
            rows = await self._exec("SELECT COUNT(*) AS C FROM MON$ATTACHMENTS")
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
            rows = await self._exec("SELECT COUNT(*) AS C FROM MON$ATTACHMENTS")
            if rows:
                active_count = int(rows[0].get("c", 0))
        except Exception:
            pass
        try:
            rows = await self._exec(
                "SELECT MON$ATTACHMENT_ID AS ID, MON$USER AS USERNAME, "
                "MON$REMOTE_ADDRESS AS REMOTE_ADDR, MON$REMOTE_PID AS REMOTE_PID "
                "FROM MON$ATTACHMENTS"
            )
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
            rows = await self._exec(
                "SELECT CAST(MON$PAGE_SIZE AS BIGINT) * MON$PAGES AS SIZE_BYTES "
                "FROM MON$DATABASE"
            )
            if rows and rows[0].get("size_bytes") is not None:
                total_size = int(rows[0]["size_bytes"])
        except Exception:
            pass
        try:
            rows = await self._exec(
                "SELECT MON$FILE_ID AS FILE_ID, MON$PAGES AS PAGES, "
                "CAST(MON$PAGE_SIZE AS BIGINT) * MON$PAGES AS SIZE_BYTES "
                "FROM MON$DATABASE_FILES"
            )
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
            rows = await self._exec(
                "SELECT MON$DATABASE_NAME AS NAME FROM MON$DATABASE"
            )
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
            rows = await self._exec(
                "SELECT USER_NAME AS USERNAME FROM RDB$USERS "
                "WHERE USER_NAME IS NOT NULL ORDER BY USER_NAME"
            )
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
                rows = await self._exec(
                    "SELECT DISTINCT MON$USER AS USERNAME FROM MON$ATTACHMENTS "
                    "WHERE MON$USER IS NOT NULL"
                )
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

    async def _exec(self, sql: str) -> List[Dict[str, Any]]:
        """Execute a query and return list of row dicts (lowercased keys)."""
        result = await self._backend.execute(sql)
        if result is None or not hasattr(result, "data"):
            return []
        rows = result.data or []
        return [{str(k).lower(): v for k, v in row.items()} for row in rows]


__all__ = [
    "SyncFirebirdStatusIntrospector",
    "AsyncFirebirdStatusIntrospector",
]
