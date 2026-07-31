# src/rhosocial/activerecord/backend/impl/firebird/mixins/dml.py
"""Firebird DML operations mixin — INSERT/UPDATE/DELETE with RETURNING."""

from typing import Any, Dict, List, Optional, Tuple


class FirebirdDMLOperationMixin:

    def format_insert_statement(self, expr) -> Tuple[str, tuple]:
        if expr.on_conflict:
            # Firebird has no ON CONFLICT clause; raise instead of silently
            # dropping the clause via the shared capability gate.
            self.format_on_conflict_clauses(expr)

        all_params: List[Any] = []

        table_sql, table_params = expr.into.to_sql()
        all_params.extend(table_params)

        columns_sql = ""
        if expr.columns:
            columns_sql = "(" + ", ".join(self.format_identifier(c) for c in expr.columns) + ")"

        from rhosocial.activerecord.backend.expression.statements import (
            DefaultValuesSource,
            ValuesSource,
            SelectSource,
        )

        source_sql = ""
        if isinstance(expr.source, DefaultValuesSource):
            source_sql = "DEFAULT VALUES"
        elif isinstance(expr.source, ValuesSource):
            all_rows_sql = []
            for row in expr.source.values_list:
                row_sql, row_params = [], []
                for val in row:
                    s, p = val.to_sql()
                    row_sql.append(s)
                    row_params.extend(p)
                all_rows_sql.append(f"({', '.join(row_sql)})")
                all_params.extend(row_params)
            source_sql = "VALUES " + ", ".join(all_rows_sql)
        elif isinstance(expr.source, SelectSource):
            s_sql, s_params = expr.source.select_query.to_sql()
            source_sql = s_sql
            all_params.extend(s_params)

        sql = f"INSERT INTO {table_sql} {columns_sql} {source_sql}".strip()

        if expr.returning:
            returning_sql, returning_params = self.format_returning_clause(expr.returning)
            sql += f" {returning_sql}"
            all_params.extend(returning_params)

        return sql, tuple(all_params)

    def format_update_statement(self, expr) -> Tuple[str, tuple]:
        all_params: List[Any] = []

        table_sql, table_params = expr.table.to_sql()
        all_params.extend(table_params)

        set_parts = []
        for col, val in expr.assignments.items():
            col_str = self.format_identifier(col)
            if hasattr(val, 'to_sql'):
                val_sql, val_params = val.to_sql()
                set_parts.append(f"{col_str} = {val_sql}")
                all_params.extend(val_params)
            else:
                all_params.append(val)
                set_parts.append(f"{col_str} = {self.get_parameter_placeholder()}")

        sql = f"UPDATE {table_sql} SET {', '.join(set_parts)}"

        if expr.where:
            where_sql, where_params = expr.where.to_sql()
            sql += f" {where_sql}"
            all_params.extend(where_params)

        if expr.returning:
            returning_sql, returning_params = self.format_returning_clause(expr.returning)
            sql += f" {returning_sql}"
            all_params.extend(returning_params)

        return sql, tuple(all_params)

    def format_delete_statement(self, expr) -> Tuple[str, tuple]:
        all_params: List[Any] = []

        table_sql, table_params = expr.tables[0].to_sql()
        all_params.extend(table_params)

        sql = f"DELETE FROM {table_sql}"

        if expr.where:
            where_sql, where_params = expr.where.to_sql()
            sql += f" {where_sql}"
            all_params.extend(where_params)

        if expr.returning:
            returning_sql, returning_params = self.format_returning_clause(expr.returning)
            sql += f" {returning_sql}"
            all_params.extend(returning_params)

        return sql, tuple(all_params)

    def format_returning_clause(self, clause) -> Tuple[str, tuple]:
        all_params = []
        expr_parts = []
        for expr in clause.expressions:
            expr_sql, expr_params = expr.to_sql()
            expr_parts.append(expr_sql)
            all_params.extend(expr_params)
        returning_sql = f"RETURNING {', '.join(expr_parts)}"
        return returning_sql, tuple(all_params)

    def format_update_or_insert(
        self,
        table_name: str,
        insert_columns: List[str],
        insert_values: List,
        match_columns: List[str],
        returning_columns: Optional[List[str]] = None,
    ) -> Tuple[str, tuple]:
        all_params = list(insert_values)

        cols_str = ', '.join(self.format_identifier(c) for c in insert_columns)
        val_strs = ', '.join(self.get_parameter_placeholder() for _ in insert_values)
        match_str = ', '.join(self.format_identifier(c) for c in match_columns)

        parts = [
            f"UPDATE OR INSERT INTO {self.format_identifier(table_name)}",
            f"({cols_str})",
            f"VALUES ({val_strs})",
            f"MATCHING ({match_str})",
        ]

        if returning_columns:
            ret_str = ', '.join(self.format_identifier(c) for c in returning_columns)
            parts.append(f"RETURNING {ret_str}")

        return ' '.join(parts), tuple(all_params)

    def format_execute_block(
        self, block: str, params: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, tuple]:
        all_params = []
        if params:
            param_defs = []
            for name, (param_type, value) in params.items():
                param_defs.append(f"{name} {param_type} = ?")
                all_params.append(value)
            sql = f"EXECUTE BLOCK ({', '.join(param_defs)})\nAS\nBEGIN\n{block}\nEND"
        else:
            sql = f"EXECUTE BLOCK\nAS\nBEGIN\n{block}\nEND"
        return sql, tuple(all_params)