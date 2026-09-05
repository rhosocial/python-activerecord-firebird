# src/rhosocial/activerecord/backend/impl/firebird/mixins/table.py
"""Firebird table DDL mixin."""

from typing import Any, List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    pass  # noinspection PyUnresolvedReferences

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

    def format_create_table_statement(self, expr) -> Tuple[str, tuple]:
        if getattr(expr, 'partition', None) is not None:
            from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
            raise UnsupportedFeatureError(
                self.name,
                "PARTITION BY clause",
                "Firebird does not support table partitioning.",
            )

        all_params: List[Any] = []
        # Firebird has no IF NOT EXISTS on CREATE TABLE. When requested, the
        # complete statement is wrapped at the end in an EXECUTE BLOCK
        # existence guard over RDB$RELATIONS so repeated creation is
        # idempotent. Only applied when the statement carries no bind
        # parameters (the DDL becomes dynamic SQL).
        apply_exists_guard = (
            getattr(expr, 'if_not_exists', False)
            and not getattr(expr, 'temporary', False)
            and not self.supports_if_not_exists_table()
        )

        parts = []
        if getattr(expr, 'temporary', False):
            # Legal Firebird word order is CREATE GLOBAL TEMPORARY TABLE;
            # "CREATE TABLE GLOBAL TEMPORARY" is rejected by the parser.
            parts.append("CREATE GLOBAL TEMPORARY TABLE")
        else:
            parts.append("CREATE TABLE")
        if getattr(expr, 'if_not_exists', False) and not apply_exists_guard:
            parts.append("IF NOT EXISTS")
        parts.append(expr.table.to_sql()[0])

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

        statement = ' '.join(parts)

        if apply_exists_guard:
            if all_params:
                from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
                raise UnsupportedFeatureError(
                    self.name,
                    "IF NOT EXISTS on CREATE TABLE",
                    "Firebird does not support IF NOT EXISTS for tables; "
                    "the existence guard requires a parameter-free statement.",
                )
            # EXECUTE BLOCK existence guard. RDB$RELATION_NAME is CHAR(31)
            # space-padded, hence TRIM. Internal single quotes are doubled
            # because the DDL becomes dynamic SQL via EXECUTE STATEMENT.
            # PSQL quirk: DECLARE VARIABLE sits between AS and BEGIN, and
            # EXISTS is not a valid IF condition — hence the COUNT(*) form.
            embedded = statement.replace("'", "''")
            table_upper = expr.table.name.upper()
            statement = (
                "EXECUTE BLOCK AS DECLARE VARIABLE CNT INTEGER; BEGIN "
                f"SELECT COUNT(*) FROM RDB$RELATIONS "
                f"WHERE TRIM(RDB$RELATION_NAME) = '{table_upper}' INTO :CNT; "
                "IF (:CNT = 0) THEN "
                f"EXECUTE STATEMENT '{embedded}'; END"
            )

        return statement, tuple(all_params)

    def format_column_definition(self, col_def) -> Tuple[str, List[Any]]:
        from rhosocial.activerecord.backend.expression.statements import ColumnConstraintType

        type_sql, _ = col_def.data_type.to_sql(self)
        parts = [self.format_identifier(col_def.name), type_sql]
        params: List[Any] = []

        # Auto-increment via constraint flag (cross-dialect convention)
        for constraint in col_def.constraints:
            if getattr(constraint, 'is_auto_increment', False):
                parts.append("GENERATED BY DEFAULT AS IDENTITY")
                break

        if getattr(col_def, 'identity', False):
            generated = getattr(col_def, 'identity_generated', 'BY DEFAULT')
            parts.append(f"GENERATED {generated} AS IDENTITY")
            start = getattr(col_def, 'identity_start', None)
            increment = getattr(col_def, 'identity_increment', None)
            if start is not None or increment is not None:
                id_parts = []
                if start is not None:
                    id_parts.append(f"START WITH {start}")
                if increment is not None:
                    id_parts.append(f"INCREMENT BY {increment}")
                parts.append(f"({' '.join(id_parts)})")

        computed_by = getattr(col_def, 'computed_by', None)
        if computed_by:
            parts.append(f"COMPUTED BY ({computed_by})")

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
                    elif isinstance(constraint.default_value, str):
                        escaped = constraint.default_value.replace("'", "''")
                        default_parts.append(f"DEFAULT '{escaped}'")
                    else:
                        default_parts.append(f"DEFAULT {constraint.default_value}")

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

    def format_table_constraint(self, t_const) -> Tuple[str, List[Any]]:
        from rhosocial.activerecord.backend.expression.statements import (
            ForeignKeyConstraint,
            ReferentialAction,
            TableConstraintType,
        )

        parts = []
        params: List[Any] = []

        if t_const.name:
            parts.append(f"CONSTRAINT {self.format_identifier(t_const.name)}")

        if t_const.constraint_type == TableConstraintType.PRIMARY_KEY:
            if t_const.columns:
                cols = ', '.join(self.format_identifier(c) for c in t_const.columns)
                parts.append(f"PRIMARY KEY ({cols})")
        elif t_const.constraint_type == TableConstraintType.UNIQUE:
            if t_const.columns:
                cols = ', '.join(self.format_identifier(c) for c in t_const.columns)
                parts.append(f"UNIQUE ({cols})")
        elif t_const.constraint_type == TableConstraintType.FOREIGN_KEY:
            if t_const.columns and t_const.foreign_key_table and t_const.foreign_key_columns:
                cols = ', '.join(self.format_identifier(c) for c in t_const.columns)
                ref_cols = ', '.join(self.format_identifier(c) for c in t_const.foreign_key_columns)
                ref_table = self.format_identifier(t_const.foreign_key_table)
                parts.append(f"FOREIGN KEY ({cols}) REFERENCES {ref_table} ({ref_cols})")
            if isinstance(t_const, ForeignKeyConstraint):
                if t_const.on_delete != ReferentialAction.NO_ACTION:
                    parts.append(f"ON DELETE {t_const.on_delete.value}")
                if t_const.on_update != ReferentialAction.NO_ACTION:
                    parts.append(f"ON UPDATE {t_const.on_update.value}")
        elif t_const.constraint_type == TableConstraintType.CHECK and t_const.check_condition:
            check_sql, check_params = t_const.check_condition.to_sql()
            parts.append(f"CHECK ({check_sql})")
            params.extend(check_params)

        return ' '.join(parts), tuple(params)

    def supports_computed_by(self) -> bool:
        return True

    def supports_identity_columns(self) -> bool:
        return True