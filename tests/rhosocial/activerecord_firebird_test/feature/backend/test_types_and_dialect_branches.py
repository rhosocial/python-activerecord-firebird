# tests/rhosocial/activerecord_firebird_test/feature/backend/test_types_and_dialect_branches.py
"""Offline branch snapshots for Firebird type formatting and dialect SQL.

Covers the FB4 data-type version gate on both sides (mixins/types.py), the
``RDB$FIELD_TYPE`` codes the Firebird 4 types arrive under (24/25 ``DECFLOAT``,
26 ``INT128``, 28/29 the zoned date-times), the ``FLOAT(bin_prec)`` and BLOB
sub-type identity branches, the RETURNING / SKIP LOCKED / SEQUENCE dialect
branches, and CREATE TABLE rebuild-statement rendering from mixins/table.py —
all via exact to_sql() snapshots with no database connection.
"""
import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.objects import Sequence, Table
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
from rhosocial.activerecord.backend.expression.statements.ddl_sequence import (
    AlterSequenceExpression,
    CreateSequenceExpression,
    DropSequenceExpression,
)
from rhosocial.activerecord.backend.expression.types import (
    BigIntType,
    BlobType,
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
    TinyIntType,
    VarCharType,
)
import rhosocial.activerecord.backend.expression as E

from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.expression.dml import (
    UpdateOrInsertExpression,
)
from rhosocial.activerecord.backend.impl.firebird.expression.generator import (
    GenIdExpression,
    NextValueForExpression,
)
from rhosocial.activerecord.backend.impl.firebird.expression.types import (
    FirebirdBlobSubType,
    FirebirdDecFloatType,
    FirebirdFloatType,
    FirebirdInt128Type,
    FirebirdTimeStampTzType,
    FirebirdTimeTzType,
    FirebirdTimeWithoutTimeZoneType,
)
from rhosocial.activerecord.backend.impl.firebird.mixins.locking import FirebirdLockingMixin


@pytest.fixture(scope="module")
def dialect() -> FirebirdDialect:
    return FirebirdDialect((4, 0))


def _column(dialect, name, data_type, *constraints):
    return ColumnDefinition(dialect, name, data_type, list(constraints))


class TestFB4TypeGateSupportedSide:
    """FB4-gated types must render on any 4.0 dialect shape.

    The ``(4, 0)`` variants pin F4: a two-component version tuple compares
    less than ``(4, 0, 0)``, so every gate must normalize before comparing.
    """

    @pytest.mark.parametrize("version", [(4, 0, 0), (4, 0)])
    @pytest.mark.parametrize("data_type_cls,kwargs,expected", [
        (FirebirdTimeStampTzType, {}, "TIMESTAMP WITH TIME ZONE"),
        (FirebirdTimeTzType, {}, "TIME WITH TIME ZONE"),
        (FirebirdDecFloatType, {"precision": 16}, "DECFLOAT(16)"),
        (FirebirdDecFloatType, {"precision": 34}, "DECFLOAT(34)"),
        (FirebirdInt128Type, {}, "INT128"),
    ])
    def test_fb4_types_render_on_4_0(self, version, data_type_cls, kwargs, expected):
        sql = FirebirdDialect(version).format_data_type(data_type_cls(**kwargs))
        assert sql == (expected, ())

    def test_support_flags_agree_with_rendering(self):
        for version in ((4, 0, 0), (4, 0)):
            assert FirebirdDialect(version).supports_decfloat() is True


class TestFB4TypeGateUnsupportedSide:
    """The same types must raise on a (3, 0, 0) dialect."""

    @pytest.mark.parametrize("data_type_cls,kwargs,feature", [
        (FirebirdTimeStampTzType, {}, "TIMESTAMP WITH TIME ZONE"),
        (FirebirdTimeTzType, {}, "TIME WITH TIME ZONE"),
        (FirebirdDecFloatType, {"precision": 16}, "DECFLOAT"),
        (FirebirdInt128Type, {}, "INT128"),
    ])
    def test_fb4_types_raise_on_3_0(self, data_type_cls, kwargs, feature):
        dialect = FirebirdDialect((3, 0))
        data_type = data_type_cls(dialect=dialect, **kwargs)
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            dialect.format_data_type(data_type)
        assert feature in str(excinfo.value)

    def test_decfloat_flag_off_on_3_0(self):
        assert FirebirdDialect((3, 0)).supports_decfloat() is False


