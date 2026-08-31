# tests/rhosocial/activerecord_firebird_test/feature/backend/test_types_and_dialect_branches.py
"""Offline branch snapshots for Firebird type formatting and dialect SQL.

Covers the FB4 data-type version gate on both sides (mixins/types.py), the
RETURNING / SKIP LOCKED / SEQUENCE dialect branches, and CREATE TABLE
rebuild-statement rendering from mixins/table.py — all via exact to_sql()
snapshots with no database connection.
"""
import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.query_parts import ForUpdateClause
from rhosocial.activerecord.backend.expression.statements import (
    ColumnConstraint,
    ColumnConstraintType,
    ColumnDefinition,
    CreateTableExpression,
    DeleteExpression,
    ForeignKeyConstraint,
    InsertExpression,
    ReturningClause,
    TableConstraint,
    TableConstraintType,
    UpdateExpression,
    ValuesSource,
    ReferentialAction,
)
from rhosocial.activerecord.backend.expression.types import (
    BigIntType,
    BooleanType,
    CharType,
    CustomType,
    DateType,
    DateTimeType,
    DecimalType,
    DoubleType,
    FloatType,
    IntegerType,
    SmallIntType,
    TextType,
    TimeType,
    TimestampType,
    VarCharType,
)
import rhosocial.activerecord.backend.expression as E

from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.expression.types import (
    FirebirdDecFloatType,
    FirebirdInt128Type,
    FirebirdTimeStampTzType,
    FirebirdTimeTzType,
)
from rhosocial.activerecord.backend.impl.firebird.mixins.locking import FirebirdLockingMixin


@pytest.fixture(scope="module")
def dialect() -> FirebirdDialect:
    return FirebirdDialect((4, 0))


def _column(name, data_type, *constraints):
    return ColumnDefinition(name, data_type, list(constraints))


class TestFB4TypeGateSupportedSide:
    """FB4-gated types must render on any 4.0 dialect shape.

    The ``(4, 0)`` variants pin F4: a two-component version tuple compares
    less than ``(4, 0, 0)``, so every gate must normalize before comparing.
    """

    @pytest.mark.parametrize("version", [(4, 0, 0), (4, 0)])
    @pytest.mark.parametrize("data_type,expected", [
        (FirebirdTimeStampTzType(), "TIMESTAMP WITH TIME ZONE"),
        (FirebirdTimeTzType(), "TIME WITH TIME ZONE"),
        (FirebirdDecFloatType(precision=16), "DECFLOAT(16)"),
        (FirebirdDecFloatType(precision=34), "DECFLOAT(34)"),
        (FirebirdInt128Type(), "INT128"),
    ])
    def test_fb4_types_render_on_4_0(self, version, data_type, expected):
        sql = FirebirdDialect(version).format_data_type(data_type)
        assert sql == (expected, ())
        assert data_type.to_sql(FirebirdDialect(version)) == (expected, ())

    def test_support_flags_agree_with_rendering(self):
        for version in ((4, 0, 0), (4, 0)):
            assert FirebirdDialect(version).supports_decfloat() is True


class TestFB4TypeGateUnsupportedSide:
    """The same types must raise on a (3, 0, 0) dialect."""

    @pytest.mark.parametrize("data_type,feature", [
        (FirebirdTimeStampTzType(), "TIMESTAMP WITH TIME ZONE"),
        (FirebirdTimeTzType(), "TIME WITH TIME ZONE"),
        (FirebirdDecFloatType(), "DECFLOAT"),
        (FirebirdInt128Type(), "INT128"),
    ])
    def test_fb4_types_raise_on_3_0(self, data_type, feature):
        dialect = FirebirdDialect((3, 0))
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            dialect.format_data_type(data_type)
        assert feature in str(excinfo.value)

    def test_decfloat_flag_off_on_3_0(self):
        assert FirebirdDialect((3, 0)).supports_decfloat() is False


