# src/rhosocial/activerecord/backend/impl/firebird/mixins/domain.py
"""Firebird DOMAIN statement formatting mixin."""

from typing import Optional, Tuple, Type, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.dialect.mixins import DomainMixin
from rhosocial.activerecord.backend.expression.statements.ddl_domain import (
    AddDomainCheckAction,
    AlterDomainExpression,
    CreateDomainExpression,
    DomainAlterAction,
    DomainNullability,
    DropDomainCheckAction,
    DropDomainDefaultAction,
    DropDomainExpression,
    DropDomainNotNullAction,
    RenameDomainAction,
    SetDomainDefaultAction,
    SetDomainNotNullAction,
)

from ..expression.ddl.domain import FirebirdSetDomainDataTypeAction, _bind_data_type
from .version_boundaries import FIREBIRD_VERSION_BOUNDARIES, _norm_version


class FirebirdDomainMixin(DomainMixin):
    """Render Firebird DOMAIN DDL and enforce its version boundaries."""

    if TYPE_CHECKING:
        version: Optional[Tuple[int, ...]]

    def supports_domains(self) -> bool:
        version = _norm_version(self.version)
        return version is not None and version >= FIREBIRD_VERSION_BOUNDARIES["DOMAIN"]

    def supports_domain(self) -> bool:
        return self.supports_domains()

    def supports_create_domain(self) -> bool:
        return self.supports_domains()

    def supports_alter_domain(self) -> bool:
        return self.supports_domains()

    def supports_drop_domain(self) -> bool:
        return self.supports_domains()

    def supports_domain_default(self) -> bool:
        return self.supports_domains()

    def supports_domain_nullability(self, nullability: DomainNullability) -> bool:
        return self.supports_domains() and nullability is DomainNullability.NOT_NULL

    def supports_domain_checks(self) -> bool:
        return self.supports_domains()

    def supports_named_domain_checks(self) -> bool:
        return False

    def supports_multiple_domain_checks(self) -> bool:
        return False

    def supports_domain_collation(self) -> bool:
        return self.supports_domains()

    def supports_alter_domain_action(
        self,
        action_type: Type[DomainAlterAction],
    ) -> bool:
        if not self.supports_domains():
            return False
        try:
            if issubclass(
                action_type,
                (SetDomainNotNullAction, DropDomainNotNullAction),
            ):
                version = _norm_version(self.version)
                return (
                    version is not None
                    and version >= FIREBIRD_VERSION_BOUNDARIES["DOMAIN_NOT_NULL_ACTION"]
                )
            return issubclass(
                action_type,
                (
                    SetDomainDefaultAction,
                    DropDomainDefaultAction,
                    AddDomainCheckAction,
                    DropDomainCheckAction,
                    RenameDomainAction,
                    FirebirdSetDomainDataTypeAction,
                ),
            )
        except TypeError:
            return False

    def supports_multiple_domain_alter_actions(self) -> bool:
        return self.supports_alter_domain()

    def supports_drop_domain_if_exists(self) -> bool:
        return False

    def supports_drop_domain_cascade(self) -> bool:
        return False

    def supports_drop_domain_restrict(self) -> bool:
        return False

    def supports_unnamed_domain_check_drop(self) -> bool:
        return self.supports_domains()

    def format_create_domain_statement(
        self,
        expr: CreateDomainExpression,
    ) -> Tuple[str, tuple]:
        if not self.supports_domains() or not self.supports_create_domain():
            raise UnsupportedFeatureError(self.name, "CREATE DOMAIN")
        data_type = _bind_data_type(self, expr.data_type)
        type_sql, type_params = data_type.to_sql()
        parts = [
            "CREATE DOMAIN",
            self.format_identifier(expr.domain_name),
            "AS",
            type_sql,
        ]
        params = list(type_params)
        if expr.default is not None:
            if not self.supports_domain_default():
                raise UnsupportedFeatureError(self.name, "DOMAIN DEFAULT")
            default_sql, default_params = expr.default.to_sql()
            if default_params:
                raise ValueError("DOMAIN DEFAULT must render without bind parameters")
            parts.append(f"DEFAULT {default_sql}")
        if expr.nullability is not DomainNullability.UNSPECIFIED:
            if not self.supports_domain_nullability(expr.nullability):
                raise UnsupportedFeatureError(
                    self.name,
                    f"DOMAIN {expr.nullability.value}",
                )
            parts.append(expr.nullability.value)
        checks = list(expr.checks)
        if checks and not self.supports_domain_checks():
            raise UnsupportedFeatureError(self.name, "DOMAIN CHECK")
        if any(check.name is not None for check in checks):
            raise UnsupportedFeatureError(self.name, "named DOMAIN CHECK")
        if len(checks) > 1:
            raise UnsupportedFeatureError(
                self.name,
                "multiple domain CHECK constraints",
            )
        for check in checks:
            check_sql, check_params = check.to_sql()
            parts.append(check_sql)
            params.extend(check_params)
        if expr.collation is not None:
            if not self.supports_domain_collation():
                raise UnsupportedFeatureError(self.name, "DOMAIN COLLATE")
            collation_parts = expr.collation.split(".")
            if any(not part.strip() for part in collation_parts):
                raise ValueError("collation must contain non-empty identifier segments")
            collation_sql = ".".join(
                self.format_identifier(part) for part in collation_parts
            )
            parts.append(f"COLLATE {collation_sql}")
        return " ".join(parts), tuple(params)

    def format_alter_domain_statement(
        self,
        expr: AlterDomainExpression,
    ) -> Tuple[str, tuple]:
        if not self.supports_domains() or not self.supports_alter_domain():
            raise UnsupportedFeatureError(self.name, "ALTER DOMAIN")
        if len(expr.actions) > 1 and not self.supports_multiple_domain_alter_actions():
            raise UnsupportedFeatureError(self.name, "multiple ALTER DOMAIN actions")
        action_groups = {
            "rename": "rename",
            "type": "TYPE",
            "default": "DEFAULT",
            "nullability": "NOT NULL",
            "check": "CHECK",
        }
        action_order = {
            "rename": 0,
            "type": 1,
            "default": 2,
            "nullability": 3,
            "check": 4,
        }
        action_groups_seen = set()
        ordered_actions = []
        for action in expr.actions:
            if not self.supports_alter_domain_action(type(action)):
                raise UnsupportedFeatureError(
                    self.name,
                    f"ALTER DOMAIN action {action.action_kind}",
                )
            group = self._domain_action_group(action)
            if group is None:
                raise UnsupportedFeatureError(
                    self.name,
                    f"ALTER DOMAIN action {action.action_kind}",
                )
            if group in action_groups_seen:
                raise UnsupportedFeatureError(
                    self.name,
                    f"multiple ALTER DOMAIN {action_groups[group]} actions",
                )
            action_groups_seen.add(group)
            ordered_actions.append((action_order[group], action))
        ordered_actions.sort(key=lambda item: item[0])
        action_parts = []
        action_params = []
        for _, action in ordered_actions:
            action_sql, params = action.to_sql()
            action_parts.append(action_sql)
            action_params.extend(params)
        return (
            f'ALTER DOMAIN {self.format_identifier(expr.domain_name)} {" ".join(action_parts)}',
            tuple(action_params),
        )

    def format_drop_domain_statement(
        self,
        expr: DropDomainExpression,
    ) -> Tuple[str, tuple]:
        return super().format_drop_domain_statement(expr)

    def format_domain_alter_action(
        self,
        expr: DomainAlterAction,
    ) -> Tuple[str, tuple]:
        if not self.supports_domains() or not self.supports_alter_domain():
            raise UnsupportedFeatureError(self.name, "ALTER DOMAIN action")
        if not self.supports_alter_domain_action(type(expr)):
            raise UnsupportedFeatureError(
                self.name,
                f"ALTER DOMAIN action {expr.action_kind}",
            )
        if isinstance(expr, FirebirdSetDomainDataTypeAction):
            data_type = expr.resolve_data_type()
            type_sql, type_params = data_type.to_sql()
            return f"TYPE {type_sql}", tuple(type_params)
        if isinstance(expr, RenameDomainAction):
            return f"TO {self.format_identifier(expr.new_name)}", ()
        if isinstance(expr, SetDomainNotNullAction):
            return "SET NOT NULL", ()
        if isinstance(expr, DropDomainNotNullAction):
            return "DROP NOT NULL", ()
        return super().format_domain_alter_action(expr)

    @staticmethod
    def _domain_action_group(action: DomainAlterAction) -> Optional[str]:
        if isinstance(action, RenameDomainAction):
            return "rename"
        if isinstance(action, FirebirdSetDomainDataTypeAction):
            return "type"
        if isinstance(action, (SetDomainDefaultAction, DropDomainDefaultAction)):
            return "default"
        if isinstance(action, (SetDomainNotNullAction, DropDomainNotNullAction)):
            return "nullability"
        if isinstance(action, (AddDomainCheckAction, DropDomainCheckAction)):
            return "check"
        return None


__all__ = ["FirebirdDomainMixin"]
