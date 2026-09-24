# tests/rhosocial/activerecord_firebird_test/feature/backend/test_domain_expression.py
"""SQL unit coverage for Firebird DOMAIN expressions and capabilities."""

import pytest
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.dialect.mixins import DomainMixin, UserDefinedTypeMixin
from rhosocial.activerecord.backend.dialect.protocols import DomainSupport, UserDefinedTypeSupport
from rhosocial.activerecord.backend.expression import Literal
from rhosocial.activerecord.backend.expression.serialization import (
    ExpressionRegistry,
    deserialize,
    deserialize_json,
    deserialize_xml,
    serialize,
    serialize_json,
    serialize_xml,
)
from rhosocial.activerecord.backend.expression.statements import (
    AddDomainCheckAction,
    AlterDomainExpression,
    CreateDomainExpression,
    DomainCheckConstraint,
    DomainNullability,
    DomainValueExpression,
    DropDomainCheckAction,
    DropDomainDefaultAction,
    DropDomainExpression,
    DropDomainNotNullAction,
    RenameDomainAction,
    SetDomainDefaultAction,
    SetDomainNotNullAction,
)
from rhosocial.activerecord.backend.expression.types import (
    ArrayType,
    DecimalType,
    IntegerType,
    VarCharType,
)
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.expression import (
    FirebirdAlterDomainExpression,
    FirebirdCreateDomainExpression,
    FirebirdDomainAlterMode,
    FirebirdDropDomainExpression,
    FirebirdSetDomainDataTypeAction,
)
from rhosocial.activerecord.backend.impl.firebird.expression.types import (
    FirebirdBlobSubType,
    FirebirdCharType,
    FirebirdDecFloatType,
    FirebirdDecimalType,
    FirebirdDoubleType,
    FirebirdFloatType,
    FirebirdInt128Type,
    FirebirdTimeStampTzType,
    FirebirdTimeWithoutTimeZoneType,
    FirebirdTimeTzType,
    FirebirdVarCharType,
)
from rhosocial.activerecord.backend.impl.firebird.mixins.domain import FirebirdDomainMixin
from rhosocial.activerecord.backend.impl.firebird.protocols import FirebirdDomainSupport
from rhosocial.activerecord.backend.impl.sqlite.dialect import SQLiteDialect


def _check(dialect, condition, *, name=None):
    return DomainCheckConstraint(dialect, condition, name=name)


def _positive_check(dialect):
    return _check(dialect, DomainValueExpression(dialect) > Literal(dialect, 0, inline_literals=True))


