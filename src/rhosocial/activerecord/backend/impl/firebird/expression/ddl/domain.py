# src/rhosocial/activerecord/backend/impl/firebird/expression/ddl/domain.py
"""Firebird DOMAIN statement expressions."""

from enum import Enum
from typing import Any, Optional, Sequence, Set, TYPE_CHECKING, Union

from rhosocial.activerecord.backend.expression.bases import SQLPredicate
from rhosocial.activerecord.backend.expression.operators import RawSQLPredicate
from rhosocial.activerecord.backend.expression.serialization import ExpressionRegistry
from rhosocial.activerecord.backend.expression.statements.ddl_domain import (
    AddDomainCheckAction,
    AlterDomainExpression,
    CreateDomainExpression,
    DomainAlterAction,
    DomainCheckConstraint,
    DomainNullability,
    DropDomainCheckAction,
    DropDomainDefaultAction,
    DropDomainExpression,
    DropDomainNotNullAction,
    SetDomainDefaultAction,
    SetDomainNotNullAction,
)
from rhosocial.activerecord.backend.expression.types import DataType

from ..types import (
    _normalize_firebird_data_type_name,
    _parse_firebird_data_type_name,
)

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class FirebirdDomainAlterMode(Enum):
    """Legacy ALTER DOMAIN clause selector."""

    SET_DEFAULT = "SET DEFAULT"
    DROP_DEFAULT = "DROP DEFAULT"
    SET_NOT_NULL = "SET NOT NULL"
    DROP_NOT_NULL = "DROP NOT NULL"
    ADD_CONSTRAINT = "ADD CONSTRAINT"
    DROP_CONSTRAINT = "DROP CONSTRAINT"
    SET_TYPE = "TYPE"


def _bind_data_type(dialect: Any, data_type: DataType) -> DataType:
    params = dict(data_type.get_params())
    params.pop("dialect", None)
    clone = type(data_type)(**params)
    clone.dialect = dialect
    return clone


class FirebirdSetDomainDataTypeAction(DomainAlterAction):
    """Replace a domain's base data type."""

    action_kind = "set_data_type"

    def __init__(
        self,
        dialect: "SQLDialectBase",
        data_type: Optional[Union[DataType, str]] = None,
        *,
        data_type_name: Optional[str] = None,
    ) -> None:
        super().__init__(dialect)
        if isinstance(data_type, str):
            if data_type_name is not None:
                raise ValueError("data_type and data_type_name are mutually exclusive")
            data_type_name = data_type
            data_type = None
        if data_type is not None and not isinstance(data_type, DataType):
            raise TypeError(
                f"data_type must be a DataType instance, got {type(data_type).__name__}"
            )
        if data_type is None and data_type_name is None:
            raise ValueError("data_type or data_type_name is required")
        if data_type is not None and data_type_name is not None:
            raise ValueError("data_type and data_type_name are mutually exclusive")
        self.data_type = data_type
        if data_type_name is None:
            self.data_type_name = None
        else:
            normalized_name = _normalize_firebird_data_type_name(data_type_name)
            _parse_firebird_data_type_name(normalized_name)
            self.data_type_name = normalized_name

    def resolve_data_type(self) -> DataType:
        if self.data_type is not None:
            return _bind_data_type(self.dialect, self.data_type)
        if self.data_type_name is None:
            raise ValueError("data_type or data_type_name is required")
        parsed = _parse_firebird_data_type_name(self.data_type_name)
        return _bind_data_type(self.dialect, parsed)


def _normalize_nullability(value: Any) -> DomainNullability:
    if isinstance(value, str):
        try:
            return DomainNullability(value)
        except ValueError as exc:
            raise ValueError(f"Invalid domain nullability: {value!r}") from exc
    if not isinstance(value, DomainNullability):
        raise TypeError(
            f"nullability must be a DomainNullability instance, got "
            f"{type(value).__name__}"
        )
    return value


def _legacy_check(
    dialect: "SQLDialectBase",
    check: str,
) -> DomainCheckConstraint:
    if not isinstance(check, str):
        raise TypeError(f"check must be a string, got {type(check).__name__}")
    if not check.strip():
        raise ValueError("check must be a non-empty SQL predicate")
    return DomainCheckConstraint(dialect, RawSQLPredicate(dialect, check))


