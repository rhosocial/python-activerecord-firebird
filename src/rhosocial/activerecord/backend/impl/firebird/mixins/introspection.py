# src/rhosocial/activerecord/backend/impl/firebird/mixins/introspection.py
"""Firebird dialect introspection: capability declarations and SQL formatters.

Every catalogue question this backend asks is a statement object. The
statement collects the parameters (``TableListQueryStatement``,
``FirebirdGeneratorListQueryStatement``, ...) and the ``format_*`` methods
below turn those parameters into ``(sql, params)``. Nothing else in this
backend spells an introspection query: the introspecters construct a
statement, execute it and parse the rows it returns.

Firebird keeps its catalogue in the ``RDB$`` relations inside the one
unnamed namespace a database file has. Two consequences are visible
throughout:

* Names are never qualified with a schema. ``RDB$`` and ``MON$`` are naming
  conventions inside that namespace, not namespaces of their own.
* A caller who asks for a namespace is refused
  (:meth:`FirebirdIntrospectionMixin.reject_namespace`) rather than answered
  for the whole database, because "the database you named does not exist
  here" and "here is everything" are different answers.
"""

from typing import List, Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

from ..query_nodes import (
    call,
    column,
    compare,
    conjunction,
    identifier,
    join,
    like,
    literal,
    null_test,
    relation,
    select_sql,
)

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.introspection.types import IntrospectionScope

    from rhosocial.activerecord.backend.expression.introspection import (
        ColumnInfoQueryStatement,
        DatabaseInfoQueryStatement,
        ForeignKeyQueryStatement,
        IndexInfoQueryStatement,
        TableInfoQueryStatement,
        TableListQueryStatement,
        TriggerInfoQueryStatement,
        TriggerListQueryStatement,
        ViewInfoQueryStatement,
        ViewListQueryStatement,
    )
    from ..expression.introspection import (
        FirebirdCharsetListQueryStatement,
        FirebirdCollationListQueryStatement,
        FirebirdConstraintListQueryStatement,
        FirebirdDependencyQueryStatement,
        FirebirdDomainInfoQueryStatement,
        FirebirdDomainListQueryStatement,
        FirebirdExceptionInfoQueryStatement,
        FirebirdExceptionListQueryStatement,
        FirebirdFunctionArgumentQueryStatement,
        FirebirdFunctionListQueryStatement,
        FirebirdGeneratorListQueryStatement,
        FirebirdGeneratorValueQueryStatement,
        FirebirdPrivilegeQueryStatement,
        FirebirdProcedureListQueryStatement,
        FirebirdProcedureParameterQueryStatement,
        FirebirdPublicationListQueryStatement,
        FirebirdRoleListQueryStatement,
        FirebirdViewRelationQueryStatement,
    )


