# src/rhosocial/activerecord/backend/impl/firebird/mixins/version_boundaries.py
"""Firebird version boundary constants."""

FIREBIRD_VERSION_BOUNDARIES = {
    'WINDOW_FUNCTIONS': (3, 0, 0),
    'CTE': (3, 0, 0),
    'BOOLEAN': (3, 0, 0),
    'IDENTITY': (3, 0, 0),
    'SEQUENCE': (3, 0, 0),
    'PACKAGES': (3, 0, 0),
    'DATABASE_TRIGGERS': (3, 0, 0),
    'AUTONOMOUS_TRANS': (3, 0, 0),
    'UUID_TO_FROM_CHAR': (3, 0, 0),
    'SKIP_LOCKED': (5, 0, 0),
    'OFFSET_FETCH': (3, 0, 0),
    'DECFLOAT': (4, 0, 0),
    'EXPLAIN_PLAN': (3, 0, 0),
    'RETURNING_NO_INTO': (3, 0, 0),
    'EXECUTE_BLOCK': (2, 5, 0),
    'ROWS_SYNTAX': (2, 5, 0),
    'MON_TABLES': (2, 5, 0),
    'LIST_FUNCTION': (2, 5, 0),
    'DATEADD_DATEDIFF': (2, 5, 0),
    'GEN_UUID': (2, 5, 0),
    'REPLACE_FUNCTION': (2, 5, 0),
    'POSITION_FUNCTION': (2, 5, 0),
    'IIF_DECODE': (2, 5, 0),
    'COMPUTED_BY': (2, 5, 0),
}