class TestCreateDomain:
    def test_legacy_expression_delegates_to_core_model(self):
        dialect = FirebirdDialect((4, 0, 0))
        expression = FirebirdCreateDomainExpression(
            dialect,
            "salary_range",
            DecimalType(precision=10, scale=2),
            default=0,
            not_null=True,
            check="VALUE >= 0",
            collation="UNICODE_FS",
        )

        assert isinstance(expression, CreateDomainExpression)
        assert expression.to_sql() == (
            'CREATE DOMAIN "SALARY_RANGE" AS DECIMAL(10, 2) DEFAULT 0 NOT NULL '
            'CHECK (VALUE >= 0) COLLATE "UNICODE_FS"'
        )

    def test_core_expression_uses_firebird_clause_order(self):
        dialect = FirebirdDialect((5, 0, 0))
        condition = DomainValueExpression(dialect) > Literal(dialect, 0, inline_literals=True)
        expression = CreateDomainExpression(
            dialect,
            "positive_code",
            VarCharType(length=8),
            default=Literal(dialect, "A", inline_literals=True),
            nullability=DomainNullability.NOT_NULL,
            checks=[_check(dialect, condition)],
            collation="UNICODE_FS",
        )

        assert expression.to_sql() == (
            'CREATE DOMAIN "POSITIVE_CODE" AS VARCHAR(8) DEFAULT \'A\' NOT NULL '
            'CHECK (VALUE > 0) COLLATE "UNICODE_FS"'
        )

    def test_minimal_create(self):
        dialect = FirebirdDialect((4, 0, 0))
        expression = FirebirdCreateDomainExpression(
            dialect,
            "amount",
            DecimalType(precision=10, scale=2),
        )

        assert expression.to_sql() == (
            'CREATE DOMAIN "AMOUNT" AS DECIMAL(10, 2)'
        )

    def test_create_rebinds_cross_dialect_data_type(self):
        dialect = FirebirdDialect((4, 0, 0))
        sqlite = SQLiteDialect(version=(3, 45, 0))
        expression = FirebirdCreateDomainExpression(
            dialect,
            "ratio",
            FirebirdDecFloatType(sqlite, precision=16),
        )

        assert expression.to_sql() == ('CREATE DOMAIN "RATIO" AS DECFLOAT(16)', ())

    def test_named_check_fails_fast(self):
        dialect = FirebirdDialect((4, 0, 0))
        expression = CreateDomainExpression(
            dialect,
            "positive",
            IntegerType(dialect),
            checks=[
                _check(
                    dialect,
                    DomainValueExpression(dialect) > Literal(dialect, 0, inline_literals=True),
                    name="positive_check",
                )
            ],
        )

        with pytest.raises(UnsupportedFeatureError, match="named DOMAIN CHECK"):
            expression.to_sql()

    def test_multiple_checks_fail_fast(self):
        dialect = FirebirdDialect((4, 0, 0))
        expression = CreateDomainExpression(
            dialect,
            "bounded",
            IntegerType(dialect),
            checks=[_positive_check(dialect), _positive_check(dialect)],
        )

        with pytest.raises(UnsupportedFeatureError, match="multiple domain CHECK"):
            expression.to_sql()

    def test_explicit_null_is_not_rendered(self):
        dialect = FirebirdDialect((4, 0, 0))
        expression = CreateDomainExpression(
            dialect,
            "nullable",
            IntegerType(dialect),
            nullability=DomainNullability.NULLABLE,
        )

        with pytest.raises(UnsupportedFeatureError, match="DOMAIN NULL"):
            expression.to_sql()

    def test_empty_legacy_check_is_not_dropped(self):
        dialect = FirebirdDialect((4, 0, 0))

        with pytest.raises(ValueError, match="non-empty SQL predicate"):
            FirebirdCreateDomainExpression(
                dialect,
                "invalid_check",
                IntegerType(dialect),
                check=" ",
            )


