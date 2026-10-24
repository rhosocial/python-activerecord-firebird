# src/rhosocial/activerecord/backend/impl/firebird/query_nodes.py
"""Expression-node builders for the Firebird backend's own queries.

Every catalogue question this backend asks -- the schema introspection, the
status overview, the ``RDB$``/``MON$`` probes, the concurrency hint -- used to
be spelled as text: whole ``SELECT`` statements inline in the introspecters,
f-strings in a ``INTROSPECTION_QUERIES`` dict, and raw driver calls in the
backend. A SQL string is a formatting artefact, so it belongs to the dialect
formatter, not to the layer that executes the query (org guide §16.2): the
node collects the parameters, the formatter writes the text, and the caller
only constructs and executes.

The helpers below state each construction once -- a column reference, a
value, a ``RDB$`` relation, a conjunction, a projection into a SELECT -- so
the builders read as the questions they ask instead of as the grammar they
happen to be written in. They take the dialect as their first argument
because the introspectors, the dialect mixin and the backend classes ask
these questions and share no common base.

Two Firebird spellings are worth stating because they are *not* what the old
text wrote:

* Identifiers are upper-cased and quoted, so ``RDB$RELATIONS`` renders as
  ``"RDB$RELATIONS"`` and ``rf.RDB$FIELD_NAME`` as ``"RF"."RDB$FIELD_NAME"``.
  Firebird folds unquoted names to upper case, so both resolve to the same
  catalogue relation and column; the quoted form is what this dialect's own
  ``format_identifier`` produces for every name it renders.
* ``RDB$`` and ``MON$`` are naming conventions inside Firebird's single
  namespace, not schemas, so these relations are reached unqualified.
"""

from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase
    from rhosocial.activerecord.backend.expression.bases import (
        BaseExpression,
        SQLPredicate,
    )
    from rhosocial.activerecord.backend.expression.sources.relation import (
        NamedRelationRef,
    )


def column(
    dialect: "SQLDialectBase",
    name: str,
    table: Optional[str] = None,
    alias: Optional[str] = None,
) -> "BaseExpression":
    """A column reference, qualified by its relation alias when given."""
    from rhosocial.activerecord.backend.expression import Column

    return Column(dialect, name, table=table, alias=alias)


def literal(dialect: "SQLDialectBase", value: Any, inline: bool = False):
    """A value in a predicate position.

    *inline* keeps the value out of the parameter tuple. Values the old text
    wrote into the statement (``1``, ``'RDB$PRIMARY%'``, a configuration name)
    keep it: those are part of what the query asks, and the callers' parameter
    tuples are a contract this refactor does not move.
    """
    from rhosocial.activerecord.backend.expression import Literal

    return Literal(dialect, value, inline=inline)


def identifier(dialect: "SQLDialectBase", name: str):
    """A bare identifier, quoted by the dialect -- an argument, not a value.

    ``GEN_ID`` takes a generator *name*, which SQL cannot bind: a placeholder
    there is a syntax error. This is how such a name is passed as a node, so
    the dialect still owns the quoting rather than the caller interpolating.
    """
    from rhosocial.activerecord.backend.expression import Identifier

    return Identifier(dialect, name)


def relation(
    dialect: "SQLDialectBase",
    name: str,
    alias: Optional[str] = None,
) -> "NamedRelationRef":
    """A readable ``RDB$``/``MON$`` relation, optionally aliased."""
    from rhosocial.activerecord.backend.expression import NamedRelationRef
    from rhosocial.activerecord.backend.expression.objects import Table

    return NamedRelationRef(dialect, Table(dialect, name), alias=alias)


def join(dialect: "SQLDialectBase", left, right, condition=None, join_type: str = "JOIN"):
    """Join two row sources on *condition*."""
    from rhosocial.activerecord.backend.expression import JoinClause

    return JoinClause(dialect, left, right, join_type=join_type, condition=condition)


def conjunction(dialect: "SQLDialectBase", *conditions):
    """The conjunction of *conditions*, as one predicate node."""
    from rhosocial.activerecord.backend.expression import LogicalPredicate

    return LogicalPredicate(dialect, "AND", *conditions)


def compare(dialect: "SQLDialectBase", op: str, left, right):
    """A comparison between two expression nodes."""
    from rhosocial.activerecord.backend.expression import ComparisonPredicate

    return ComparisonPredicate(dialect, op, left, right)


def null_test(dialect: "SQLDialectBase", operand, is_not: bool = False):
    """``operand IS [NOT] NULL``."""
    from rhosocial.activerecord.backend.expression import IsNullPredicate

    return IsNullPredicate(dialect, operand, is_not=is_not)


def like(
    dialect: "SQLDialectBase",
    operand,
    pattern: str,
    negated: bool = False,
):
    """``operand LIKE '<pattern>'`` with the pattern inline, as the text had it.

    ``negated`` renders ``NOT LIKE``. The pattern is a string constant that
    says which names belong to the engine, so it rides the tree inline rather
    than becoming a bind parameter.
    """
    from rhosocial.activerecord.backend.expression import LikeOperator, LikePredicate

    return LikePredicate(
        dialect,
        LikeOperator.NOT_LIKE if negated else LikeOperator.LIKE,
        operand,
        literal(dialect, pattern, inline=True),
    )


def call(
    dialect: "SQLDialectBase",
    name: str,
    *args,
    alias: Optional[str] = None,
    niladic: bool = False,
):
    """A function call node, optionally aliased."""
    from rhosocial.activerecord.backend.expression import FunctionCall

    return FunctionCall(dialect, name, *args, alias=alias, niladic=niladic)


def row_count(dialect: "SQLDialectBase"):
    """The ``*`` that counts rows, as ``COUNT(*)`` takes it."""
    from rhosocial.activerecord.backend.expression import RowCountWildcard

    return RowCountWildcard(dialect)