class TestBaseDataTypeRendering:
    @pytest.mark.parametrize("data_type,expected", [
        (IntegerType(), "INTEGER"),
        (BigIntType(), "BIGINT"),
        (SmallIntType(), "SMALLINT"),
        (FloatType(), "FLOAT"),
        (DoubleType(), "DOUBLE PRECISION"),
        (BooleanType(), "BOOLEAN"),
        (VarCharType(length=50), "VARCHAR(50)"),
        (VarCharType(None), "VARCHAR(255)"),
        (CharType(length=10), "CHAR(10)"),
        (CharType(None), "CHAR(1)"),
        (TextType(), "BLOB SUB_TYPE TEXT"),
        (DateTimeType(), "TIMESTAMP"),
        (TimestampType(), "TIMESTAMP"),
        (DateType(), "DATE"),
        (TimeType(), "TIME"),
    ])
    def test_format_data_type(self, dialect, data_type, expected):
        assert dialect.format_data_type(data_type) == (expected, ())

    @pytest.mark.parametrize("data_type,expected", [
        (DecimalType(precision=10, scale=2), "DECIMAL(10, 2)"),
        (DecimalType(precision=18), "DECIMAL(18)"),
        (DecimalType(), "DECIMAL"),
    ])
    def test_decimal_variants(self, dialect, data_type, expected):
        assert dialect.format_data_type(data_type) == (expected, ())

    def test_parse_type_integer_family(self, dialect):
        assert isinstance(dialect.parse_type("INTEGER"), IntegerType)
        assert isinstance(dialect.parse_type("int"), IntegerType)
        assert isinstance(dialect.parse_type("BIGINT"), BigIntType)
        assert isinstance(dialect.parse_type("SMALLINT"), SmallIntType)

    def test_parse_type_float_family(self, dialect):
        assert isinstance(dialect.parse_type("FLOAT"), FloatType)
        assert isinstance(dialect.parse_type("REAL"), FloatType)
        assert isinstance(dialect.parse_type("DOUBLE PRECISION"), DoubleType)

    @pytest.mark.parametrize("raw,precision,scale", [
        ("DECIMAL(10,2)", 10, 2),
        ("NUMERIC(8,3)", 8, 3),
        ("DECIMAL", None, None),
    ])
    def test_parse_type_decimal_family(self, dialect, raw, precision, scale):
        parsed = dialect.parse_type(raw)
        assert isinstance(parsed, DecimalType)
        assert parsed.precision == precision
        assert parsed.scale == scale

    def test_parse_type_string_family(self, dialect):
        assert dialect.parse_type("VARCHAR(50)") == VarCharType(length=50)
        assert dialect.parse_type("VARCHAR") == VarCharType(length=255)
        assert dialect.parse_type("CHAR(10)") == CharType(length=10)
        assert dialect.parse_type("CHARACTER(5)") == CharType(length=5)
        assert dialect.parse_type("CHAR") == CharType(length=1)

    def test_parse_type_misc(self, dialect):
        assert isinstance(dialect.parse_type("BLOB SUB_TYPE TEXT"), TextType)
        assert isinstance(dialect.parse_type("DATE"), DateType)
        assert isinstance(dialect.parse_type("TIME"), TimeType)
        assert isinstance(dialect.parse_type("BOOLEAN"), BooleanType)
        assert dialect.parse_type("SOMETHING WEIRD") == CustomType(raw="SOMETHING WEIRD")

    def test_parse_type_timestamp_takes_precedence_over_time(self, dialect):
        """F7 anchor: startswith("TIME") used to swallow TIMESTAMP strings."""
        parsed = dialect.parse_type("TIMESTAMP")
        assert isinstance(parsed, DateTimeType)
        assert not isinstance(parsed, TimeType)
        assert isinstance(dialect.parse_type("timestamp with time zone"), DateTimeType)
        # Plain TIME must still parse as TimeType after the reorder.
        assert isinstance(dialect.parse_type("TIME"), TimeType)


