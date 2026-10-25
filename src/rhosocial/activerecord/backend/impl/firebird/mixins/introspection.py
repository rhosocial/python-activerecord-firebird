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

from typing import Optional, TYPE_CHECKING

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
        FirebirdDomainListQueryStatement,
        FirebirdGeneratorListQueryStatement,
        FirebirdGeneratorValueQueryStatement,
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
            [column(self, "RDB$RELATION_NAME"), column(self, "RDB$VIEW_BLR")],
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
                column(self, "RDB$POSITION", "rf", alias="POSITION"),
                column(self, "RDB$COMPUTED_SOURCE", "rf", alias="COMPUTED_SOURCE"),
            ],
            from_=joined,
            where=compare(
                self,
                "eq",
                column(self, "RDB$RELATION_NAME", "rf"),
                literal(self, table_name),
            ),
            order_by=[column(self, "RDB$POSITION", "rf")],
        )

    def format_index_info_query_statement(
        self, expr: "IndexInfoQueryStatement"
    ) -> tuple:
        """Render one relation's indexes with their key columns, in key order."""
        params = expr.get_params()
        self.reject_namespace(params.get("schema"))
        table_name = params.get("table_name", "")

        joined = join(
            self,
            relation(self, "RDB$INDICES", alias="i"),
            relation(self, "RDB$INDEX_SEGMENTS", alias="isg"),
            condition=compare(
                self,
                "eq",
                column(self, "RDB$INDEX_NAME", "i"),
                column(self, "RDB$INDEX_NAME", "isg"),
            ),
        )
        return select_sql(
            self,
            [
                column(self, "RDB$INDEX_NAME", "i", alias="INDEX_NAME"),
                column(self, "RDB$UNIQUE_FLAG", "i", alias="UNIQUE_FLAG"),
                column(self, "RDB$INDEX_INACTIVE", "i", alias="INACTIVE"),
                column(self, "RDB$INDEX_TYPE", "i", alias="INDEX_TYPE"),
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

        Six relation reads: the constraint and its referencing index, that
        index's own segments, the unique index the constraint points at and
        that index's segments, and finally the target relation itself. Each
        join is stated where it belongs rather than in one flat FROM list, so
        which relation reads to which is visible in the tree.
        """
        params = expr.get_params()
        self.reject_namespace(params.get("schema"))
        table_name = params.get("table_name", "")

        # seg reads the referencing index's columns; ref_seg the referenced
        # index's. Both join on an index name, so they are kept apart by the
        # distinct relations they hang from, not by name alone.
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
                            relation(self, "RDB$REF_CONSTRAINTS", alias="rc"),
                            relation(self, "RDB$INDEX_SEGMENTS", alias="seg"),
                            condition=compare(
                                self,
                                "eq",
                                column(self, "RDB$INDEX_NAME", "rc"),
                                column(self, "RDB$INDEX_NAME", "seg"),
                            ),
                        ),
                        relation(self, "RDB$INDICES", alias="i"),
                        condition=compare(
                            self,
                            "eq",
                            column(self, "RDB$INDEX_NAME", "rc"),
                            column(self, "RDB$INDEX_NAME", "i"),
                        ),
                    ),
                    relation(self, "RDB$INDEX_SEGMENTS", alias="ref_seg"),
                    condition=compare(
                        self,
                        "eq",
                        column(self, "RDB$CONSTRAINT_NAME_UQ", "rc"),
                        column(self, "RDB$INDEX_NAME", "ref_seg"),
                    ),
                ),
                relation(self, "RDB$INDICES", alias="ref_i"),
                condition=compare(
                    self,
                    "eq",
                    column(self, "RDB$CONSTRAINT_NAME_UQ", "rc"),
                    column(self, "RDB$INDEX_NAME", "ref_i"),
                ),
            ),
            relation(self, "RDB$RELATIONS", alias="ref"),
            condition=compare(
                self,
                "eq",
                column(self, "RDB$RELATION_NAME", "ref_i"),
                column(self, "RDB$RELATION_NAME", "ref"),
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
                column(self, "RDB$DELETE_RULE", "rc", alias="DELETE_RULE"),
            ],
            from_=joined,
            where=compare(
                self,
                "eq",
                column(self, "RDB$RELATION_NAME", "i"),
                literal(self, table_name),
            ),
            order_by=[column(self, "RDB$FIELD_POSITION", "seg")],
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