def _coalesce_checks(
    dialect: "SQLDialectBase",
    check: Optional[str],
    checks: Optional[Sequence[DomainCheckConstraint]],
) -> Optional[Sequence[DomainCheckConstraint]]:
    if check is None:
        return checks
    legacy_check = _legacy_check(dialect, check)
    if checks is None:
        return [legacy_check]
    if isinstance(checks, (DomainCheckConstraint, SQLPredicate)):
        check_items = [checks]
    else:
        check_items = list(checks)
    if len(check_items) != 1 or not isinstance(check_items[0], DomainCheckConstraint):
        raise ValueError("check and checks must describe the same single CHECK")
    condition = check_items[0].condition
    if (
        check_items[0].name is not None
        or not isinstance(condition, RawSQLPredicate)
        or condition.expression != check
        or condition.params
    ):
        raise ValueError("check and checks must describe the same single CHECK")
    return check_items


class FirebirdCreateDomainExpression(CreateDomainExpression):
    """Compatibility wrapper for the core CREATE DOMAIN expression."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        domain_name: str,
        data_type: DataType,
        default: Any = None,
        not_null: bool = False,
        check: Optional[str] = None,
        *,
        nullability: Optional[Union[DomainNullability, str]] = None,
        checks: Optional[Sequence[DomainCheckConstraint]] = None,
        collation: Optional[str] = None,
    ) -> None:
        if not isinstance(not_null, bool):
            raise TypeError(f"not_null must be a bool, got {type(not_null).__name__}")
        normalized_nullability = (
            None if nullability is None else _normalize_nullability(nullability)
        )
        if not_null:
            if (
                normalized_nullability is not None
                and normalized_nullability is not DomainNullability.NOT_NULL
            ):
                raise ValueError("not_null conflicts with nullability")
            normalized_nullability = DomainNullability.NOT_NULL
        elif normalized_nullability is None:
            normalized_nullability = DomainNullability.UNSPECIFIED
        normalized_checks = _coalesce_checks(dialect, check, checks)
        super().__init__(
            dialect,
            domain_name,
            data_type,
            default=default,
            nullability=normalized_nullability,
            checks=normalized_checks,
            collation=collation,
        )
        self.not_null = not_null
        self.check = check


class FirebirdAlterDomainExpression(AlterDomainExpression):
    """Compatibility wrapper accepting either the legacy mode or core actions."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        domain_name: str,
        mode: Optional[FirebirdDomainAlterMode] = None,
        value: Any = None,
        data_type: Optional[Union[DataType, str]] = None,
        constraint_name: Optional[str] = None,
        constraint_sql: Optional[str] = None,
        *,
        actions: Optional[Sequence[DomainAlterAction]] = None,
        data_type_name: Optional[str] = None,
    ) -> None:
        legacy_fields = {
            "value": value,
            "data_type": data_type,
            "constraint_name": constraint_name,
            "constraint_sql": constraint_sql,
            "data_type_name": data_type_name,
        }
        if mode is None:
            if any(field is not None for field in legacy_fields.values()):
                raise ValueError("legacy ALTER DOMAIN fields require mode")
            selected_actions = list(actions) if actions is not None else []
        else:
            expected_action = self._legacy_action(
                dialect,
                mode,
                value=value,
                data_type=data_type,
                constraint_name=constraint_name,
                constraint_sql=constraint_sql,
                data_type_name=data_type_name,
            )
            if actions is None:
                selected_actions = [expected_action]
            else:
                selected_actions = list(actions)
                if (
                    len(selected_actions) != 1
                    or not self._actions_equivalent(expected_action, selected_actions[0])
                ):
                    raise ValueError("mode and actions describe different ALTER DOMAIN changes")
        super().__init__(dialect, domain_name, selected_actions)
        self.mode = mode
        self.value = value
        self.data_type = data_type
        self.constraint_name = constraint_name
        self.constraint_sql = constraint_sql
        self.data_type_name = data_type_name

    @staticmethod
    def _reject_unused_fields(
        mode: FirebirdDomainAlterMode,
        fields: dict[str, Any],
        allowed: Set[str],
    ) -> None:
        unexpected = sorted(
            name for name, value in fields.items() if name not in allowed and value is not None
        )
        if unexpected:
            names = ", ".join(unexpected)
            raise ValueError(f"{mode.value} does not accept: {names}")

    @classmethod
    def _legacy_action(
        cls,
        dialect: "SQLDialectBase",
        mode: FirebirdDomainAlterMode,
        *,
        value: Any,
        data_type: Optional[Union[DataType, str]],
        constraint_name: Optional[str],
        constraint_sql: Optional[str],
        data_type_name: Optional[str],
    ) -> DomainAlterAction:
        if not isinstance(mode, FirebirdDomainAlterMode):
            raise TypeError(
                f"mode must be a FirebirdDomainAlterMode instance, got "
                f"{type(mode).__name__}"
            )
        fields = {
            "value": value,
            "data_type": data_type,
            "constraint_name": constraint_name,
            "constraint_sql": constraint_sql,
            "data_type_name": data_type_name,
        }
        if mode is FirebirdDomainAlterMode.SET_DEFAULT:
            cls._reject_unused_fields(mode, fields, {"value"})
            if value is None:
                raise ValueError("SET DEFAULT requires a value")
            return SetDomainDefaultAction(dialect, value)
        if mode is FirebirdDomainAlterMode.DROP_DEFAULT:
            cls._reject_unused_fields(mode, fields, set())
            return DropDomainDefaultAction(dialect)
        if mode is FirebirdDomainAlterMode.SET_NOT_NULL:
            cls._reject_unused_fields(mode, fields, set())
            return SetDomainNotNullAction(dialect)
        if mode is FirebirdDomainAlterMode.DROP_NOT_NULL:
            cls._reject_unused_fields(mode, fields, set())
            return DropDomainNotNullAction(dialect)
        if mode is FirebirdDomainAlterMode.ADD_CONSTRAINT:
            cls._reject_unused_fields(mode, fields, {"constraint_name", "constraint_sql"})
            if constraint_sql is None:
                raise ValueError("ADD CONSTRAINT requires constraint_sql")
            check = _legacy_check(dialect, constraint_sql)
            if constraint_name is not None:
                check = DomainCheckConstraint(
                    dialect,
                    check.condition,
                    name=constraint_name,
                )
            return AddDomainCheckAction(dialect, check)
        if mode is FirebirdDomainAlterMode.DROP_CONSTRAINT:
            cls._reject_unused_fields(mode, fields, {"constraint_name"})
            return DropDomainCheckAction(dialect, name=constraint_name)
        cls._reject_unused_fields(mode, fields, {"data_type", "data_type_name"})
        if data_type is None and data_type_name is None:
            raise ValueError("SET TYPE requires data_type or data_type_name")
        return FirebirdSetDomainDataTypeAction(
            dialect,
            data_type=data_type,
            data_type_name=data_type_name,
        )

    @staticmethod
    def _actions_equivalent(expected: DomainAlterAction, actual: DomainAlterAction) -> bool:
        if type(expected) is not type(actual):
            return False
        if isinstance(expected, SetDomainDefaultAction) and isinstance(
            actual,
            SetDomainDefaultAction,
        ):
            return expected.default.to_sql() == actual.default.to_sql()
        if isinstance(expected, AddDomainCheckAction) and isinstance(
            actual,
            AddDomainCheckAction,
        ):
            return (
                expected.check.name == actual.check.name
                and expected.check.condition.to_sql() == actual.check.condition.to_sql()
            )
        if isinstance(expected, DropDomainCheckAction) and isinstance(
            actual,
            DropDomainCheckAction,
        ):
            return expected.name == actual.name
        if isinstance(expected, FirebirdSetDomainDataTypeAction) and isinstance(
            actual,
            FirebirdSetDomainDataTypeAction,
        ):
            if expected.data_type is not None or actual.data_type is not None:
                return expected.data_type == actual.data_type
            return expected.data_type_name == actual.data_type_name
        return True


class FirebirdDropDomainExpression(DropDomainExpression):
    """Firebird-named DROP DOMAIN expression."""


ExpressionRegistry.register(FirebirdCreateDomainExpression)
ExpressionRegistry.register(FirebirdAlterDomainExpression)
ExpressionRegistry.register(FirebirdDropDomainExpression)
ExpressionRegistry.register(FirebirdSetDomainDataTypeAction)


__all__ = [
    "FirebirdDomainAlterMode",
    "FirebirdCreateDomainExpression",
    "FirebirdAlterDomainExpression",
    "FirebirdDropDomainExpression",
    "FirebirdSetDomainDataTypeAction",
]