class TestBaseDataTypeRendering:
    @pytest.mark.parametrize("data_type_cls,kwargs,expected", [
        (IntegerType, {}, "INTEGER"),
        (BigIntType, {}, "BIGINT"),
        (SmallIntType, {}, "SMALLINT"),
        (FloatType, {}, "FLOAT"),
        (DoubleType, {}, "DOUBLE PRECISION"),
        (BooleanType, {}, "BOOLEAN"),
        (VarCharType, {"length": 50}, "VARCHAR(50)"),
        (VarCharType, {}, "VARCHAR(255)"),
        (CharType, {"length": 10}, "CHAR(10)"),
        (CharType, {}, "CHAR(1)"),
        (TextType, {}, "BLOB SUB_TYPE TEXT"),
        (DateTimeType, {}, "TIMESTAMP"),
        (TimestampType, {}, "TIMESTAMP"),
        (DateType, {}, "DATE"),
        (TimeType, {}, "TIME"),
    ])
    def test_format_data_type(self, dialect, data_type_cls, kwargs, expected):
        data_type = data_type_cls(dialect=dialect, **kwargs)
        assert dialect.format_data_type(data_type) == (expected, ())

    @pytest.mark.parametrize("kwargs,expected", [
        ({"precision": 10, "scale": 2}, "DECIMAL(10, 2)"),
        ({"precision": 18}, "DECIMAL(18)"),
        ({}, "DECIMAL"),
    ])
    def test_decimal_variants(self, dialect, kwargs, expected):
        data_type = DecimalType(dialect=dialect, **kwargs)
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
        assert dialect.parse_type("CHAR") == CharType(length=1)

    def test_parse_type_records_the_long_character_form(self, dialect):
        """The SQL long forms record themselves as the spelling that was read.

        Both are the same *concept* as their short form — one class, one type —
        and the recorded spelling is what Firebird's grammar wrote, not a
        different column.
        """
        assert dialect.parse_type("CHARACTER(5)") == CharType(
            length=5, spelling="character"
        )
        assert dialect.parse_type("CHARACTER VARYING(5)") == VarCharType(
            length=5, spelling="character varying"
        )

    def test_parse_type_character_varying_is_variable_length(self, dialect):
        """``CHARACTER VARYING`` is SQL's long form of ``VARCHAR``.

        It used to land in the fixed-length branch because the dispatch tested
        only for a leading ``VARCHAR``, so ``CHARACTER`` matched and the varying
        half was thrown away — a variable-length column parsed as
        ``CHARACTER(5)``. The class is the whole point: one concept in, one class
        out.
        """
        parsed = dialect.parse_type("CHARACTER VARYING(30)")
        assert isinstance(parsed, VarCharType)
        assert not isinstance(parsed, CharType)
        assert parsed.length == 30
        # And the fixed-length long form is still fixed-length.
        assert isinstance(dialect.parse_type("CHARACTER(30)"), CharType)

    @pytest.mark.parametrize("spelling,expected_class", [
        ("integer", IntegerType), ("int", IntegerType),
        ("tinyint", TinyIntType), ("int1", TinyIntType),
        ("smallint", SmallIntType), ("int2", SmallIntType),
        ("bigint", BigIntType), ("int8", BigIntType),
        ("char", CharType), ("character", CharType),
        ("varchar", VarCharType), ("character varying", VarCharType),
        ("text", TextType), ("clob", TextType),
        ("decimal", DecimalType), ("numeric", DecimalType), ("dec", DecimalType),
        ("double", DoubleType), ("double precision", DoubleType),
        ("boolean", BooleanType), ("bool", BooleanType),
        ("blob", BlobType), ("bytea", BlobType),
    ])
    def test_parse_type_is_canonical_over_spelling_pairs(self, dialect, spelling,
                                                         expected_class):
        """One concept in, one class out (D8).

        Two spellings of one concept must never produce two classes: a caller
        reading a schema and a caller declaring one would then be holding
        different objects for the same storage, and a schema diff between them
        would report a change that does not exist.
        """
        parsed = dialect.parse_type(spelling)
        assert type(parsed) is expected_class, spelling
        # Whatever it parsed to must render back to a column on this dialect.
        assert dialect.format_data_type(parsed)[0], spelling

    def test_parse_type_misc(self, dialect):
        assert isinstance(dialect.parse_type("BLOB SUB_TYPE TEXT"), TextType)
        assert isinstance(dialect.parse_type("DATE"), DateType)
        assert isinstance(dialect.parse_type("TIME"), TimeType)
        assert isinstance(dialect.parse_type("BOOLEAN"), BooleanType)
        # An identifier-shaped name the framework has no class for is kept, so a
        # Firebird type it does not model stays reachable.
        assert dialect.parse_type("SOMETHING_WEIRD") == CustomType(raw="SOMETHING_WEIRD")

    def test_parse_type_refuses_a_name_that_is_not_an_identifier(self, dialect):
        """A type name lands where a bound parameter cannot go, so it is
        validated rather than preserved. A space has no meaning there, and
        accepting one would put arbitrary text into the statement."""
        from rhosocial.activerecord.backend.expression.type_name import InvalidTypeNameError

        with pytest.raises(InvalidTypeNameError):
            dialect.parse_type("SOMETHING WEIRD")

    def test_parse_type_timestamp_takes_precedence_over_time(self, dialect):
        """F7 anchor: startswith("TIME") used to swallow TIMESTAMP strings."""
        parsed = dialect.parse_type("TIMESTAMP")
        assert isinstance(parsed, DateTimeType)
        assert not isinstance(parsed, TimeType)
        # Plain TIME must still parse as TimeType after the reorder.
        assert isinstance(dialect.parse_type("TIME"), TimeType)

    def test_parse_type_reaches_the_firebird_zoned_classes(self, dialect):
        """Firebird 4.0's zoned date-time types must not parse as unzoned ones.

        The catalog reports ``RDB$FIELD_TYPE`` 28 for ``TIME WITH TIME ZONE``
        and 29 for ``TIMESTAMP WITH TIME ZONE`` (language reference, D.11), and
        the introspector turns each into the words Firebird writes. Before this
        was recognised, the ``DATE``/``TIMESTAMP``/``TIME`` family matched on the
        leading word and threw the zone clause away — so a zoned column
        introspected as an unzoned one and, because the differ compares parsed
        types with ``!=``, a schema diff reported no change at all between the
        two.
        """
        assert dialect.parse_type("TIME WITH TIME ZONE") == FirebirdTimeTzType()
        assert dialect.parse_type("TIMESTAMP WITH TIME ZONE") == (
            FirebirdTimeStampTzType()
        )
        assert dialect.parse_type("timestamp with time zone") == (
            FirebirdTimeStampTzType()
        )
        # Neither is the unzoned concept it used to collapse into.
        assert dialect.parse_type("TIME WITH TIME ZONE") != dialect.parse_type("TIME")
        assert dialect.parse_type(
            "TIMESTAMP WITH TIME ZONE"
        ) != dialect.parse_type("TIMESTAMP")

    @pytest.mark.parametrize("raw", [
        "TIMESTAMP(4) WITH TIME ZONE",
        "TIME(2) WITH TIME ZONE",
        "TIME(3) WITHOUT TIME ZONE",
        "TIMESTAMP(6)",
        "TIME(6)",
        "DATE(4)",
    ])
    def test_parse_type_refuses_a_precision_the_grammar_has_no_place_for(
        self, dialect, raw
    ):
        """A precision on ``TIME``/``TIMESTAMP``/``DATE`` is not Firebird DDL.

        §3.4.2, §3.4.3 and the §3.12 Data Type Declaration Syntax give
        ``TIME [{WITHOUT | WITH} TIME ZONE]`` and ``TIMESTAMP [{WITHOUT | WITH}
        TIME ZONE]`` with no argument, in the 4.0 and 5.0 references alike.

        The parser used to accept the three zoned forms and hand back a class
        carrying the precision, whose formatter then wrote it into DDL — so
        ``parse_type`` blessed a string that ``format_data_type`` could not
        render back. And it silently accepted the bare forms too, discarding the
        ``(6)`` and returning a plain ``TIMESTAMP``: a *different column* than the
        one that was named, read as though it were the same. Both are refused now,
        with the field and the two sections named.
        """
        with pytest.raises(ValueError, match="4779"):
            dialect.parse_type(raw)

    def test_parse_type_reaches_the_spelled_out_without_zone_form(self, dialect):
        """``TIME WITHOUT TIME ZONE`` is Firebird 4.0's long form of ``TIME``.

        It has its own class and its own renderer, so parsing it as the bare
        ``TimeType`` discarded the spelling the declaration actually used.
        """
        assert dialect.parse_type("TIME WITHOUT TIME ZONE") == (
            FirebirdTimeWithoutTimeZoneType()
        )

    def test_parsed_temporal_types_render_back_exactly(self, dialect):
        """Whatever ``parse_type`` accepts must render back to those words.

        The other half of refusing the precision: having stopped parsing
        ``TIMESTAMP(4)``, nothing else may quietly widen the accepted set.
        """
        for raw in (
            "TIMESTAMP WITH TIME ZONE", "TIME WITH TIME ZONE",
            "TIME WITHOUT TIME ZONE", "TIMESTAMP", "TIME", "DATE",
        ):
            parsed = dialect.parse_type(raw)
            assert dialect.format_data_type(parsed) == (raw, ())

    @pytest.mark.parametrize("raw,zoned_class", [
        ("TIME WITH TIME ZONE", "FirebirdTimeTzType"),
        ("TIMESTAMP WITH TIME ZONE", "FirebirdTimeStampTzType"),
        ("TIME WITHOUT TIME ZONE", "FirebirdTimeWithoutTimeZoneType"),
    ])
    def test_parse_type_zoned_spellings_need_firebird_4(self, raw, zoned_class):
        """Firebird 3 has no zoned date-time type, so a 3.0 dialect must not
        name one — but it must not quietly answer with the unzoned class either.

        Handing back ``TimeType`` would render a *different* column than the one
        that was read, with nothing to say why; ``CustomType`` keeps the
        declaration verbatim instead.
        """
        parsed = FirebirdDialect((3, 0, 0)).parse_type(raw)
        assert type(parsed) is CustomType
        assert parsed.raw == raw
        assert zoned_class != type(parsed).__name__