class TestReturningBranches:
    def test_insert_returning_snapshot(self, dialect):
        insert = InsertExpression(
            dialect, "users",
            ValuesSource(dialect, [[E.RawSQLExpression(dialect, "?")]]),
            columns=["name"],
            returning=ReturningClause(dialect, expressions=[E.Column(dialect, "id"), E.Column(dialect, "name")]),
        )
        assert insert.to_sql() == ('INSERT INTO "USERS" ("NAME") VALUES (?) RETURNING "ID", "NAME"', ())

    def test_insert_without_returning_has_no_clause(self, dialect):
        insert = InsertExpression(
            dialect, "users",
            ValuesSource(dialect, [[E.Literal(dialect, "Bob")]]),
            columns=["name"],
        )
        assert insert.to_sql() == ('INSERT INTO "USERS" ("NAME") VALUES (?)', ("Bob",))

    def test_update_returning_snapshot(self, dialect):
        update = UpdateExpression(
            dialect, "users", {"name": E.Literal(dialect, "Bob")},
            where=E.Column(dialect, "id") == E.Literal(dialect, 7),
            returning=ReturningClause(dialect, expressions=[E.Column(dialect, "id")]),
        )
        assert update.to_sql() == (
            'UPDATE "USERS" SET "NAME" = ? WHERE "ID" = ? RETURNING "ID"',
            ("Bob", 7),
        )

    def test_delete_returning_wildcard_snapshot(self, dialect):
        delete = DeleteExpression(
            dialect, "users",
            where=E.Column(dialect, "id") == E.Literal(dialect, 7),
            returning=ReturningClause(dialect, expressions=[E.RawSQLExpression(dialect, "*")]),
        )
        assert delete.to_sql() == ('DELETE FROM "USERS" WHERE "ID" = ? RETURNING *', (7,))

    def test_update_or_insert_with_matching_and_returning(self, dialect):
        sql, params = dialect.format_update_or_insert(
            "users", ["name", "age"], ["Ann", 30], ["name"], returning_columns=["id"]
        )
        assert sql == 'UPDATE OR INSERT INTO "USERS" ("NAME", "AGE") VALUES (?, ?) MATCHING ("NAME") RETURNING "ID"'
        assert params == ("Ann", 30)

    def test_capability_flags(self, dialect):
        assert dialect.supports_returning_insert() is True
        assert dialect.supports_returning_update() is True
        assert dialect.supports_returning_delete() is True


