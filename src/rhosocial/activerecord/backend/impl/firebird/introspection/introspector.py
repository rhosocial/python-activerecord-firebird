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


class SyncFirebirdIntrospector(FirebirdAsyncIntrospectorMixin, SyncAbstractIntrospector):
    """Synchronous Firebird schema introspector."""

    def __init__(self, backend):
        executor = SyncIntrospectorExecutor(backend)
        super().__init__(backend, executor)

    async def get_table_info(
        self, table_name: str, schema: Optional[str] = None
    ) -> Optional[TableInfo]:
        from copy import copy
        tables = self.list_tables(schema)
        table = next((t for t in tables if t.name == table_name), None)
        if table is None:
            return None
        table = copy(table)
        table.columns = self.list_columns(table_name, schema)
        table.indexes = self.list_indexes(table_name, schema)
        table.foreign_keys = self.list_foreign_keys(table_name, schema)
        return table


__all__ = ["SyncFirebirdIntrospector"]