class TestFirebird4CatalogCodesOffline:
    """``FB_FIELD_TYPES`` → ``parse_type`` → rendered SQL, with no database.

    Documentation-based, not measured: ``fbclient`` is not installed on this
    machine, so no row was ever read from ``RDB$FIELDS``. The authority is the
    Firebird 4.0 language reference, D.11 ``RDB$FIELDS``, whose ``RDB$FIELD_TYPE``
    (and ``RDB$EXTERNAL_TYPE``, with the same codes) reads:

        23 - BOOLEAN      24 - DECFLOAT(16)   25 - DECFLOAT(34)
        26 - INT128       27 - DOUBLE PRECISION

    Two of those codes were unmapped, or mapped to the unqualified word
    ``DECFLOAT``, which is how a ``DECFLOAT(16)`` column and a ``DECFLOAT(34)``
    one came to compare equal.
    """

    @staticmethod
    def _field_types():
        from rhosocial.activerecord.backend.impl.firebird.introspection.async_introspector import (
            FB_FIELD_TYPES,
        )
        return FB_FIELD_TYPES

    @pytest.mark.parametrize("code,expected", [
        (24, "DECFLOAT(16)"),
        (25, "DECFLOAT(34)"),
        (26, "INT128"),
        (28, "TIME WITH TIME ZONE"),
        (29, "TIMESTAMP WITH TIME ZONE"),
    ])
    def test_code_to_name(self, code, expected):
        assert self._field_types()[code] == expected

    @pytest.mark.parametrize("code", [24, 25, 26, 28, 29])
    def test_code_to_render_is_the_identity(self, dialect, code):
        """Every FB4 code this table knows re-renders as the words it was read as.

        The chain an introspected column actually travels: the catalog reports a
        code, this table turns it into words, ``parse_type`` turns the words into
        a class, and the class renders those words. A break at any link produces
        DDL that does not match the database.
        """
        type_name = self._field_types()[code]
        assert dialect.format_data_type(dialect.parse_type(type_name)) == (
            type_name, ()
        )

    def test_the_two_decfloat_widths_are_not_one_column(self, dialect):
        """16 significant digits and 34 are different columns, not spellings.

        ``FirebirdDecFloatType.PARAMETERS`` is ``("precision",)``, so the value
        object already called them different; the introspector is what has to keep
        that true by writing the width into the name it reports.
        """
        field_types = self._field_types()
        assert field_types[24] != field_types[25]
        assert dialect.parse_type(field_types[24]) != dialect.parse_type(
            field_types[25]
        )
        assert dialect.format_data_type(dialect.parse_type(field_types[24]))[0] != (
            dialect.format_data_type(dialect.parse_type(field_types[25]))[0]
        )

    def test_int128_is_not_folded_into_bigint(self, dialect):
        assert type(dialect.parse_type(self._field_types()[26])) is FirebirdInt128Type
        assert dialect.parse_type(self._field_types()[26]) != BigIntType()

    def test_decfloat_is_not_folded_into_decimal(self, dialect):
        """``DECFLOAT`` and ``NUMERIC`` are both "decimal" and are different types.

        ``DecimalType`` has a scale rule and a 1..18 precision range;
        ``DECFLOAT`` has an exponent and 16 or 34 significant digits.
        """
        assert type(dialect.parse_type(self._field_types()[25])) is (
            FirebirdDecFloatType
        )
        assert dialect.parse_type(self._field_types()[25]) != DecimalType(
            precision=34
        )

    @pytest.mark.parametrize("raw", ["DECFLOAT(16)", "DECFLOAT(34)", "INT128"])
    def test_codes_need_firebird_4(self, raw):
        """One gate, the same one the renderers use.

        A Firebird 3 server never reports 24/25/26, so this branch is about the
        parser agreeing with the formatters rather than about a column that can
        occur — and the agreement is what keeps a 3.0 dialect from answering with
        a narrower *real* type, which would render a different column silently.
        """
        dialect = FirebirdDialect((3, 0))
        parsed = dialect.parse_type(raw)
        assert type(parsed) is CustomType
        assert parsed.raw == raw
        assert dialect.supports_data_type_firebird_decfloat() is False
        assert dialect.supports_data_type_firebird_int128() is False

    def test_a_bare_decfloat_precision_is_the_documented_default(self, dialect):
        """``DECFLOAT`` alone is legal Firebird; ``dec_prec`` defaults to 34."""
        parsed = dialect.parse_type("DECFLOAT")
        assert isinstance(parsed, FirebirdDecFloatType)
        assert parsed.precision == 34

    def test_an_unlisted_decfloat_width_is_not_rounded(self, dialect):
        """The dialect must not pick a width the declaration never named."""
        with pytest.raises(ValueError, match="16 or 34"):
            dialect.parse_type("DECFLOAT(20)")


