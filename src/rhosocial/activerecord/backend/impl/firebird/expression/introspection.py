# src/rhosocial/activerecord/backend/impl/firebird/expression/introspection.py
"""Firebird's own introspection questions.

The core statement classes cover the catalogue questions every backend asks:
the database, its relations, columns, indexes, foreign keys, views and
triggers. Firebird's catalogue answers for more than that -- generators,
domains, exceptions, procedures, functions, constraints, roles, privileges,
character sets, collations, dependencies, publications and view dependencies
are all schema objects with a ``RDB$`` relation of their own and no core entry
point -- so they get statements here.

Like every other expression, each class collects all its parameters at
construction and names -- through ``format_method`` -- the one dialect
formatter that renders it. The SQL lives on the dialect; this module only
carries the question. A statement that reads two relations (procedure
parameters, check expressions) is still one question and therefore one
statement: the join belongs to the formatter, not to the caller.

Three families are deliberately absent:

* ``RDB$PACKAGES`` exists and holds rows, but this backend's probe recorded
  ``CREATE PACKAGE`` refused on 5.0.4 and on the 6.0.0 server in
  ``tests/config/firebird_scenarios.yaml``, so it treats the relation as
  reserved infrastructure. Firebird 5's language reference does document
  ``CREATE PACKAGE``; the contradiction is recorded in
  ``docs/introspection.md`` for a re-measurement before a family is added.
* ``MON$`` is runtime state, not schema. It belongs to the ``status``
  introspector, which is a different layer with different questions.
* ``RDB$PAGES``, ``RDB$FILES``, ``RDB$FORMATS``, ``RDB$TRANSACTIONS``,
  ``RDB$CONFIG`` and ``RDB$BACKUP_HISTORY`` describe the database file, not
  objects in it, and are likewise status material.
"""

from typing import TYPE_CHECKING, Optional, Sequence

from rhosocial.activerecord.backend.expression.bases import BaseExpression
from rhosocial.activerecord.backend.expression.introspection import (
    ColumnDataProfileQueryStatement,
)

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase

__all__ = [
    "FirebirdCharsetListQueryStatement",
    "FirebirdCollationListQueryStatement",
    "FirebirdColumnDataProfileQueryStatement",
    "FirebirdConstraintListQueryStatement",
    "FirebirdDependencyQueryStatement",
    "FirebirdDomainInfoQueryStatement",
    "FirebirdDomainListQueryStatement",
    "FirebirdExceptionInfoQueryStatement",
    "FirebirdExceptionListQueryStatement",
    "FirebirdFunctionArgumentQueryStatement",
    "FirebirdFunctionListQueryStatement",
    "FirebirdGeneratorListQueryStatement",
    "FirebirdGeneratorValueQueryStatement",
    "FirebirdPrivilegeQueryStatement",
    "FirebirdProcedureListQueryStatement",
    "FirebirdProcedureParameterQueryStatement",
    "FirebirdPublicationListQueryStatement",
    "FirebirdRoleListQueryStatement",
    "FirebirdViewRelationQueryStatement",
]


class FirebirdGeneratorListQueryStatement(BaseExpression):
    """Ask for this database's generators (sequences).

    Args:
        dialect: The dialect the statement is bound to.
        include_system: Whether to include the generators Firebird owns
            (identity columns and other internal sequences). Defaults to
            False.
    """

    def __init__(self, dialect: "SQLDialectBase", include_system: bool = False):
        super().__init__(dialect)
        self.include_system = include_system

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this statement."""
        return "format_firebird_generator_list_query_statement"

    def __repr__(self) -> str:
        return (
            f"FirebirdGeneratorListQueryStatement("
            f"include_system={self.include_system!r})"
        )


class FirebirdGeneratorValueQueryStatement(BaseExpression):
    """Ask for one generator's current value.

    Args:
        dialect: The dialect the statement is bound to.
        generator_name: The generator whose value is read.
    """

    def __init__(self, dialect: "SQLDialectBase", generator_name: str):
        super().__init__(dialect)
        self.generator_name = generator_name

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this statement."""
        return "format_firebird_generator_value_query_statement"

    def __repr__(self) -> str:
        return (
            f"FirebirdGeneratorValueQueryStatement("
            f"generator_name={self.generator_name!r})"
        )