class TestAlterDomain:
    def test_legacy_modes_render_core_actions(self):
        dialect = FirebirdDialect((4, 0, 0))
        cases = (
            (FirebirdDomainAlterMode.SET_DEFAULT, {"value": 7}, 'ALTER DOMAIN "D" SET DEFAULT 7'),
            (FirebirdDomainAlterMode.DROP_DEFAULT, {}, 'ALTER DOMAIN "D" DROP DEFAULT'),
            (FirebirdDomainAlterMode.SET_NOT_NULL, {}, 'ALTER DOMAIN "D" SET NOT NULL'),
            (FirebirdDomainAlterMode.DROP_NOT_NULL, {}, 'ALTER DOMAIN "D" DROP NOT NULL'),
            (
                FirebirdDomainAlterMode.ADD_CONSTRAINT,
                {"constraint_sql": "VALUE > 0"},
                'ALTER DOMAIN "D" ADD CHECK (VALUE > 0)',
            ),
            (
                FirebirdDomainAlterMode.DROP_CONSTRAINT,
                {},
                'ALTER DOMAIN "D" DROP CONSTRAINT',
            ),
            (
                FirebirdDomainAlterMode.SET_TYPE,
                {"data_type": VarCharType(length=12)},
                'ALTER DOMAIN "D" TYPE VARCHAR(12)',
            ),
        )

        for mode, fields, expected in cases:
            expression = FirebirdAlterDomainExpression(dialect, "d", mode, **fields)
            assert isinstance(expression, AlterDomainExpression)
            assert expression.to_sql() == expected

    def test_unbound_data_type_is_bound_to_firebird(self):
        dialect = FirebirdDialect((4, 0, 0))
        action = FirebirdSetDomainDataTypeAction(dialect, VarCharType(length=12))

        assert action.to_sql() == ("TYPE VARCHAR(12)", ())

    def test_cross_dialect_data_type_is_rebound_to_firebird(self):
        dialect = FirebirdDialect((4, 0, 0))
        sqlite = SQLiteDialect(version=(3, 45, 0))
        action = FirebirdSetDomainDataTypeAction(
            dialect,
            FirebirdDecFloatType(sqlite, precision=16),
        )

        assert action.to_sql() == ("TYPE DECFLOAT(16)", ())

    def test_unsupported_cross_dialect_data_type_fails(self):
        dialect = FirebirdDialect((4, 0, 0))
        sqlite = SQLiteDialect(version=(3, 45, 0))
        action = FirebirdSetDomainDataTypeAction(
            dialect,
            ArrayType(sqlite, IntegerType(sqlite), dimensions=1),
        )

        with pytest.raises(TypeError, match="generic type 'array'"):
            action.to_sql()

    def test_legacy_data_type_name_api_is_preserved(self):
        dialect = FirebirdDialect((4, 0, 0))
        action = FirebirdSetDomainDataTypeAction(dialect, "VARCHAR(20)")
        expression = FirebirdAlterDomainExpression(
            dialect,
            "d",
            FirebirdDomainAlterMode.SET_TYPE,
            data_type_name="DECIMAL(10, 2)",
        )

        assert action.to_sql() == ("TYPE VARCHAR(20)", ())
        assert expression.to_sql() == ('ALTER DOMAIN "D" TYPE DECIMAL(10, 2)', ())

    @pytest.mark.parametrize(
        "data_type_name",
        (
            "INTEGER; DROP DOMAIN D",
            "INTEGER DROP DOMAIN D",
            "VARCHAR(20) EXTRA",
            "VARCHAR(20) CHARACTER SET UTF8 DROP DOMAIN D",
            "DROP",
        ),
    )
    def test_data_type_name_rejects_unsafe_syntax(self, data_type_name):
        dialect = FirebirdDialect((4, 0, 0))

        with pytest.raises(ValueError, match="data_type_name"):
            FirebirdSetDomainDataTypeAction(
                dialect,
                data_type_name=data_type_name,
            )

    @pytest.mark.parametrize(
        ("data_type_name", "expected"),
        (
            ("INT", "TYPE INTEGER"),
            ("NUMERIC(10, 2)", "TYPE DECIMAL(10, 2)"),
            ("DOUBLE PRECISION", "TYPE DOUBLE PRECISION"),
            ("BLOB SUB_TYPE TEXT", "TYPE BLOB SUB_TYPE TEXT"),
            (
                "VARCHAR(40) CHARACTER SET UTF8",
                "TYPE VARCHAR(40) CHARACTER SET UTF8",
            ),
            ("CHAR(5) CHARACTER SET UTF8", "TYPE CHAR(5) CHARACTER SET UTF8"),
            ("APP.MY_DOMAIN", "TYPE APP.MY_DOMAIN"),
        ),
    )
    def test_legal_data_type_names_map_to_firebird_types(
        self,
        data_type_name,
        expected,
    ):
        dialect = FirebirdDialect((4, 0, 0))
        action = FirebirdSetDomainDataTypeAction(
            dialect,
            data_type_name=data_type_name,
        )

        assert action.to_sql() == (expected, ())

    @pytest.mark.parametrize(
        ("data_type_name", "expected"),
        (
            ("DECFLOAT", "TYPE DECFLOAT(16)"),
            ("DECFLOAT(16)", "TYPE DECFLOAT(16)"),
            ("INT128", "TYPE INT128"),
            ("TIME WITH TIME ZONE", "TYPE TIME WITH TIME ZONE"),
            ("TIMESTAMP WITH TIME ZONE", "TYPE TIMESTAMP WITH TIME ZONE"),
            ("TIME WITHOUT TIME ZONE", "TYPE TIME WITHOUT TIME ZONE"),
            ("TIME(6) WITHOUT TIME ZONE", "TYPE TIME(6) WITHOUT TIME ZONE"),
            (
                "TIMESTAMP(6) WITH TIME ZONE",
                "TYPE TIMESTAMP(6) WITH TIME ZONE",
            ),
        ),
    )
    def test_firebird_4_data_type_names_are_version_gated(
        self,
        data_type_name,
        expected,
    ):
        action = FirebirdSetDomainDataTypeAction(
            FirebirdDialect((3, 0, 0)),
            data_type_name=data_type_name,
        )

        with pytest.raises(UnsupportedFeatureError):
            action.to_sql()

        firebird_4 = FirebirdSetDomainDataTypeAction(
            FirebirdDialect((4, 0, 0)),
            data_type_name=data_type_name,
        )
        assert firebird_4.to_sql() == (expected, ())

    def test_boolean_data_type_name_is_version_gated(self):
        action = FirebirdSetDomainDataTypeAction(
            FirebirdDialect((2, 5, 0)),
            data_type_name="BOOLEAN",
        )

        with pytest.raises(UnsupportedFeatureError):
            action.to_sql()

    def test_invalid_decfloat_precision_is_rejected(self):
        with pytest.raises(ValueError, match="16 or 34"):
            FirebirdSetDomainDataTypeAction(
                FirebirdDialect((4, 0, 0)),
                data_type_name="DECFLOAT(17)",
            )

    def test_multiple_actions_use_firebird_order(self):
        dialect = FirebirdDialect((4, 0, 0))
        actions = [
            SetDomainNotNullAction(dialect),
            RenameDomainAction(dialect, "d_v2"),
            FirebirdSetDomainDataTypeAction(dialect, VarCharType(length=12)),
            SetDomainDefaultAction(dialect, 7),
        ]
        expression = FirebirdAlterDomainExpression(dialect, "d", actions=actions)

        assert expression.to_sql() == (
            'ALTER DOMAIN "D" TO "D_V2" TYPE VARCHAR(12) '
            'SET DEFAULT 7 SET NOT NULL'
        )

    def test_core_alter_expression_uses_same_formatter(self):
        dialect = FirebirdDialect((4, 0, 0))
        expression = AlterDomainExpression(
            dialect,
            "d",
            [
                DropDomainDefaultAction(dialect),
                RenameDomainAction(dialect, "d_v2"),
            ],
        )

        assert expression.to_sql() == 'ALTER DOMAIN "D" TO "D_V2" DROP DEFAULT'

    def test_named_check_actions_fail_fast(self):
        dialect = FirebirdDialect((4, 0, 0))
        named_check = _check(
            dialect,
            DomainValueExpression(dialect) > Literal(dialect, 0, inline_literals=True),
            name="positive_check",
        )
        add_expression = AlterDomainExpression(
            dialect,
            "d",
            [AddDomainCheckAction(dialect, named_check)],
        )
        drop_expression = AlterDomainExpression(
            dialect,
            "d",
            [DropDomainCheckAction(dialect, name="positive_check")],
        )

        with pytest.raises(UnsupportedFeatureError, match="named DOMAIN CHECK"):
            add_expression.to_sql()
        with pytest.raises(UnsupportedFeatureError, match="named DOMAIN CHECK drop"):
            drop_expression.to_sql()

    def test_legacy_named_check_actions_fail_fast(self):
        dialect = FirebirdDialect((4, 0, 0))
        add_expression = FirebirdAlterDomainExpression(
            dialect,
            "d",
            FirebirdDomainAlterMode.ADD_CONSTRAINT,
            constraint_name="positive_check",
            constraint_sql="VALUE > 0",
        )
        drop_expression = FirebirdAlterDomainExpression(
            dialect,
            "d",
            FirebirdDomainAlterMode.DROP_CONSTRAINT,
            constraint_name="positive_check",
        )

        with pytest.raises(UnsupportedFeatureError, match="named DOMAIN CHECK"):
            add_expression.to_sql()
        with pytest.raises(UnsupportedFeatureError, match="named DOMAIN CHECK drop"):
            drop_expression.to_sql()

    def test_only_one_check_action_is_rendered(self):
        dialect = FirebirdDialect((4, 0, 0))
        expression = AlterDomainExpression(
            dialect,
            "d",
            [
                AddDomainCheckAction(dialect, _positive_check(dialect)),
                AddDomainCheckAction(dialect, _positive_check(dialect)),
            ],
        )

        with pytest.raises(UnsupportedFeatureError, match="multiple ALTER DOMAIN CHECK"):
            expression.to_sql()

    def test_missing_legacy_action_fields_fail_fast(self):
        dialect = FirebirdDialect((4, 0, 0))

        with pytest.raises(ValueError, match="SET DEFAULT requires a value"):
            FirebirdAlterDomainExpression(
                dialect,
                "d",
                FirebirdDomainAlterMode.SET_DEFAULT,
            )
        with pytest.raises(ValueError, match="ADD CONSTRAINT requires constraint_sql"):
            FirebirdAlterDomainExpression(
                dialect,
                "d",
                FirebirdDomainAlterMode.ADD_CONSTRAINT,
            )
        with pytest.raises(ValueError, match="SET TYPE requires data_type"):
            FirebirdAlterDomainExpression(
                dialect,
                "d",
                FirebirdDomainAlterMode.SET_TYPE,
            )

    def test_conflicting_mode_and_actions_fail_fast(self):
        dialect = FirebirdDialect((4, 0, 0))

        with pytest.raises(ValueError, match="different ALTER DOMAIN changes"):
            FirebirdAlterDomainExpression(
                dialect,
                "d",
                FirebirdDomainAlterMode.SET_DEFAULT,
                value=7,
                actions=[DropDomainDefaultAction(dialect)],
            )