class TestFloatAndBlobSubTypeIdentityBranches:
    """The identity fields Firebird either cannot or must not write.

    Documentation-based, not measured. ``fbclient`` is not installed on this
    machine, so no server confirmed any of these facts; the authorities are the
    Firebird 4.0 and 5.0 language references — chapter 3, §3.1 Integer Data Types
    ("Firebird does not support an unsigned integer data type"), §3.2.1.1 /
    §3.12 for ``FLOAT(bin_prec)``, and §3.4.2 / §3.4.3 / §3.12 for the
    date-time declarations that take no precision — plus Firebird 4.0 release
    notes CORE-6109 for the ``FLOAT(p)`` meaning change.
    """

    def test_float_precision_branch(self):
        dialect = FirebirdDialect((4, 0))
        assert dialect.format_data_type(FloatType()) == ("FLOAT", ())
        assert dialect.format_data_type(
            FirebirdFloatType(precision=24)
        ) == ("FLOAT(24)", ())
        # 25..53 is the documented double-precision half, not an error:
        # "1 - 24: 32-bit single precision; 25 - 53: 64-bit double precision"
        # (§3.2.1.1, Table 3.2). The generic ``FloatType`` renderer used to
        # reject it while this one accepted it.
        assert dialect.format_data_type(FloatType(precision=53)) == ("FLOAT(53)", ())
        assert dialect.format_data_type(
            FirebirdFloatType(precision=53)
        ) == ("FLOAT(53)", ())

    def test_float_precision_branch_is_closed_below_firebird_4(self):
        """Both renderers, because the 3.0 ``FLOAT(p)`` counted decimal digits.

        CORE-6109: ``FLOAT(p)`` became binary-precision in 4.0, and the 3.0
        reference's declaration syntax is ``FLOAT | DOUBLE PRECISION`` with no
        argument at all — so the same text names different columns either side of
        that boundary and neither renderer may write it without knowing which
        server is there.
        """
        for data_type in (FloatType(precision=24), FirebirdFloatType(precision=24)):
            with pytest.raises(UnsupportedFeatureError, match="FLOAT"):
                FirebirdDialect((3, 0)).format_data_type(data_type)

    @pytest.mark.parametrize("cls", [TimeType, TimestampType, DateTimeType])
    def test_temporal_precision_branch_is_closed(self, cls):
        """No Firebird ``TIME``/``TIMESTAMP``/``DATE`` declaration takes one.

        §3.4.2, §3.4.3 and §3.12 give the productions with no argument, while
        fractional seconds are stored to ten-thousandths of a second whatever the
        declaration says. ``precision`` is in each concept's ``PARAMETERS``, so
        dropping it would render two declarations the framework calls different
        columns as the same SQL while reporting success.
        """
        with pytest.raises(UnsupportedFeatureError, match="precision"):
            FirebirdDialect((4, 0)).format_data_type(cls(precision=6))
        # precision=None is the ordinary case and renders unchanged.
        assert FirebirdDialect((4, 0)).format_data_type(cls()) == (
            FirebirdDialect((4, 0)).format_data_type(cls(precision=None))
        )

    def test_blob_sub_type_declares_no_identity(self):
        assert FirebirdBlobSubType.PARAMETERS == ()
        assert FirebirdBlobSubType().identity() == ()

    def test_blob_sub_type_unsigned_branch_is_closed(self):
        dialect = FirebirdDialect((4, 0))
        with pytest.raises(UnsupportedFeatureError, match="UNSIGNED"):
            dialect.format_data_type(FirebirdBlobSubType(unsigned=True))

    @pytest.mark.parametrize("cls", [
        TinyIntType, SmallIntType, IntegerType, BigIntType,
    ])
    def test_core_integer_unsigned_branch_is_closed(self, cls):
        with pytest.raises(UnsupportedFeatureError, match="UNSIGNED"):
            FirebirdDialect((4, 0)).format_data_type(cls(unsigned=True))


