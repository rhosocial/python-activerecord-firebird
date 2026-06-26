# src/rhosocial/activerecord/backend/impl/firebird/mixins/introspection.py
"""Firebird schema introspection mixin using RDB$ system tables."""


class FirebirdIntrospectionMixin:

    INTROSPECTION_QUERIES = {
        'tables': """
            SELECT
                RDB$RELATION_NAME AS TABLE_NAME,
                RDB$VIEW_SOURCE AS VIEW_SOURCE,
                RDB$SYSTEM_FLAG AS SYSTEM_FLAG
            FROM RDB$RELATIONS
            WHERE RDB$SYSTEM_FLAG = 0
            ORDER BY RDB$RELATION_NAME
        """,
        'columns': """
            SELECT
                rf.RDB$FIELD_NAME AS COLUMN_NAME,
                f.RDB$FIELD_TYPE AS FIELD_TYPE,
                f.RDB$FIELD_SUB_TYPE AS FIELD_SUB_TYPE,
                f.RDB$CHARACTER_LENGTH AS CHAR_LENGTH,
                f.RDB$FIELD_PRECISION AS PRECISION,
                f.RDB$FIELD_SCALE AS SCALE,
                rf.RDB$NULL_FLAG AS NULL_FLAG,
                rf.RDB$DEFAULT_SOURCE AS DEFAULT_SOURCE,
                rf.RDB$POSITION AS POSITION,
                rf.RDB$COMPUTED_SOURCE AS COMPUTED_SOURCE
            FROM RDB$RELATION_FIELDS rf
            JOIN RDB$FIELDS f ON rf.RDB$FIELD_SOURCE = f.RDB$FIELD_NAME
            WHERE rf.RDB$RELATION_NAME = ?
            ORDER BY rf.RDB$POSITION
        """,
        'indices': """
            SELECT
                i.RDB$INDEX_NAME AS INDEX_NAME,
                i.RDB$UNIQUE_FLAG AS UNIQUE_FLAG,
                i.RDB$INDEX_TYPE AS INDEX_TYPE,
                i.RDB$INDEX_INACTIVE AS INACTIVE,
                isg.RDB$FIELD_NAME AS FIELD_NAME,
                isg.RDB$FIELD_POSITION AS FIELD_POSITION
            FROM RDB$INDICES i
            JOIN RDB$INDEX_SEGMENTS isg ON i.RDB$INDEX_NAME = isg.RDB$INDEX_NAME
            WHERE i.RDB$RELATION_NAME = ?
            ORDER BY i.RDB$INDEX_NAME, isg.RDB$FIELD_POSITION
        """,
        'triggers': """
            SELECT
                RDB$TRIGGER_NAME AS TRIGGER_NAME,
                RDB$RELATION_NAME AS TABLE_NAME,
                RDB$TRIGGER_TYPE AS TRIGGER_TYPE,
                RDB$TRIGGER_SOURCE AS SOURCE,
                RDB$TRIGGER_INACTIVE AS INACTIVE,
                RDB$TRIGGER_SEQUENCE AS SEQUENCE
            FROM RDB$TRIGGERS
            WHERE RDB$RELATION_NAME IS NOT NULL
            ORDER BY RDB$TRIGGER_NAME
        """,
        'generators': """
            SELECT
                RDB$GENERATOR_NAME AS GENERATOR_NAME,
                RDB$GENERATOR_ID AS GENERATOR_ID,
                RDB$SYSTEM_FLAG AS SYSTEM_FLAG
            FROM RDB$GENERATORS
            WHERE RDB$SYSTEM_FLAG = 0
            ORDER BY RDB$GENERATOR_NAME
        """,
        'procedures': """
            SELECT
                RDB$PROCEDURE_NAME AS PROCEDURE_NAME,
                RDB$PROCEDURE_INPUTS AS INPUT_PARAMS,
                RDB$PROCEDURE_OUTPUTS AS OUTPUT_PARAMS,
                RDB$PROCEDURE_SOURCE AS SOURCE
            FROM RDB$PROCEDURES
            WHERE RDB$SYSTEM_FLAG = 0
            ORDER BY RDB$PROCEDURE_NAME
        """,
    }