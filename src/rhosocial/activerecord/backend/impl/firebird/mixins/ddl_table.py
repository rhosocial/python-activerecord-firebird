# src/rhosocial/activerecord/backend/impl/firebird/mixins/table.py
"""Firebird table DDL mixin."""

from typing import Any, List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.expression.statements import (
        ColumnDefinition,
        CreateTableExpression,
        TableConstraint,
    )

from rhosocial.activerecord.backend.dialect.mixins.ddl_table import TableMixin


class FirebirdTableMixin:

    # -- Cascade capability switches (declared on the dialect, Ref to TableSupport protocol)

    def supports_drop_table_cascade(self) -> bool:
        """Firebird has no CASCADE keyword on DROP TABLE."""
        return False

    def supports_drop_table_restrict(self) -> bool:
        """Firebird has no RESTRICT keyword on DROP TABLE."""
        return False

    # Delegate to TableMixin for DropTableExpression formatting.
    # FirebirdDialect's MRO resolves TableSupport.format_drop_table_statement
    # (the empty Protocol stub) before TableMixin's actual implementation due to
    # Python's C3 linearization. Re-binding the concrete method here ensures the
    # MRO picks up the TypeScript-level override.
    format_drop_table_statement = TableMixin.format_drop_table_statement
    # format_drop_table_statement = TableMixin.__dict__['format_drop_table_statement']

    # Same C3 linearization issue applies to ALTER TABLE: TableSupport ships an
    # empty format_alter_table_statement stub that would otherwise win over the
    # concrete TableMixin implementation, so re-bind it here as well.
    format_alter_table_statement = TableMixin.format_alter_table_statement

    def format_create_table_statement(self, expr: "CreateTableExpression") -> Tuple[str, tuple]:
        if getattr(expr, 'partition', None) is not None:
            from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
            raise UnsupportedFeatureError(
                self.name,
                "PARTITION BY clause",
                "Firebird does not support table partitioning.",
            )
        if getattr(getattr(expr, 'table_options', None), 'comment', None):
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
        if getattr(expr, 'temporary', False):
            # Legal Firebird word order is CREATE GLOBAL TEMPORARY TABLE;
            # "CREATE TABLE GLOBAL TEMPORARY" is rejected by the parser.
            parts.append("CREATE GLOBAL TEMPORARY TABLE")
        else:
            parts.append("CREATE TABLE")
        if getattr(expr, 'if_not_exists', False):
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
        parts.append(self.format_identifier(expr.table_name))

        if getattr(expr, 'temporary', False):
            on_commit = getattr(expr, 'on_commit_delete', True)
            if on_commit:
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

        external_file = getattr(expr, 'external_file', None)
        if external_file:
            parts.append(f"EXTERNAL FILE '{external_file}'")

        return ' '.join(parts), tuple(all_params)

    def format_column_definition(self, col_def: "ColumnDefinition") -> Tuple[str, tuple]:
        """Format a single column definition with Firebird-specific syntax.

        Accepts both the generic ``ColumnDefinition`` and the Firebird
        ``FirebirdColumnDefinition``; the latter's Firebird-only attributes
        (``computed_by`` / ``character_set`` / ``collation``) are rendered here.
        """
        from rhosocial.activerecord.backend.expression.statements import ColumnConstraintType
        from rhosocial.activerecord.backend.impl.firebird.expression.column import (
            FirebirdColumnDefinition,
        )

        if getattr(col_def, "comment", None):
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
            if getattr(constraint, 'is_auto_increment', False):
                parts.append("GENERATED BY DEFAULT AS IDENTITY")
                break

        attr_sql, attr_params = self.format_column_attributes(col_def)
        if attr_sql:
            parts.append(attr_sql.strip())
        params.extend(attr_params)

        if isinstance(col_def, FirebirdColumnDefinition) and col_def.character_set:
            parts.append(f"CHARACTER SET {col_def.character_set}")

        computed_by = getattr(col_def, 'computed_by', None)
        if computed_by:
            parts.append(f"COMPUTED BY ({computed_by})")
        else:
            # A generic GeneratedColumnExpression maps onto Firebird's
            # ``COMPUTED BY (<expr>)`` form (Firebird has no GENERATED ALWAYS
            # syntax); a declared generated column is never silently dropped.
            generated = getattr(col_def, 'generated_expression', None)
            if generated is not None:
                gen_sql, gen_params = generated.expression.to_sql()
                parts.append(f"COMPUTED BY ({gen_sql})")
                params.extend(gen_params)

        constraint_parts = []
        default_parts: List[str] = []
        for constraint in col_def.constraints:
            if constraint.constraint_type == ColumnConstraintType.PRIMARY_KEY:
                constraint_parts.append("PRIMARY KEY")
            elif constraint.constraint_type == ColumnConstraintType.NOT_NULL:
                constraint_parts.append("NOT NULL")
            elif constraint.constraint_type == ColumnConstraintType.UNIQUE:
                constraint_parts.append("UNIQUE")
            elif constraint.constraint_type == ColumnConstraintType.NULL:
                constraint_parts.append("NULL")
            elif constraint.constraint_type == ColumnConstraintType.DEFAULT:
                if constraint.default_value is not None:
                    from rhosocial.activerecord.backend.expression import bases
                    if isinstance(constraint.default_value, bases.BaseExpression):
                        default_sql, default_params = constraint.default_value.to_sql()
                        default_parts.append(f"DEFAULT {default_sql}")
                        params.extend(default_params)
                    else:
                        default_parts.append(f"DEFAULT {self.inline_sql_literal(constraint.default_value)}")

        # Firebird requires the DEFAULT clause to follow the data type directly;
        # it must be emitted before column constraints such as NOT NULL/UNIQUE,
        # otherwise the parser rejects the column definition with a
        # "Token unknown ... DEFAULT" error.
        constraint_parts = default_parts + constraint_parts

        if constraint_parts:
            parts.append(' '.join(constraint_parts))

        collation = getattr(col_def, 'collation', None)
        if collation:
            parts.append(f"COLLATE {collation}")

        return ' '.join(parts), tuple(params)

    def format_table_constraint(self, expr: "TableConstraint") -> Tuple[str, tuple]:
        from rhosocial.activerecord.backend.expression.statements import (
            ForeignKeyConstraint,
            ReferentialAction,
            TableConstraintType,
        )
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

        if getattr(expr, "deferrable", None) is not None:
            raise UnsupportedFeatureError(
                self.name, "DEFERRABLE constraint",
                "Firebird does not support deferrable constraints.",
            )
        if isinstance(expr, ForeignKeyConstraint) and getattr(expr, "match_type", None) is not None:
            raise UnsupportedFeatureError(
                self.name, "FOREIGN KEY MATCH",
                "Firebird does not support FOREIGN KEY MATCH.",
            )

        parts = []
        params: List[Any] = []

        if expr.name:
            parts.append(f"CONSTRAINT {self.format_identifier(expr.name)}")

        if expr.constraint_type == TableConstraintType.PRIMARY_KEY:
            if expr.columns:
                cols = ', '.join(self.format_identifier(c) for c in expr.columns)
                parts.append(f"PRIMARY KEY ({cols})")
        elif expr.constraint_type == TableConstraintType.UNIQUE:
            if expr.columns:
                cols = ', '.join(self.format_identifier(c) for c in expr.columns)
                parts.append(f"UNIQUE ({cols})")
        elif expr.constraint_type == TableConstraintType.FOREIGN_KEY:
            if expr.columns and expr.foreign_key_table and expr.foreign_key_columns:
                cols = ', '.join(self.format_identifier(c) for c in expr.columns)
                ref_cols = ', '.join(self.format_identifier(c) for c in expr.foreign_key_columns)
                ref_table = self.format_identifier(expr.foreign_key_table)
                parts.append(f"FOREIGN KEY ({cols}) REFERENCES {ref_table} ({ref_cols})")
            if isinstance(expr, ForeignKeyConstraint):
                if expr.on_delete != ReferentialAction.NO_ACTION:
                    parts.append(f"ON DELETE {expr.on_delete.value}")
                if expr.on_update != ReferentialAction.NO_ACTION:
                    parts.append(f"ON UPDATE {expr.on_update.value}")
        elif expr.constraint_type == TableConstraintType.CHECK and expr.check_condition:
            check_sql, check_params = expr.check_condition.to_sql()
            parts.append(f"CHECK ({check_sql})")
            params.extend(check_params)

        return ' '.join(parts), tuple(params)

    def supports_computed_by(self) -> bool:
        return True

    def supports_identity_columns(self) -> bool:
        return True

    def supports_external_file(self) -> bool:
        return True