class TestReturningBranches:
    def test_insert_returning_snapshot(self, dialect):
        insert = InsertExpression(
            dialect, Table(dialect, "users"),
            ValuesSource(dialect, [[E.RawSQLExpression(dialect, "?")]]),
            columns=["name"],
            returning=ReturningClause(dialect, expressions=[E.Column(dialect, "id"), E.Column(dialect, "name")]),
        )
        assert insert.to_sql() == ('INSERT INTO "USERS" ("NAME") VALUES (?) RETURNING "ID", "NAME"', ())

    def test_insert_without_returning_has_no_clause(self, dialect):
        insert = InsertExpression(
            dialect, Table(dialect, "users"),
            ValuesSource(dialect, [[E.Literal(dialect, "Bob")]]),
            columns=["name"],
        )
        assert insert.to_sql() == ('INSERT INTO "USERS" ("NAME") VALUES (?)', ("Bob",))

    def test_update_returning_snapshot(self, dialect):
        update = UpdateExpression(
            dialect, Table(dialect, "users"), {"name": E.Literal(dialect, "Bob")},
            where=E.ComparisonPredicate(dialect, "=", E.Column(dialect, "id"), E.Literal(dialect, 7)),
            returning=ReturningClause(dialect, expressions=[E.Column(dialect, "id")]),
        )
        assert update.to_sql() == (
            'UPDATE "USERS" SET "NAME" = ? WHERE "ID" = ? RETURNING "ID"',
            ("Bob", 7),
        )

    def test_delete_returning_wildcard_snapshot(self, dialect):
        delete = DeleteExpression(
            dialect, Table(dialect, "users"),
            where=E.ComparisonPredicate(dialect, "=", E.Column(dialect, "id"), E.Literal(dialect, 7)),
            returning=ReturningClause(dialect, expressions=[E.RawSQLExpression(dialect, "*")]),
        )
        assert delete.to_sql() == ('DELETE FROM "USERS" WHERE "ID" = ? RETURNING *', (7,))

    def test_update_or_insert_with_matching_and_returning(self, dialect):
        expr = UpdateOrInsertExpression(
            dialect,
            Table(dialect, "users"),
            ["name", "age"],
            ["Ann", 30],
            ["name"],
            returning_columns=["id"],
        )
        sql, params = expr.to_sql()
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
        ((4, 0, 0), {"nowait": True}, "FOR UPDATE WITH LOCK"),
    ])
    def test_for_update_expression_snapshots(self, version, kwargs, expected):
        dialect = FirebirdDialect(version)
        assert ForUpdateClause(dialect, **kwargs).to_sql() == (expected, ())


