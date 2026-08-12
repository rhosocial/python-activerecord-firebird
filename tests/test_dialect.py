# tests/test_dialect.py
"""Tests for FirebirdDialect SQL generation."""


from rhosocial.activerecord.backend.impl.firebird import FirebirdDialect


class TestFirebirdDialectBasic:
    """Basic dialect tests."""

    def test_parameter_placeholder(self, dialect):
        assert dialect.get_parameter_placeholder() == "?"
        assert dialect.get_parameter_placeholder(1) == "?"

    def test_identifier_quoting(self, dialect):
        assert dialect.format_identifier("mytable") == '"MYTABLE"'
        assert dialect.format_identifier("my table") == '"MY TABLE"'

    def test_identifier_escaping(self, dialect):
        result = dialect.format_identifier('my"table')
        assert '"MY""TABLE"' in result

    def test_name_property(self, dialect):
        assert dialect.name == "Firebird"

    def test_version(self, dialect):
        assert dialect.version == (3, 0, 0)


class TestFirebirdDialectFeatureSupport:
    """Feature detection tests."""

    def test_window_functions_supported_fb3(self, dialect):
        assert dialect.supports_window_functions() is True

    def test_window_functions_not_supported_fb2_5(self, sqlite_style_dialect):
        assert sqlite_style_dialect.supports_window_functions() is False

    def test_cte_supported_fb3(self, dialect):
        assert dialect.supports_basic_cte() is True
        assert dialect.supports_recursive_cte() is True

    def test_returning_supported(self, dialect):
        assert dialect.supports_returning_insert() is True
        assert dialect.supports_returning_update() is True
        assert dialect.supports_returning_delete() is True

    def test_upsert_supported(self, dialect):
        assert dialect.supports_upsert() is True
        assert dialect.get_upsert_syntax_type() == "UPDATE OR INSERT"

    def test_json_not_supported(self, dialect):
        assert dialect.supports_json_type() is False

    def test_skip_locked_fb4(self, fb4_dialect):
        assert fb4_dialect.supports_for_update_skip_locked() is False

    def test_skip_locked_fb5(self):
        d = FirebirdDialect(version=(5, 0, 0))
        assert d.supports_for_update_skip_locked() is True

    def test_skip_locked_fb3(self, dialect):
        assert dialect.supports_for_update_skip_locked() is False

    def test_boolean_fb3(self, dialect):
        assert dialect.supports_boolean_type() is True

    def test_decfloat_fb4(self, fb4_dialect):
        assert fb4_dialect.supports_decfloat() is True

    def test_identity_fb3(self, dialect):
        assert dialect.supports_identity_columns() is True


class TestFirebirdDialectUnsupportedFeatures:
    """Tests for features that Firebird does not support."""

    def test_fulltext_search(self, dialect):
        assert dialect.supports_fulltext_index() is False

    def test_ilike(self, dialect):
        assert dialect.supports_ilike() is False

    def test_qualify(self, dialect):
        assert dialect.supports_qualify_clause() is False

    def test_materialized_views(self, dialect):
        assert dialect.supports_materialized_view() is False

    def test_statement_triggers(self, dialect):
        assert dialect.supports_statement_trigger() is False

    def test_table_partitioning(self, dialect):
        assert dialect.supports_table_partitioning() is False

    def test_array_constructor(self, dialect):
        assert dialect.supports_array_constructor() is False


class TestFirebirdDialectDDLSupport:
    """DDL support detection tests."""

    def test_create_table(self, dialect):
        assert dialect.supports_create_table() is True

    def test_create_view(self, dialect):
        assert dialect.supports_create_view() is True
        assert dialect.supports_or_replace_view() is True

    def test_trigger(self, dialect):
        assert dialect.supports_trigger() is True
        assert dialect.supports_instead_of_trigger() is True

    def test_generated_columns(self, dialect):
        assert dialect.supports_generated_columns() is True

    def test_temporary_table(self, dialect):
        assert dialect.supports_temporary_table() is True

    def test_foreign_key(self, dialect):
        assert dialect.supports_foreign_key_constraint() is True
        assert dialect.supports_fk_on_delete() is True
        assert dialect.supports_fk_on_update() is True


class TestFirebirdDialectPagination:
    """Pagination support tests."""

    def test_rows_syntax_fb2_5(self, sqlite_style_dialect):
        sql, params = sqlite_style_dialect.format_limit_offset(limit=10, offset=20)
        assert "ROWS" in sql
        assert "21" in sql
        assert "30" in sql

    def test_offset_fetch_fb4(self, fb4_dialect):
        sql, params = fb4_dialect.format_limit_offset(limit=10, offset=20)
        assert "OFFSET" in sql
        assert "FETCH" in sql

    def test_offset_fetch_fb3(self, dialect):
        sql, params = dialect.format_limit_offset(limit=10, offset=20)
        assert "OFFSET" in sql
        assert "FETCH" in sql

    def test_no_limit_offset(self, dialect):
        sql, params = dialect.format_limit_offset()
        assert sql == ""


class TestFirebirdDialectTransaction:
    """Transaction SQL formatting tests."""

    def test_format_set_transaction(self, dialect):
        from rhosocial.activerecord.backend.transaction import IsolationLevel, TransactionMode
        from rhosocial.activerecord.backend.expression.transaction import SetTransactionExpression

        expr = SetTransactionExpression(dialect)
        expr._isolation_level = IsolationLevel.READ_COMMITTED
        expr._mode = TransactionMode.READ_WRITE

        sql, params = dialect.format_set_transaction(expr)
        assert sql.startswith("SET TRANSACTION")
        assert "READ COMMITTED" in sql
        assert "READ WRITE" in sql


class TestFirebirdDialectFunctions:
    """Function support tests."""

    def test_supports_functions_returns_dict(self, dialect):
        result = dialect.supports_functions()
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_gen_uuid_supported(self, dialect):
        result = dialect.supports_functions()
        assert "gen_uuid" in result

    def test_sqlxml_constructors_are_not_plain_functions(self, dialect):
        result = dialect.supports_functions()
        sqlxml_constructors = [
            "xmlparse", "xmlserialize", "xmlelement", "xmlattributes",
            "xmlforest", "xmlconcat", "xmlcomment", "xmlpi", "xmlroot",
            "xmlagg", "xmlquery", "xmlexists", "xmltable",
        ]
        for func in sqlxml_constructors:
            assert func not in result