class FirebirdDomainListQueryStatement(BaseExpression):
    """Ask for this database's domains.

    Args:
        dialect: The dialect the statement is bound to.
        include_system: Whether to include the domains Firebird creates for
            inline-declared column types. Defaults to False.
    """

    def __init__(self, dialect: "SQLDialectBase", include_system: bool = False):
        super().__init__(dialect)
        self.include_system = include_system

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this statement."""
        return "format_firebird_domain_list_query_statement"

    def __repr__(self) -> str:
        return (
            f"FirebirdDomainListQueryStatement("
            f"include_system={self.include_system!r})"
        )


class FirebirdDomainInfoQueryStatement(BaseExpression):
    """Ask for one domain.

    The listing and the single read share a projection; only the predicate
    differs, so a caller that has a name keeps the whole answer rather than
    filtering a listing in Python.

    Args:
        dialect: The dialect the statement is bound to.
        domain_name: The domain to describe.
    """

    def __init__(self, dialect: "SQLDialectBase", domain_name: str):
        super().__init__(dialect)
        self.domain_name = domain_name

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this statement."""
        return "format_firebird_domain_info_query_statement"

    def __repr__(self) -> str:
        return (
            f"FirebirdDomainInfoQueryStatement(domain_name={self.domain_name!r})"
        )


class FirebirdExceptionListQueryStatement(BaseExpression):
    """Ask for this database's exceptions.

    Args:
        dialect: The dialect the statement is bound to.
        include_system: Whether to include the exceptions Firebird owns.
            Defaults to False.
    """

    def __init__(self, dialect: "SQLDialectBase", include_system: bool = False):
        super().__init__(dialect)
        self.include_system = include_system

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this statement."""
        return "format_firebird_exception_list_query_statement"

    def __repr__(self) -> str:
        return (
            f"FirebirdExceptionListQueryStatement("
            f"include_system={self.include_system!r})"
        )


class FirebirdExceptionInfoQueryStatement(BaseExpression):
    """Ask for one exception.

    Args:
        dialect: The dialect the statement is bound to.
        exception_name: The exception to describe.
    """

    def __init__(self, dialect: "SQLDialectBase", exception_name: str):
        super().__init__(dialect)
        self.exception_name = exception_name

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this statement."""
        return "format_firebird_exception_info_query_statement"

    def __repr__(self) -> str:
        return (
            f"FirebirdExceptionInfoQueryStatement("
            f"exception_name={self.exception_name!r})"
        )


class FirebirdProcedureListQueryStatement(BaseExpression):
    """Ask for this database's stored procedures.

    Args:
        dialect: The dialect the statement is bound to.
        include_system: Whether to include Firebird's own procedures.
            Defaults to False.
        include_source: Whether to select the PSQL body. Off by default: the
            source can be tens of kilobytes per procedure and most callers
            want the signature.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        include_system: bool = False,
        include_source: bool = False,
    ):
        super().__init__(dialect)
        self.include_system = include_system
        self.include_source = include_source

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this statement."""
        return "format_firebird_procedure_list_query_statement"

    def __repr__(self) -> str:
        return (
            f"FirebirdProcedureListQueryStatement("
            f"include_system={self.include_system!r}, "
            f"include_source={self.include_source!r})"
        )


