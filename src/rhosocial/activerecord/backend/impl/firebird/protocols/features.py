# src/rhosocial/activerecord/backend/impl/firebird/protocols/features.py
"""Firebird's dialect-specific feature protocols.

These are the extensions Firebird adds on top of the core protocol set: the
capability switches and formatters for Firebird-only SQL (GENERATOR, EXECUTE
BLOCK, BLOB SUB_TYPE, snapshot isolation, DECFLOAT, packages, monitoring
tables, ...). They are grouped here so that the concerns the schema-object
refactor introduced -- :mod:`~.namespace` and :mod:`~.sources` -- have a
file of their own, matching the ``mixins/`` naming one-for-one.
"""

from typing import Any, Protocol, Tuple, runtime_checkable

from rhosocial.activerecord.backend.dialect.protocols import (
    AlterDomainSupport,
    CreateDomainSupport,
    DataTypeSupport,
    DropDomainSupport,
)


@runtime_checkable
class FirebirdDMLOperationSupport(Protocol):
    def supports_update_or_insert(self) -> bool: ...
    def supports_returning(self) -> bool: ...
    def supports_merge(self) -> bool: ...
    def supports_execute_block(self) -> bool: ...
    def format_update_or_insert(self, expr: Any) -> Tuple[str, tuple]: ...
    def format_execute_block(self, expr: Any) -> Tuple[str, tuple]: ...


@runtime_checkable
class FirebirdGeneratorSupport(Protocol):
    def supports_create_sequence(self) -> bool: ...
    def supports_create_generator(self) -> bool: ...
    def supports_alter_sequence(self) -> bool: ...
    def format_gen_id(self, expr: Any) -> Tuple[str, tuple]: ...
    def format_next_value_for(self, expr: Any) -> Tuple[str, tuple]: ...


@runtime_checkable
class FirebirdBlobSupport(Protocol):
    def supports_blob(self) -> bool: ...
    def supports_blob_sub_type(self, sub_type: int) -> bool: ...
    def format_blob_column(self, expr: Any) -> Tuple[str, tuple]: ...
    def format_blob_literal(self, expr: Any) -> Tuple[str, tuple]: ...


@runtime_checkable
class FirebirdLockingSupport(Protocol):
    def supports_for_update_with_lock(self) -> bool: ...
    def supports_skip_locked(self) -> bool: ...


@runtime_checkable
class FirebirdTransactionSupport(Protocol):
    def supports_snapshot_isolation(self) -> bool: ...
    def supports_table_stability(self) -> bool: ...
    def supports_wait_option(self) -> bool: ...
    def supports_lock_timeout(self) -> bool: ...


@runtime_checkable
class FirebirdTableSupport(Protocol):
    def supports_computed_by(self) -> bool: ...
    def supports_generated_always(self) -> bool: ...
    def supports_external_file(self) -> bool: ...


@runtime_checkable
class FirebirdDomainSupport(
    CreateDomainSupport, AlterDomainSupport, DropDomainSupport, Protocol
):
    """Firebird implementation of the core DOMAIN DDL protocols.

    The core splits DOMAIN DDL per statement, so this mirrors it: creating,
    altering and dropping a domain each get their own contract, and Firebird
    answers all three.
    """


@runtime_checkable
class FirebirdTriggerSupport(Protocol):
    def supports_trigger_position(self) -> bool: ...


@runtime_checkable
class FirebirdReturningSupport(Protocol):
    def supports_returning_into(self) -> bool: ...


@runtime_checkable
class FirebirdIntrospectionSupport(Protocol):
    def supports_mon_tables(self) -> bool: ...


@runtime_checkable
class FirebirdExecuteBlockSupport(Protocol):
    def supports_execute_block(self) -> bool: ...
    def format_execute_block(self, expr: Any) -> Tuple[str, tuple]: ...


@runtime_checkable
class FirebirdExplainSupport(Protocol):
    def supports_explain_plan(self) -> bool: ...


@runtime_checkable
class FirebirdFunctionSupport(Protocol):
    def supports_list_function(self) -> bool: ...
    def supports_replace_function(self) -> bool: ...
    def supports_position_function(self) -> bool: ...
    def supports_char_length_function(self) -> bool: ...
    def supports_bit_functions(self) -> bool: ...
    def supports_date_time_functions(self) -> bool: ...
    def supports_string_functions(self) -> bool: ...
    def supports_gen_uid(self) -> bool: ...


