# src/rhosocial/activerecord/backend/impl/firebird/function_versions.py
"""Firebird function version requirements mapping.

Each entry maps function name to (min_version, max_version) tuple.
None means no version restriction.
"""

FIREBIRD_FUNCTION_VERSIONS = {
    # Window functions: Firebird 3.0+
    "row_number": ((3, 0, 0), None),
    "rank": ((3, 0, 0), None),
    "dense_rank": ((3, 0, 0), None),
    "ntile": ((3, 0, 0), None),
    "lead": ((3, 0, 0), None),
    "lag": ((3, 0, 0), None),
    "first_value": ((3, 0, 0), None),
    "last_value": ((3, 0, 0), None),
    "nth_value": ((3, 0, 0), None),
    "cume_dist": ((3, 0, 0), None),
    "percent_rank": ((3, 0, 0), None),
    # String functions: All versions
    "trim": (None, None),
    "substring": (None, None),
    "upper": (None, None),
    "lower": (None, None),
    "replace": ((2, 5, 0), None),
    "position": ((2, 5, 0), None),
    "char_length": ((2, 5, 0), None),
    "character_length": ((2, 5, 0), None),
    "octet_length": ((2, 5, 0), None),
    "bit_length": ((2, 5, 0), None),
    "lpad": ((2, 5, 0), None),
    "rpad": ((2, 5, 0), None),
    # Aggregate functions: All versions
    "list": ((2, 5, 0), None),
    "count": (None, None),
    "sum": (None, None),
    "avg": (None, None),
    "min": (None, None),
    "max": (None, None),
    # Math functions: All versions
    "abs": (None, None),
    "ceil": (None, None),
    "ceiling": (None, None),
    "floor": (None, None),
    "round": (None, None),
    "trunc": (None, None),
    "truncate": (None, None),
    "sqrt": (None, None),
    "power": (None, None),
    "mod": (None, None),
    "exp": (None, None),
    "ln": (None, None),
    "log": (None, None),
    "log10": (None, None),
    "sin": (None, None),
    "cos": (None, None),
    "tan": (None, None),
    "cot": (None, None),
    "asin": (None, None),
    "acos": (None, None),
    "atan": (None, None),
    "atan2": (None, None),
    "sign": (None, None),
    "rand": (None, None),
    # Date/Time functions: All versions
    "dateadd": ((2, 5, 0), None),
    "datediff": ((2, 5, 0), None),
    "extract": (None, None),
    "current_date": (None, None),
    "current_time": (None, None),
    "current_timestamp": (None, None),
    "date": (None, None),
    "time": (None, None),
    "timestamp": (None, None),
    "year": (None, None),
    "month": (None, None),
    "day": (None, None),
    "hour": (None, None),
    "minute": (None, None),
    "second": (None, None),
    "millisecond": (None, None),
    # UUID functions
    "gen_uuid": ((2, 5, 0), None),
    "uuid_to_char": ((3, 0, 0), None),
    "char_to_uuid": ((3, 0, 0), None),
    # Bitwise functions: All versions
    "bin_and": (None, None),
    "bin_or": (None, None),
    "bin_xor": (None, None),
    "bin_not": (None, None),
    # Conversion functions: All versions
    "cast": (None, None),
    "convert": (None, None),
    # NULL handling: All versions
    "coalesce": (None, None),
    "nullif": (None, None),
    "iif": ((2, 5, 0), None),
    "decode": ((2, 5, 0), None),
}

__all__ = ["FIREBIRD_FUNCTION_VERSIONS"]