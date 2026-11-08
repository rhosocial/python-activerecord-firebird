# src/rhosocial/activerecord/backend/impl/firebird/mixins/datetime.py
"""Firebird datetime formatting mixin."""

from typing import Any, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


class FirebirdDateTimeMixin:

    def format_date_trunc_expression(self, expr: "Any") -> Tuple[str, tuple]:
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

    def format_interval_expression(self, expr: "Any") -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name,
            "standalone INTERVAL expression",
            "Use date_add() or date_sub() for Firebird date arithmetic.",
        )

    def format_datetime_add_expression(self, expr: "Any") -> Tuple[str, tuple]:
        source_sql, source_params = expr.source.to_sql()
        unit = expr.interval.unit.value.upper()
        value = expr.interval.value * 7 if unit == "WEEK" else expr.interval.value
        unit = "DAY" if unit == "WEEK" else unit
        sql = f"DATEADD({self.p()} {unit} TO {source_sql})"
        return self.apply_alias(sql, (value,) + source_params, expr)

    def format_datetime_subtract_expression(self, expr: "Any") -> Tuple[str, tuple]:
        source_sql, source_params = expr.source.to_sql()
        unit = expr.interval.unit.value.upper()
        value = expr.interval.value * 7 if unit == "WEEK" else expr.interval.value
        unit = "DAY" if unit == "WEEK" else unit
        sql = f"DATEADD({self.p()} {unit} TO {source_sql})"
        return self.apply_alias(sql, (-value,) + source_params, expr)

    def format_datetime_diff_expression(self, expr: "Any") -> Tuple[str, tuple]:
        start_sql, start_params = expr.start.to_sql()
        end_sql, end_params = expr.end.to_sql()
        unit = "DAY" if expr.unit.value == "week" else expr.unit.value.upper()
        sql = f"DATEDIFF({unit} FROM {start_sql} TO {end_sql})"
        if expr.unit.value == "week":
            sql = f"({sql} / 7)"
        return self.apply_alias(sql, start_params + end_params, expr)

    def format_seconds_between_expression(self, expr: "Any") -> Tuple[str, tuple]:
        """Signed seconds from ``start`` to ``end`` in Firebird's spelling.

        Firebird has no interval value to subtract, so the distance is asked
        of ``DATEDIFF``: the unit is a keyword of the call, not a bind value.
        ``MILLISECOND`` is the finest unit it keeps -- Firebird timestamps
        store four fractional digits, i.e. tenths of a millisecond, and
        ``DATEDIFF(MILLISECOND, ...)`` returns ``NUMERIC(18, 1)``, so no
        stored digit is lost. Multiplying that count by ``0.001`` converts
        it to seconds and keeps the fraction; Firebird's exact numeric
        arithmetic yields four decimal places rather than rounding to the
        scale of a division by ``1000.0`` (which would truncate a
        tenth-millisecond difference to ``0.00``).

        The product is cast back to ``NUMERIC(18, 4)``: left bare, the
        multiplication widens to ``INT128``, and the Firebird 3 client
        library still installed by many Linux distributions cannot decode
        that answer -- it fails the prepare with "Data type unknown". The
        cast keeps the same four exact decimal places inside the ``INT64``
        the older client understands, and the whole Firebird timestamp range
        (about 3.16e11 seconds) still fits in 18 digits at scale 4.

        ``DATEDIFF`` is signed -- moment2 before moment1 is negative -- so
        the rendered ``end`` minus ``start`` keeps the direction without a
        ``CASE``. The parameters are collected in SQL order: ``start`` first,
        because it is the first placeholder, then ``end``.
        """
        start_sql, start_params = expr.start.to_sql()
        end_sql, end_params = expr.end.to_sql()
        sql = (
            f"(CAST(DATEDIFF(MILLISECOND FROM {start_sql} TO {end_sql}) "
            f"* 0.001 AS NUMERIC(18, 4)))"
        )
        return self.apply_alias(sql, start_params + end_params, expr)
