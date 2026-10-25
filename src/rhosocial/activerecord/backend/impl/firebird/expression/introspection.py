# src/rhosocial/activerecord/backend/impl/firebird/expression/introspection.py
"""Firebird's own introspection questions.

The core statement classes cover the catalogue questions every backend asks.
Generators (sequences) and domains are Firebird's own object families with no
core entry point, so they get statements of their own here.

Like every other expression, each class collects all its parameters at
construction and names -- through ``format_method`` -- the one dialect
formatter that renders it. The SQL lives on the dialect; this module only
carries the question.
"""

from typing import TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase

__all__ = [
    "FirebirdDomainListQueryStatement",
    "FirebirdGeneratorListQueryStatement",
    "FirebirdGeneratorValueQueryStatement",
]


class FirebirdGeneratorListQueryStatement(BaseExpression):
    """Ask for this database's generators (sequences).

    Args:
        dialect: The dialect the statement is bound to.
        include_system: Whether to include the generators Firebird owns
            (identity columns and other internal sequences). Defaults to
            False.
    """

    def __init__(self, dialect: "SQLDialectBase", include_system: bool = False):
        super().__init__(dialect)
        self.include_system = include_system

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this statement."""
        return "format_firebird_generator_list_query_statement"

    def __repr__(self) -> str:
        return (
            f"FirebirdGeneratorListQueryStatement("
            f"include_system={self.include_system!r})"
        )


class FirebirdGeneratorValueQueryStatement(BaseExpression):
    """Ask for one generator's current value.

    Args:
        dialect: The dialect the statement is bound to.
        generator_name: The generator whose value is read.
    """

    def __init__(self, dialect: "SQLDialectBase", generator_name: str):
        super().__init__(dialect)
        self.generator_name = generator_name

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this statement."""
        return "format_firebird_generator_value_query_statement"

    def __repr__(self) -> str:
        return (
            f"FirebirdGeneratorValueQueryStatement("
            f"generator_name={self.generator_name!r})"
        )


class FirebirdDomainListQueryStatement(BaseExpression):
    """Ask for this database's domains.

    Args:
        dialect: The dialect the statement is bound to.
        include_system: Whether to include the domains Firebird creates for
            inline-declared column types. Defaults to False.
    """

    def __init__(self, dialect: "SQLDialectBase", include_system: bool = False):
        super().__init__(dialect)
        self.include_system = include_system

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this statement."""
        return "format_firebird_domain_list_query_statement"

    def __repr__(self) -> str:
        return (
            f"FirebirdDomainListQueryStatement("
            f"include_system={self.include_system!r})"
        )
