# src/rhosocial/activerecord/backend/impl/firebird/introspection/introspector.py
"""Firebird schema introspector.

Uses Firebird system tables (RDB$) to introspect database schema.
"""

from typing import Optional

from rhosocial.activerecord.backend.introspection.base import (
    SyncAbstractIntrospector,
)
from rhosocial.activerecord.backend.introspection.executor import (
    SyncIntrospectorExecutor,
)
from rhosocial.activerecord.backend.introspection.types import (
    TableInfo,
)

from .async_introspector import FirebirdAsyncIntrospectorMixin
from .status_introspector import SyncFirebirdStatusIntrospector


class SyncFirebirdIntrospector(FirebirdAsyncIntrospectorMixin, SyncAbstractIntrospector):
    """Synchronous Firebird schema introspector."""

    def __init__(self, backend):
        executor = SyncIntrospectorExecutor(backend)
        super().__init__(backend, executor)
        self._status_instance = None

    @property
    def status(self) -> SyncFirebirdStatusIntrospector:
        """Firebird status introspector (lazily created)."""
        if self._status_instance is None:
            self._status_instance = SyncFirebirdStatusIntrospector(self._backend)
        return self._status_instance

    async def get_table_info(
        self, table: str, schema: Optional[str] = None
    ) -> Optional[TableInfo]:
        from copy import copy
        tables = self.list_tables(schema)
        table = next((t for t in tables if t.name == table), None)
        if table is None:
            return None
        table = copy(table)
        table.columns = self.list_columns(table, schema)
        table.indexes = self.list_indexes(table, schema)
        table.foreign_keys = self.list_foreign_keys(table, schema)
        return table


__all__ = ["SyncFirebirdIntrospector"]