class TestSkipLockedBranches:
    @pytest.mark.parametrize("version,expected_skip_locked", [
        ((3, 0, 0), False),
        ((4, 0, 0), True),
        ((5, 0, 0), True),
    ])
    def test_supports_skip_locked_gate(self, version, expected_skip_locked):
        dialect = FirebirdDialect(version)
        assert dialect.supports_skip_locked() is expected_skip_locked
        assert dialect.supports_for_update_skip_locked() is expected_skip_locked
        # Single source of truth: the mixin must not carry its own threshold.
        assert "supports_skip_locked" not in vars(FirebirdLockingMixin)

    def test_supports_for_update_gate_follows_protocol(self):
        assert FirebirdDialect((3, 0, 0)).supports_for_update() is True
        assert FirebirdDialect((2, 5, 0)).supports_for_update() is False
        assert FirebirdDialect((4, 0)).supports_for_update() is True

    @pytest.mark.parametrize("version,kwargs,fragments", [
        ((3, 0, 0), {}, ('SELECT "ID" FROM "T"', 'FOR UPDATE')),
        ((3, 0, 0), {"skip_locked": True}, ('FOR UPDATE',)),
        ((3, 0, 0), {"nowait": True}, ('FOR UPDATE WITH LOCK',)),
        ((4, 0, 0), {"skip_locked": True}, ('FOR UPDATE', 'SKIP LOCKED')),
        ((5, 0, 0), {"skip_locked": True}, ('FOR UPDATE', 'SKIP LOCKED')),
        ((4, 0), {"nowait": True}, ('FOR UPDATE WITH LOCK',)),
        ((4, 0), {"skip_locked": True}, ('FOR UPDATE', 'SKIP LOCKED')),
    ])
    def test_for_update_renders_through_query_path(self, version, kwargs, fragments):
        """FOR UPDATE/SKIP LOCKED must render through the real query path.

        F2/F3 anchor flip: this used to assert that every version raised
        UnsupportedFeatureError because the mixin method name missed the
        LockingSupport protocol; now the clause renders positively.
        """
        dialect = FirebirdDialect(version)
        query = E.QueryExpression(
            dialect, select=[E.Column(dialect, "id")], from_="t",
            for_update=ForUpdateClause(dialect, **kwargs),
        )
        sql, params = query.to_sql()
        for fragment in fragments:
            assert fragment in sql
        if kwargs.get("skip_locked") and not dialect.supports_skip_locked():
            assert "SKIP LOCKED" not in sql
        assert params == ()

    def test_for_update_of_columns_render_through_query_path(self):
        dialect = FirebirdDialect((3, 0, 0))
        query = E.QueryExpression(
            dialect, select=[E.Column(dialect, "id")], from_="t",
            for_update=ForUpdateClause(
                dialect,
                of_columns=["id", E.Column(dialect, "name")],
                nowait=True,
            ),
        )
        sql, _ = query.to_sql()
        assert sql.endswith('FOR UPDATE OF "ID", "NAME" WITH LOCK')

    @pytest.mark.parametrize("version,kwargs,expected", [
        ((3, 0, 0), {}, "FOR UPDATE"),
        ((3, 0, 0), {"skip_locked": True}, "FOR UPDATE"),
        ((4, 0, 0), {"skip_locked": True}, "FOR UPDATE SKIP LOCKED"),
        ((5, 0, 0), {"skip_locked": True}, "FOR UPDATE SKIP LOCKED"),
        ((4, 0, 0), {"with_lock": True}, "FOR UPDATE WITH LOCK"),
        ((4, 0, 0), {"nowait": True}, "FOR UPDATE WITH LOCK"),
    ])
    def test_locking_mixin_branches_directly(self, version, kwargs, expected):
        dialect = FirebirdDialect(version)

        class LockRequest:
            pass

        request = LockRequest()
        request.with_lock = kwargs.get("with_lock", False)
        request.skip_locked = kwargs.get("skip_locked", False)
        request.nowait = kwargs.get("nowait", False)
        assert FirebirdLockingMixin.format_for_update_clause(dialect, request) == (expected, ())


class TestSequenceBranches:
    def test_create_sequence_defaults(self, dialect):
        assert dialect.format_create_sequence("seq_a") == ('CREATE SEQUENCE "SEQ_A"', ())

    def test_create_sequence_start_and_increment(self, dialect):
        assert dialect.format_create_sequence("seq_b", start_value=100, increment=5) == (
            'CREATE SEQUENCE "SEQ_B" START WITH 100 INCREMENT BY 5', ()
        )

    def test_create_generator_form(self, dialect):
        assert dialect.format_create_sequence("gen_c", use_generator=True) == ('CREATE GENERATOR "GEN_C"', ())

    def test_gen_id_step(self, dialect):
        assert dialect.format_gen_id("gen_c", 2) == ('GEN_ID("GEN_C", 2)', ())

    def test_next_value_for(self, dialect):
        assert dialect.format_next_value_for("seq_b") == ('NEXT VALUE FOR "SEQ_B"', ())

    def test_sequence_capability_flags(self, dialect):
        assert dialect.supports_sequence() is True
        assert dialect.supports_create_sequence() is True
        assert dialect.supports_alter_sequence() is True
        assert dialect.supports_create_generator() is True