class FirebirdProcedureParameterQueryStatement(BaseExpression):
    """Ask for one procedure's parameters.

    Inputs and outputs live in the same relation, told apart by
    ``RDB$PARAMETER_TYPE``; one read returns both, ordered by that type and by
    position, so a caller never has to merge two lists.

    Args:
        dialect: The dialect the statement is bound to.
        procedure_name: The procedure whose parameters are read.
    """

    def __init__(self, dialect: "SQLDialectBase", procedure_name: str):
        super().__init__(dialect)
        self.procedure_name = procedure_name

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this statement."""
        return "format_firebird_procedure_parameter_query_statement"

    def __repr__(self) -> str:
        return (
            f"FirebirdProcedureParameterQueryStatement("
            f"procedure_name={self.procedure_name!r})"
        )


class FirebirdFunctionListQueryStatement(BaseExpression):
    """Ask for this database's functions.

    Firebird keeps two kinds in ``RDB$FUNCTIONS``: PSQL functions
    (``RDB$LEGACY_FLAG`` 0) and legacy UDFs that call into a native module
    (flag 1, ``RDB$MODULE_NAME``/``RDB$ENTRYPOINT``). Both are listed, because
    both are callable schema objects.

    Args:
        dialect: The dialect the statement is bound to.
        include_system: Whether to include Firebird's own functions. Defaults
            to False.
        include_source: Whether to select the PSQL body. Off by default.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        include_system: bool = False,
        include_source: bool = False,
    ):
        super().__init__(dialect)
        self.include_system = include_system
        self.include_source = include_source

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this statement."""
        return "format_firebird_function_list_query_statement"

    def __repr__(self) -> str:
        return (
            f"FirebirdFunctionListQueryStatement("
            f"include_system={self.include_system!r}, "
            f"include_source={self.include_source!r})"
        )


class FirebirdFunctionArgumentQueryStatement(BaseExpression):
    """Ask for one function's arguments.

    Args:
        dialect: The dialect the statement is bound to.
        function_name: The function whose arguments are read.
    """

    def __init__(self, dialect: "SQLDialectBase", function_name: str):
        super().__init__(dialect)
        self.function_name = function_name

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this statement."""
        return "format_firebird_function_argument_query_statement"

    def __repr__(self) -> str:
        return (
            f"FirebirdFunctionArgumentQueryStatement("
            f"function_name={self.function_name!r})"
        )


class FirebirdConstraintListQueryStatement(BaseExpression):
    """Ask for constraints, optionally of one relation and/or one kind.

    Every kind lives in ``RDB$RELATION_CONSTRAINTS``: ``PRIMARY KEY``,
    ``UNIQUE``, ``FOREIGN KEY``, ``CHECK`` and the ``NOT NULL`` rows Firebird
    records as constraints. The CHECK predicate itself is not in that relation
    -- it is the source of the trigger ``RDB$CHECK_CONSTRAINTS`` points at --
    so the formatter reads it through the two extra relations and leaves
    ``CHECK_SOURCE`` null for the kinds that have no predicate.

    Outgoing foreign keys keep their own family
    (:class:`~...expression.introspection.ForeignKeyQueryStatement` in core),
    because a foreign key answers a different question -- which columns point
    at which table -- and needs a second index read to answer it.

    Args:
        dialect: The dialect the statement is bound to.
        table_name: Restrict to one relation, or ``None`` for all.
        constraint_type: Restrict to one type (``PRIMARY KEY``, ``UNIQUE``,
            ``FOREIGN KEY``, ``CHECK``, ``NOT NULL``), or ``None`` for all.
        include_system: Whether to include constraints on ``RDB$`` relations.
            ``RDB$RELATION_CONSTRAINTS`` has no system flag, so the test is on
            the relation name. Defaults to False.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        table_name: Optional[str] = None,
        constraint_type: Optional[str] = None,
        include_system: bool = False,
    ):
        super().__init__(dialect)
        self.table_name = table_name
        self.constraint_type = constraint_type
        self.include_system = include_system

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this statement."""
        return "format_firebird_constraint_list_query_statement"

    def __repr__(self) -> str:
        return (
            f"FirebirdConstraintListQueryStatement("
            f"table_name={self.table_name!r}, "
            f"constraint_type={self.constraint_type!r}, "
            f"include_system={self.include_system!r})"
        )


