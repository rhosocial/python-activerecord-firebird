# src/rhosocial/activerecord/backend/impl/firebird/reserved_words.py
"""
Firebird reserved words list.

Source: Firebird 5.0 Language Reference
"""

FIREBIRD_RESERVED_WORDS = frozenset({
    "absolute", "action", "add", "admin", "after", "all", "alter", "and",
    "any", "as", "asc", "ascending", "at", "auto", "autonomous", "avg",
    "base_name", "before", "begin", "between", "blob", "blob_id", "by",
    "cache", "call", "cascade", "case", "cast", "char", "character",
    "check", "close", "coalesce", "collate", "column", "comment", "commit",
    "computed", "conditional", "connect", "constraint", "containing",
    "count", "create", "cstring", "current", "current_date",
    "current_time", "current_timestamp", "cursor", "database", "date",
    "day", "deallocate", "dec", "decimal", "declare", "default", "delete",
    "desc", "descending", "descriptor", "disconnect", "distinct", "do",
    "domain", "double", "drop", "else", "end", "entry_point", "escape",
    "exception", "execute", "exists", "exit", "external", "extract",
    "false", "fetch", "file", "filter", "float", "for", "foreign",
    "found", "free_it", "from", "function", "generator", "global", "goto",
    "grant", "group", "group_commit_id", "having", "hour", "if", "immediate",
    "in", "in_silence", "index", "inner", "input_type", "insert", "int",
    "integer", "into", "is", "isolation", "key", "language", "leading",
    "left", "length", "lock", "long", "manual", "max", "max_segment",
    "merge", "min", "minute", "module_name", "month", "national", "natural",
    "nchar", "no", "not", "null", "num_log_bu", "numeric", "octet_length",
    "of", "on", "only", "open", "option", "or", "order", "outer", "output",
    "overflow", "page", "page_size", "pages", "parameter", "password",
    "plan", "position", "post_event", "precision", "primary", "privileges",
    "procedure", "public", "quit", "raw_partitions", "read", "real",
    "record_version", "references", "release", "returning_values",
    "returns", "revoke", "right", "role", "rollback", "rows_affected",
    "row_count", "schema", "second", "segment", "select", "set", "shadow",
    "shared", "singular", "size", "smallint", "snapshot", "some",
    "sort_type", "sql", "sqlcode", "stability", "start", "starting",
    "statistics", "stop", "substring", "sum", "suspend", "table", "temp",
    "temporary", "then", "time", "timestamp", "timezone_hour",
    "timezone_minute", "to", "trailing", "transaction", "trigger", "trim",
    "true", "unbounded", "union", "unique", "update", "upper", "user",
    "using", "value", "values", "varchar", "variable", "varying", "view",
    "wait", "when", "where", "while", "with", "work", "write",
})