class TestCreateTableRebuildSnapshots:
    def test_basic_table(self, dialect):
        expr = CreateTableExpression(dialect, "users", [
            _column("id", IntegerType(), ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)),
            _column("name", VarCharType(length=100)),
        ])
        assert expr.to_sql() == (
            'CREATE TABLE "USERS" ("ID" INTEGER PRIMARY KEY, "NAME" VARCHAR(100))', ()
        )

    @pytest.mark.parametrize("on_commit_delete,expected_tail", [
        (True, 'ON COMMIT DELETE ROWS'),
        (False, 'ON COMMIT PRESERVE ROWS'),
    ])
    def test_global_temporary_table(self, dialect, on_commit_delete, expected_tail):
        expr = CreateTableExpression(dialect, "tmp_t", [_column("id", IntegerType())], temporary=True)
        expr.on_commit_delete = on_commit_delete
        sql, _ = expr.to_sql()
        assert sql.startswith('CREATE GLOBAL TEMPORARY TABLE "TMP_T"')
        assert expected_tail in sql

    @pytest.mark.parametrize("on_commit_delete,expected", [
        (True, 'CREATE GLOBAL TEMPORARY TABLE "GT_A" ON COMMIT DELETE ROWS ("ID" INTEGER)'),
        (False, 'CREATE GLOBAL TEMPORARY TABLE "GT_A" ON COMMIT PRESERVE ROWS ("ID" INTEGER)'),
    ])
    def test_global_temporary_word_order_snapshot(self, dialect, on_commit_delete, expected):
        """F5 anchor: exact to_sql() snapshot of the corrected word order."""
        expr = CreateTableExpression(dialect, "gt_a", [_column("id", IntegerType())], temporary=True)
        expr.on_commit_delete = on_commit_delete
        assert expr.to_sql() == (expected, ())

    def test_if_not_exists_wrapped_in_execute_block_guard(self, dialect):
        """F6 anchor: Firebird lacks native IF NOT EXISTS on CREATE TABLE.

        Since the EXECUTE BLOCK existence guard landed, requesting
        ``if_not_exists`` no longer raises: the statement is wrapped in an
        idempotent RDB$RELATIONS existence check instead.
        """
        expr = CreateTableExpression(dialect, "tbl_c", [_column("id", IntegerType())], if_not_exists=True)
        sql, _ = expr.to_sql()
        assert "EXECUTE BLOCK" in sql
        assert "RDB$RELATIONS" in sql
        assert 'CREATE TABLE "TBL_C"' in sql

    def test_if_not_exists_renders_when_capability_present(self, dialect):
        expr = CreateTableExpression(dialect, "tbl_c", [_column("id", IntegerType())], if_not_exists=True)
        from unittest import mock
        with mock.patch.object(FirebirdDialect, "supports_if_not_exists_table", return_value=True):
            sql, _ = expr.to_sql()
        assert sql.startswith('CREATE TABLE IF NOT EXISTS "TBL_C"')

    def test_external_file_clause(self, dialect):
        expr = CreateTableExpression(dialect, "ext_t", [_column("id", IntegerType())])
        expr.external_file = "/data/ext.fdb"
        assert expr.to_sql() == ('CREATE TABLE "EXT_T" ("ID" INTEGER) EXTERNAL FILE \'/data/ext.fdb\'', ())

    def test_computed_by_column(self, dialect):
        col = _column("full_name", VarCharType(length=200))
        col.computed_by = '"FIRST_NAME" || \' \' || "LAST_NAME"'
        assert CreateTableExpression(dialect, "emp", [col]).to_sql() == (
            'CREATE TABLE "EMP" '
            '("FULL_NAME" VARCHAR(200) COMPUTED BY ("FIRST_NAME" || \' \' || "LAST_NAME"))',
            (),
        )

    def test_identity_with_start_and_increment(self, dialect):
        col = _column("id", IntegerType())
        col.identity = True
        col.identity_generated = "ALWAYS"
        col.identity_start = 1000
        col.identity_increment = 10
        assert CreateTableExpression(dialect, "ident_t", [col]).to_sql() == (
            'CREATE TABLE "IDENT_T" '
            '("ID" INTEGER GENERATED ALWAYS AS IDENTITY (START WITH 1000 INCREMENT BY 10))',
            (),
        )

    def test_auto_increment_constraint_flag(self, dialect):
        col = _column(
            "id", IntegerType(),
            ColumnConstraint(ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True),
        )
        assert CreateTableExpression(dialect, "autoinc", [col]).to_sql() == (
            'CREATE TABLE "AUTOINC" ("ID" INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY)', ()
        )

    def test_string_default_escaped_and_ordered_before_not_null(self, dialect):
        col = _column(
            "status", VarCharType(length=20),
            ColumnConstraint(ColumnConstraintType.DEFAULT, default_value="O'Brien"),
            ColumnConstraint(ColumnConstraintType.NOT_NULL),
        )
        assert CreateTableExpression(dialect, "t5", [col]).to_sql() == (
            "CREATE TABLE \"T5\" (\"STATUS\" VARCHAR(20) DEFAULT 'O''Brien' NOT NULL)", ()
        )

    def test_expression_default_contributes_params(self, dialect):
        col = _column(
            "created_at", DateTimeType(),
            ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=E.Literal(dialect, "CURRENT_TIMESTAMP")),
        )
        assert CreateTableExpression(dialect, "t5b", [col]).to_sql() == (
            'CREATE TABLE "T5B" ("CREATED_AT" TIMESTAMP DEFAULT ?)', ("CURRENT_TIMESTAMP",)
        )

    def test_numeric_default_with_explicit_null(self, dialect):
        col = _column(
            "amount", DecimalType(precision=18, scale=2),
            ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=0),
            ColumnConstraint(ColumnConstraintType.NULL),
        )
        assert CreateTableExpression(dialect, "t5c", [col]).to_sql() == (
            'CREATE TABLE "T5C" ("AMOUNT" DECIMAL(18, 2) DEFAULT 0 NULL)', ()
        )

    def test_table_constraints_snapshot(self, dialect):
        fk = ForeignKeyConstraint(
            name="fk_order_customer", columns=["customer_id"],
            foreign_key_table="customers", foreign_key_columns=["id"],
            on_delete=ReferentialAction.CASCADE, on_update=ReferentialAction.SET_NULL,
        )
        unique = TableConstraint(TableConstraintType.UNIQUE, name="uq_email", columns=["email"])
        pk = TableConstraint(TableConstraintType.PRIMARY_KEY, columns=["id"])
        check = TableConstraint(
            TableConstraintType.CHECK,
            check_condition=E.Column(dialect, "amount") >= E.Literal(dialect, 0),
        )
        expr = CreateTableExpression(
            dialect, "orders",
            [
                _column("id", IntegerType()),
                _column("customer_id", IntegerType()),
                _column("email", VarCharType(length=255)),
                _column("amount", DecimalType(precision=18, scale=2)),
            ],
            table_constraints=[pk, unique, fk, check],
        )
        sql, params = expr.to_sql()
        assert sql == (
            'CREATE TABLE "ORDERS" ("ID" INTEGER, "CUSTOMER_ID" INTEGER, "EMAIL" VARCHAR(255), '
            '"AMOUNT" DECIMAL(18, 2), PRIMARY KEY ("ID"), CONSTRAINT "UQ_EMAIL" UNIQUE ("EMAIL"), '
            'CONSTRAINT "FK_ORDER_CUSTOMER" FOREIGN KEY ("CUSTOMER_ID") REFERENCES "CUSTOMERS" ("ID") '
            'ON DELETE CASCADE ON UPDATE SET NULL, CHECK ("AMOUNT" >= ?))'
        )
        assert params == (0,)

    def test_partition_rejected(self, dialect):
        partition = E.PartitionClause(dialect, method=E.PartitionStrategy.HASH, keys=[E.Column(dialect, "id")])
        expr = CreateTableExpression(dialect, "pt", [_column("id", IntegerType())], partition=partition)
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            expr.to_sql()
        assert "PARTITION BY clause" in str(excinfo.value)