class FirebirdRoleListQueryStatement(BaseExpression):
    """Ask for this database's roles.

    Args:
        dialect: The dialect the statement is bound to.
        include_system: Whether to include the predefined roles. Defaults to
            False.
    """

    def __init__(self, dialect: "SQLDialectBase", include_system: bool = False):
        super().__init__(dialect)
        self.include_system = include_system

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this statement."""
        return "format_firebird_role_list_query_statement"

    def __repr__(self) -> str:
        return (
            f"FirebirdRoleListQueryStatement("
            f"include_system={self.include_system!r})"
        )


class FirebirdPrivilegeQueryStatement(BaseExpression):
    """Ask for grants, optionally on one object and/or to one grantee.

    One relation answers for both halves of a grant: SQL privileges
    (``SELECT``/``INSERT``/``UPDATE``/``DELETE``/``REFERENCES``/``EXECUTE``)
    and system privileges, which Firebird 4 records in the same relation with
    a ``$``-prefixed code. The grantee may be a user, a role, a procedure or a
    trigger, told apart by ``RDB$USER_TYPE``.

    Args:
        dialect: The dialect the statement is bound to.
        object_name: Restrict to grants on one relation, view, procedure or
            role, or ``None`` for all.
        user_name: Restrict to grants made to one grantee, or ``None``.
        include_system: Whether to include grants on ``RDB$`` relations.
            Defaults to False.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        object_name: Optional[str] = None,
        user_name: Optional[str] = None,
        include_system: bool = False,
    ):
        super().__init__(dialect)
        self.object_name = object_name
        self.user_name = user_name
        self.include_system = include_system

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this statement."""
        return "format_firebird_privilege_query_statement"

    def __repr__(self) -> str:
        return (
            f"FirebirdPrivilegeQueryStatement("
            f"object_name={self.object_name!r}, "
            f"user_name={self.user_name!r}, "
            f"include_system={self.include_system!r})"
        )


class FirebirdCharsetListQueryStatement(BaseExpression):
    """Ask for this database's character sets.

    ``RDB$CHARACTER_SETS`` mixes the built-in sets with any the database
    declared, and both are answerable questions, so there is no system filter.

    Args:
        dialect: The dialect the statement is bound to.
    """

    def __init__(self, dialect: "SQLDialectBase"):
        super().__init__(dialect)

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this statement."""
        return "format_firebird_charset_list_query_statement"

    def __repr__(self) -> str:
        return "FirebirdCharsetListQueryStatement()"


class FirebirdCollationListQueryStatement(BaseExpression):
    """Ask for collations, optionally of one character set.

    Args:
        dialect: The dialect the statement is bound to.
        charset_name: Restrict to one character set, or ``None`` for all.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        charset_name: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.charset_name = charset_name

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this statement."""
        return "format_firebird_collation_list_query_statement"

    def __repr__(self) -> str:
        return (
            f"FirebirdCollationListQueryStatement("
            f"charset_name={self.charset_name!r})"
        )


class FirebirdDependencyQueryStatement(BaseExpression):
    """Ask what depends on what.

    ``RDB$DEPENDENCIES`` records one row per edge, in either direction: the
    dependent object (a view, trigger, procedure, computed field or index
    expression) and what it depends on (a relation, procedure, function or
    another view). Passing a name returns the edges where it is either end,
    which is what "what breaks if I drop this" needs.

    Args:
        dialect: The dialect the statement is bound to.
        object_name: Restrict to edges naming this object on either side, or
            ``None`` for all.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        object_name: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.object_name = object_name

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this statement."""
        return "format_firebird_dependency_query_statement"

    def __repr__(self) -> str:
        return (
            f"FirebirdDependencyQueryStatement(object_name={self.object_name!r})"
        )