class TestVersionBoundaries:
    def test_domain_statements_start_at_firebird_25(self):
        dialect = FirebirdDialect((2, 5, 0))
        create = FirebirdCreateDomainExpression(
            dialect,
            "positive",
            IntegerType(dialect),
            not_null=True,
        )
        alter = AlterDomainExpression(
            dialect,
            "positive",
            [FirebirdSetDomainDataTypeAction(dialect, IntegerType(dialect))],
        )
        drop = FirebirdDropDomainExpression(dialect, "positive")

        assert create.to_sql() == 'CREATE DOMAIN "POSITIVE" AS INTEGER NOT NULL'
        assert alter.to_sql() == 'ALTER DOMAIN "POSITIVE" TYPE INTEGER'
        assert drop.to_sql() == 'DROP DOMAIN "POSITIVE"'

    @pytest.mark.parametrize("action_type", [SetDomainNotNullAction, DropDomainNotNullAction])
    def test_not_null_actions_require_firebird_30(self, action_type):
        dialect = FirebirdDialect((2, 5, 0))
        action = action_type(dialect)
        expression = AlterDomainExpression(dialect, "positive", [action])

        assert dialect.supports_alter_domain_action(action_type) is False
        with pytest.raises(UnsupportedFeatureError, match="ALTER DOMAIN action"):
            expression.to_sql()

    def test_not_null_actions_render_on_firebird_30(self):
        dialect = FirebirdDialect((3, 0, 0))

        assert dialect.supports_alter_domain_action(SetDomainNotNullAction) is True
        assert dialect.supports_alter_domain_action(DropDomainNotNullAction) is True

    def test_domain_statements_fail_before_firebird_25(self):
        dialect = FirebirdDialect((2, 0, 0))

        with pytest.raises(UnsupportedFeatureError, match="CREATE DOMAIN"):
            FirebirdCreateDomainExpression(dialect, "d", IntegerType(dialect)).to_sql()
        with pytest.raises(UnsupportedFeatureError, match="DROP DOMAIN"):
            DropDomainExpression(dialect, "d").to_sql()


