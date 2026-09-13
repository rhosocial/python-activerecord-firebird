# src/rhosocial/activerecord/backend/impl/firebird/mixins/datetime.py
"""Firebird datetime formatting mixin."""

from typing import Any, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


class FirebirdDateTimeMixin:

    def format_date_trunc_expression(self, expr: "Any") -> Tuple[str, Tuple]:
        source_sql, source_params = expr.source.to_sql()
        if expr.field.value == "year":
            sql = f"CAST(EXTRACT(YEAR FROM {source_sql}) || '-01-01 00:00:00' AS TIMESTAMP)"
        elif expr.field.value == "month":
            sql = (
                f"CAST(EXTRACT(YEAR FROM {source_sql}) || '-' || "
                f"EXTRACT(MONTH FROM {source_sql}) || '-01 00:00:00' AS TIMESTAMP)"
            )
        elif expr.field.value == "day":
            sql = f"CAST(CAST({source_sql} AS DATE) AS TIMESTAMP)"
        elif expr.field.value == "hour":
            sql = (
                f"DATEADD(EXTRACT(MINUTE FROM {source_sql}) * -1 MINUTE TO "
                f"DATEADD(EXTRACT(SECOND FROM {source_sql}) * -1 SECOND TO {source_sql}))"
            )
        elif expr.field.value == "minute":
            sql = f"DATEADD(EXTRACT(SECOND FROM {source_sql}) * -1 SECOND TO {source_sql})"
        elif expr.field.value == "second":
            sql = source_sql
        else:
            raise UnsupportedFeatureError(self.name, f"date_trunc({expr.field.value})")
        return self.apply_alias(sql, source_params, expr)

    def format_interval_expression(self, expr: "Any") -> Tuple[str, Tuple]:
        raise UnsupportedFeatureError(
            self.name,
            "standalone INTERVAL expression",
            "Use date_add() or date_sub() for Firebird date arithmetic.",
        )

    def format_datetime_add_expression(self, expr: "Any") -> Tuple[str, Tuple]:
        source_sql, source_params = expr.source.to_sql()
        unit = expr.interval.unit.value.upper()
        value = expr.interval.value * 7 if unit == "WEEK" else expr.interval.value
        unit = "DAY" if unit == "WEEK" else unit
        sql = f"DATEADD(? {unit} TO {source_sql})"
        return self.apply_alias(sql, (value,) + source_params, expr)

    def format_datetime_subtract_expression(self, expr: "Any") -> Tuple[str, Tuple]:
        source_sql, source_params = expr.source.to_sql()
        unit = expr.interval.unit.value.upper()
        value = expr.interval.value * 7 if unit == "WEEK" else expr.interval.value
        unit = "DAY" if unit == "WEEK" else unit
        sql = f"DATEADD(? {unit} TO {source_sql})"
        return self.apply_alias(sql, (-value,) + source_params, expr)

    def format_datetime_diff_expression(self, expr: "Any") -> Tuple[str, Tuple]:
        start_sql, start_params = expr.start.to_sql()
        end_sql, end_params = expr.end.to_sql()
        unit = "DAY" if expr.unit.value == "week" else expr.unit.value.upper()
        sql = f"DATEDIFF({unit} FROM {start_sql} TO {end_sql})"
        if expr.unit.value == "week":
            sql = f"({sql} / 7)"
        return self.apply_alias(sql, start_params + end_params, expr)