class FirebirdIntrospectionMixin:
    """What Firebird can be asked about, and how each question is spelled.

    The capability switches answer for the dialect; the formatters write the
    SQL. They were previously spread over a ``INTROSPECTION_QUERIES`` mapping
    and a set of ``_make_*`` builders on the introspector, which meant the
    same query existed twice and the formatters -- the only copy the
    expression layer can reach -- did not exist at all.
    """

    # ------------------------------------------------------------------ #
    # Capabilities
    # ------------------------------------------------------------------ #

    def supports_introspection(self) -> bool:
        """Firebird introspects through the ``RDB$`` catalogue."""
        return True

    def supports_database_info(self) -> bool:
        """``MON$DATABASE`` answers for the database's own facts."""
        return True

    def supports_table_introspection(self) -> bool:
        """``RDB$RELATIONS`` reads tables and views alike."""
        return True

    def supports_column_introspection(self) -> bool:
        """``RDB$RELATION_FIELDS`` joined to ``RDB$FIELDS``."""
        return True

    def supports_index_introspection(self) -> bool:
        """``RDB$INDICES`` with ``RDB$INDEX_SEGMENTS`` for the ordering."""
        return True

    def supports_foreign_key_introspection(self) -> bool:
        """``RDB$REF_CONSTRAINTS`` with ``RDB$RELATION_CONSTRAINTS``."""
        return True

    def supports_view_introspection(self) -> bool:
        """A view is a relation with ``RDB$VIEW_BLR`` set."""
        return True

    def supports_trigger_introspection(self) -> bool:
        """``RDB$TRIGGERS`` carries the timing, the events and the source."""
        return True

    def supports_domain_introspection(self) -> bool:
        """Firebird answers for its domains from ``RDB$FIELDS``.

        A domain is Firebird's reusable type layer, and the catalogue
        question is the same one a column's type descriptor answers -- which
        is why this lives here rather than on a domain-specific mixin.
        """
        return True

    def supports_generator_introspection(self) -> bool:
        """``RDB$GENERATORS`` names them; ``GEN_ID(name, 0)`` reads a value."""
        return True

    def supports_exception_introspection(self) -> bool:
        """``RDB$EXCEPTIONS`` carries the name, the number and the message."""
        return True

    def supports_procedure_introspection(self) -> bool:
        """``RDB$PROCEDURES`` for the signature, its parameters relation for
        the argument list."""
        return True

    def supports_function_introspection(self) -> bool:
        """``RDB$FUNCTIONS`` lists PSQL functions and legacy UDFs alike."""
        return True

    def supports_constraint_introspection(self) -> bool:
        """``RDB$RELATION_CONSTRAINTS`` holds every kind, including the
        ``NOT NULL`` rows Firebird records as constraints."""
        return True

    def supports_role_introspection(self) -> bool:
        """``RDB$ROLES``."""
        return True

    def supports_privilege_introspection(self) -> bool:
        """``RDB$USER_PRIVILEGES`` holds SQL and system grants in one place."""
        return True

    def supports_charset_introspection(self) -> bool:
        """``RDB$CHARACTER_SETS``."""
        return True

    def supports_collation_introspection(self) -> bool:
        """``RDB$COLLATIONS``, keyed to its character set by id."""
        return True

    def supports_dependency_introspection(self) -> bool:
        """``RDB$DEPENDENCIES`` records one edge per row, both directions."""
        return True

    def supports_view_relation_introspection(self) -> bool:
        """``RDB$VIEW_RELATIONS`` binds a view's contexts to relations."""
        return True

    def supports_publication_introspection(self) -> bool:
        """Logical replication arrived in Firebird 4.

        ``RDB$PUBLICATIONS`` does not exist before that, so asking an older
        server would be a ``-204`` relation-unknown rather than an empty list.
        The version is read off the dialect, which answers ``False`` when it
        has not been adapted yet rather than raising mid-probe.
        """
        return self.version_at_least((4, 0, 0))

    def get_supported_introspection_scopes(self) -> List["IntrospectionScope"]:
        """The scopes this backend answers for, in core's own vocabulary.

        Only eight of the twenty-two families have a scope here: the enum has
        no member for domains, exceptions, routines, roles, privileges,
        charsets, collations, dependencies, view relations or publications. The
        list below is therefore what core can *express*, not the whole of what
        this backend can answer -- ``_TYPE_CAPABILITIES`` in the CLI is the
        longer list. Adding members to ``IntrospectionScope`` is a core decision
        (the enum keys the introspection cache), not one this backend can make.
        """
        from rhosocial.activerecord.backend.introspection.types import (
            IntrospectionScope,
        )

        return [
            IntrospectionScope.DATABASE,
            IntrospectionScope.TABLE,
            IntrospectionScope.COLUMN,
            IntrospectionScope.INDEX,
            IntrospectionScope.FOREIGN_KEY,
            IntrospectionScope.VIEW,
            IntrospectionScope.TRIGGER,
            IntrospectionScope.SEQUENCE,
        ]

    # ------------------------------------------------------------------ #
    # Namespace
    # ------------------------------------------------------------------ #

    def reject_namespace(self, schema: Optional[str]) -> Optional[str]:
        """Accept the empty namespace; refuse any other.

        Firebird has one unnamed namespace per database file. ``None`` and
        ``""`` both mean "the whole database"; a name means the caller
        expects a scope that does not exist.

        Args:
            schema: The namespace a caller asked to introspect, or ``None`` /
                ``""`` for "the whole database".

        Returns:
            ``None``, so a formatter can write
            ``schema = self.reject_namespace(schema)``.

        Raises:
            UnsupportedFeatureError: ``schema`` names a namespace.
        """
        if schema:
            raise UnsupportedFeatureError(
                self.name,
                "schema-scoped introspection",
                suggestion=(
                    f"Firebird has a single unnamed namespace, so {schema!r} "
                    f"cannot be selected from: the whole database is the only "
                    f"scope. Pass schema=None."
                ),
            )
        return None

    # ------------------------------------------------------------------ #
    # Core catalogue questions
    # ------------------------------------------------------------------ #

    def format_database_info_query_statement(
        self, expr: "DatabaseInfoQueryStatement"
    ) -> tuple:
        """Render the database informational query.

        ``MON$DATABASE_NAME`` is the attachment's file path, which is the
        only name a Firebird database has.
        """
        params = expr.get_params()
        self.reject_namespace(params.get("schema"))
        return select_sql(
            self,
            [column(self, "MON$DATABASE_NAME")],
            from_=relation(self, "MON$DATABASE"),
        )

    def format_table_list_query_statement(
        self, expr: "TableListQueryStatement"
    ) -> tuple:
        """Render the table (and view) listing.

        ``RDB$SYSTEM_FLAG = 0`` drops the catalogue's own relations and
        ``RDB$VIEW_BLR IS NULL`` drops views; both are conditions of the
        question, not data, so they stay inline. ``table_type`` narrows the
        relation kind when the caller names one; the core's table API passes
        ``None`` and the question is then the unfiltered one.

        ``RDB$RELATION_TYPE`` is projected because it is the column that tells
        a persistent table from a global temporary or an external one, and a
        list that dropped it would leave the parser unable to name the kind --
        Firebird's GTTs are ordinary relations with ``RDB$SYSTEM_FLAG = 0``,
        so nothing else in the row betrays them.
        """
        params = expr.get_params()
        self.reject_namespace(params.get("schema"))
        include_system = params.get("include_system", False)
        include_views = params.get("include_views", True)
        table_type = params.get("table_type")

        conditions = []
        if not include_system:
            conditions.append(
                compare(
                    self, "eq", column(self, "RDB$SYSTEM_FLAG"), literal(self, 0, inline=True)
                )
            )
        if not include_views:
            conditions.append(null_test(self, column(self, "RDB$VIEW_BLR")))
        elif table_type:
            spelled = str(table_type).upper()
            if spelled == "VIEW":
                conditions.append(
                    null_test(self, column(self, "RDB$VIEW_BLR"), is_not=True)
                )
            elif spelled in ("TABLE", "BASE TABLE"):
                conditions.append(null_test(self, column(self, "RDB$VIEW_BLR")))

        return select_sql(
            self,
            [
                column(self, "RDB$RELATION_NAME"),
                column(self, "RDB$VIEW_BLR"),
                column(self, "RDB$RELATION_TYPE"),
            ],
            from_=relation(self, "RDB$RELATIONS"),
            where=conjunction(self, *conditions) if conditions else None,
            order_by=[column(self, "RDB$RELATION_NAME")],
        )

    def format_table_info_query_statement(
        self, expr: "TableInfoQueryStatement"
    ) -> tuple:
        """Render the single-relation question.

        The core's ``get_table_info`` synthesizes its answer from the list,
        column, index and foreign-key questions, so this one is not on that
        path. It still has to be a real question for the statement to be
        renderable: it asks for the relation and for whether it is a view.
        """
        params = expr.get_params()
        self.reject_namespace(params.get("schema"))
        return select_sql(
            self,
            [column(self, "RDB$RELATION_NAME"), column(self, "RDB$VIEW_BLR")],
            from_=relation(self, "RDB$RELATIONS"),
            where=compare(
                self,
                "eq",
                column(self, "RDB$RELATION_NAME"),
                literal(self, params.get("table_name", "")),
            ),
        )

    def format_column_info_query_statement(
        self, expr: "ColumnInfoQueryStatement"
    ) -> tuple:
        """Render one relation's columns, with the domain each is built on.

        ``RDB$RELATION_FIELDS`` holds the per-column facts and ``RDB$FIELDS``
        the domain the column was declared from, so the two are joined
        through ``RDB$FIELD_SOURCE``. The relation name is a bind position.
        """
        params = expr.get_params()
        self.reject_namespace(params.get("schema"))
        table_name = params.get("table_name", "")

        joined = join(
            self,
            relation(self, "RDB$RELATION_FIELDS", alias="rf"),
            relation(self, "RDB$FIELDS", alias="f"),
            condition=compare(
                self,
                "eq",
                column(self, "RDB$FIELD_SOURCE", "rf"),
                column(self, "RDB$FIELD_NAME", "f"),
            ),
        )
        return select_sql(
            self,
            [
                column(self, "RDB$FIELD_NAME", "rf", alias="COLUMN_NAME"),
                column(self, "RDB$FIELD_TYPE", "f", alias="FIELD_TYPE"),
                column(self, "RDB$FIELD_SUB_TYPE", "f", alias="FIELD_SUB_TYPE"),
                column(self, "RDB$CHARACTER_LENGTH", "f", alias="CHAR_LENGTH"),
                column(self, "RDB$FIELD_PRECISION", "f", alias="PRECISION"),
                column(self, "RDB$FIELD_SCALE", "f", alias="SCALE"),
                column(self, "RDB$NULL_FLAG", "rf", alias="NULL_FLAG"),
                column(self, "RDB$DEFAULT_SOURCE", "rf", alias="DEFAULT_SOURCE"),
                column(self, "RDB$FIELD_POSITION", "rf", alias="POSITION"),
                column(self, "RDB$COMPUTED_SOURCE", "f", alias="COMPUTED_SOURCE"),
                column(self, "RDB$IDENTITY_TYPE", "rf", alias="IDENTITY_TYPE"),
                column(self, "RDB$GENERATOR_NAME", "rf", alias="GENERATOR_NAME"),
                column(self, "RDB$COLLATION_ID", "rf", alias="COLLATION_ID"),
                column(self, "RDB$DESCRIPTION", "rf", alias="DESCRIPTION"),
            ],
            from_=joined,
            where=compare(
                self,
                "eq",
                column(self, "RDB$RELATION_NAME", "rf"),
                literal(self, table_name),
            ),
            order_by=[column(self, "RDB$FIELD_POSITION", "rf")],
        )

    def format_index_info_query_statement(
        self, expr: "IndexInfoQueryStatement"
    ) -> tuple:
        """Render one relation's indexes with their key columns, in key order.

        The constraint read is a left join on the same relation and index: a
        primary-key index and the constraint that owns it are two rows about
        one object, and leaving the join outer keeps ordinary indexes in the
        answer. ``RDB$CONSTRAINT_TYPE`` is what makes ``is_primary``
        answerable at all -- Firebird names a primary-key index ``INTEG_nn``,
        so nothing in the index name says which kind it is.
        """
        params = expr.get_params()
        self.reject_namespace(params.get("schema"))
        table_name = params.get("table_name", "")

        joined = join(
            self,
            join(
                self,
                relation(self, "RDB$INDICES", alias="i"),
                relation(self, "RDB$INDEX_SEGMENTS", alias="isg"),
                condition=compare(
                    self,
                    "eq",
                    column(self, "RDB$INDEX_NAME", "i"),
                    column(self, "RDB$INDEX_NAME", "isg"),
                ),
            ),
            relation(self, "RDB$RELATION_CONSTRAINTS", alias="rc"),
            condition=conjunction(
                self,
                compare(
                    self,
                    "eq",
                    column(self, "RDB$INDEX_NAME", "rc"),
                    column(self, "RDB$INDEX_NAME", "i"),
                ),
                compare(
                    self,
                    "eq",
                    column(self, "RDB$RELATION_NAME", "rc"),
                    column(self, "RDB$RELATION_NAME", "i"),
                ),
            ),
            join_type="LEFT",
        )
        return select_sql(
            self,
            [
                column(self, "RDB$INDEX_NAME", "i", alias="INDEX_NAME"),
                column(self, "RDB$UNIQUE_FLAG", "i", alias="UNIQUE_FLAG"),
                column(self, "RDB$INDEX_INACTIVE", "i", alias="INACTIVE"),
                column(self, "RDB$INDEX_TYPE", "i", alias="INDEX_TYPE"),
                column(self, "RDB$CONSTRAINT_TYPE", "rc", alias="CONSTRAINT_TYPE"),
                column(self, "RDB$FIELD_NAME", "isg", alias="FIELD_NAME"),
                column(self, "RDB$FIELD_POSITION", "isg", alias="FIELD_POSITION"),
            ],
            from_=joined,
            where=compare(
                self,
                "eq",
                column(self, "RDB$RELATION_NAME", "i"),
                literal(self, table_name),
            ),
            order_by=[
                column(self, "RDB$INDEX_NAME", "i"),
                column(self, "RDB$FIELD_POSITION", "isg"),
            ],
        )

    def format_foreign_key_query_statement(
        self, expr: "ForeignKeyQueryStatement"
    ) -> tuple:
        """Render one relation's outgoing foreign keys, with their targets.

        A foreign key is spelled across four relations and read as eight
        joins:

        * ``rc`` is the constraint row itself -- it owns the name, the type,
          the referencing relation and the referencing index;
        * ``refc`` adds what only a *foreign* key has: the referential rules
          and ``RDB$CONST_NAME_UQ``, the name of the *constraint* it points
          at;
        * ``seg`` walks the referencing index's segments, ``ref_seg`` the
          referenced index's, paired by ``RDB$FIELD_POSITION`` so a
          two-column key lines up column by column rather than as a cross
          product;
        * ``refrc`` is the hop that was missing: ``RDB$CONST_NAME_UQ`` names a
          constraint, not an index, so the referenced index is only reachable
          through that constraint's row. Joining ``RDB$INDICES`` straight to
          the constraint name happens to work when Firebird generated the
          index name from the constraint, which is why the defect stayed
          hidden until a key was named by hand;
        * ``ref`` is the referenced relation, reached through the referenced
          index rather than through the constraint, because that is the row
          that actually says which table the index belongs to.

        ``RDB$REF_CONSTRAINTS`` has no ``RDB$INDEX_NAME`` and never had: the
        earlier tree read one from it, which is a ``-206 column unknown`` on
        every server.
        """
        params = expr.get_params()
        self.reject_namespace(params.get("schema"))
        table_name = params.get("table_name", "")

        joined = join(
            self,
            join(
                self,
                join(
                    self,
                    join(
                        self,
                        join(
                            self,
                            join(
                                self,
                                join(
                                    self,
                                    relation(self, "RDB$RELATION_CONSTRAINTS", alias="rc"),
                                    relation(self, "RDB$REF_CONSTRAINTS", alias="refc"),
                                    condition=compare(
                                        self,
                                        "eq",
                                        column(self, "RDB$CONSTRAINT_NAME", "refc"),
                                        column(self, "RDB$CONSTRAINT_NAME", "rc"),
                                    ),
                                ),
                                relation(self, "RDB$INDEX_SEGMENTS", alias="seg"),
                                condition=compare(
                                    self,
                                    "eq",
                                    column(self, "RDB$INDEX_NAME", "seg"),
                                    column(self, "RDB$INDEX_NAME", "rc"),
                                ),
                            ),
                            relation(self, "RDB$RELATION_CONSTRAINTS", alias="refrc"),
                            condition=compare(
                                self,
                                "eq",
                                column(self, "RDB$CONSTRAINT_NAME", "refrc"),
                                column(self, "RDB$CONST_NAME_UQ", "refc"),
                            ),
                        ),
                        relation(self, "RDB$INDEX_SEGMENTS", alias="ref_seg"),
                        condition=conjunction(
                            self,
                            compare(
                                self,
                                "eq",
                                column(self, "RDB$INDEX_NAME", "ref_seg"),
                                column(self, "RDB$INDEX_NAME", "refrc"),
                            ),
                            compare(
                                self,
                                "eq",
                                column(self, "RDB$FIELD_POSITION", "ref_seg"),
                                column(self, "RDB$FIELD_POSITION", "seg"),
                            ),
                        ),
                    ),
                    relation(self, "RDB$INDICES", alias="ref_i"),
                    condition=compare(
                        self,
                        "eq",
                        column(self, "RDB$INDEX_NAME", "ref_i"),
                        column(self, "RDB$INDEX_NAME", "refrc"),
                    ),
                ),
                relation(self, "RDB$RELATIONS", alias="ref"),
                condition=compare(
                    self,
                    "eq",
                    column(self, "RDB$RELATION_NAME", "ref"),
                    column(self, "RDB$RELATION_NAME", "ref_i"),
                ),
            ),
            relation(self, "RDB$INDICES", alias="i"),
            condition=compare(
                self,
                "eq",
                column(self, "RDB$INDEX_NAME", "i"),
                column(self, "RDB$INDEX_NAME", "rc"),
            ),
        )
        return select_sql(
            self,
            [
                column(self, "RDB$CONSTRAINT_NAME", "rc", alias="CONSTRAINT_NAME"),
                column(self, "RDB$INDEX_NAME", "rc", alias="INDEX_NAME"),
                column(self, "RDB$FIELD_NAME", "seg", alias="COLUMN_NAME"),
                column(self, "RDB$RELATION_NAME", "ref", alias="REF_TABLE"),
                column(self, "RDB$FIELD_NAME", "ref_seg", alias="REF_COLUMN"),
                column(self, "RDB$DELETE_RULE", "refc", alias="DELETE_RULE"),
                column(self, "RDB$UPDATE_RULE", "refc", alias="UPDATE_RULE"),
                column(self, "RDB$MATCH_OPTION", "refc", alias="MATCH_OPTION"),
            ],
            from_=joined,
            where=conjunction(
                self,
                compare(
                    self,
                    "eq",
                    column(self, "RDB$RELATION_NAME", "rc"),
                    literal(self, table_name),
                ),
                compare(
                    self,
                    "eq",
                    column(self, "RDB$CONSTRAINT_TYPE", "rc"),
                    literal(self, "FOREIGN KEY", inline=True),
                ),
            ),
            order_by=[
                column(self, "RDB$CONSTRAINT_NAME", "rc"),
                column(self, "RDB$FIELD_POSITION", "seg"),
            ],
        )

    def format_view_list_query_statement(
        self, expr: "ViewListQueryStatement"
    ) -> tuple:
        """Render the database's views.

        ``RDB$VIEW_BLR IS NOT NULL`` is what makes a relation a view;
        ``RDB$VIEW_SOURCE`` carries its text.
        """
        params = expr.get_params()
        self.reject_namespace(params.get("schema"))
        conditions = []
        if not params.get("include_system", False):
            conditions.append(
                compare(
                    self, "eq", column(self, "RDB$SYSTEM_FLAG"), literal(self, 0, inline=True)
                )
            )
        conditions.append(null_test(self, column(self, "RDB$VIEW_BLR"), is_not=True))

        return select_sql(
            self,
            [column(self, "RDB$RELATION_NAME"), column(self, "RDB$VIEW_SOURCE")],
            from_=relation(self, "RDB$RELATIONS"),
            where=conjunction(self, *conditions),
            order_by=[column(self, "RDB$RELATION_NAME")],
        )

    def format_view_info_query_statement(
        self, expr: "ViewInfoQueryStatement"
    ) -> tuple:
        """Render the single-view question, narrowed by name."""
        params = expr.get_params()
        self.reject_namespace(params.get("schema"))
        return select_sql(
            self,
            [column(self, "RDB$RELATION_NAME"), column(self, "RDB$VIEW_SOURCE")],
            from_=relation(self, "RDB$RELATIONS"),
            where=conjunction(
                self,
                compare(
                    self, "eq", column(self, "RDB$SYSTEM_FLAG"), literal(self, 0, inline=True)
                ),
                null_test(self, column(self, "RDB$VIEW_BLR"), is_not=True),
                compare(
                    self,
                    "eq",
                    column(self, "RDB$RELATION_NAME"),
                    literal(self, params.get("view_name", "")),
                ),
            ),
        )

    def format_trigger_list_query_statement(
        self, expr: "TriggerListQueryStatement"
    ) -> tuple:
        """Render the trigger listing, optionally for one relation.

        ``RDB$RELATION_NAME IS NOT NULL`` excludes database-level triggers:
        their rows have no table, and the result type is a table trigger's.
        """
        params = expr.get_params()
        self.reject_namespace(params.get("schema"))
        table_name = params.get("table_name")

        conditions = [null_test(self, column(self, "RDB$RELATION_NAME"), is_not=True)]
        if table_name:
            conditions.append(
                compare(
                    self,
                    "eq",
                    column(self, "RDB$RELATION_NAME"),
                    literal(self, table_name),
                )
            )
        return select_sql(
            self,
            [
                column(self, "RDB$TRIGGER_NAME", alias="TRIGGER_NAME"),
                column(self, "RDB$RELATION_NAME", alias="TABLE_NAME"),
                column(self, "RDB$TRIGGER_TYPE", alias="TRIGGER_TYPE"),
                column(self, "RDB$TRIGGER_SOURCE", alias="SOURCE"),
                column(self, "RDB$TRIGGER_INACTIVE", alias="INACTIVE"),
                column(self, "RDB$TRIGGER_SEQUENCE", alias="SEQUENCE"),
            ],
            from_=relation(self, "RDB$TRIGGERS"),
            where=conjunction(self, *conditions),
            order_by=[column(self, "RDB$TRIGGER_NAME")],
        )

    def format_trigger_info_query_statement(
        self, expr: "TriggerInfoQueryStatement"
    ) -> tuple:
        """Render the single-trigger question, narrowed by name."""
        params = expr.get_params()
        self.reject_namespace(params.get("schema"))
        return select_sql(
            self,
            [
                column(self, "RDB$TRIGGER_NAME", alias="TRIGGER_NAME"),
                column(self, "RDB$RELATION_NAME", alias="TABLE_NAME"),
                column(self, "RDB$TRIGGER_TYPE", alias="TRIGGER_TYPE"),
                column(self, "RDB$TRIGGER_SOURCE", alias="SOURCE"),
                column(self, "RDB$TRIGGER_INACTIVE", alias="INACTIVE"),
                column(self, "RDB$TRIGGER_SEQUENCE", alias="SEQUENCE"),
            ],
            from_=relation(self, "RDB$TRIGGERS"),
            where=conjunction(
                self,
                null_test(self, column(self, "RDB$RELATION_NAME"), is_not=True),
                compare(
                    self,
                    "eq",
                    column(self, "RDB$TRIGGER_NAME"),
                    literal(self, params.get("trigger_name", "")),
                ),
            ),
        )

    # ------------------------------------------------------------------ #
    # Firebird's own object families
    # ------------------------------------------------------------------ #

    def format_firebird_generator_list_query_statement(
        self, expr: "FirebirdGeneratorListQueryStatement"
    ) -> tuple:
        """Render the generator (sequence) listing.

        ``RDB$GENERATORS`` records the name and the system flag, but **not
        the value**: the number a generator has reached is engine state, not
        a catalogue column. The value is a separate question per generator
        (:meth:`format_firebird_generator_value_query_statement`).
        """
        params = expr.get_params()
        conditions = []
        if not params.get("include_system", False):
            conditions.append(
                compare(
                    self, "eq", column(self, "RDB$SYSTEM_FLAG"), literal(self, 0, inline=True)
                )
            )
        return select_sql(
            self,
            [
                column(self, "RDB$GENERATOR_NAME", alias="GENERATOR_NAME"),
                column(self, "RDB$SYSTEM_FLAG", alias="SYSTEM_FLAG"),
            ],
            from_=relation(self, "RDB$GENERATORS"),
            where=conjunction(self, *conditions) if conditions else None,
            order_by=[column(self, "RDB$GENERATOR_NAME")],
        )

    def format_firebird_generator_value_query_statement(
        self, expr: "FirebirdGeneratorValueQueryStatement"
    ) -> tuple:
        """Render one generator's current value.

        ``GEN_ID(<name>, 0)`` increments by zero and returns the result, so
        it is a read. A generator name cannot be a bind parameter, which is
        why the name is rendered as an identifier while the step stays a
        literal -- both are arguments of the function, and this is the one
        function whose name argument is not data.
        """
        params = expr.get_params()
        return select_sql(
            self,
            [
                call(
                    self,
                    "gen_id",
                    identifier(self, params.get("generator_name", "")),
                    literal(self, 0, inline=True),
                    alias="GENERATOR_VALUE",
                )
            ],
            from_=relation(self, "RDB$DATABASE"),
        )

    def format_firebird_domain_list_query_statement(
        self, expr: "FirebirdDomainListQueryStatement"
    ) -> tuple:
        """Render the domain listing.

        One relation, not two. ``RDB$FIELDS`` is where Firebird keeps "the
        definitions of columns and domains, both system and custom"; there
        is no ``RDB$DOMAINS`` table.

        ``RDB$CHARACTER_SETS`` is a **LEFT** join because the charset id is
        NULL for non-character types: an inner join would silently drop every
        numeric, date and blob domain from the answer.

        What separates a domain from an implicit column domain is the name.
        ``RDB$FIELDS`` also carries the row Firebird generates for every
        column declared inline (``NUMERIC(9,2)`` and friends), and those are
        not objects a caller created -- system-created domain names start
        with ``RDB$``. A caller asking for the domains it declared therefore
        gets the rows whose names do not; ``include_system`` reads every row
        instead, the system ones included.
        """
        params = expr.get_params()
        # A LEFT join, not INNER: RDB$CHARACTER_SET_ID is only meaningful for
        # character types, and the join must not delete the rest of the answer.
        source = join(
            self,
            relation(self, "RDB$FIELDS", alias="f"),
            relation(self, "RDB$CHARACTER_SETS", alias="cs"),
            condition=compare(
                self,
                "eq",
                column(self, "RDB$CHARACTER_SET_ID", "f"),
                column(self, "RDB$CHARACTER_SET_ID", "cs"),
            ),
            join_type="LEFT JOIN",
        )
        conditions = []
        if not params.get("include_system", False):
            # Two filters, because they say different things.
            #
            # ``RDB$SYSTEM_FLAG`` is what the caller means by "not system":
            # it is the column the ``is_system`` field on the result is read
            # from, so filtering on it is what keeps the answer honest.
            #
            # ``NOT LIKE 'RDB$%'`` removes the *implicit* descriptors
            # Firebird writes for every inline-declared column. The flag
            # alone does not catch them: they are marked as created by the
            # system only when the column type was written inline.
            conditions.append(
                compare(
                    self,
                    "eq",
                    column(self, "RDB$SYSTEM_FLAG", "f"),
                    literal(self, 0, inline=True),
                )
            )
            conditions.append(
                like(self, column(self, "RDB$FIELD_NAME", "f"), "RDB$%", negated=True)
            )
        return select_sql(
            self,
            [
                column(self, "RDB$FIELD_NAME", "f", alias="DOMAIN_NAME"),
                column(self, "RDB$FIELD_TYPE", "f", alias="FIELD_TYPE"),
                column(self, "RDB$FIELD_SUB_TYPE", "f", alias="FIELD_SUB_TYPE"),
                column(self, "RDB$FIELD_LENGTH", "f", alias="FIELD_LENGTH"),
                column(self, "RDB$CHARACTER_LENGTH", "f", alias="CHARACTER_LENGTH"),
                column(self, "RDB$FIELD_PRECISION", "f", alias="PRECISION"),
                column(self, "RDB$FIELD_SCALE", "f", alias="SCALE"),
                column(self, "RDB$CHARACTER_SET_NAME", "cs", alias="CHARACTER_SET_NAME"),
                column(self, "RDB$NULL_FLAG", "f", alias="NULL_FLAG"),
                column(self, "RDB$DEFAULT_SOURCE", "f", alias="DEFAULT_SOURCE"),
                column(self, "RDB$VALIDATION_SOURCE", "f", alias="VALIDATION_SOURCE"),
                column(self, "RDB$SYSTEM_FLAG", "f", alias="SYSTEM_FLAG"),
                column(self, "RDB$DESCRIPTION", "f", alias="DESCRIPTION"),
            ],
            from_=source,
            where=conjunction(self, *conditions) if conditions else None,
            order_by=[column(self, "RDB$FIELD_NAME", "f")],
        )

    def format_firebird_domain_info_query_statement(
        self, expr: "FirebirdDomainInfoQueryStatement"
    ) -> tuple:
        """Render one domain.

        The listing's projection and joins, narrowed by name. Sharing the shape
        rather than writing a second one keeps "what a domain is" stated once:
        a caller inspecting one domain sees exactly the fields the listing
        shows, so no field exists on only one of the two paths.
        """
        params = expr.get_params()
        source = join(
            self,
            relation(self, "RDB$FIELDS", alias="f"),
            relation(self, "RDB$CHARACTER_SETS", alias="cs"),
            condition=compare(
                self,
                "eq",
                column(self, "RDB$CHARACTER_SET_ID", "f"),
                column(self, "RDB$CHARACTER_SET_ID", "cs"),
            ),
            join_type="LEFT JOIN",
        )
        return select_sql(
            self,
            [
                column(self, "RDB$FIELD_NAME", "f", alias="DOMAIN_NAME"),
                column(self, "RDB$FIELD_TYPE", "f", alias="FIELD_TYPE"),
                column(self, "RDB$FIELD_SUB_TYPE", "f", alias="FIELD_SUB_TYPE"),
                column(self, "RDB$FIELD_LENGTH", "f", alias="FIELD_LENGTH"),
                column(self, "RDB$CHARACTER_LENGTH", "f", alias="CHARACTER_LENGTH"),
                column(self, "RDB$FIELD_PRECISION", "f", alias="PRECISION"),
                column(self, "RDB$FIELD_SCALE", "f", alias="SCALE"),
                column(self, "RDB$CHARACTER_SET_NAME", "cs", alias="CHARACTER_SET_NAME"),
                column(self, "RDB$NULL_FLAG", "f", alias="NULL_FLAG"),
                column(self, "RDB$DEFAULT_SOURCE", "f", alias="DEFAULT_SOURCE"),
                column(self, "RDB$VALIDATION_SOURCE", "f", alias="VALIDATION_SOURCE"),
                column(self, "RDB$SYSTEM_FLAG", "f", alias="SYSTEM_FLAG"),
                column(self, "RDB$DESCRIPTION", "f", alias="DESCRIPTION"),
            ],
            from_=source,
            where=compare(
                self,
                "eq",
                column(self, "RDB$FIELD_NAME", "f"),
                literal(self, params.get("domain_name", "")),
            ),
        )

    def format_firebird_exception_list_query_statement(
        self, expr: "FirebirdExceptionListQueryStatement"
    ) -> tuple:
        """Render the exception listing.

        ``RDB$EXCEPTIONS`` holds the name, the number a ``WHEN`` clause names
        and the message text, so one read answers the whole family.
        """
        params = expr.get_params()
        conditions = []
        if not params.get("include_system", False):
            conditions.append(
                compare(
                    self,
                    "eq",
                    column(self, "RDB$SYSTEM_FLAG"),
                    literal(self, 0, inline=True),
                )
            )
        return select_sql(
            self,
            [
                column(self, "RDB$EXCEPTION_NAME", alias="EXCEPTION_NAME"),
                column(self, "RDB$EXCEPTION_NUMBER", alias="EXCEPTION_NUMBER"),
                column(self, "RDB$MESSAGE", alias="MESSAGE"),
                column(self, "RDB$OWNER_NAME", alias="OWNER_NAME"),
                column(self, "RDB$SYSTEM_FLAG", alias="SYSTEM_FLAG"),
                column(self, "RDB$DESCRIPTION", alias="DESCRIPTION"),
            ],
            from_=relation(self, "RDB$EXCEPTIONS"),
            where=conjunction(self, *conditions) if conditions else None,
            order_by=[column(self, "RDB$EXCEPTION_NAME")],
        )

    def format_firebird_exception_info_query_statement(
        self, expr: "FirebirdExceptionInfoQueryStatement"
    ) -> tuple:
        """Render one exception, with the listing's projection."""
        params = expr.get_params()
        return select_sql(
            self,
            [
                column(self, "RDB$EXCEPTION_NAME", alias="EXCEPTION_NAME"),
                column(self, "RDB$EXCEPTION_NUMBER", alias="EXCEPTION_NUMBER"),
                column(self, "RDB$MESSAGE", alias="MESSAGE"),
                column(self, "RDB$OWNER_NAME", alias="OWNER_NAME"),
                column(self, "RDB$SYSTEM_FLAG", alias="SYSTEM_FLAG"),
                column(self, "RDB$DESCRIPTION", alias="DESCRIPTION"),
            ],
            from_=relation(self, "RDB$EXCEPTIONS"),
            where=compare(
                self,
                "eq",
                column(self, "RDB$EXCEPTION_NAME"),
                literal(self, params.get("exception_name", "")),
            ),
        )

    def format_firebird_procedure_list_query_statement(
        self, expr: "FirebirdProcedureListQueryStatement"
    ) -> tuple:
        """Render the stored-procedure listing.

        ``RDB$PROCEDURE_SOURCE`` is selected only when asked for: it is a blob
        holding the whole PSQL body, and a listing that carries every body is a
        different, much larger answer than a listing of signatures.
        """
        params = expr.get_params()
        conditions = []
        if not params.get("include_system", False):
            conditions.append(
                compare(
                    self,
                    "eq",
                    column(self, "RDB$SYSTEM_FLAG"),
                    literal(self, 0, inline=True),
                )
            )
        projections = [
            column(self, "RDB$PROCEDURE_NAME", alias="PROCEDURE_NAME"),
            column(self, "RDB$PROCEDURE_ID", alias="PROCEDURE_ID"),
            column(self, "RDB$PROCEDURE_INPUTS", alias="INPUTS"),
            column(self, "RDB$PROCEDURE_OUTPUTS", alias="OUTPUTS"),
            column(self, "RDB$PROCEDURE_TYPE", alias="PROCEDURE_TYPE"),
            column(self, "RDB$OWNER_NAME", alias="OWNER_NAME"),
            column(self, "RDB$VALID_BLR", alias="VALID_BLR"),
            column(self, "RDB$PRIVATE_FLAG", alias="PRIVATE_FLAG"),
            column(self, "RDB$SQL_SECURITY", alias="SQL_SECURITY"),
            column(self, "RDB$DESCRIPTION", alias="DESCRIPTION"),
            column(self, "RDB$SYSTEM_FLAG", alias="SYSTEM_FLAG"),
        ]
        if params.get("include_source", False):
            projections.append(
                column(self, "RDB$PROCEDURE_SOURCE", alias="PROCEDURE_SOURCE")
            )
        return select_sql(
            self,
            projections,
            from_=relation(self, "RDB$PROCEDURES"),
            where=conjunction(self, *conditions) if conditions else None,
            order_by=[column(self, "RDB$PROCEDURE_NAME")],
        )

    def format_firebird_procedure_parameter_query_statement(
        self, expr: "FirebirdProcedureParameterQueryStatement"
    ) -> tuple:
        """Render one procedure's parameters.

        Inputs and outputs share ``RDB$PROCEDURE_PARAMETERS``; the type column
        and the position order them, so the caller reads one ordered list
        instead of two. The type descriptor lives in ``RDB$FIELDS``, reachable
        through ``RDB$FIELD_SOURCE`` -- the same descriptor a column uses.
        """
        params = expr.get_params()
        joined = join(
            self,
            relation(self, "RDB$PROCEDURE_PARAMETERS", alias="p"),
            relation(self, "RDB$FIELDS", alias="f"),
            condition=compare(
                self,
                "eq",
                column(self, "RDB$FIELD_SOURCE", "p"),
                column(self, "RDB$FIELD_NAME", "f"),
            ),
        )
        return select_sql(
            self,
            [
                column(self, "RDB$PARAMETER_NAME", "p", alias="PARAMETER_NAME"),
                column(self, "RDB$PARAMETER_NUMBER", "p", alias="PARAMETER_NUMBER"),
                column(self, "RDB$PARAMETER_TYPE", "p", alias="PARAMETER_TYPE"),
                column(self, "RDB$FIELD_TYPE", "f", alias="FIELD_TYPE"),
                column(self, "RDB$FIELD_SUB_TYPE", "f", alias="FIELD_SUB_TYPE"),
                column(self, "RDB$CHARACTER_LENGTH", "f", alias="CHARACTER_LENGTH"),
                column(self, "RDB$FIELD_PRECISION", "f", alias="PRECISION"),
                column(self, "RDB$FIELD_SCALE", "f", alias="SCALE"),
                column(self, "RDB$NULL_FLAG", "p", alias="NULL_FLAG"),
                column(self, "RDB$DEFAULT_SOURCE", "p", alias="DEFAULT_SOURCE"),
                column(self, "RDB$DESCRIPTION", "p", alias="DESCRIPTION"),
            ],
            from_=joined,
            where=compare(
                self,
                "eq",
                column(self, "RDB$PROCEDURE_NAME", "p"),
                literal(self, params.get("procedure_name", "")),
            ),
            order_by=[
                column(self, "RDB$PARAMETER_TYPE", "p"),
                column(self, "RDB$PARAMETER_NUMBER", "p"),
            ],
        )

    def format_firebird_function_list_query_statement(
        self, expr: "FirebirdFunctionListQueryStatement"
    ) -> tuple:
        """Render the function listing, PSQL and legacy UDF alike.

        ``RDB$LEGACY_FLAG`` is what tells the two apart: a legacy UDF names a
        ``RDB$MODULE_NAME`` and an ``RDB$ENTRYPOINT``, a PSQL function carries
        its body in ``RDB$FUNCTION_SOURCE``. Both are callable schema objects,
        so both are listed and the distinguishing columns are selected.
        """
        params = expr.get_params()
        conditions = []
        if not params.get("include_system", False):
            conditions.append(
                compare(
                    self,
                    "eq",
                    column(self, "RDB$SYSTEM_FLAG"),
                    literal(self, 0, inline=True),
                )
            )
        projections = [
            column(self, "RDB$FUNCTION_NAME", alias="FUNCTION_NAME"),
            column(self, "RDB$FUNCTION_TYPE", alias="FUNCTION_TYPE"),
            column(self, "RDB$LEGACY_FLAG", alias="LEGACY_FLAG"),
            column(self, "RDB$DETERMINISTIC_FLAG", alias="DETERMINISTIC_FLAG"),
            column(self, "RDB$RETURN_ARGUMENT", alias="RETURN_ARGUMENT"),
            column(self, "RDB$OWNER_NAME", alias="OWNER_NAME"),
            column(self, "RDB$VALID_BLR", alias="VALID_BLR"),
            column(self, "RDB$ENGINE_NAME", alias="ENGINE_NAME"),
            column(self, "RDB$MODULE_NAME", alias="MODULE_NAME"),
            column(self, "RDB$ENTRYPOINT", alias="ENTRYPOINT"),
            column(self, "RDB$PRIVATE_FLAG", alias="PRIVATE_FLAG"),
            column(self, "RDB$SQL_SECURITY", alias="SQL_SECURITY"),
            column(self, "RDB$DESCRIPTION", alias="DESCRIPTION"),
            column(self, "RDB$SYSTEM_FLAG", alias="SYSTEM_FLAG"),
        ]
        if params.get("include_source", False):
            projections.append(
                column(self, "RDB$FUNCTION_SOURCE", alias="FUNCTION_SOURCE")
            )
        return select_sql(
            self,
            projections,
            from_=relation(self, "RDB$FUNCTIONS"),
            where=conjunction(self, *conditions) if conditions else None,
            order_by=[column(self, "RDB$FUNCTION_NAME")],
        )

    def format_firebird_function_argument_query_statement(
        self, expr: "FirebirdFunctionArgumentQueryStatement"
    ) -> tuple:
        """Render one function's arguments.

        ``RDB$FUNCTION_ARGUMENTS`` carries the type descriptor inline rather
        than through ``RDB$FIELD_SOURCE``, which is why this projection names
        the type columns directly instead of joining ``RDB$FIELDS``.
        """
        params = expr.get_params()
        return select_sql(
            self,
            [
                column(self, "RDB$ARGUMENT_POSITION", alias="ARGUMENT_POSITION"),
                column(self, "RDB$ARGUMENT_NAME", alias="ARGUMENT_NAME"),
                column(self, "RDB$MECHANISM", alias="MECHANISM"),
                column(self, "RDB$FIELD_TYPE", alias="FIELD_TYPE"),
                column(self, "RDB$FIELD_SUB_TYPE", alias="FIELD_SUB_TYPE"),
                column(self, "RDB$FIELD_LENGTH", alias="FIELD_LENGTH"),
                column(self, "RDB$CHARACTER_LENGTH", alias="CHARACTER_LENGTH"),
                column(self, "RDB$FIELD_PRECISION", alias="PRECISION"),
                column(self, "RDB$FIELD_SCALE", alias="SCALE"),
                column(self, "RDB$NULL_FLAG", alias="NULL_FLAG"),
                column(self, "RDB$DEFAULT_SOURCE", alias="DEFAULT_SOURCE"),
                column(self, "RDB$DESCRIPTION", alias="DESCRIPTION"),
            ],
            from_=relation(self, "RDB$FUNCTION_ARGUMENTS"),
            where=compare(
                self,
                "eq",
                column(self, "RDB$FUNCTION_NAME"),
                literal(self, params.get("function_name", "")),
            ),
            order_by=[column(self, "RDB$ARGUMENT_POSITION")],
        )

    def format_firebird_constraint_list_query_statement(
        self, expr: "FirebirdConstraintListQueryStatement"
    ) -> tuple:
        """Render constraints of every kind, with the CHECK predicate when any.

        ``RDB$RELATION_CONSTRAINTS`` states the constraint; the CHECK predicate
        is the source of the trigger ``RDB$CHECK_CONSTRAINTS`` points at, so
        the two reads are joined. Both joins are outer: a primary key has no
        check trigger, and an inner join would erase every constraint that is
        not a CHECK.

        ``RDB$RELATION_CONSTRAINTS`` has no system flag, so "system" here means
        a constraint on an ``RDB$`` relation -- the only reading the relation
        allows.
        """
        params = expr.get_params()
        source = join(
            self,
            join(
                self,
                relation(self, "RDB$RELATION_CONSTRAINTS", alias="rc"),
                relation(self, "RDB$CHECK_CONSTRAINTS", alias="cc"),
                condition=compare(
                    self,
                    "eq",
                    column(self, "RDB$CONSTRAINT_NAME", "cc"),
                    column(self, "RDB$CONSTRAINT_NAME", "rc"),
                ),
                join_type="LEFT JOIN",
            ),
            relation(self, "RDB$TRIGGERS", alias="t"),
            condition=compare(
                self,
                "eq",
                column(self, "RDB$TRIGGER_NAME", "t"),
                column(self, "RDB$TRIGGER_NAME", "cc"),
            ),
            join_type="LEFT JOIN",
        )

        conditions = []
        table_name = params.get("table_name")
        if table_name:
            conditions.append(
                compare(
                    self,
                    "eq",
                    column(self, "RDB$RELATION_NAME", "rc"),
                    literal(self, table_name),
                )
            )
        constraint_type = params.get("constraint_type")
        if constraint_type:
            conditions.append(
                compare(
                    self,
                    "eq",
                    column(self, "RDB$CONSTRAINT_TYPE", "rc"),
                    literal(self, constraint_type),
                )
            )
        if not params.get("include_system", False):
            conditions.append(
                like(
                    self,
                    column(self, "RDB$RELATION_NAME", "rc"),
                    "RDB$%",
                    negated=True,
                )
            )

        return select_sql(
            self,
            [
                column(self, "RDB$CONSTRAINT_NAME", "rc", alias="CONSTRAINT_NAME"),
                column(self, "RDB$CONSTRAINT_TYPE", "rc", alias="CONSTRAINT_TYPE"),
                column(self, "RDB$RELATION_NAME", "rc", alias="RELATION_NAME"),
                column(self, "RDB$DEFERRABLE", "rc", alias="DEFERRABLE"),
                column(self, "RDB$INITIALLY_DEFERRED", "rc", alias="INITIALLY_DEFERRED"),
                column(self, "RDB$INDEX_NAME", "rc", alias="INDEX_NAME"),
                column(self, "RDB$TRIGGER_NAME", "cc", alias="CHECK_TRIGGER"),
                column(self, "RDB$TRIGGER_SOURCE", "t", alias="CHECK_SOURCE"),
            ],
            from_=source,
            where=conjunction(self, *conditions) if conditions else None,
            order_by=[
                column(self, "RDB$RELATION_NAME", "rc"),
                column(self, "RDB$CONSTRAINT_NAME", "rc"),
            ],
        )

    def format_firebird_role_list_query_statement(
        self, expr: "FirebirdRoleListQueryStatement"
    ) -> tuple:
        """Render the role listing.

        ``RDB$SYSTEM_PRIVILEGES`` says whether the role carries system
        privileges, which is a different fact from owning ordinary grants and
        is not visible anywhere else.
        """
        params = expr.get_params()
        conditions = []
        if not params.get("include_system", False):
            conditions.append(
                compare(
                    self,
                    "eq",
                    column(self, "RDB$SYSTEM_FLAG"),
                    literal(self, 0, inline=True),
                )
            )
        return select_sql(
            self,
            [
                column(self, "RDB$ROLE_NAME", alias="ROLE_NAME"),
                column(self, "RDB$OWNER_NAME", alias="OWNER_NAME"),
                column(self, "RDB$SYSTEM_PRIVILEGES", alias="SYSTEM_PRIVILEGES"),
                column(self, "RDB$SYSTEM_FLAG", alias="SYSTEM_FLAG"),
                column(self, "RDB$DESCRIPTION", alias="DESCRIPTION"),
            ],
            from_=relation(self, "RDB$ROLES"),
            where=conjunction(self, *conditions) if conditions else None,
            order_by=[column(self, "RDB$ROLE_NAME")],
        )

    def format_firebird_privilege_query_statement(
        self, expr: "FirebirdPrivilegeQueryStatement"
    ) -> tuple:
        """Render grants, from ``RDB$USER_PRIVILEGES``.

        One relation holds both halves of ``GRANT``: SQL privileges on a
        relation, view or procedure, and system privileges, which Firebird 4
        records here with a ``$``-prefixed code. ``RDB$OBJECT_TYPE`` and
        ``RDB$USER_TYPE`` are what let a caller tell a grant on a table from a
        grant on a role.

        The default excludes grants on ``RDB$`` relations, because a fresh
        database already carries more than a thousand of them and they are not
        what "who may read this table" asks. Database-wide grants have a null
        relation and stay in the answer: they are user-facing even though they
        name no relation.
        """
        from rhosocial.activerecord.backend.expression import LogicalPredicate

        params = expr.get_params()
        conditions = []
        object_name = params.get("object_name")
        if object_name:
            conditions.append(
                compare(
                    self,
                    "eq",
                    column(self, "RDB$RELATION_NAME"),
                    literal(self, object_name),
                )
            )
        user_name = params.get("user_name")
        if user_name:
            conditions.append(
                compare(
                    self,
                    "eq",
                    column(self, "RDB$USER"),
                    literal(self, user_name),
                )
            )
        if not params.get("include_system", False):
            # The OR sits under the AND above, so the dialect brackets it:
            # "object = ? AND (relation IS NULL OR relation NOT LIKE 'RDB$%')".
            # The null branch is not optional -- a database-wide grant names no
            # relation, and "NOT LIKE" over NULL is unknown, which would drop
            # those rows.
            conditions.append(
                LogicalPredicate(
                    self,
                    "OR",
                    null_test(self, column(self, "RDB$RELATION_NAME")),
                    like(self, column(self, "RDB$RELATION_NAME"), "RDB$%", negated=True),
                )
            )
        return select_sql(
            self,
            [
                column(self, "RDB$USER", alias="GRANTEE"),
                column(self, "RDB$USER_TYPE", alias="GRANTEE_TYPE"),
                column(self, "RDB$GRANTOR", alias="GRANTOR"),
                column(self, "RDB$PRIVILEGE", alias="PRIVILEGE"),
                column(self, "RDB$GRANT_OPTION", alias="GRANT_OPTION"),
                column(self, "RDB$RELATION_NAME", alias="OBJECT_NAME"),
                column(self, "RDB$OBJECT_TYPE", alias="OBJECT_TYPE"),
                column(self, "RDB$FIELD_NAME", alias="FIELD_NAME"),
            ],
            from_=relation(self, "RDB$USER_PRIVILEGES"),
            where=conjunction(self, *conditions) if conditions else None,
            order_by=[
                column(self, "RDB$RELATION_NAME"),
                column(self, "RDB$USER"),
                column(self, "RDB$PRIVILEGE"),
            ],
        )

    def format_firebird_charset_list_query_statement(
        self, expr: "FirebirdCharsetListQueryStatement"
    ) -> tuple:
        """Render the character-set listing.

        No system filter: ``RDB$CHARACTER_SETS`` is almost entirely built-in
        sets, and a listing that hid them would answer nothing a caller wants.
        """
        return select_sql(
            self,
            [
                column(self, "RDB$CHARACTER_SET_NAME", alias="CHARACTER_SET_NAME"),
                column(self, "RDB$CHARACTER_SET_ID", alias="CHARACTER_SET_ID"),
                column(self, "RDB$FORM_OF_USE", alias="FORM_OF_USE"),
                column(self, "RDB$NUMBER_OF_CHARACTERS", alias="NUMBER_OF_CHARACTERS"),
                column(self, "RDB$BYTES_PER_CHARACTER", alias="BYTES_PER_CHARACTER"),
                column(self, "RDB$DEFAULT_COLLATE_NAME", alias="DEFAULT_COLLATION_NAME"),
                column(self, "RDB$FUNCTION_NAME", alias="FUNCTION_NAME"),
                column(self, "RDB$SYSTEM_FLAG", alias="SYSTEM_FLAG"),
                column(self, "RDB$DESCRIPTION", alias="DESCRIPTION"),
            ],
            from_=relation(self, "RDB$CHARACTER_SETS"),
            order_by=[column(self, "RDB$CHARACTER_SET_NAME")],
        )

    def format_firebird_collation_list_query_statement(
        self, expr: "FirebirdCollationListQueryStatement"
    ) -> tuple:
        """Render collations, with their character set's name.

        The relation only stores ``RDB$CHARACTER_SET_ID``; the name a caller
        recognises lives one join away, and an id alone would make the caller
        join it themselves.
        """
        params = expr.get_params()
        source = join(
            self,
            relation(self, "RDB$COLLATIONS", alias="c"),
            relation(self, "RDB$CHARACTER_SETS", alias="cs"),
            condition=compare(
                self,
                "eq",
                column(self, "RDB$CHARACTER_SET_ID", "c"),
                column(self, "RDB$CHARACTER_SET_ID", "cs"),
            ),
        )
        conditions = []
        charset_name = params.get("charset_name")
        if charset_name:
            conditions.append(
                compare(
                    self,
                    "eq",
                    column(self, "RDB$CHARACTER_SET_NAME", "cs"),
                    literal(self, charset_name),
                )
            )
        return select_sql(
            self,
            [
                column(self, "RDB$COLLATION_NAME", "c", alias="COLLATION_NAME"),
                column(self, "RDB$CHARACTER_SET_NAME", "cs", alias="CHARACTER_SET_NAME"),
                column(self, "RDB$COLLATION_ID", "c", alias="COLLATION_ID"),
                column(self, "RDB$BASE_COLLATION_NAME", "c", alias="BASE_COLLATION_NAME"),
                column(self, "RDB$SPECIFIC_ATTRIBUTES", "c", alias="SPECIFIC_ATTRIBUTES"),
                column(self, "RDB$FUNCTION_NAME", "c", alias="FUNCTION_NAME"),
                column(self, "RDB$SYSTEM_FLAG", "c", alias="SYSTEM_FLAG"),
                column(self, "RDB$DESCRIPTION", "c", alias="DESCRIPTION"),
            ],
            from_=source,
            where=conjunction(self, *conditions) if conditions else None,
            order_by=[column(self, "RDB$COLLATION_NAME", "c")],
        )

    def format_firebird_dependency_query_statement(
        self, expr: "FirebirdDependencyQueryStatement"
    ) -> tuple:
        """Render dependency edges, optionally narrowed to one object.

        The filter matches either end, because "what does this depend on" and
        "what depends on this" are the same table read in opposite directions,
        and a caller inspecting one object wants both.
        """
        from rhosocial.activerecord.backend.expression import LogicalPredicate

        params = expr.get_params()
        conditions = []
        object_name = params.get("object_name")
        if object_name:
            conditions.append(
                LogicalPredicate(
                    self,
                    "OR",
                    compare(
                        self,
                        "eq",
                        column(self, "RDB$DEPENDENT_NAME"),
                        literal(self, object_name),
                    ),
                    compare(
                        self,
                        "eq",
                        column(self, "RDB$DEPENDED_ON_NAME"),
                        literal(self, object_name),
                    ),
                )
            )
        return select_sql(
            self,
            [
                column(self, "RDB$DEPENDENT_NAME", alias="DEPENDENT_NAME"),
                column(self, "RDB$DEPENDENT_TYPE", alias="DEPENDENT_TYPE"),
                column(self, "RDB$DEPENDED_ON_NAME", alias="DEPENDED_ON_NAME"),
                column(self, "RDB$DEPENDED_ON_TYPE", alias="DEPENDED_ON_TYPE"),
                column(self, "RDB$FIELD_NAME", alias="FIELD_NAME"),
            ],
            from_=relation(self, "RDB$DEPENDENCIES"),
            where=conjunction(self, *conditions) if conditions else None,
            order_by=[
                column(self, "RDB$DEPENDENT_NAME"),
                column(self, "RDB$DEPENDED_ON_NAME"),
            ],
        )

    def format_firebird_view_relation_query_statement(
        self, expr: "FirebirdViewRelationQueryStatement"
    ) -> tuple:
        """Render the relations a view reads.

        ``RDB$VIEW_CONTEXT`` is the number the view's compiled ``BLR`` uses for
        that relation, and ``RDB$CONTEXT_NAME`` is the alias its ``SELECT``
        gave it -- neither is recoverable from ``RDB$VIEW_SOURCE`` once the
        text is written.
        """
        params = expr.get_params()
        conditions = []
        view_name = params.get("view_name")
        if view_name:
            conditions.append(
                compare(
                    self,
                    "eq",
                    column(self, "RDB$VIEW_NAME"),
                    literal(self, view_name),
                )
            )
        return select_sql(
            self,
            [
                column(self, "RDB$VIEW_NAME", alias="VIEW_NAME"),
                column(self, "RDB$RELATION_NAME", alias="RELATION_NAME"),
                column(self, "RDB$VIEW_CONTEXT", alias="VIEW_CONTEXT"),
                column(self, "RDB$CONTEXT_NAME", alias="CONTEXT_NAME"),
                column(self, "RDB$CONTEXT_TYPE", alias="CONTEXT_TYPE"),
            ],
            from_=relation(self, "RDB$VIEW_RELATIONS"),
            where=conjunction(self, *conditions) if conditions else None,
            order_by=[
                column(self, "RDB$VIEW_NAME"),
                column(self, "RDB$VIEW_CONTEXT"),
            ],
        )

    def format_firebird_publication_list_query_statement(
        self, expr: "FirebirdPublicationListQueryStatement"
    ) -> tuple:
        """Render the publication listing (Firebird 4 and later).

        The relation is absent on older servers, which the capability switch
        reports; the formatter is written once and does not branch on version.
        """
        params = expr.get_params()
        conditions = []
        if not params.get("include_system", False):
            conditions.append(
                compare(
                    self,
                    "eq",
                    column(self, "RDB$SYSTEM_FLAG"),
                    literal(self, 0, inline=True),
                )
            )
        return select_sql(
            self,
            [
                column(self, "RDB$PUBLICATION_NAME", alias="PUBLICATION_NAME"),
                column(self, "RDB$OWNER_NAME", alias="OWNER_NAME"),
                column(self, "RDB$ACTIVE_FLAG", alias="ACTIVE_FLAG"),
                column(self, "RDB$AUTO_ENABLE", alias="AUTO_ENABLE"),
                column(self, "RDB$SYSTEM_FLAG", alias="SYSTEM_FLAG"),
            ],
            from_=relation(self, "RDB$PUBLICATIONS"),
            where=conjunction(self, *conditions) if conditions else None,
            order_by=[column(self, "RDB$PUBLICATION_NAME")],
        )
