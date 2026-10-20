# src/rhosocial/activerecord/backend/impl/firebird/mixins/introspection.py
"""Firebird schema introspection mixin.

The ``INTROSPECTION_QUERIES`` mapping below used to hold six hand-written
``SELECT`` statements -- f-strings around ``self.p()`` for the two that take a
relation name, plain text for the rest. A SQL string is a formatting artefact,
so it belongs to the dialect formatter, not to a dict beside the dialect (org
guide §16.2). Each entry is now a ``QueryStatement`` over the same ``RDB$``
relations and is rendered by this dialect when the mapping is read, so the
mapping is a set of *questions* rather than a set of statements.

The execution path proper lives in ``introspection/async_introspector.py``,
which builds the same shapes from the same nodes; this mapping is kept as the
dialect-level view of them (it names the keys, not the SQL).
"""


class FirebirdIntrospectionMixin:
    """Dialect-level introspection query mapping, built from nodes."""

    @property
    def INTROSPECTION_QUERIES(self):
        """Render the six catalogue queries this backend names.

        Each value is a ``(sql, params)`` pair from the dialect's own
        formatter, so nothing here spells SQL. This property is recomputed
        per access: the dialect's version can be adapted after construction
        (``introspect_and_adapt``), and a cached mapping would then answer for
        the old one.

        The two queries that are filtered by a relation name have no such
        filter here on purpose: this is the *shape* view, and a name is data
        the caller supplies. The introspector builds the filtered form from
        the same nodes and binds the actual name (``introspection/
        async_introspector.py``); inventing a placeholder value here would put
        a bind marker in the text with nothing to bind it.
        """
        from ..query_nodes import (
            column,
            compare,
            join,
            literal,
            null_test,
            relation,
            select_sql,
        )

        return {
            "tables": select_sql(
                self,
                [
                    column(self, "RDB$RELATION_NAME", alias="TABLE_NAME"),
                    column(self, "RDB$VIEW_SOURCE", alias="VIEW_SOURCE"),
                    column(self, "RDB$SYSTEM_FLAG", alias="SYSTEM_FLAG"),
                ],
                from_=relation(self, "RDB$RELATIONS"),
                where=compare(
                    self, "eq", column(self, "RDB$SYSTEM_FLAG"), literal(self, 0, inline=True)
                ),
                order_by=[column(self, "RDB$RELATION_NAME")],
            ),
            "columns": select_sql(
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
                from_=join(
                    self,
                    relation(self, "RDB$RELATION_FIELDS", alias="rf"),
                    relation(self, "RDB$FIELDS", alias="f"),
                    condition=compare(
                        self,
                        "eq",
                        column(self, "RDB$FIELD_SOURCE", "rf"),
                        column(self, "RDB$FIELD_NAME", "f"),
                    ),
                ),
                order_by=[column(self, "RDB$POSITION", "rf")],
            ),
            "indices": select_sql(
                self,
                [
                    column(self, "RDB$INDEX_NAME", "i", alias="INDEX_NAME"),
                    column(self, "RDB$UNIQUE_FLAG", "i", alias="UNIQUE_FLAG"),
                    column(self, "RDB$INDEX_TYPE", "i", alias="INDEX_TYPE"),
                    column(self, "RDB$INDEX_INACTIVE", "i", alias="INACTIVE"),
                    column(self, "RDB$FIELD_NAME", "isg", alias="FIELD_NAME"),
                    column(self, "RDB$FIELD_POSITION", "isg", alias="FIELD_POSITION"),
                ],
                from_=join(
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
                order_by=[
                    column(self, "RDB$INDEX_NAME", "i"),
                    column(self, "RDB$FIELD_POSITION", "isg"),
                ],
            ),
            "triggers": select_sql(
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
                where=null_test(self, column(self, "RDB$RELATION_NAME"), is_not=True),
                order_by=[column(self, "RDB$TRIGGER_NAME")],
            ),
            "generators": select_sql(
                self,
                [
                    column(self, "RDB$GENERATOR_NAME", alias="GENERATOR_NAME"),
                    column(self, "RDB$GENERATOR_ID", alias="GENERATOR_ID"),
                    column(self, "RDB$SYSTEM_FLAG", alias="SYSTEM_FLAG"),
                ],
                from_=relation(self, "RDB$GENERATORS"),
                where=compare(
                    self, "eq", column(self, "RDB$SYSTEM_FLAG"), literal(self, 0, inline=True)
                ),
                order_by=[column(self, "RDB$GENERATOR_NAME")],
            ),
            "procedures": select_sql(
                self,
                [
                    column(self, "RDB$PROCEDURE_NAME", alias="PROCEDURE_NAME"),
                    column(self, "RDB$PROCEDURE_INPUTS", alias="INPUT_PARAMS"),
                    column(self, "RDB$PROCEDURE_OUTPUTS", alias="OUTPUT_PARAMS"),
                    column(self, "RDB$PROCEDURE_SOURCE", alias="SOURCE"),
                ],
                from_=relation(self, "RDB$PROCEDURES"),
                where=compare(
                    self, "eq", column(self, "RDB$SYSTEM_FLAG"), literal(self, 0, inline=True)
                ),
                order_by=[column(self, "RDB$PROCEDURE_NAME")],
            ),
        }