class TestSequenceBranches:
    def test_create_sequence_defaults(self, dialect):
        expr = CreateSequenceExpression(dialect, Sequence(dialect, "seq_a"))
        assert dialect.format_create_sequence_statement(expr) == (
            'CREATE SEQUENCE "SEQ_A"', ()
        )

    def test_create_sequence_start_and_increment(self, dialect):
        expr = CreateSequenceExpression(
            dialect, Sequence(dialect, "seq_b"), start=100, increment=5
        )
        assert dialect.format_create_sequence_statement(expr) == (
            'CREATE SEQUENCE "SEQ_B" START WITH 100 INCREMENT BY 5', ()
        )

    def test_create_sequence_explicit_defaults_are_omitted(self, dialect):
        """A request for the defaults is the same SQL as omitting them."""
        expr = CreateSequenceExpression(
            dialect, Sequence(dialect, "seq_d"), start=1, increment=1
        )
        assert dialect.format_create_sequence_statement(expr) == (
            'CREATE SEQUENCE "SEQ_D"', ()
        )

    def test_create_sequence_explicit_zero_start_is_kept(self, dialect):
        """``START WITH 0`` is a real request, not a missing value.

        The old ``getattr(expr, 'start', None) or 1`` treated ``0`` as absent
        and silently fell back to the default, which changes the sequence's
        first value.
        """
        expr = CreateSequenceExpression(dialect, Sequence(dialect, "seq_e"), start=0)
        assert dialect.format_create_sequence_statement(expr) == (
            'CREATE SEQUENCE "SEQ_E" START WITH 0', ()
        )

    def test_create_generator_form(self, dialect):
        expr = CreateSequenceExpression(dialect, Sequence(dialect, "gen_c"))
        expr.use_generator = True
        assert dialect.format_create_sequence_statement(expr) == (
            'CREATE GENERATOR "GEN_C"', ()
        )

    def test_create_generator_accepts_start_and_increment(self, dialect):
        """The legacy spelling takes the same two clauses as the standard one."""
        expr = CreateSequenceExpression(
            dialect, Sequence(dialect, "gen_d"), start=7, increment=3
        )
        expr.use_generator = True
        assert dialect.format_create_sequence_statement(expr) == (
            'CREATE GENERATOR "GEN_D" START WITH 7 INCREMENT BY 3', ()
        )

    @pytest.mark.parametrize("kwargs,feature", [
        ({"if_not_exists": True}, "CREATE SEQUENCE IF NOT EXISTS"),
        ({"minvalue": 1}, "SEQUENCE MINVALUE"),
        ({"maxvalue": 10}, "SEQUENCE MAXVALUE"),
        ({"cycle": True}, "SEQUENCE CYCLE"),
        ({"no_cycle": True}, "SEQUENCE CYCLE"),
        ({"cache": 10}, "SEQUENCE CACHE"),
        ({"no_cache": True}, "SEQUENCE CACHE"),
        ({"order": True}, "SEQUENCE ORDER"),
        ({"no_order": True}, "SEQUENCE ORDER"),
        ({"owned_by": "t.id"}, "SEQUENCE OWNED BY"),
    ])
    def test_unsupported_create_option_is_refused_not_dropped(
        self, dialect, kwargs, feature
    ):
        """Both spellings of every pair are refused by name, never dropped."""
        expr = CreateSequenceExpression(
            dialect, Sequence(dialect, "seq_f"), **kwargs
        )
        with pytest.raises(UnsupportedFeatureError) as exc_info:
            dialect.format_create_sequence_statement(expr)
        assert feature in str(exc_info.value)

    def test_gen_id_step(self, dialect):
        assert GenIdExpression(dialect, "gen_c", 2).to_sql() == ('GEN_ID("GEN_C", 2)', ())

    def test_next_value_for(self, dialect):
        assert NextValueForExpression(dialect, "seq_b").to_sql() == ('NEXT VALUE FOR "SEQ_B"', ())

    def test_sequence_capability_flags(self, dialect):
        assert dialect.supports_sequence() is True
        assert dialect.supports_create_sequence() is True
        assert dialect.supports_drop_sequence() is True
        assert dialect.supports_alter_sequence() is True
        assert dialect.supports_create_generator() is True

    def test_sequence_option_probes(self, dialect):
        """Firebird's grammar has ``START WITH`` and ``INCREMENT`` only."""
        assert dialect.supports_sequence_start() is True
        assert dialect.supports_sequence_increment() is True
        for probe in (
            dialect.supports_sequence_if_not_exists,
            dialect.supports_sequence_if_exists,
            dialect.supports_sequence_minvalue,
            dialect.supports_sequence_maxvalue,
            dialect.supports_sequence_cycle,
            dialect.supports_sequence_cache,
            dialect.supports_sequence_order,
            dialect.supports_sequence_owned_by,
        ):
            assert probe() is False

    def test_sequence_version_gate(self):
        """This backend declares sequence support from Firebird 3.0.

        The ``SEQUENCE`` spelling itself is older (2.5 already lists it as a
        synonym for ``GENERATOR``); the gate follows the declared floor.
        """
        assert FirebirdDialect((2, 5, 0)).supports_sequence() is False
        assert FirebirdDialect((2, 5, 0)).supports_create_sequence() is False
        assert FirebirdDialect((2, 5, 0)).supports_alter_sequence() is False
        assert FirebirdDialect((3, 0, 0)).supports_sequence() is True
        assert FirebirdDialect((4, 0, 0)).supports_sequence() is True
        assert FirebirdDialect((5, 0, 0)).supports_sequence() is True

    def test_sequence_version_gate_refuses_the_render(self):
        dialect = FirebirdDialect((2, 5, 0))
        expr = CreateSequenceExpression(dialect, Sequence(dialect, "seq_g"))
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_create_sequence_statement(expr)

    def test_create_sequence_dispatches_to_the_firebird_formatter(self, dialect):
        """The dispatched name resolves to this backend, not core or a protocol.

        ``FirebirdSequenceMixin`` precedes ``SequenceMixin`` and the
        ``CreateSequenceSupport`` protocol in the bases, so the method the
        expression dispatches to is the Firebird one. A protocol body or the
        core formatter would both satisfy ``getattr``, so the identity is pinned
        rather than the name merely existing.
        """
        from rhosocial.activerecord.backend.impl.firebird.mixins.sequence import (
            FirebirdSequenceMixin,
        )

        assert (
            type(dialect).format_create_sequence_statement
            is FirebirdSequenceMixin.format_create_sequence_statement
        )

    def test_old_undispatched_name_is_gone(self, dialect):
        """``format_create_sequence`` was reachable by nothing and is deleted."""
        assert not hasattr(dialect, "format_create_sequence")

    def test_drop_and_alter_render_through_core(self, dialect):
        """Firebird has no local drop/alter formatter; core's render its grammar.

        Both clauses core emits here are the ones Firebird's ``ALTER SEQUENCE``
        grammar has (``RESTART [WITH]`` and ``INCREMENT [BY]``); ``DROP
        SEQUENCE`` takes no options, which is why the ``IF EXISTS`` probe is
        False and a request for it raises rather than being dropped.
        """
        assert DropSequenceExpression(dialect, Sequence(dialect, "seq_h")).to_sql() == (
            'DROP SEQUENCE "SEQ_H"', ()
        )
        assert AlterSequenceExpression(
            dialect, Sequence(dialect, "seq_h"), restart=5, increment=2
        ).to_sql() == (
            'ALTER SEQUENCE "SEQ_H" RESTART WITH 5 INCREMENT BY 2', ()
        )