def all_columns(dialect: "SQLDialectBase"):
    """The select-list ``*``."""
    from rhosocial.activerecord.backend.expression import AllColumnsWildcard

    return AllColumnsWildcard(dialect)


def cast(dialect: "SQLDialectBase", node, type_name: str):
    """``CAST(node AS type_name)``."""
    from rhosocial.activerecord.backend.expression.types._base import DataType

    return node.cast(DataType.parse_data_type_str(dialect, type_name))


def multiply(dialect: "SQLDialectBase", left, right):
    """``left * right`` as an arithmetic node."""
    from rhosocial.activerecord.backend.expression.operators import (
        ArithmeticOperation,
        ArithmeticOperator,
    )

    return ArithmeticOperation(dialect, ArithmeticOperator.MUL, left, right)


def query(
    dialect: "SQLDialectBase",
    select: List["BaseExpression"],
    from_=None,
    where: Optional["SQLPredicate"] = None,
    order_by: Optional[list] = None,
    distinct: bool = False,
):
    """A ``QueryStatement`` node, ready to render or to nest.

    Args:
        dialect: The dialect the node is bound to.
        select: The projection, in order.
        from_: A relation or join node, or ``None``.
        where: A predicate node, or ``None`` for no WHERE clause.
        order_by: ``(expression, direction)`` pairs, or ``None``.
        distinct: Whether the select list is ``DISTINCT``.

    Returns:
        The ``QueryStatement`` node.
    """
    from rhosocial.activerecord.backend.expression import (
        OrderByClause,
        QueryStatement,
        SelectModifier,
        WhereClause,
    )

    kwargs: Dict[str, Any] = {"select": select}
    if from_ is not None:
        kwargs["from_"] = from_
    if where is not None:
        kwargs["where"] = WhereClause(dialect, where)
    if order_by is not None:
        kwargs["order_by"] = OrderByClause(dialect, order_by)
    if distinct:
        kwargs["select_modifier"] = SelectModifier.DISTINCT
    return QueryStatement(dialect, **kwargs)


def select_sql(
    dialect: "SQLDialectBase",
    select: List["BaseExpression"],
    from_=None,
    where: Optional["SQLPredicate"] = None,
    order_by: Optional[list] = None,
    distinct: bool = False,
) -> Tuple[str, tuple]:
    """Render one SELECT from nodes, in the dialect's own spelling."""
    return query(
        dialect,
        select,
        from_=from_,
        where=where,
        order_by=order_by,
        distinct=distinct,
    ).to_sql()


def engine_version_sql(dialect: "SQLDialectBase") -> Tuple[str, tuple]:
    """The engine version string from the system context."""
    return select_sql(
        dialect,
        [
            call(
                dialect,
                "rdb$get_context",
                literal(dialect, "SYSTEM", inline=True),
                literal(dialect, "ENGINE_VERSION", inline=True),
                alias="VERSION",
            )
        ],
        from_=relation(dialect, "RDB$DATABASE"),
    )


def generator_value_sql(dialect: "SQLDialectBase", name: str) -> Tuple[str, tuple]:
    """The current value of one generator, read without advancing it.

    ``GEN_ID(<name>, 0)`` increments by zero and returns the result, so it is
    a read. It is used in preference to the two alternatives because it is the
    only one that is both exact and version-independent:

    * ``RDB$GENERATORS`` records the name and id, never the value -- there is
      no value column to read.
    * ``RDB$GET_CONTEXT('SYSTEM', <name>)`` answers for context variables the
      caller set, not for generator state, so it returns NULL for a generator.

    The call is also transaction-independent: two connections see the same
    number, whereas a value cached in application code would not.
    """
    from rhosocial.activerecord.backend.expression import Identifier

    return select_sql(
        dialect,
        [
            call(
                dialect,
                "gen_id",
                Identifier(dialect, name),
                literal(dialect, 0, inline=True),
                alias="GENERATOR_VALUE",
            )
        ],
        from_=relation(dialect, "RDB$DATABASE"),
    )


def mon_version_sql(dialect: "SQLDialectBase") -> Tuple[str, tuple]:
    """The ``MON$VERSION`` of this attachment (the older way to ask)."""
    return select_sql(
        dialect, [column(dialect, "MON$VERSION")], from_=relation(dialect, "MON$DATABASE")
    )


def database_probe_sql(dialect: "SQLDialectBase") -> Tuple[str, tuple]:
    """``SELECT * FROM RDB$DATABASE``: the last-resort version probe."""
    return select_sql(
        dialect, [all_columns(dialect)], from_=relation(dialect, "RDB$DATABASE")
    )


def health_check_sql(dialect: "SQLDialectBase") -> Tuple[str, tuple]:
    """The cheapest statement that proves the connection answers."""
    return select_sql(
        dialect, [literal(dialect, 1, inline=True)], from_=relation(dialect, "RDB$DATABASE")
    )


def max_connections_sql(dialect: "SQLDialectBase") -> Tuple[str, tuple]:
    """``MON$MAX_CONNECTIONS`` -- present on Firebird 3/4, gone in 5+."""
    return select_sql(
        dialect,
        [column(dialect, "MON$MAX_CONNECTIONS")],
        from_=relation(dialect, "MON$DATABASE"),
    )


__all__ = [
    "all_columns",
    "call",
    "cast",
    "column",
    "compare",
    "conjunction",
    "database_probe_sql",
    "engine_version_sql",
    "generator_value_sql",
    "health_check_sql",
    "identifier",
    "join",
    "like",
    "literal",
    "max_connections_sql",
    "mon_version_sql",
    "multiply",
    "null_test",
    "query",
    "relation",
    "row_count",
    "select_sql",
]