@runtime_checkable
class FirebirdBooleanSupport(Protocol):
    def supports_boolean_type(self) -> bool: ...


@runtime_checkable
class FirebirdDecFloatSupport(Protocol):
    def supports_decfloat(self) -> bool: ...


@runtime_checkable
class FirebirdPaginationSupport(Protocol):
    def supports_rows_syntax(self) -> bool: ...
    def supports_offset_fetch(self) -> bool: ...


@runtime_checkable
class FirebirdDatabaseTriggerSupport(Protocol):
    def supports_database_triggers(self) -> bool: ...


@runtime_checkable
class FirebirdWindowFunctionSupport(Protocol):
    def supports_window_functions(self) -> bool: ...


@runtime_checkable
class FirebirdCTESupport(Protocol):
    def supports_cte(self) -> bool: ...
    def supports_recursive_cte(self) -> bool: ...


@runtime_checkable
class FirebirdFullTextSearchSupport(Protocol):
    def supports_fulltext_index(self) -> bool: ...


@runtime_checkable
class FirebirdUDFSupport(Protocol):
    def supports_udf(self) -> bool: ...
    def supports_declare_external_function(self) -> bool: ...


@runtime_checkable
class FirebirdPackageSupport(Protocol):
    def supports_packages(self) -> bool: ...
    def supports_create_package(self) -> bool: ...
    def supports_create_package_body(self) -> bool: ...


@runtime_checkable
class FirebirdGlobalMappingSupport(Protocol):
    def supports_global_temporary_table(self) -> bool: ...
    def supports_on_commit_delete_rows(self) -> bool: ...
    def supports_on_commit_preserve_rows(self) -> bool: ...


@runtime_checkable
class FirebirdMonitoringSupport(Protocol):
    def supports_monitoring(self) -> bool: ...


@runtime_checkable
class FirebirdRoleSupport(Protocol):
    def supports_roles(self) -> bool: ...
    def supports_create_role(self) -> bool: ...
    def supports_autonomous_transaction(self) -> bool: ...


@runtime_checkable
class FirebirdCursorSupport(Protocol):
    def supports_for_cursor(self) -> bool: ...
    def supports_as_cursor(self) -> bool: ...


@runtime_checkable
class FirebirdCollationSupport(Protocol):
    def supports_collation(self) -> bool: ...
    def supports_character_set(self) -> bool: ...


@runtime_checkable
class FirebirdExceptionSupport(Protocol):
    def supports_exception(self) -> bool: ...
    def supports_create_exception(self) -> bool: ...


@runtime_checkable
class FirebirdContextVariableSupport(Protocol):
    def supports_context_variables(self) -> bool: ...


