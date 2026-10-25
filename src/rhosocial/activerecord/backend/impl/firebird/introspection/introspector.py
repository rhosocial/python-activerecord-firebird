# src/rhosocial/activerecord/backend/impl/firebird/introspection/introspector.py
"""Firebird schema introspector.

Uses Firebird system tables (RDB$) to introspect database schema.

The sync and async introspectors are separate classes that cannot coexist;
they share every question (``_make_*``) and every parser through
:class:`FirebirdAsyncIntrospectorMixin`, and each declares the I/O half with
the same method names and signatures. ``list_generators``/``get_generator_info``
and ``list_domains``/``get_domain_info`` are Firebird's own object families and
are declared below as the sync half of that pair.
"""

from typing import Dict, List, Optional

from rhosocial.activerecord.backend.introspection.base import (
    SyncAbstractIntrospector,
)
from rhosocial.activerecord.backend.introspection.cache import (
    IntrospectionCache,
)
from rhosocial.activerecord.backend.introspection.executor import (
    SyncIntrospectorExecutor,
)
from rhosocial.activerecord.backend.introspection.types import (
    IntrospectionScope,
    IntrospectionTableInfo,
)

from .async_introspector import FirebirdAsyncIntrospectorMixin
from .status_introspector import SyncFirebirdStatusIntrospector
from .types import FirebirdDomainInfo, FirebirdGeneratorInfo


class SyncFirebirdIntrospector(FirebirdAsyncIntrospectorMixin, SyncAbstractIntrospector):
    """Synchronous Firebird schema introspector."""

    def __init__(
        self,
        backend,
        cache: Optional[IntrospectionCache] = None,
    ):
        executor = SyncIntrospectorExecutor(backend)
        super().__init__(backend, executor, cache)
        self._status_instance = None

    @property
    def status(self) -> SyncFirebirdStatusIntrospector:
        """Firebird status introspector (lazily created)."""
        if self._status_instance is None:
            self._status_instance = SyncFirebirdStatusIntrospector(self._backend)
        return self._status_instance

    async def get_table_info(
        self, table_name: str, schema: Optional[str] = None
    ) -> Optional[IntrospectionTableInfo]:
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

    # ------------------------------------------------------------------
    # Firebird-specific object families
    #
    # Generators and domains have no core entry point: the core's scopes name
    # them (SEQUENCE; and SCHEMA for a database-wide type catalogue), but the
    # questions and their results are Firebird's own. These methods are the
    # sync half of the pair the async introspector declares -- same names,
    # same signatures, same returns.
    # ------------------------------------------------------------------

    def list_generators(self, include_system: bool = False) -> List[FirebirdGeneratorInfo]:
        """List the generators (sequences) of this database with their values.

        One ``GEN_ID(<name>, 0)`` per generator: a generator name cannot be
        bound as a parameter, so the catalogue read and the value reads cannot
        be one statement. The result is cached, so the cost is paid once per
        cache generation rather than once per call.
        """
        key = self._cache.key(
            IntrospectionScope.SEQUENCE, extra=f"generators:{include_system}"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        sql, params = self.generator_list_statement(include_system).to_sql()
        rows = self._executor.execute(sql, params)
        values: Dict[str, int] = {}
        for row in rows:
            name = self._row_name(row, "GENERATOR_NAME")
            if not name:
                continue
            value_sql, value_params = self.generator_value_statement(name).to_sql()
            value_rows = self._executor.execute(value_sql, value_params)
            values[name] = int(value_rows[0]["GENERATOR_VALUE"])

        result = self.parse_generators(rows, values)
        self._cache.set(key, result)
        return result

    def get_generator_info(self, name: str) -> Optional[FirebirdGeneratorInfo]:
        """Return the named generator (sequence), or ``None``.

        The default list answers first, so looking up a generator the user
        created never reads the system's own rows -- and never pays their
        ``GEN_ID`` calls. Only a name that list does not contain falls back to
        ``include_system=True``.
        """
        found = self._find_by_name(self.list_generators(), name)
        if found is not None:
            return found
        return self._find_by_name(self.list_generators(include_system=True), name)

    def list_domains(self, include_system: bool = False) -> List[FirebirdDomainInfo]:
        """List the domains of this database with their declared attributes."""
        key = self._cache.key(
            IntrospectionScope.SCHEMA, extra=f"domains:{include_system}"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        sql, params = self.domain_list_statement(include_system).to_sql()
        result = self.parse_domains(self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    def get_domain_info(self, name: str) -> Optional[FirebirdDomainInfo]:
        """Return the named domain, or ``None``.

        The default list answers first; only a system domain's name needs the
        ``include_system=True`` pass.
        """
        found = self._find_by_name(self.list_domains(), name)
        if found is not None:
            return found
        return self._find_by_name(self.list_domains(include_system=True), name)


__all__ = ["SyncFirebirdIntrospector"]