class TestCapabilities:
    def test_firebird_domain_capabilities(self):
        dialect = FirebirdDialect((4, 0, 0))

        assert dialect.supports_domain() is True
        assert dialect.supports_domains() is True
        assert dialect.supports_create_domain() is True
        assert dialect.supports_alter_domain() is True
        assert dialect.supports_drop_domain() is True
        assert dialect.supports_domain_default() is True
        assert dialect.supports_domain_nullability(DomainNullability.NOT_NULL) is True
        assert dialect.supports_domain_nullability(DomainNullability.NULLABLE) is False
        assert dialect.supports_domain_checks() is True
        assert dialect.supports_named_domain_checks() is False
        assert dialect.supports_multiple_domain_checks() is False
        assert dialect.supports_domain_collation() is True
        assert dialect.supports_multiple_domain_alter_actions() is True
        assert dialect.supports_drop_domain_if_exists() is False
        assert dialect.supports_drop_domain_cascade() is False
        assert dialect.supports_drop_domain_restrict() is False
        assert dialect.supports_unnamed_domain_check_drop() is True

    def test_independent_type_capabilities_are_all_false(self):
        dialect = FirebirdDialect((4, 0, 0))
        capability_names = (
            "supports_type_objects",
            "supports_create_type",
            "supports_alter_type",
            "supports_drop_type",
            "supports_create_type_if_not_exists",
            "supports_create_type_or_replace",
            "supports_alter_type_if_exists",
            "supports_drop_type_if_exists",
            "supports_multiple_type_alter_actions",
        )

        for name in capability_names:
            assert getattr(dialect, name)() is False
        assert dialect.supported_type_definitions() == ()
        assert dialect.supports_type_definition(IntegerType) is False
        assert dialect.supports_type_alter_action(DropDomainDefaultAction) is False
        assert FirebirdDialect.supports_type_objects is UserDefinedTypeMixin.supports_type_objects

    def test_domain_protocols_and_mro(self):
        dialect = FirebirdDialect((4, 0, 0))

        assert issubclass(FirebirdDomainSupport, DomainSupport)
        assert isinstance(dialect, FirebirdDomainSupport)
        assert isinstance(dialect, DomainSupport)
        assert isinstance(dialect, DomainMixin)
        assert isinstance(dialect, UserDefinedTypeSupport)