class FirebirdViewRelationQueryStatement(BaseExpression):
    """Ask which relations a view reads, with the context they are bound to.

    ``RDB$VIEW_RELATIONS`` binds each name used inside a view's ``SELECT`` to
    the ``RDB$CONTEXT_NAME`` that resolves to a relation. It is the answer to
    "what does this view stand on", which ``RDB$DEPENDENCIES`` only gives at
    object granularity.

    Args:
        dialect: The dialect the statement is bound to.
        view_name: Restrict to one view, or ``None`` for all.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        view_name: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.view_name = view_name

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this statement."""
        return "format_firebird_view_relation_query_statement"

    def __repr__(self) -> str:
        return (
            f"FirebirdViewRelationQueryStatement(view_name={self.view_name!r})"
        )


class FirebirdPublicationListQueryStatement(BaseExpression):
    """Ask for this database's publications.

    Logical replication arrived in Firebird 4: a publication is the set of
    tables replicated together. The relation does not exist on older servers,
    which is what the capability switch is for -- the statement itself stays
    version-agnostic.

    Args:
        dialect: The dialect the statement is bound to.
        include_system: Whether to include Firebird's own publications.
            Defaults to False.
    """

    def __init__(self, dialect: "SQLDialectBase", include_system: bool = False):
        super().__init__(dialect)
        self.include_system = include_system

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this statement."""
        return "format_firebird_publication_list_query_statement"

    def __repr__(self) -> str:
        return (
            f"FirebirdPublicationListQueryStatement("
            f"include_system={self.include_system!r})"
        )



class FirebirdColumnDataProfileQueryStatement(ColumnDataProfileQueryStatement):
    """Ask for one table's per-column profile, answered as a single row.

    Core's class already carries the question: the table, the (empty) namespace,
    and the column list an aggregating dialect cannot do without. This one adds
    the fact the SQL needs beyond the names -- *which* columns the aggregates
    can read at all.

    Firebird's ``MIN`` and ``MAX`` are defined over comparable types only, and a
    ``BLOB`` is not comparable: ``MIN(blob_col)`` is rejected when the statement
    is prepared, not answered as ``NULL``. ``COUNT(DISTINCT blob_col)`` fails for
    the same reason, because ``DISTINCT`` needs an ordering. So a profile that
    named a BLOB column in those positions would be refused as a whole rather
    than answer for the columns it can read. ``opaque_columns`` names them, and
    the formatter leaves their distinct count and both bounds as SQL ``NULL``
    while still counting their nulls and the table's rows.

    The introspector supplies that list from the column catalogue it reads the
    names from -- ``RDB$FIELDS.RDB$FIELD_TYPE`` is where the declared type is
    known, and the profile itself cannot see it.

    The profile is one row rather than one ``UNION ALL`` arm per column. Two
    reasons, one of which is Firebird's own: the statement reads the table once
    either way on this engine, but a union has to reconcile one type per column
    position across every arm, and ``min_value`` carrying an ``INTEGER`` from one
    column and a ``VARCHAR`` from another has no common type Firebird will
    accept. A single projection keeps each column's own bounds type.

    ``format_method`` is inherited deliberately: one formatter answers the
    question, reading ``opaque_columns`` when the statement carries it so that
    core's own statement -- which does not -- still renders, with every column
    assumed readable.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        table_name: str,
        schema: Optional[str] = None,
        columns: Sequence[str] = (),
        opaque_columns: Sequence[str] = (),
    ):
        """Initialize the column data profile statement.

        Args:
            dialect: The dialect the statement is bound to.
            table_name: The table whose columns are profiled.
            schema: The namespace; Firebird has one unnamed namespace, so this
                must be ``None`` or empty.
            columns: Every column of the table, in the order the profile's slots
                are projected.
            opaque_columns: The subset of *columns* whose declared type the
                aggregates cannot read. Their distinct count and bounds are
                rendered as ``NULL``.
        """
        super().__init__(
            dialect, table_name=table_name, schema=schema, columns=columns
        )
        self.opaque_columns = tuple(opaque_columns)

    def __repr__(self) -> str:
        return (
            f"FirebirdColumnDataProfileQueryStatement("
            f"table_name={self.table_name!r}, schema={self.schema!r}, "
            f"columns={self.columns!r}, opaque_columns={self.opaque_columns!r})"
        )
