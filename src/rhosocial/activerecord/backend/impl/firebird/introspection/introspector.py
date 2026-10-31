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
from .types import (
    FirebirdCharsetInfo,
    FirebirdCollationInfo,
    FirebirdConstraintInfo,
    FirebirdDependencyInfo,
    FirebirdDomainInfo,
    FirebirdExceptionInfo,
    FirebirdFunctionArgumentInfo,
    FirebirdFunctionInfo,
    FirebirdGeneratorInfo,
    FirebirdProcedureInfo,
    FirebirdProcedureParameterInfo,
    FirebirdPublicationInfo,
    FirebirdPrivilegeInfo,
    FirebirdRoleInfo,
    FirebirdViewRelationInfo,
)


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

    def get_table_info(
        self, table_name: str, schema: Optional[str] = None
    ) -> Optional[IntrospectionTableInfo]:
        """One table's columns, indexes and foreign keys as a single answer.

        Synchronous, because everything it calls is: the ``async def`` this
        used to carry made the sync introspector return an un-awaited coroutine,
        so ``get_table_info`` answered with an object that had no columns at all
        and the ``table`` CLI subcommand exited non-zero without saying why.
        """
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

    # ------------------------------------------------------------------
    # Schema-object families
    #
    # The sync half of each pair declared in
    # :class:`FirebirdAsyncIntrospectorMixin`; same names, same arguments, so a
    # caller can move between the two introspectors by changing nothing but the
    # ``await``.
    # ------------------------------------------------------------------

    def list_exceptions(
        self, include_system: bool = False
    ) -> List[FirebirdExceptionInfo]:
        """List the exceptions (named PSQL messages) of this database."""
        key = self._cache.key(
            IntrospectionScope.SCHEMA, extra=f"exceptions:{include_system}"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = self.exception_list_statement(include_system).to_sql()
        result = self.parse_exceptions(self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    def get_exception_info(self, name: str) -> Optional[FirebirdExceptionInfo]:
        """Return the named exception, or ``None``."""
        found = self._find_by_name(self.list_exceptions(), name)
        if found is not None:
            return found
        return self._find_by_name(self.list_exceptions(include_system=True), name)

    def list_procedures(
        self, include_system: bool = False, include_source: bool = False
    ) -> List[FirebirdProcedureInfo]:
        """List stored procedures, their signatures and optionally their bodies."""
        key = self._cache.key(
            IntrospectionScope.SCHEMA,
            extra=f"procedures:{include_system}:{include_source}",
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = self.procedure_list_statement(
            include_system, include_source
        ).to_sql()
        result = self.parse_procedures(self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    def get_procedure_info(self, name: str) -> Optional[FirebirdProcedureInfo]:
        """Return the named procedure, or ``None``."""
        found = self._find_by_name(self.list_procedures(), name)
        if found is not None:
            return found
        return self._find_by_name(self.list_procedures(include_system=True), name)

    def list_procedure_parameters(
        self, procedure_name: str
    ) -> List[FirebirdProcedureParameterInfo]:
        """List one procedure's parameters, inputs then outputs."""
        key = self._cache.key(
            IntrospectionScope.SCHEMA,
            extra=f"procedure-parameters:{procedure_name}",
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = self.procedure_parameter_statement(procedure_name).to_sql()
        result = self.parse_procedure_parameters(self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    def list_functions(
        self, include_system: bool = False, include_source: bool = False
    ) -> List[FirebirdFunctionInfo]:
        """List functions, PSQL and legacy UDF alike."""
        key = self._cache.key(
            IntrospectionScope.SCHEMA,
            extra=f"functions:{include_system}:{include_source}",
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = self.function_list_statement(
            include_system, include_source
        ).to_sql()
        result = self.parse_functions(self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    def get_function_info(self, name: str) -> Optional[FirebirdFunctionInfo]:
        """Return the named function, or ``None``."""
        found = self._find_by_name(self.list_functions(), name)
        if found is not None:
            return found
        return self._find_by_name(self.list_functions(include_system=True), name)

    def list_function_arguments(
        self, function_name: str
    ) -> List[FirebirdFunctionArgumentInfo]:
        """List one function's arguments, the return slot included."""
        key = self._cache.key(
            IntrospectionScope.SCHEMA, extra=f"function-arguments:{function_name}"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = self.function_argument_statement(function_name).to_sql()
        result = self.parse_function_arguments(self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    def list_constraints(
        self,
        table_name: Optional[str] = None,
        constraint_type: Optional[str] = None,
        include_system: bool = False,
    ) -> List[FirebirdConstraintInfo]:
        """List constraints of every kind, optionally of one table or type."""
        key = self._cache.key(
            IntrospectionScope.TABLE,
            extra=f"constraints:{table_name}:{constraint_type}:{include_system}",
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = self.constraint_list_statement(
            table_name, constraint_type, include_system
        ).to_sql()
        result = self.parse_constraints(self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    def list_roles(self, include_system: bool = False) -> List[FirebirdRoleInfo]:
        """List roles."""
        key = self._cache.key(
            IntrospectionScope.SCHEMA, extra=f"roles:{include_system}"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = self.role_list_statement(include_system).to_sql()
        result = self.parse_roles(self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    def list_privileges(
        self,
        object_name: Optional[str] = None,
        user_name: Optional[str] = None,
        include_system: bool = False,
    ) -> List[FirebirdPrivilegeInfo]:
        """List grants, optionally of one object and/or to one grantee."""
        key = self._cache.key(
            IntrospectionScope.SCHEMA,
            extra=f"privileges:{object_name}:{user_name}:{include_system}",
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = self.privilege_statement(
            object_name, user_name, include_system
        ).to_sql()
        result = self.parse_privileges(self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    def list_charsets(self) -> List[FirebirdCharsetInfo]:
        """List character sets."""
        key = self._cache.key(IntrospectionScope.SCHEMA, extra="charsets")
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = self.charset_list_statement().to_sql()
        result = self.parse_charsets(self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    def list_collations(
        self, charset_name: Optional[str] = None
    ) -> List[FirebirdCollationInfo]:
        """List collations, optionally of one character set."""
        key = self._cache.key(
            IntrospectionScope.SCHEMA, extra=f"collations:{charset_name}"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = self.collation_list_statement(charset_name).to_sql()
        result = self.parse_collations(self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    def list_dependencies(
        self, object_name: Optional[str] = None
    ) -> List[FirebirdDependencyInfo]:
        """List dependency edges, optionally those naming one object."""
        key = self._cache.key(
            IntrospectionScope.SCHEMA, extra=f"dependencies:{object_name}"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = self.dependency_statement(object_name).to_sql()
        result = self.parse_dependencies(self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    def list_view_relations(
        self, view_name: Optional[str] = None
    ) -> List[FirebirdViewRelationInfo]:
        """List the relations a view reads, optionally of one view."""
        key = self._cache.key(
            IntrospectionScope.VIEW, extra=f"view-relations:{view_name}"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = self.view_relation_statement(view_name).to_sql()
        result = self.parse_view_relations(self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    def list_publications(
        self, include_system: bool = False
    ) -> List[FirebirdPublicationInfo]:
        """List publications (Firebird 4 and later)."""
        key = self._cache.key(
            IntrospectionScope.SCHEMA, extra=f"publications:{include_system}"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = self.publication_list_statement(include_system).to_sql()
        result = self.parse_publications(self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result


__all__ = ["SyncFirebirdIntrospector"]