class TestDispatchAndSerialization:
    def test_dispatch_uses_firebird_mixin(self):
        dialect = FirebirdDialect((4, 0, 0))

        assert type(dialect).format_create_domain_statement is FirebirdDomainMixin.format_create_domain_statement
        assert type(dialect).format_alter_domain_statement is FirebirdDomainMixin.format_alter_domain_statement
        assert type(dialect).format_drop_domain_statement is FirebirdDomainMixin.format_drop_domain_statement
        assert type(dialect).format_domain_alter_action is FirebirdDomainMixin.format_domain_alter_action

    def test_backend_domain_classes_are_registered(self):
        classes = (
            FirebirdCreateDomainExpression,
            FirebirdAlterDomainExpression,
            FirebirdDropDomainExpression,
            FirebirdSetDomainDataTypeAction,
        )

        for expression_class in classes:
            fqn = f"{expression_class.__module__}.{expression_class.__name__}"
            assert ExpressionRegistry.lookup(fqn) is expression_class

    def test_firebird_data_types_are_registered(self):
        classes = (
            FirebirdDecimalType,
            FirebirdFloatType,
            FirebirdDoubleType,
            FirebirdBlobSubType,
            FirebirdCharType,
            FirebirdVarCharType,
            FirebirdTimeStampTzType,
            FirebirdTimeWithoutTimeZoneType,
            FirebirdTimeTzType,
            FirebirdDecFloatType,
            FirebirdInt128Type,
        )

        for expression_class in classes:
            fqn = f"{expression_class.__module__}.{expression_class.__name__}"
            assert ExpressionRegistry.lookup(fqn) is expression_class

    def test_firebird_data_types_round_trip_in_all_codecs(self):
        dialect = FirebirdDialect((4, 0, 0))
        expressions = (
            FirebirdDecimalType(dialect, precision=10, scale=2),
            FirebirdFloatType(dialect),
            FirebirdDoubleType(dialect),
            FirebirdBlobSubType(dialect),
            FirebirdCharType(dialect, length=5),
            FirebirdVarCharType(dialect, length=40),
            FirebirdTimeStampTzType(dialect, precision=6),
            FirebirdTimeWithoutTimeZoneType(dialect, precision=6),
            FirebirdTimeTzType(dialect, precision=6),
            FirebirdDecFloatType(dialect, precision=16),
            FirebirdInt128Type(dialect),
        )
        codecs = (
            (serialize, deserialize),
            (serialize_json, deserialize_json),
            (serialize_xml, deserialize_xml),
        )

        for expression in expressions:
            for encoder, decoder in codecs:
                payload = encoder(expression)
                restored = decoder(payload, dialect)
                assert type(restored) is type(expression)
                assert restored.to_sql() == expression.to_sql()
                assert encoder(restored) == payload

    def test_backend_domain_classes_round_trip_in_all_codecs(self):
        dialect = FirebirdDialect((4, 0, 0))
        expressions = (
            FirebirdCreateDomainExpression(
                dialect,
                "positive",
                IntegerType(dialect),
                default=0,
                not_null=True,
                check="VALUE >= 0",
            ),
            FirebirdAlterDomainExpression(
                dialect,
                "positive",
                FirebirdDomainAlterMode.SET_DEFAULT,
                value=1,
            ),
            FirebirdAlterDomainExpression(
                dialect,
                "positive",
                FirebirdDomainAlterMode.SET_TYPE,
                data_type_name="DECIMAL(10, 2)",
            ),
            FirebirdAlterDomainExpression(
                dialect,
                "positive",
                actions=[
                    FirebirdSetDomainDataTypeAction(
                        dialect,
                        FirebirdDecFloatType(precision=16),
                    )
                ],
            ),
            FirebirdDropDomainExpression(dialect, "positive"),
            FirebirdSetDomainDataTypeAction(
                dialect,
                FirebirdDecFloatType(precision=16),
            ),
            FirebirdSetDomainDataTypeAction(
                dialect,
                data_type_name="VARCHAR(20)",
            ),
        )
        codecs = (
            (serialize, deserialize),
            (serialize_json, deserialize_json),
            (serialize_xml, deserialize_xml),
        )

        for expression in expressions:
            for encoder, decoder in codecs:
                payload = encoder(expression)
                restored = decoder(payload, dialect)
                assert type(restored) is type(expression)
                assert restored.to_sql() == expression.to_sql()
                assert encoder(restored) == payload
