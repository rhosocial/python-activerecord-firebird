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

from typing import Any, Dict, List, Optional

from rhosocial.activerecord.backend.introspection.base import (
    AbstractIntrospector,
)
from rhosocial.activerecord.backend.introspection.cache import (
    IntrospectionCache,
)
from rhosocial.activerecord.backend.introspection.errors import (
    ObjectNotFoundError,
)
from rhosocial.activerecord.backend.introspection.executor import (
    IntrospectorExecutor,
)
from rhosocial.activerecord.backend.introspection.types import (
    ColumnDataProfile,
    ConstraintState,
    DerivedObjectState,
    IndexState,
    IntrospectionScope,
    IntrospectionTableInfo,
    ItemKind,
    PartitionState,
    SequenceState,
    TableState,
)

from .async_introspector import FirebirdAsyncIntrospectorMixin
from .status_introspector import FirebirdStatusIntrospector
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


class FirebirdIntrospector(FirebirdAsyncIntrospectorMixin, AbstractIntrospector):
    """Synchronous Firebird schema introspector."""

    def __init__(
        self,
        backend,
        cache: Optional[IntrospectionCache] = None,
    ):
        executor = IntrospectorExecutor(backend)
        super().__init__(backend, executor, cache)
        self._status_instance = None

    @property
    def status(self) -> FirebirdStatusIntrospector:
        """Firebird status introspector (lazily created)."""
        if self._status_instance is None:
            self._status_instance = FirebirdStatusIntrospector(self._backend)
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

    def list_column_data_profiles(
        self,
        table_name: str,
        schema: Optional[str] = None,
    ) -> List[ColumnDataProfile]:
        """Profile one table's columns from its rows.

        Firebird keeps no per-column statistics catalogue, so the answer is one
        aggregate over the table -- exact, and paid for in time rather than in
        money. The response is one wide row, which this reshapes into the
        per-column records the family promises.

        The column catalogue is read first, and not only for the names: the
        aggregates need the names, and the formatter needs each column's
        declared type to know which figures Firebird will refuse to compute. A
        BLOB is not comparable, so its distinct count and bounds are left
        ``NULL`` while its null count and the table's row count are answered;
        asking for all of them would make the server reject the whole query.

        The cache key is core's, so a caller that reaches this method and one
        that reaches it through the base class share an answer.

        The catalogue read folds the name -- see :meth:`_catalogue_name` for
        why the column question needs a hand here that no other family gives
        it, and why the answer is still empty for a deliberately mixed-case
        table.
        """
        key = self._cache.key(
            IntrospectionScope.COLUMN, table_name, "data_profile", schema=schema
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        # The table itself is read under its folded name: the statement's FROM
        # renders ``Table``, which folds on its own, and the two agree.
        target = self._catalogue_name(table_name)
        columns = self.list_columns(target, schema)
        sql, params = self.profile_statement(
            table_name=target, schema=schema, columns=columns
        ).to_sql()
        result = self.parse_column_data_profiles(
            self._executor.execute(sql, params),
            schema if schema is not None else self.default_schema,
            table_name,
        )
        self._cache.set(key, result)
        return result

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

    # ------------------------------------------------------------------
    # Neutral object state
    #
    # Core's object-state API, answered from this backend's own catalogue.
    # The shared half -- the statements, the parsers and the one fact
    # Firebird has no question for -- lives in
    # :class:`FirebirdAsyncIntrospectorMixin`; these methods add the I/O and
    # the cache, and the async introspector declares the same names.
    # ------------------------------------------------------------------

    def get_table_state(
        self,
        table_name: str,
        schema: Optional[str] = None,
    ) -> TableState:
        """Read one relation's kind, comment and storage state.

        The relation name is bound as written and, for an unquoted name, as
        folded -- see :meth:`catalogue_name_candidates`: Firebird folds
        unquoted identifiers, and a bare ``"orders"`` would otherwise be
        compared case-sensitively against the catalogue's ``"ORDERS"`` and
        read as a missing table.

        ``ObjectNotFoundError`` answers a name the catalogue does not hold,
        rather than a default state that would read as a real regular table.
        """
        key = self._cache.key(
            IntrospectionScope.TABLE, table_name, "state", schema=schema
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        rows: List[Dict[str, Any]] = []
        for candidate in self.catalogue_name_candidates(table_name):
            sql, params = self.table_state_statement(candidate, schema).to_sql()
            rows = self._executor.execute(sql, params)
            if rows:
                break

        state = self.parse_table_state(
            rows,
            table_name,
            schema if schema is not None else self.default_schema,
        )
        if state is None:
            raise ObjectNotFoundError("table", table_name, schema)
        self._cache.set(key, state)
        return state

    def get_partition_state(
        self,
        table_name: str,
        schema: Optional[str] = None,
        include_stats: bool = False,
    ) -> PartitionState:
        """Answer the partition question with this engine's one fact.

        Firebird has no table partitioning at all, so the answer is a
        ``PartitionState`` whose ``scheme`` is ``None`` -- core's single
        neutral spelling for "not partitioned". This is an engine-level fact,
        not a catalogue read: the return is a ``PartitionState``, never
        ``None``, and ``scheme=None`` does not mean "unknown", which is what
        the base class's refusal would say. ``include_stats`` changes nothing
        because there are no partitions to measure.
        """
        self.dialect.reject_namespace(schema)
        return self.partition_state()

    def list_index_states(
        self,
        table_name: str,
        schema: Optional[str] = None,
    ) -> List[IndexState]:
        """Read every index on the table, including the unusable ones.

        An index switched ``INACTIVE`` stays in ``RDB$INDICES`` and is still
        reported here, with ``usable=False``: that flag is exactly the state
        a plan needs to know about before trusting the index. The family is
        answered only for a relation that exists, for the reason
        :meth:`get_table_state` gives.
        """
        state = self.get_table_state(table_name, schema)
        key = self._cache.key(
            IntrospectionScope.INDEX, state.name, "state", schema=schema
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = self.index_state_statement(state.name, schema).to_sql()
        result = self.parse_index_states(
            self._executor.execute(sql, params),
            state.name,
            schema if schema is not None else self.default_schema,
        )
        self._cache.set(key, result)
        return result

    def list_constraint_states(
        self,
        table_name: str,
        schema: Optional[str] = None,
    ) -> List[ConstraintState]:
        """Read every constraint on the table, with its deferral state."""
        state = self.get_table_state(table_name, schema)
        key = self._cache.key(
            IntrospectionScope.TABLE, state.name, "constraint_states", schema=schema
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = self.constraint_state_statement(state.name, schema).to_sql()
        result = self.parse_constraint_states(
            self._executor.execute(sql, params),
            state.name,
            schema if schema is not None else self.default_schema,
        )
        self._cache.set(key, result)
        return result

    def list_sequence_states(self, schema: Optional[str] = None) -> List[SequenceState]:
        """Read the user sequences this database holds and their owners.

        Firebird's generators and sequences are one kind, and the system
        ones (the generators behind identity columns) are excluded, exactly
        as the ``generators`` listing excludes them: this answers the
        sequences a caller created or can drop. The declaration's start and
        increment are not catalogue columns and stay ``None``.
        """
        self.dialect.reject_namespace(schema)
        key = self._cache.key(IntrospectionScope.SEQUENCE, extra="states")
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = self.sequence_state_statement(schema).to_sql()
        result = self.parse_sequence_states(
            self._executor.execute(sql, params),
            schema if schema is not None else self.default_schema,
        )
        self._cache.set(key, result)
        return result

    def list_derived_objects(
        self,
        table_name: str,
        schema: Optional[str] = None,
    ) -> List[DerivedObjectState]:
        """Read the indexes Firebird created for a table's constraints.

        The answer is derived from the constraint states rather than read
        by a second query: the constraint listing already names the index
        each constraint owns, and asking ``RDB$INDICES`` again would be the
        same fact spelled twice.
        """
        state = self.get_table_state(table_name, schema)
        key = self._cache.key(
            IntrospectionScope.TABLE, state.name, "derived_objects", schema=schema
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        result = self.derived_objects_from_constraints(
            self.list_constraint_states(state.name, schema)
        )
        self._cache.set(key, result)
        return result

    def item_exists(
        self,
        kind: ItemKind,
        name: str,
        schema: Optional[str] = None,
    ) -> bool:
        """Whether a shared object of one of this engine's kinds exists.

        The answer follows core's three-case rule, and the sets declared on
        :class:`FirebirdAsyncIntrospectorMixin` name which case a kind takes:

        * :data:`SUPPORTED_ITEM_KINDS` -- the engine has the objects and this
          backend can query them, so the family is asked and the result
          returned. That is a schema (the one unnamed namespace per database
          file), a domain and a function through their own families, a
          sequence through :meth:`list_sequence_states` (a user generator;
          an identity column's internal generator is not one), and a table
          through the table listing, which includes views as the catalogue
          reports them.
        * :data:`ENGINE_ABSENT_ITEM_KINDS` -- Firebird has no user types,
          extensions, tablespaces, partition functions/schemes or full-text
          catalogues at all, so absence is the fact rather than a failure to
          look.
        * :data:`REFUSED_ITEM_KINDS` -- Firebird has indexes, but this
          backend reads them only as part of a table's answer
          (:meth:`list_index_states`), so a name alone cannot be resolved.
          That is an implementation gap, and a ``False`` here would disguise
          it as absence.
        """
        kind = ItemKind(kind)
        if kind in self.REFUSED_ITEM_KINDS:
            self._refuse("StructureIntrospectionSupport", "item_exists")
        if kind not in self.SUPPORTED_ITEM_KINDS:
            return False

        self.dialect.reject_namespace(schema)
        if kind is ItemKind.SCHEMA:
            return not (name or "").strip()
        if kind is ItemKind.DOMAIN:
            return self.get_domain_info(name) is not None
        if kind is ItemKind.FUNCTION:
            return self.get_function_info(name) is not None
        if kind is ItemKind.SEQUENCE:
            return self._find_by_name(self.list_sequence_states(schema), name) is not None
        if kind is ItemKind.TABLE:
            return self._find_by_name(self.list_tables(schema), name) is not None

        # Every supported kind has a branch above; this is reached only if
        # one was added to the set without a query. Refusing keeps that a
        # loud gap rather than a silent False.
        self._refuse("StructureIntrospectionSupport", "item_exists")
        return False


__all__ = ["FirebirdIntrospector"]