class TestCreateTableRebuildSnapshots:
    def test_basic_table(self, dialect):
        expr = CreateTableExpression(dialect, Table(dialect, "users"), [
            _column(dialect, "id", IntegerType(dialect), ColumnConstraint(dialect, ColumnConstraintType.PRIMARY_KEY)),
            _column(dialect, "name", VarCharType(length=100, dialect=dialect)),
        ])
        assert expr.to_sql() == (
            'CREATE TABLE "USERS" ("ID" INTEGER PRIMARY KEY, "NAME" VARCHAR(100))', ()
        )

    @pytest.mark.parametrize("on_commit_delete,expected_tail", [
        (True, 'ON COMMIT DELETE ROWS'),
        (False, 'ON COMMIT PRESERVE ROWS'),
    ])
    def test_global_temporary_table(self, dialect, on_commit_delete, expected_tail):
        expr = CreateTableExpression(dialect, Table(dialect, "tmp_t"), [_column(dialect, "id", IntegerType(dialect))], temporary=True)
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
        expr = CreateTableExpression(dialect, Table(dialect, "gt_a"), [_column(dialect, "id", IntegerType(dialect))], temporary=True)
        expr.on_commit_delete = on_commit_delete
        assert expr.to_sql() == (expected, ())

    def test_if_not_exists_raises_when_unsupported(self, dialect):
        """F6 anchor: Firebird lacks IF NOT EXISTS on CREATE TABLE.

        Previously the clause was rendered unconditionally; it must now be
        rejected through supports_if_not_exists_table().
        """
        expr = CreateTableExpression(
            dialect,
            Table(dialect, "tbl_c"),
            [_column(dialect, "id", IntegerType(dialect))],
            if_not_exists=True,
        )
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            expr.to_sql()
        assert "IF NOT EXISTS" in str(excinfo.value)

    def test_if_not_exists_renders_when_capability_present(self, dialect):
        expr = CreateTableExpression(
            dialect,
            Table(dialect, "tbl_c"),
            [_column(dialect, "id", IntegerType(dialect))],
            if_not_exists=True,
        )
        from unittest import mock
        with mock.patch.object(FirebirdDialect, "supports_if_not_exists_table", return_value=True):
            sql, _ = expr.to_sql()
        assert sql.startswith('CREATE TABLE IF NOT EXISTS "TBL_C"')

    def test_external_file_clause(self, dialect):
        expr = CreateTableExpression(dialect, Table(dialect, "ext_t"), [_column(dialect, "id", IntegerType(dialect))])
        expr.external_file = "/data/ext.fdb"
        assert expr.to_sql() == ('CREATE TABLE "EXT_T" ("ID" INTEGER) EXTERNAL FILE \'/data/ext.fdb\'', ())

    def test_computed_by_column(self, dialect):
        col = _column(dialect, "full_name", VarCharType(length=200, dialect=dialect))
        col.computed_by = '"FIRST_NAME" || \' \' || "LAST_NAME"'
        assert CreateTableExpression(dialect, Table(dialect, "emp"), [col]).to_sql() == (
            'CREATE TABLE "EMP" '
            '("FULL_NAME" VARCHAR(200) COMPUTED BY ("FIRST_NAME" || \' \' || "LAST_NAME"))',
            (),
        )

    def test_identity_with_start_and_increment(self, dialect):
        from rhosocial.activerecord.base import IdentityAttribute

        col = _column(dialect, "id", IntegerType(dialect))
        col.attributes = [IdentityAttribute(generation="ALWAYS", start=1000, increment=10)]
        assert CreateTableExpression(dialect, Table(dialect, "ident_t"), [col]).to_sql() == (
            'CREATE TABLE "IDENT_T" '
            '("ID" INTEGER GENERATED ALWAYS AS IDENTITY (START WITH 1000 INCREMENT BY 10))',
            (),
        )

    def test_auto_increment_constraint_flag(self, dialect):
        col = _column(
            dialect, "id", IntegerType(dialect),
            ColumnConstraint(dialect, ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True),
        )
        assert CreateTableExpression(dialect, Table(dialect, "autoinc"), [col]).to_sql() == (
            'CREATE TABLE "AUTOINC" ("ID" INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY)', ()
        )

    def test_string_default_escaped_and_ordered_before_not_null(self, dialect):
        col = _column(
            dialect, "status", VarCharType(length=20, dialect=dialect),
            ColumnConstraint(dialect, ColumnConstraintType.DEFAULT, default_value="O'Brien"),
            ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL),
        )
        assert CreateTableExpression(dialect, Table(dialect, "t5"), [col]).to_sql() == (
            "CREATE TABLE \"T5\" (\"STATUS\" VARCHAR(20) DEFAULT 'O''Brien' NOT NULL)", ()
        )

    def test_expression_default_contributes_params(self, dialect):
        col = _column(
            dialect,
            "created_at",
            DateTimeType(dialect=dialect),
            ColumnConstraint(
                dialect,
                ColumnConstraintType.DEFAULT,
                default_value=E.Literal(dialect, "CURRENT_TIMESTAMP"),
            ),
        )
        assert CreateTableExpression(dialect, Table(dialect, "t5b"), [col]).to_sql() == (
            'CREATE TABLE "T5B" ("CREATED_AT" TIMESTAMP DEFAULT ?)', ("CURRENT_TIMESTAMP",)
        )

    def test_numeric_default_with_explicit_null(self, dialect):
        col = _column(
            dialect, "amount", DecimalType(precision=18, scale=2, dialect=dialect),
            ColumnConstraint(dialect, ColumnConstraintType.DEFAULT, default_value=0),
            ColumnConstraint(dialect, ColumnConstraintType.NULL),
        )
        assert CreateTableExpression(dialect, Table(dialect, "t5c"), [col]).to_sql() == (
            'CREATE TABLE "T5C" ("AMOUNT" DECIMAL(18, 2) DEFAULT 0 NULL)', ()
        )

    def test_table_constraints_snapshot(self, dialect):
        fk = ForeignKeyConstraint(
            dialect, name="fk_order_customer", columns=["customer_id"],
            foreign_key_table=Table(dialect, "customers"), foreign_key_columns=["id"],
            on_delete=ReferentialAction.CASCADE, on_update=ReferentialAction.SET_NULL,
        )
        unique = TableConstraint(dialect, TableConstraintType.UNIQUE, name="uq_email", columns=["email"])
        pk = TableConstraint(dialect, TableConstraintType.PRIMARY_KEY, columns=["id"])
        check = TableConstraint(
            dialect, TableConstraintType.CHECK,
            check_condition=E.ComparisonPredicate(dialect, ">=", E.Column(dialect, "amount"), E.Literal(dialect, 0)),
        )
        expr = CreateTableExpression(
            dialect, Table(dialect, "orders"),
            [
                _column(dialect, "id", IntegerType(dialect)),
                _column(dialect, "customer_id", IntegerType(dialect)),
                _column(dialect, "email", VarCharType(length=255, dialect=dialect)),
                 _column(dialect, "amount", DecimalType(precision=18, scale=2, dialect=dialect)),
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
        expr = CreateTableExpression(dialect, Table(dialect, "pt"), [_column(dialect, "id", IntegerType(dialect))], partition=partition)
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            expr.to_sql()
        assert "PARTITION BY clause" in str(excinfo.value)