@runtime_checkable
class FirebirdTypeSupport(DataTypeSupport, Protocol):
    """Firebird's own ``firebird_*`` data-type family.

    The core concepts need no protocol: they are dispatched by naming
    convention (``format_data_type_<name>`` / ``supports_data_type_<name>``
    derived from the type's generic ``name``), which is the point of that
    convention. The types Firebird *owns* are not derivable that way — the only
    way to learn that ``firebird_decfloat`` exists and needs a Firebird 4
    version gate is to be told — so this family states its own shape instead of
    leaving it implied by a naming pattern.

    Each ``firebird_*`` name appears twice, as a formatter and as a support
    check, and the two correspond 1:1 exactly as the core family does. The
    formatter for a Firebird 4 type returns SQL the server will only accept from
    4.0 on, so its ``supports_data_type_*`` counterpart carries the version gate
    and answers ``False`` on an older dialect: asking "can you declare an
    ``INT128`` here?" is answerable without issuing DDL and finding out.

    The core-concept half of the contract — total ``format_data_type`` dispatch,
    ``parse_type``, ``supports_data_types`` and ``suggested_data_types`` — is
    inherited from :class:`DataTypeSupport` rather than restated here: a Protocol
    that redeclared those members with empty bodies would shadow the concrete
    implementations when the dialect lists it among its bases, because a
    dialect's bases resolve left to right.

    Note what is **not** here: ``timetz`` and ``timestamptz``. This dialect
    renders neither — Firebird's ``TIME`` and ``TIMESTAMP`` are its *unzoned*
    types (language reference §3.4), so writing them for a zoned concept would
    declare a column that drops the zone — and it names the unzoned concept as
    their substitute through ``suggested_data_types``. The zoned columns
    themselves are the ``firebird_timetz`` / ``firebird_timestamptz`` formatters
    above, under Firebird's own words.
    """

    # --- Firebird 4.0+ types: version-gated formatters ---

    def format_data_type_firebird_timestamptz(self, data_type: Any) -> Tuple[str, tuple]:
        """Render ``TIMESTAMP WITH TIME ZONE``."""
        ...

    def format_data_type_firebird_timetz(self, data_type: Any) -> Tuple[str, tuple]:
        """Render ``TIME WITH TIME ZONE``."""
        ...

    def format_data_type_firebird_time_without_time_zone(
        self, data_type: Any
    ) -> Tuple[str, tuple]:
        """Render ``TIME WITHOUT TIME ZONE``."""
        ...

    def format_data_type_firebird_decfloat(self, data_type: Any) -> Tuple[str, tuple]:
        """Render ``DECFLOAT(16|34)``."""
        ...

    def format_data_type_firebird_int128(self, data_type: Any) -> Tuple[str, tuple]:
        """Render ``INT128``."""
        ...

    # --- Types every Firebird version this backend supports has ---

    def format_data_type_firebird_decimal(self, data_type: Any) -> Tuple[str, tuple]:
        """Render ``DECIMAL`` under the Firebird dispatch key."""
        ...

    def format_data_type_firebird_float(self, data_type: Any) -> Tuple[str, tuple]:
        """Render Firebird's bare ``FLOAT``."""
        ...

    def format_data_type_firebird_double(self, data_type: Any) -> Tuple[str, tuple]:
        """Render ``DOUBLE PRECISION``."""
        ...

    def format_data_type_firebird_blob_subtype(self, data_type: Any) -> Tuple[str, tuple]:
        """Render ``BLOB SUB_TYPE TEXT``."""
        ...

    def format_data_type_firebird_char(self, data_type: Any) -> Tuple[str, tuple]:
        """Render ``CHAR(n) CHARACTER SET UTF8``."""
        ...

    def format_data_type_firebird_varchar(self, data_type: Any) -> Tuple[str, tuple]:
        """Render ``VARCHAR(n) CHARACTER SET UTF8``."""
        ...

    def supports_data_type_firebird_timestamptz(self) -> bool:
        """``TIMESTAMP WITH TIME ZONE`` arrived in Firebird 4.0."""
        ...

    def supports_data_type_firebird_timetz(self) -> bool:
        """``TIME WITH TIME ZONE`` arrived in Firebird 4.0."""
        ...

    def supports_data_type_firebird_time_without_time_zone(self) -> bool:
        """``TIME WITHOUT TIME ZONE`` arrived in Firebird 4.0."""
        ...

    def supports_data_type_firebird_decfloat(self) -> bool:
        """``DECFLOAT`` arrived in Firebird 4.0."""
        ...

    def supports_data_type_firebird_int128(self) -> bool:
        """``INT128`` arrived in Firebird 4.0."""
        ...

    def supports_data_type_firebird_decimal(self) -> bool: ...
    def supports_data_type_firebird_float(self) -> bool: ...
    def supports_data_type_firebird_double(self) -> bool: ...
    def supports_data_type_firebird_blob_subtype(self) -> bool: ...
    def supports_data_type_firebird_char(self) -> bool: ...
    def supports_data_type_firebird_varchar(self) -> bool: ...


__all__ = [
    "FirebirdDMLOperationSupport",
    "FirebirdGeneratorSupport",
    "FirebirdBlobSupport",
    "FirebirdLockingSupport",
    "FirebirdTransactionSupport",
    "FirebirdTableSupport",
    "FirebirdDomainSupport",
    "FirebirdTriggerSupport",
    "FirebirdReturningSupport",
    "FirebirdIntrospectionSupport",
    "FirebirdExecuteBlockSupport",
    "FirebirdExplainSupport",
    "FirebirdFunctionSupport",
    "FirebirdBooleanSupport",
    "FirebirdDecFloatSupport",
    "FirebirdPaginationSupport",
    "FirebirdDatabaseTriggerSupport",
    "FirebirdWindowFunctionSupport",
    "FirebirdCTESupport",
    "FirebirdFullTextSearchSupport",
    "FirebirdUDFSupport",
    "FirebirdPackageSupport",
    "FirebirdGlobalMappingSupport",
    "FirebirdMonitoringSupport",
    "FirebirdRoleSupport",
    "FirebirdCursorSupport",
    "FirebirdCollationSupport",
    "FirebirdExceptionSupport",
    "FirebirdContextVariableSupport",
    "FirebirdTypeSupport",
]
