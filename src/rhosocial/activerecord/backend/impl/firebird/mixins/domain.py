# src/rhosocial/activerecord/backend/impl/firebird/mixins/domain.py
"""Firebird DOMAIN statement formatting mixin."""

from typing import Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.dialect.mixins import DomainMixin
from rhosocial.activerecord.backend.expression.objects import Domain
from rhosocial.activerecord.backend.expression.statements.ddl_domain import (
    AddDomainCheckAction,
    AlterDomainStatement,
    CreateDomainStatement,
    DomainAlterAction,
    DomainNullability,
    DropDomainCheckAction,
    DropDomainDefaultAction,
    DropDomainStatement,
    DropDomainNotNullAction,
    RenameDomainAction,
    SetDomainDefaultAction,
    SetDomainNotNullAction,
)

from ..expression.ddl.domain import FirebirdSetDomainDataTypeAction, _bind_data_type
from .version_boundaries import FIREBIRD_VERSION_BOUNDARIES


class FirebirdDomainMixin(DomainMixin):
    """Render Firebird DOMAIN DDL and enforce its version boundaries."""

    if TYPE_CHECKING:
        version: Optional[Tuple[int, ...]]

    def supports_domains(self) -> bool:
        return self.version_at_least(FIREBIRD_VERSION_BOUNDARIES["DOMAIN"])

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

    def supports_domain_nullable(self) -> bool:
        # A Firebird domain is nullable unless ``NOT NULL`` is stated, and the
        # CREATE DOMAIN grammar has no ``NULL`` clause to spell. The old
        # parameterized switch answered ``False`` for ``NULLABLE``; that answer
        # is now the switch itself.
        return False

    def supports_domain_not_null(self) -> bool:
        return self.supports_domains()

    def supports_domain_checks(self) -> bool:
        return self.supports_domains()

    def supports_named_domain_checks(self) -> bool:
        return False

    def supports_multiple_domain_checks(self) -> bool:
        return False

    def supports_domain_collation(self) -> bool:
        return self.supports_domains()

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
        expr: CreateDomainStatement,
    ) -> Tuple[str, tuple]:
        """Render CREATE DOMAIN <name> AS <type> [...checks].

        Raises:
            TypeError: ``CreateDomainStatement.domain`` is not a Domain. A table
                or a sequence would have had its own name rendered as the domain.
            UnsupportedFeatureError: The clause requested is not one Firebird
                spells, or this engine version does not have DOMAINs.
            ValueError: A DEFAULT or collation that cannot be rendered without
                bind parameters, or a collation with an empty segment.
        """
        if not self.supports_domains() or not self.supports_create_domain():
            raise UnsupportedFeatureError(self.name, "CREATE DOMAIN")
        if not isinstance(expr.domain, Domain):
            raise TypeError(
                f"CreateDomainStatement.domain must be a Domain, "
                f"got {type(expr.domain).__name__}"
            )
        data_type = _bind_data_type(self, expr.data_type)
        type_sql, type_params = data_type.to_sql()
        parts = [
            "CREATE DOMAIN",
            expr.domain.to_sql()[0],
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
        if expr.nullability is DomainNullability.NULLABLE:
            if not self.supports_domain_nullable():
                raise UnsupportedFeatureError(self.name, "DOMAIN NULL")
            parts.append(expr.nullability.value)
        elif expr.nullability is DomainNullability.NOT_NULL:
            if not self.supports_domain_not_null():
                raise UnsupportedFeatureError(self.name, "DOMAIN NOT NULL")
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
        expr: AlterDomainStatement,
    ) -> Tuple[str, tuple]:
        """Render ALTER DOMAIN <name> <actions>.

        Raises:
            TypeError: ``AlterDomainStatement.domain`` is not a Domain. Another
                object kind would have had its own name rendered as the domain
                being altered.
            UnsupportedFeatureError: The action set is not one Firebird accepts,
                or this engine version does not have DOMAINs.
        """
        if not self.supports_domains() or not self.supports_alter_domain():
            raise UnsupportedFeatureError(self.name, "ALTER DOMAIN")
        if not isinstance(expr.domain, Domain):
            raise TypeError(
                f"AlterDomainStatement.domain must be a Domain, "
                f"got {type(expr.domain).__name__}"
            )
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
            group = self._domain_action_group(action)
            if group is None or not self._can_spell_domain_action(action):
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
            f'ALTER DOMAIN {expr.domain.to_sql()[0]} {" ".join(action_parts)}',
            tuple(action_params),
        )

    def format_drop_domain_statement(
        self,
        expr: DropDomainStatement,
    ) -> Tuple[str, tuple]:
        return super().format_drop_domain_statement(expr)

    def format_domain_alter_action(
        self,
        expr: DomainAlterAction,
    ) -> Tuple[str, tuple]:
        """Render one ALTER DOMAIN action, or refuse the kind by name.

        The kind vocabulary is Firebird's, so an action class this formatter
        does not know is not a capability question -- it is a node with no
        spelling, and the method therefore ends in an unconditional refusal.
        """
        if not self.supports_domains() or not self.supports_alter_domain():
            raise UnsupportedFeatureError(self.name, "ALTER DOMAIN action")
        if isinstance(expr, FirebirdSetDomainDataTypeAction):
            data_type = expr.resolve_data_type()
            type_sql, type_params = data_type.to_sql()
            return f"TYPE {type_sql}", tuple(type_params)
        if isinstance(expr, RenameDomainAction):
            # The rename target is a domain like any other: it names the object
            # the domain becomes, so it goes through the same object layer.
            return f"TO {Domain(self, expr.new_name).to_sql()[0]}", ()
        if isinstance(expr, (SetDomainNotNullAction, DropDomainNotNullAction)):
            if not self._can_spell_domain_action(expr):
                raise UnsupportedFeatureError(
                    self.name,
                    f"ALTER DOMAIN action {expr.action_kind}",
                )
            if isinstance(expr, SetDomainNotNullAction):
                return "SET NOT NULL", ()
            return "DROP NOT NULL", ()
        if isinstance(expr, SetDomainDefaultAction):
            if not self.supports_domain_default():
                raise UnsupportedFeatureError(self.name, "ALTER DOMAIN SET DEFAULT")
            value_sql, params = expr.default.to_sql()
            if params:
                raise ValueError("ALTER DOMAIN DEFAULT must render without bind parameters")
            return f"SET DEFAULT {value_sql}", ()
        if isinstance(expr, DropDomainDefaultAction):
            if not self.supports_domain_default():
                raise UnsupportedFeatureError(self.name, "ALTER DOMAIN DROP DEFAULT")
            return "DROP DEFAULT", ()
        if isinstance(expr, AddDomainCheckAction):
            check_sql, params = expr.check.to_sql()
            return f"ADD {check_sql}", tuple(params)
        if isinstance(expr, DropDomainCheckAction):
            if not self.supports_domain_checks():
                raise UnsupportedFeatureError(self.name, "ALTER DOMAIN DROP CHECK")
            if expr.name is None:
                if not self.supports_unnamed_domain_check_drop():
                    raise UnsupportedFeatureError(
                        self.name,
                        "unnamed DOMAIN CHECK drop",
                    )
                return "DROP CONSTRAINT", ()
            if not self.supports_named_domain_checks():
                raise UnsupportedFeatureError(self.name, "named DOMAIN CHECK drop")
            return f"DROP CONSTRAINT {self.format_identifier(expr.name)}", ()
        raise UnsupportedFeatureError(
            self.name,
            f"ALTER DOMAIN action {expr.action_kind}",
        )

    def _can_spell_domain_action(self, action: DomainAlterAction) -> bool:
        """Whether this engine version has *action*'s ALTER DOMAIN spelling.

        A node-kind question, not a capability switch: Firebird learned
        ``SET``/``DROP NOT NULL`` on ALTER DOMAIN in 3.0, while the other
        actions exist as soon as DOMAIN itself does.
        """
        if isinstance(action, (SetDomainNotNullAction, DropDomainNotNullAction)):
            return self.version_at_least(
                FIREBIRD_VERSION_BOUNDARIES["DOMAIN_NOT_NULL_ACTION"]
            )
        return self._domain_action_group(action) is not None

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
