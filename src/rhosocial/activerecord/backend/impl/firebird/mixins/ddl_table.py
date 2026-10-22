# src/rhosocial/activerecord/backend/impl/firebird/mixins/ddl_table.py
"""Firebird table DDL mixin.

Every relation name this mixin emits -- ``CREATE TABLE``, ``REFERENCES``,
``ALTER TABLE`` -- is rendered from the :class:`Table` object the statement
holds, so a name that carries a namespace slot is reported instead of quietly
reaching the parser, which has no qualified-name syntax.
"""

from typing import Any, List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.expression.statements import (
        AlterTableStatement,
        ColumnDefinition,
        CreateTableStatement,
    )

from rhosocial.activerecord.backend.dialect.mixins.ddl_table import TableMixin
from rhosocial.activerecord.backend.expression.objects import Table

from .version_boundaries import _norm_version


class FirebirdTableMixin:

    # -- Cascade capability switches (declared on the dialect, Ref to DropTableSupport protocol)

    def supports_create_table_as(self) -> bool:
        """Whether ``CREATE TABLE ... AS <query>`` (CTAS) is supported.

        Measured on the two live servers: 5.0.4 answers ``Token unknown -
        AS`` for both ``CREATE TABLE t AS (SELECT ...)`` and ``CREATE TABLE t
        AS SELECT ...``; 6.0.0 creates the table, populates it, and accepts
        ``WITH DATA`` / ``WITH NO DATA`` on it. The gate is therefore the
        version the measurement found, not a flat answer.
        """
        return _norm_version(self.version) >= (6, 0, 0)

    def supports_with_data_clause(self) -> bool:
        """Whether the ``WITH [NO] DATA`` population clause is supported.

        The clause is shared by CTAS, CREATE MATERIALIZED VIEW and REFRESH
        MATERIALIZED VIEW. Firebird's only carrier is the 6.0.0 CTAS (measured:
        bare CTAS populates one row; ``WITH DATA`` populates one row; ``WITH NO
        DATA`` creates an empty table). 5.0.4 has no CTAS at all, and no
        Firebird version has materialized views, so the clause answers with the
        same version gate as the CTAS statement.
        """
        return _norm_version(self.version) >= (6, 0, 0)

    def supports_drop_table_cascade(self) -> bool:
        """Firebird has no CASCADE keyword on DROP TABLE."""
        return False

    def supports_drop_table_restrict(self) -> bool:
        """Firebird has no RESTRICT keyword on DROP TABLE."""
        return False

    # Delegate to TableMixin for DropTableStatement formatting.
    # FirebirdDialect's MRO resolves DropTableSupport.format_drop_table_statement
    # (the empty Protocol stub) before TableMixin's actual implementation due to
    # Python's C3 linearization. Re-binding the concrete method here ensures the
    # MRO picks up the TypeScript-level override.
    format_drop_table_statement = TableMixin.format_drop_table_statement

    def format_alter_table_statement(self, expr: "AlterTableStatement") -> Tuple[str, tuple]:
        """Render ALTER TABLE, naming the relation through a schema object.

        Firebird's ALTER TABLE grammar has no table name inside an action, so
        the relation is named once here and each action -- including the
        Firebird-only ``ALTER COLUMN "X" SET GENERATED ...`` fragments from
        ``FirebirdAlterTableModifierMixin``, which are action text without a
        table -- is appended after it.

        The action-combination rule is the core's: one comma-separated statement
        when ``supports_multi_action_alter_table()``, otherwise one statement
        per action joined by ``;``. What changes here is only where the table
        name comes from: a :class:`Table` schema object rather than a bare
        ``format_identifier``, so a name carrying a namespace slot is reported.

        Raises:
            TypeError: ``AlterTableStatement.table`` is not a Table. Another
                object kind would have had its own name rendered as the relation
                being altered.
        """
        if not isinstance(expr.table, Table):
            raise TypeError(
                f"AlterTableStatement.table must be a Table, "
                f"got {type(expr.table).__name__}"
            )
        all_params: List[Any] = []
        action_parts: List[str] = []
        for action in expr.actions:
            action_sql, action_params = action.to_sql()
            action_parts.append(action_sql)
            all_params.extend(action_params)

        table_sql, _ = expr.table.to_sql()
        if not action_parts:
            return f"ALTER TABLE {table_sql}", ()

        if self.supports_multi_action_alter_table():
            return f"ALTER TABLE {table_sql} {', '.join(action_parts)}", tuple(all_params)
        return "; ".join(
            f"ALTER TABLE {table_sql} {part}" for part in action_parts
        ), tuple(all_params)

    def format_create_table_statement(self, expr: "CreateTableStatement") -> Tuple[str, tuple]:
        """Render CREATE TABLE, naming the relation through a schema object.

        Raises:
            TypeError: ``CreateTableStatement.table`` is not a Table. A view or a
                sequence would have had its own name rendered as the relation
                being created.
            UnsupportedFeatureError: A Firebird-unreadable clause was requested --
                TABLESPACE, INHERITS, PARTITION BY, an inline comment, or
                IF NOT EXISTS, which Firebird has no syntax for.
        """
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

        if not isinstance(expr.table, Table):
            raise TypeError(
                f"CreateTableStatement.table must be a Table, "
                f"got {type(expr.table).__name__}"
            )
        if expr.tablespace:
            raise UnsupportedFeatureError(
                self.name,
                "TABLESPACE",
                "Firebird does not support table tablespaces.",
            )
        if expr.inherits:
            raise UnsupportedFeatureError(
                self.name,
                "table INHERITS",
                "Firebird does not support table inheritance.",
            )
        if expr.partition is not None:
            raise UnsupportedFeatureError(
                self.name,
                "PARTITION BY clause",
                "Firebird does not support table partitioning.",
            )
        if expr.table_options is not None and expr.table_options.comment:
            # Firebird annotates comments through the standalone
            # COMMENT ON statement (no inline table option); a comment on the
            # table options is never silently dropped.
            from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
            raise UnsupportedFeatureError(
                self.name,
                "TABLE COMMENT",
                "Firebird has no inline table comment; use a standalone "
                "COMMENT ON TABLE statement.",
            )

        all_params: List[Any] = []

        parts = []
        if expr.temporary:
            # Legal Firebird word order is CREATE GLOBAL TEMPORARY TABLE;
            # "CREATE TABLE GLOBAL TEMPORARY" is rejected by the parser.
            parts.append("CREATE GLOBAL TEMPORARY TABLE")
        else:
            parts.append("CREATE TABLE")
        if expr.if_not_exists:
            # Capability gate: Firebird has no IF NOT EXISTS on CREATE TABLE,
            # so rendering it anyway would produce broken DDL.
            if not self.supports_if_not_exists_table():
                from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
                raise UnsupportedFeatureError(
                    self.name,
                    "IF NOT EXISTS on CREATE TABLE",
                    "Firebird does not support IF NOT EXISTS for tables.",
                )
            parts.append("IF NOT EXISTS")
        # ``expr.table`` is the Table object itself, not a flat string, and it
        # renders itself -- so a namespace slot it carries is reported by the
        # object layer rather than dropped here.
        parts.append(expr.table.to_sql()[0])

        if expr.temporary:
            # ``on_commit_delete`` is FirebirdCreateTableStatement's field --
            # the generic statement has no such clause, and omitting it is the
            # server's own default (ON COMMIT DELETE ROWS). The kind decides
            # whether the question exists, then the field is read.
            from rhosocial.activerecord.backend.impl.firebird.expression.create_table import (
                FirebirdCreateTableStatement,
            )

            if isinstance(expr, FirebirdCreateTableStatement):
                if expr.on_commit_delete:
                    parts.append("ON COMMIT DELETE ROWS")
                else:
                    parts.append("ON COMMIT PRESERVE ROWS")

        column_parts = []
        for col_def in expr.columns:
            col_sql, col_params = self.format_column_definition(col_def)
            column_parts.append(col_sql)
            all_params.extend(col_params)

        for t_const in expr.table_constraints:
            const_sql, const_params = self.format_table_constraint(t_const)
            column_parts.append(const_sql)
            all_params.extend(const_params)

        parts.append(f"({', '.join(column_parts)})")

        # ``external_file`` is FirebirdCreateTableStatement's field; the
        # generic statement declares no such clause, so the kind decides
        # whether the question exists, then the field is read.
        from rhosocial.activerecord.backend.impl.firebird.expression.create_table import (
            FirebirdCreateTableStatement,
        )

        if isinstance(expr, FirebirdCreateTableStatement) and expr.external_file:
            parts.append(f"EXTERNAL FILE '{expr.external_file}'")

        return ' '.join(parts), tuple(all_params)

    def format_column_definition(self, col_def: "ColumnDefinition") -> Tuple[str, tuple]:
        """Format a single column definition with Firebird-specific syntax.

        Accepts both the generic ``ColumnDefinition`` and the Firebird
        ``FirebirdColumnDefinition``; the latter's Firebird-only attributes
        (``computed_by`` / ``character_set`` / ``collation``) are rendered here.

        Each constraint is dispatched on its **branch class** rather than on a
        ``constraint_type`` tag: the two-level nodes name the kind in a class
        now, so the renderer reads the same thing it did before without the
        enum. The spellings this method emits are unchanged -- the branch split
        is a shape change, not a rendering change.
        """
        from rhosocial.activerecord.backend.expression.statements import (
            ColumnDefaultConstraint,
            ColumnGeneratedConstraint,
            ColumnPrimaryKeyConstraint,
        )
        from rhosocial.activerecord.backend.impl.firebird.expression.column import (
            FirebirdColumnDefinition,
        )

        if col_def.comment is not None:
            # Firebird annotates column comments through the standalone
            # COMMENT ON COLUMN statement (no inline column clause); a comment
            # on a column definition is never silently dropped.
            from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
            raise UnsupportedFeatureError(
                self.name, "COLUMN COMMENT",
                "Firebird has no inline column comment; use a standalone "
                "COMMENT ON COLUMN statement.",
            )

        type_sql, _ = col_def.data_type.to_sql()
        parts = [self.format_identifier(col_def.name), type_sql]
        params: List[Any] = []

        for constraint in col_def.constraints:
            # The flag lives on the branch now: ``is_auto_increment`` is
            # specific to PRIMARY KEY, so it is part of that alternative rather
            # than of the production. The branch's class decides whether the
            # question exists, then the field is read.
            if (
                isinstance(constraint.branch, ColumnPrimaryKeyConstraint)
                and constraint.branch.is_auto_increment
            ):
                parts.append("GENERATED BY DEFAULT AS IDENTITY")
                break

        attr_sql, attr_params = self.format_column_attributes(col_def)
        if attr_sql:
            parts.append(attr_sql.strip())
        params.extend(attr_params)

        if isinstance(col_def, FirebirdColumnDefinition) and col_def.character_set:
            parts.append(f"CHARACTER SET {col_def.character_set}")

        # ``computed_by`` is FirebirdColumnDefinition's field; the generic
        # column definition declares no such clause, so the kind decides
        # whether the question exists, then the field is read.
        if isinstance(col_def, FirebirdColumnDefinition) and col_def.computed_by:
            parts.append(f"COMPUTED BY ({col_def.computed_by})")
        else:
            # A generic ColumnGeneratedConstraint maps onto Firebird's
            # ``COMPUTED BY (<expr>)`` form (Firebird has no GENERATED ALWAYS
            # syntax); a declared generated column is never silently dropped.
            generated = col_def.generated_expression
            if generated is not None:
                gen_sql, gen_params = generated.expression.to_sql()
                parts.append(f"COMPUTED BY ({gen_sql})")
                params.extend(gen_params)

        constraint_parts = []
        default_parts: List[str] = []
        for constraint in col_def.constraints:
            branch = constraint.branch
            if isinstance(branch, ColumnDefaultConstraint):
                # ``DEFAULT`` is rendered through its own branch value rather
                # than through the constraint clause, because Firebird requires
                # the DEFAULT clause to follow the data type directly -- it must
                # be emitted *before* NOT NULL / UNIQUE (see below), which is
                # the one place this backend's column order differs from the
                # core's ``format_column_definition``.
                if branch.value is not None:
                    from rhosocial.activerecord.backend.expression import bases
                    if isinstance(branch.value, bases.BaseExpression):
                        default_sql, default_params = branch.value.to_sql()
                        default_parts.append(f"DEFAULT {default_sql}")
                        params.extend(default_params)
                    else:
                        default_parts.append(f"DEFAULT {self.inline_sql_literal(branch.value)}")
                continue
            # A generated column is Firebird's ``COMPUTED BY (<expr>)`` and has
            # no ``GENERATED ALWAYS AS`` spelling at all, so a
            # ``ColumnGeneratedConstraint`` that arrives through the constraint
            # list (the ``generated_expression`` channel is handled above) must
            # not be delegated to core's ``GENERATED ALWAYS`` renderer.
            if isinstance(branch, ColumnGeneratedConstraint):
                gen_sql, gen_params = branch.expression.to_sql()
                constraint_parts.append(f"COMPUTED BY ({gen_sql})")
                params.extend(gen_params)
                continue
            # Everything else -- PRIMARY KEY, UNIQUE, NOT NULL, NULL, CHECK,
            # REFERENCES, a generated column -- is rendered by the shared
            # ``format_column_constraint``, which owns the production-level
            # ``CONSTRAINT <name>`` prefix and the branch dispatch. Routing them
            # through it rather than re-spelling each kind here is what keeps a
            # branch from being *silently dropped* when this list was incomplete:
            # before this change a column-level CHECK and a column-level
            # ``REFERENCES`` produced no SQL at all on this backend.
            suffix, suffix_params = self.format_column_constraint(constraint)
            constraint_parts.append(suffix.strip())
            params.extend(suffix_params)

        # Firebird requires the DEFAULT clause to follow the data type directly;
        # it must be emitted before column constraints such as NOT NULL/UNIQUE,
        # otherwise the parser rejects the column definition with a
        # "Token unknown ... DEFAULT" error.
        constraint_parts = default_parts + constraint_parts

        if constraint_parts:
            parts.append(' '.join(constraint_parts))

        # ``collation`` is FirebirdColumnDefinition's field; the generic column
        # definition declares no such clause, so the kind decides whether the
        # question exists, then the field is read.
        if isinstance(col_def, FirebirdColumnDefinition) and col_def.collation:
            parts.append(f"COLLATE {col_def.collation}")

        return ' '.join(parts), tuple(params)

    def supports_computed_by(self) -> bool:
        return True

    def supports_external_file(self) -> bool:
        return True