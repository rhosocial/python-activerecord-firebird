# tests/rhosocial/activerecord_firebird_test/feature/backend/test_expression_roundtrip_all.py
"""
Functional serialization coverage for every expression class the Firebird dialect
has to render: the core expression package *and* this backend's own.

Both packages are collected. The other five backends' matrices cover only their
own package, which is how ``postgres``' ``comment.py`` reading a field core had
removed months earlier stayed green -- the class lived in core, so no backend
matrix ever rendered it. Firebird has no matrix at all, so both gaps apply.

Why ``to_sql()`` is classified rather than caught
==================================================

The testsuite helper ``sql_consistent`` wraps the first render in
``try/except Exception: return``. That makes every render failure a green tick:
the round-trip comparison never runs, so a formatter reading a field that no
longer exists is indistinguishable from a formatter for a feature Firebird does
not support. Each outcome here is named and asserted instead:

* **renders** -- all three encodings must restore byte-identical SQL *and*
  byte-identical bind parameters.
* a member of :data:`LEGITIMATE_NON_RENDERS` -- cannot render for a reason
  belonging to its own tree. Each entry pins the exception type *and* a message
  fragment, so a class that starts failing for a different reason fails here
  rather than staying quietly green.
* ``UnsupportedFeatureError`` from a class *not* named in the dict -- Firebird
  does not model the feature. Asserted as exactly that type, so nothing else can
  hide behind it.
* **anything else** -- a failure naming the class and the exception.

The dict is read before the ``UnsupportedFeatureError`` branch, because core now
reports a *missing formatter* through that same type; see
:func:`assert_sql_roundtrip_classified`.

And when a class cannot be constructed
======================================

``make_instance(...) is None`` becomes a skip, but only for a class named in
:data:`UNCONSTRUCTIBLE`, and ``test_unconstructible_list_is_exact`` pins that
tuple in both directions. A class that gains a constructor fails CI until the
entry is removed; a class that starts failing to build fails CI too. There is no
"at most N" ceiling anywhere in this file -- a ceiling absorbs new gaps, which is
the failure mode this matrix exists to prevent.
"""

import inspect
from typing import Dict

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression import graph as graph_mod
from rhosocial.activerecord.backend.expression.advanced_functions import (
    CaseExpression,
    WindowClause,
    WindowDefinition,
    WindowSpecification,
)
from rhosocial.activerecord.backend.expression.collation import CollateExpression
from rhosocial.activerecord.backend.expression.core import Column, Literal
from rhosocial.activerecord.backend.expression.datetime import (
    TemporalOptionsExpression,
)
from rhosocial.activerecord.backend.expression.objects import (
    Database,
    Domain,
    EdgeTable as EdgeTableObject,
    Function,
    Index,
    MaterializedView,
    NodeTable,
    PropertyGraph,
    Sequence,
    Schema,
    Table,
    Trigger,
    View,
)
from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate
from rhosocial.activerecord.backend.expression.query_parts import JoinClause
from rhosocial.activerecord.backend.expression.serialization import (
    ExpressionRegistry,
    deserialize,
    deserialize_json,
    deserialize_xml,
    serialize,
    serialize_json,
    serialize_xml,
)
from rhosocial.activerecord.backend.expression.sources import NamedRelationRef
from rhosocial.activerecord.backend.impl.firebird.expression.blob import (
    BlobLiteralExpression,
)
from rhosocial.activerecord.backend.impl.firebird.expression.column import (
    FirebirdColumnDefinition,
)
from rhosocial.activerecord.backend.impl.firebird.expression.ddl.domain import (
    FirebirdAlterDomainExpression,
    FirebirdSetDomainDataTypeAction,
)
from rhosocial.activerecord.backend.impl.firebird.expression.ddl.routine import (
    FirebirdCreateFunctionExpression,
    FirebirdCreateProcedureExpression,
)
from rhosocial.activerecord.backend.expression.statements import (
    ddl_alter,
    ddl_comment,
    ddl_database,
    ddl_domain,
    ddl_function,
    ddl_index,
    ddl_schema,
    ddl_sequence,
    ddl_table,
    ddl_trigger,
    ddl_truncate,
    ddl_view,
    dml,
)
from rhosocial.activerecord.backend.expression.statements.ddl_domain import (
    DomainCheckConstraint,
    RenameDomainAction,
)
from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    ColumnConstraint,
    ColumnConstraintType,
    ForeignKeyConstraint,
    IndexDefinition,
    ReferencesClause,
    TableConstraint,
    TableConstraintType,
)
from rhosocial.activerecord.backend.expression.statements.ddl_trigger import (
    TriggerEvent,
    TriggerTiming,
)
from rhosocial.activerecord.backend.expression.statements.dql import QueryExpression
from rhosocial.activerecord.backend.expression.transaction import (
    BeginTransactionExpression,
    SetTransactionExpression,
)
from rhosocial.activerecord.backend.expression.statements.dml import (
    MergeAction,
    MergeActionType,
)
from rhosocial.activerecord.backend.expression.types import IntegerType
from rhosocial.activerecord.backend.expression.types.custom import CustomType
from rhosocial.activerecord.testsuite.utils.expression import (
    collect_expression_classes,
    make_instance,
    register_all,
    register_special_constructor,
    roundtrip_expression,
)

CORE_EXPR_PKG = "rhosocial.activerecord.backend.expression"
FIREBIRD_EXPR_PKG = "rhosocial.activerecord.backend.impl.firebird.expression"

#: Both packages, in the order the report lists them. The core package comes
#: first because most of the interesting classes live there.
MATRIX_PACKAGES = (CORE_EXPR_PKG, FIREBIRD_EXPR_PKG)


def _collect_matrix_classes():
    """Every concrete expression class the two packages define.

    Collected by walking each package, not by reading ``ExpressionRegistry``:
    the registry is process-global and *grows* as sibling test modules import
    their own backends, so reading it makes this matrix's contents depend on
    which files pytest happened to import first. Reading it once in this
    process, once for this purpose, gave three different numbers across three
    sessions; a package walk is deterministic.

    ``ddl_alter`` exports aliases (four spellings of two classes), and several
    modules re-export under a second name. They are the same objects, so the
    first name wins and the matrix does not test one class several times.
    """
    ExpressionRegistry._auto_register_builtins()
    collected: Dict[str, type] = {}
    for package in MATRIX_PACKAGES:
        for fqn, cls in sorted(collect_expression_classes(package).items()):
            collected.setdefault(fqn, cls)
    register_all(collected)

    by_identity: Dict[int, str] = {}
    for fqn, cls in sorted(collected.items()):
        by_identity.setdefault(id(cls), fqn)
    return {
        fqn: cls
        for cls in collected.values()
        if not inspect.isabstract(cls)
        for fqn in [by_identity[id(cls)]]
    }


REGISTERED = _collect_matrix_classes()


# ---------------------------------------------------------------------------
# Special constructors: a real value where the introspective guess is a lie
# ---------------------------------------------------------------------------
#
# ``make_instance`` reads each required parameter's annotation and guesses:
# ``"x"`` for a string, ``[]`` for a list, ``IntegerType()`` for a type. That is
# right for a name and wrong for every parameter that wants a catalogue object --
# a Table, an Index, a PropertyGraph -- because a bare ``"x"`` is not one. It is
# also wrong for the containers that require at least one member (CASE, WINDOW,
# JOIN, temporal options) and for the statements that must render without bind
# parameters (DOMAIN CHECK).
#
# Every registration below replaces a guess that would otherwise have produced an
# instance the dialect cannot render. Suffixes are spelled relative to the
# expression package because ``make_instance`` matches with ``str.endswith`` and
# several modules export identically named classes.


def _table_obj(dialect, name="t"):
    """A table with a bare name and no namespace."""
    return Table(dialect, name)


def _column_predicate(dialect):
    """A predicate comparing two columns, so it renders with no bind parameters."""
    return ComparisonPredicate(dialect, "=", Column(dialect, "a"), Column(dialect, "b"))


def _one_column_query(dialect):
    """A single-column ``SELECT`` over a table."""
    return QueryExpression(
        dialect, select=[Column(dialect, "id")], from_=_table_obj(dialect)
    )


def _integer_column(dialect, name="col"):
    """A column definition carrying a *dialect-bound* type.

    The binding is load-bearing, not cosmetic: ``to_sql()`` dispatches on the
    type through its own dialect, so an unbound ``IntegerType()`` raises
    ``ValueError: ... has no dialect bound`` the moment anything renders it.
    """
    return ddl_table.ColumnDefinition(dialect, name, IntegerType(dialect))


def register_specials():
    """Replace every introspective guess that would cost a real assertion."""
    # -- the FROM side ------------------------------------------------------
    register_special_constructor(
        "sources.relation.NamedRelationRef",
        lambda d: NamedRelationRef(d, _table_obj(d)),
    )
    register_special_constructor(
        "query_parts.JoinClause",
        lambda d: JoinClause(
            d,
            left_table=NamedRelationRef(d, _table_obj(d)),
            right_table=NamedRelationRef(d, Table(d, "other")),
            condition=_column_predicate(d),
        ),
    )

    # -- tables -------------------------------------------------------------
    register_special_constructor(
        "statements.ddl_table.CreateTableExpression",
        lambda d: ddl_table.CreateTableExpression(d, _table_obj(d), [_integer_column(d)]),
    )
    register_special_constructor(
        "statements.ddl_table.DropTableExpression",
        lambda d: ddl_table.DropTableExpression(d, _table_obj(d)),
    )
    register_special_constructor(
        "statements.ddl_table.CreateTableLikeExpression",
        lambda d: ddl_table.CreateTableLikeExpression(
            d, _table_obj(d), Table(d, "other")
        ),
    )
    register_special_constructor(
        "statements.ddl_table.CreateTableCloneExpression",
        lambda d: ddl_table.CreateTableCloneExpression(
            d, _table_obj(d), Table(d, "other")
        ),
    )
    register_special_constructor(
        "statements.ddl_table.CreateTableAsExpression",
        lambda d: ddl_table.CreateTableAsExpression(d, _table_obj(d), _one_column_query(d)),
    )
    register_special_constructor(
        "statements.ddl_table.CreateTableFromTemplateExpression",
        lambda d: ddl_table.CreateTableFromTemplateExpression(
            d, _table_obj(d), _one_column_query(d)
        ),
    )
    register_special_constructor(
        "statements.ddl_truncate.TruncateExpression",
        lambda d: ddl_truncate.TruncateExpression(d, _table_obj(d)),
    )
    # Overrides the shared testsuite factory, which binds no dialect to its type.
    register_special_constructor(
        "statements.ddl_table.ColumnDefinition", _integer_column
    )

    # -- indexes ------------------------------------------------------------
    register_special_constructor(
        "statements.ddl_index.CreateIndexExpression",
        lambda d: ddl_index.CreateIndexExpression(
            d, index=Index(d, "i"), table=_table_obj(d), columns=["a"]
        ),
    )
    register_special_constructor(
        "statements.ddl_index.DropIndexExpression",
        lambda d: ddl_index.DropIndexExpression(d, index=Index(d, "i")),
    )
    register_special_constructor(
        "statements.ddl_index.CreateFulltextIndexExpression",
        lambda d: ddl_index.CreateFulltextIndexExpression(
            d, index=Index(d, "i"), table=_table_obj(d), columns=["a"]
        ),
    )
    register_special_constructor(
        "statements.ddl_index.DropFulltextIndexExpression",
        lambda d: ddl_index.DropFulltextIndexExpression(
            d, index=Index(d, "i"), table=_table_obj(d)
        ),
    )
    register_special_constructor(
        "statements.ddl_alter.DropIndex",
        lambda d: ddl_alter.DropIndex(d, Index(d, "i")),
    )

    # -- schemas, sequences, databases, domains, types ---------------------
    register_special_constructor(
        "statements.ddl_schema.CreateSchemaExpression",
        lambda d: ddl_schema.CreateSchemaExpression(d, Schema(d, "s")),
    )
    register_special_constructor(
        "statements.ddl_schema.DropSchemaExpression",
        lambda d: ddl_schema.DropSchemaExpression(d, Schema(d, "s")),
    )
    register_special_constructor(
        "statements.ddl_sequence.CreateSequenceExpression",
        lambda d: ddl_sequence.CreateSequenceExpression(d, Sequence(d, "s")),
    )
    register_special_constructor(
        "statements.ddl_sequence.AlterSequenceExpression",
        lambda d: ddl_sequence.AlterSequenceExpression(d, Sequence(d, "s"), restart=1),
    )
    register_special_constructor(
        "statements.ddl_sequence.DropSequenceExpression",
        lambda d: ddl_sequence.DropSequenceExpression(d, Sequence(d, "s")),
    )
    register_special_constructor(
        "statements.ddl_database.DropDatabaseExpression",
        lambda d: ddl_database.DropDatabaseExpression(d, Database(d, "db")),
    )
    register_special_constructor(
        "statements.ddl_domain.CreateDomainExpression",
        lambda d: ddl_domain.CreateDomainExpression(d, Domain(d, "dom"), IntegerType(d)),
    )
    register_special_constructor(
        "statements.ddl_domain.DropDomainExpression",
        lambda d: ddl_domain.DropDomainExpression(d, Domain(d, "dom")),
    )
    register_special_constructor(
        "statements.ddl_domain.AlterDomainExpression",
        lambda d: ddl_domain.AlterDomainExpression(
            d, Domain(d, "dom"), [RenameDomainAction(d, "other")]
        ),
    )
    # A DOMAIN CHECK is DDL: it must render without bind parameters, so its
    # condition compares two columns rather than a column and a literal.
    register_special_constructor(
        "statements.ddl_domain.DomainCheckConstraint",
        lambda d: DomainCheckConstraint(d, _column_predicate(d), name="chk"),
    )
    # Firebird has no user-defined types -- a DOMAIN is its nearest equivalent --
    # so there is no TypeDefinition to register. CREATE TYPE / ALTER TYPE reach
    # the dialect's own capability gate and report UnsupportedFeatureError, which
    # the classifier accepts for any class; no pin is needed.

    # -- routines, triggers, comments --------------------------------------
    register_special_constructor(
        "statements.ddl_function.DropFunctionExpression",
        lambda d: ddl_function.DropFunctionExpression(d, Function(d, "fn")),
    )
    register_special_constructor(
        "statements.ddl_trigger.CreateTriggerExpression",
        lambda d: ddl_trigger.CreateTriggerExpression(
            d,
            trigger=Trigger(d, "trg"),
            table=_table_obj(d),
            timing=TriggerTiming.BEFORE,
            events=[TriggerEvent.INSERT],
            function=Function(d, "fn"),
        ),
    )
    register_special_constructor(
        "statements.ddl_trigger.DropTriggerExpression",
        lambda d: ddl_trigger.DropTriggerExpression(d, trigger=Trigger(d, "trg")),
    )
    register_special_constructor(
        "statements.ddl_comment.CommentOnExpression",
        lambda d: ddl_comment.CommentOnExpression(d, "table", _table_obj(d), comment="c"),
    )

    # -- views --------------------------------------------------------------
    register_special_constructor(
        "statements.ddl_view.DropViewExpression",
        lambda d: ddl_view.DropViewExpression(d, View(d, "v")),
    )
    register_special_constructor(
        "statements.ddl_view.CreateMaterializedViewExpression",
        lambda d: ddl_view.CreateMaterializedViewExpression(
            d, MaterializedView(d, "mv"), _one_column_query(d)
        ),
    )
    register_special_constructor(
        "statements.ddl_view.DropMaterializedViewExpression",
        lambda d: ddl_view.DropMaterializedViewExpression(d, MaterializedView(d, "mv")),
    )
    register_special_constructor(
        "statements.ddl_view.RefreshMaterializedViewExpression",
        lambda d: ddl_view.RefreshMaterializedViewExpression(
            d, MaterializedView(d, "mv")
        ),
    )

    # -- DML ----------------------------------------------------------------
    register_special_constructor(
        "statements.dml.InsertExpression",
        lambda d: dml.InsertExpression(
            d, into=_table_obj(d), source=dml.ValuesSource(d, [[Literal(d, 1)]])
        ),
    )
    register_special_constructor(
        "statements.dml.DeleteExpression",
        lambda d: dml.DeleteExpression(d, _table_obj(d)),
    )
    register_special_constructor(
        "statements.dml.MergeExpression",
        lambda d: dml.MergeExpression(
            d,
            target_table=_table_obj(d),
            source=NamedRelationRef(d, Table(d, "src")),
            on_condition=_column_predicate(d),
            when_matched=[
                MergeAction(
                    d,
                    MergeActionType.UPDATE,
                    {"a": Literal(d, 1)},
                    _column_predicate(d),
                    "matched",
                )
            ],
        ),
    )
    register_special_constructor(
        "statements.dml.MergeAction",
        lambda d: MergeAction(
            d,
            MergeActionType.UPDATE,
            {"a": Literal(d, 1)},
            _column_predicate(d),
            "matched",
        ),
    )

    # -- constraints and column pieces --------------------------------------
    register_special_constructor(
        "statements.ddl_table.ColumnConstraint",
        lambda d: ColumnConstraint(d, ColumnConstraintType.NOT_NULL, name="c"),
    )
    register_special_constructor(
        "statements.ddl_table.TableConstraint",
        lambda d: TableConstraint(
            d, TableConstraintType.PRIMARY_KEY, name="c", columns=["a"]
        ),
    )
    register_special_constructor(
        "statements.ddl_table.ForeignKeyConstraint",
        lambda d: ForeignKeyConstraint(
            d,
            columns=["a"],
            foreign_key_table=Table(d, "other"),
            foreign_key_columns=["b"],
            name="fk",
        ),
    )
    register_special_constructor(
        "statements.ddl_table.ReferencesClause",
        lambda d: ReferencesClause(d, Table(d, "other"), ["b"]),
    )
    register_special_constructor(
        "statements.ddl_alter.AddColumn",
        lambda d: ddl_alter.AddColumn(d, _integer_column(d)),
    )
    register_special_constructor(
        "statements.ddl_alter.AddIndex",
        lambda d: ddl_alter.AddIndex(d, IndexDefinition(d, "i", ["a"])),
    )
    register_special_constructor(
        "statements.ddl_alter.AddTableConstraint",
        lambda d: ddl_alter.AddTableConstraint(
            d,
            TableConstraint(
                d, TableConstraintType.PRIMARY_KEY, name="c", columns=["a"]
            ),
        ),
    )

    # -- expressions that need at least one member --------------------------
    register_special_constructor(
        "advanced_functions.CaseExpression",
        lambda d: CaseExpression(
            d,
            cases=[(_column_predicate(d), Literal(d, 1))],
            else_result=Literal(d, 0),
        ),
    )
    register_special_constructor(
        "advanced_functions.WindowSpecification",
        lambda d: WindowSpecification(d, partition_by=["a"]),
    )
    register_special_constructor(
        "advanced_functions.WindowDefinition",
        lambda d: WindowDefinition(d, "w", WindowSpecification(d, partition_by=["a"])),
    )
    register_special_constructor(
        "advanced_functions.WindowClause",
        lambda d: WindowClause(
            d, [WindowDefinition(d, "w", WindowSpecification(d, partition_by=["a"]))]
        ),
    )
    # An empty options dict is refused by the formatter, so a time-travel clause
    # needs an actual option.
    register_special_constructor(
        "datetime.TemporalOptionsExpression",
        lambda d: TemporalOptionsExpression(d, {"as_of": "2020-01-01"}),
    )

    # -- property graphs ----------------------------------------------------
    def node_table(d):
        return NodeTable(d, "people")

    def edge_table(d):
        return EdgeTableObject(d, "knows")

    def path_pattern(d):
        return graph_mod.PathPattern(
            d, graph_mod.GraphVertex(d, "n", node_table(d))
        )

    register_special_constructor(
        "graph.GraphVertex", lambda d: graph_mod.GraphVertex(d, "n", node_table(d))
    )
    register_special_constructor(
        "graph.GraphEdge", lambda d: graph_mod.GraphEdge(d, "e", edge_table(d))
    )
    register_special_constructor(
        "graph.VertexTable",
        lambda d: graph_mod.VertexTable(d, node_table(d), key_columns=["id"]),
    )
    register_special_constructor(
        "graph.EdgeTable",
        lambda d: graph_mod.EdgeTable(d, edge_table(d), ["src"], ["dst"]),
    )
    register_special_constructor(
        "graph.QuantifiedPath",
        lambda d: graph_mod.QuantifiedPath(
            d, graph_mod.GraphEdge(d, "e", edge_table(d)), min_repeats=1, max_repeats=3
        ),
    )
    register_special_constructor("graph.PathPattern", path_pattern)
    register_special_constructor(
        "graph.MatchClause", lambda d: graph_mod.MatchClause(d, path_pattern(d))
    )
    register_special_constructor(
        "graph.CreatePropertyGraphExpression",
        lambda d: graph_mod.CreatePropertyGraphExpression(
            d, graph=PropertyGraph(d, "g"),
            vertex_tables=[graph_mod.VertexTable(d, node_table(d))],
        ),
    )
    # The formatter accepts "add"/"drop" against "vertex tables"/"edge tables"/
    # "tables"; anything else is refused.
    register_special_constructor(
        "graph.AlterPropertyGraphExpression",
        lambda d: graph_mod.AlterPropertyGraphExpression(
            d,
            graph=PropertyGraph(d, "g"),
            action="add",
            target="vertex tables",
            vertex_tables=[graph_mod.VertexTable(d, node_table(d))],
        ),
    )
    register_special_constructor(
        "graph.DropPropertyGraphExpression",
        lambda d: graph_mod.DropPropertyGraphExpression(d, graph=PropertyGraph(d, "g")),
    )

    # The three XML classes are deliberately NOT registered. Firebird declares no
    # `format_xml*` method, so a registration would buy no render assertion
    # here, and the generic guess now builds each of them from an empty item
    # list, which is the same thing a registration would have to invent. They are
    # pinned in LEGITIMATE_NON_RENDERS instead, which says why they cannot
    # render.

    # -- Firebird's own ------------------------------------------------------
    # ``data_type`` carries no annotation, so the guess supplies nothing bound
    # and the column cannot render a type. Firebird columns are its own class
    # rather than the core ColumnDefinition, and its ``computed_by`` /
    # ``character_set`` / ``collation`` keyword-only slots are Firebird-only.
    register_special_constructor(
        "impl.firebird.expression.column.FirebirdColumnDefinition",
        lambda d: FirebirdColumnDefinition(d, "col", IntegerType(d)),
    )
    # ALTER DOMAIN needs the actions list; the guess supplies nothing, and the
    # class refuses an action-less ALTER.
    register_special_constructor(
        "impl.firebird.expression.ddl.domain.FirebirdAlterDomainExpression",
        lambda d: FirebirdAlterDomainExpression(
            d, Domain(d, "dom"), actions=[RenameDomainAction(d, "other")]
        ),
    )
    # A SET DOMAIN TYPE action with no data type has nothing to render.
    register_special_constructor(
        "impl.firebird.expression.ddl.domain.FirebirdSetDomainDataTypeAction",
        lambda d: FirebirdSetDomainDataTypeAction(d, IntegerType(d)),
    )
    # The blob literal holds raw bytes and renders them as a hex literal; the
    # guess supplies an int.
    register_special_constructor(
        "impl.firebird.expression.blob.BlobLiteralExpression",
        lambda d: BlobLiteralExpression(d, b"\x01\x02"),
    )
    # COLLATE names a collation Firebird actually declares; the guess's "x" is
    # not one and is refused by name. Firebird's whitelist is UNICODE /
    # UNICODE_CI / UNICODE_CI_AI.
    register_special_constructor(
        "collation.CollateExpression",
        lambda d: CollateExpression(d, Column(d, "a"), "UNICODE_CI"),
    )
    # This backend's own CREATE PROCEDURE / CREATE FUNCTION carry a PSQL ``mode``
    # and render through the same formatter names as the core statements.
    register_special_constructor(
        "impl.firebird.expression.ddl.routine.FirebirdCreateProcedureExpression",
        lambda d: FirebirdCreateProcedureExpression(
            d, "proc", params=[("a", "INTEGER")], body="SELECT 1"
        ),
    )
    register_special_constructor(
        "impl.firebird.expression.ddl.routine.FirebirdCreateFunctionExpression",
        lambda d: FirebirdCreateFunctionExpression(
            d, "fn", params=[("a", "INTEGER")], returns="INTEGER", body="SELECT 1"
        ),
    )

    # -- core CUSTOM needs the type name its ``raw`` slot exists to carry -----
    # ``raw`` defaults to the empty string, the filler skips it, and the class
    # refuses that empty name while constructing -- so it builds fine once it
    # is handed a real one, and there is nothing to skip.
    register_special_constructor(
        "types.custom.CustomType", lambda d: CustomType(d, "VARCHAR(10)")
    )


register_specials()


# ---------------------------------------------------------------------------
# Lists that cannot grow or shrink silently
# ---------------------------------------------------------------------------

#: Classes the generic introspective constructor cannot build, each with the
#: reason it cannot be built.
#:
#: ``test_unconstructible_list_is_exact`` pins this mapping in both directions, so
#: a class that gains a constructor fails CI until its entry is removed, and a
#: class that starts failing to build fails CI too. Nothing here is a ceiling:
#: every entry is a named class with a named reason, and there is no test that
#: passes when the list is *at most* some number.
UNCONSTRUCTIBLE = {
    # -- core: keyword-only parameters the introspective constructor skips ----
    # `name` and `constraint_type` sit behind defaulted positionals and are
    # keyword-only, so the constructor skips them and the class refuses an
    # incomplete action.
    "rhosocial.activerecord.backend.expression.statements.ddl_alter.AlterConstraint":
        "`name` and `constraint_type` are keyword-only behind defaulted positionals.",
    # Same shape as AlterConstraint: the required `name` is keyword-only.
    "rhosocial.activerecord.backend.expression.statements.ddl_alter.ValidateConstraint":
        "the required `name` is keyword-only behind a defaulted positional.",
    # Widens a SQLPredicate into a DomainCheckConstraint and needs one; the guess
    # supplies a bare comparison whose literal would have to render as a bind
    # parameter, which DDL cannot carry.
    "rhosocial.activerecord.backend.expression.statements.ddl_domain.AddDomainCheckAction":
        "needs a SQLPredicate that renders without bind parameters.",
    # Its `values` list is keyword-only behind a defaulted positional, so the
    # constructor skips it and the type declares no members.
    "rhosocial.activerecord.backend.expression.types.enum_.EnumType":
        "the `values` list is keyword-only behind a defaulted positional.",
    # XMLTABLE and the three XML constructors below used to be pinned here. None
    # of the four had a construction gap: each takes its item list as
    # `Sequence[...]`, and the introspective guess read the annotation's own
    # __name__ -- "Sequence" -- matched that against the Table/View/Sequence
    # relation pattern, and handed the parameter a catalogue Sequence object
    # instead of a list. The guess now decides a parameterised alias before
    # testing for a relation name, so all four build and move to
    # LEGITIMATE_NON_RENDERS -- against the `format_xml*` methods Firebird
    # declares no name for, which was the second half of each old reason and is
    # still the reason none of them can render.

    # UUIDCastExpression refuses in __init__, not in to_sql(). Firebird has no
    # cast from text to a UUID, so the refusal is the same whatever the
    # argument, and no registered constructor can hand it something that
    # changes the answer.
    "rhosocial.activerecord.backend.expression.uuid.UUIDCastExpression":
        "refuses in __init__ -- Firebird has no cast from text to a UUID.",
    # The nil/max constant and the generation node refuse the same way, and for
    # the same reason: Firebird spells no UUID SQL, so each says so from
    # __init__ whatever it is handed. Measured with valid arguments -- an
    # invalid ``which`` raises ValueError first and would have hidden this.
    "rhosocial.activerecord.backend.expression.uuid.UUIDConstantExpression":
        "refuses in __init__ -- Firebird spells no UUID constants.",
    "rhosocial.activerecord.backend.expression.uuid.UUIDGenerationExpression":
        "refuses in __init__ -- Firebird has no server-side UUID generator.",
}


#: Classes that construct but cannot render, for a reason belonging to their own
#: tree rather than to a defect. Each entry pins the exception type and a message
#: fragment, so a class that starts failing for a *different* reason fails here.
_NO_FORMATTER = "does not declare its dialect formatting method name"
#: The *dispatch* failure -- ``format_method`` named a method the dialect does not
#: define, so ``to_sql()`` never called anything. Core reported that as
#: ``AttributeError`` and now reports it as ``UnsupportedFeatureError``, which is
#: the type a dialect uses when it *knows* a statement and refuses it. The two are
#: the same type now, so the fragment is what separates them: this is the one
#: phrase only the dispatch's suggestion contains, offering to mix in a mixin.
#: A class that stopped being a dispatch failure and became a genuine refusal
#: would raise the same type and fail on the fragment instead.
_NO_DIALECT_METHOD = "mix in the mixin that provides it"

#: Firebird's COMMENT ON targets a set of things the framework's catalogue has no
#: kind for, so they remain plain strings and there is no object to build. Listed
#: in the test that asserts the dispatch table, not here, because these classes
#: are constructible -- it is their *target* that is a string.
LEGITIMATE_NON_RENDERS = {
    # ---- bases that name an expression category, not a renderable thing ----
    # Each deliberately declares no `format_method`, so `to_sql()` reports there
    # is nothing to dispatch. They are not `inspect.isabstract` -- they are
    # concrete enough to construct -- so the collector keeps them.
    "rhosocial.activerecord.backend.expression.bases.SQLPredicate": (
        NotImplementedError, _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.bases.SQLValueExpression": (
        NotImplementedError, _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.datetime._TemporalValueExpression": (
        NotImplementedError, _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.introspection.IntrospectionExpression": (
        NotImplementedError, _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_alter.AlterTableAction": (
        NotImplementedError, _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.statements.dml.InsertDataSource": (
        NotImplementedError, _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.transaction.TransactionExpression": (
        NotImplementedError, _NO_FORMATTER,
    ),
    # The roots of the object tree. Each concrete object overrides `format_method`
    # with its own `format_*_object`; the base names only what every catalogue
    # object has in common.
    "rhosocial.activerecord.backend.expression.objects.base.SchemaObject": (
        NotImplementedError, _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.objects.relation.RelationObject": (
        NotImplementedError, _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.objects.routine.RoutineObject": (
        NotImplementedError, _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.objects.type_.TypeObject": (
        NotImplementedError, _NO_FORMATTER,
    ),

    # ---- roots whose incompleteness is structural -------------------------
    # The root of the row-source tree. No concrete source renders through
    # `format_table_source`; each overrides `format_method`. The dispatch fails
    # before any formatter runs, so UnsupportedFeatureError, not AttributeError.
    "rhosocial.activerecord.backend.expression.sources.base.TableSource": (
        UnsupportedFeatureError, _NO_DIALECT_METHOD,
    ),
    # The root of the type tree. Every concrete type declares its own generic
    # `name`, which is what `format_data_type` dispatches on; the root declares
    # none. TypeError, not UnsupportedFeatureError, because the class is
    # incomplete rather than the dialect being unable.
    "rhosocial.activerecord.backend.expression.types._base.DataType": (
        TypeError, "does not declare a valid generic type name",
    ),

    # ---- object kinds Firebird does not have ------------------------------
    # Firebird declares no materialized view, foreign table, synonym or property
    # graph, and `format_alter_database_statement` is not among its formatters,
    # so a statement holding one is refused at dispatch rather than silently
    # rendered. The dialect's own comment on the class bases says exactly this.
    # The two type roots that keep an AttributeError further down are the
    # formatter-name *collisions*, which is a different thing: there the dispatch
    # finds a formatter and the formatter trips over a field the core class does
    # not carry.
    "rhosocial.activerecord.backend.expression.objects.graph.PropertyGraph": (
        UnsupportedFeatureError, _NO_DIALECT_METHOD,
    ),
    "rhosocial.activerecord.backend.expression.objects.relation.ForeignTable": (
        UnsupportedFeatureError, _NO_DIALECT_METHOD,
    ),
    "rhosocial.activerecord.backend.expression.objects.relation.MaterializedView": (
        UnsupportedFeatureError, _NO_DIALECT_METHOD,
    ),
    "rhosocial.activerecord.backend.expression.objects.synonym.Synonym": (
        UnsupportedFeatureError, _NO_DIALECT_METHOD,
    ),
    "rhosocial.activerecord.backend.expression.graph.AlterPropertyGraphExpression": (
        UnsupportedFeatureError, _NO_DIALECT_METHOD,
    ),
    "rhosocial.activerecord.backend.expression.graph.CreatePropertyGraphExpression": (
        UnsupportedFeatureError, _NO_DIALECT_METHOD,
    ),
    "rhosocial.activerecord.backend.expression.graph.DropPropertyGraphExpression": (
        UnsupportedFeatureError, _NO_DIALECT_METHOD,
    ),
    "rhosocial.activerecord.backend.expression.graph.ColumnsClause": (
        UnsupportedFeatureError, _NO_DIALECT_METHOD,
    ),
    "rhosocial.activerecord.backend.expression.graph.TablePropertiesClause": (
        UnsupportedFeatureError, _NO_DIALECT_METHOD,
    ),
    "rhosocial.activerecord.backend.expression.graph.EdgeTable": (
        UnsupportedFeatureError, _NO_DIALECT_METHOD,
    ),
    "rhosocial.activerecord.backend.expression.graph.VertexTable": (
        UnsupportedFeatureError, _NO_DIALECT_METHOD,
    ),
    "rhosocial.activerecord.backend.expression.graph.GraphTableExpression": (
        UnsupportedFeatureError, _NO_DIALECT_METHOD,
    ),
    "rhosocial.activerecord.backend.expression.pivot.PivotExpression": (
        UnsupportedFeatureError, _NO_DIALECT_METHOD,
    ),
    "rhosocial.activerecord.backend.expression.pivot.UnpivotExpression": (
        UnsupportedFeatureError, _NO_DIALECT_METHOD,
    ),
    # Firebird has no ALTER DATABASE: the two database statements it declares are
    # CREATE and DROP, which this backend overrides with its own operational
    # option set.
    "rhosocial.activerecord.backend.expression.statements.ddl_database."
    "AlterDatabaseExpression": (
        UnsupportedFeatureError, _NO_DIALECT_METHOD,
    ),

    # ---- a generic type the Firebird type layer does not spell ------------
    # `FirebirdTypeSupportMixin` declares no formatter for these seven generic
    # names. An unsupported *type* is a dialect gap and is reported as one, which
    # is why these are TypeError and not UnsupportedFeatureError.
    "rhosocial.activerecord.backend.expression.types.array.ArrayType": (
        TypeError, "does not support the generic type 'array'",
    ),
    "rhosocial.activerecord.backend.expression.types.datetime_.IntervalType": (
        TypeError, "does not support the generic type 'interval'",
    ),
    # TIME WITH TIME ZONE and TIMESTAMP WITH TIME ZONE exist in Firebird, but
    # only under their own classes; the generic names dispatch to nothing.
    "rhosocial.activerecord.backend.expression.types.datetime_.TimeTzType": (
        TypeError, "does not support the generic type 'timetz'",
    ),
    "rhosocial.activerecord.backend.expression.types.datetime_.TimestampTzType": (
        TypeError, "does not support the generic type 'timestamptz'",
    ),
    "rhosocial.activerecord.backend.expression.types.json_.JsonType": (
        TypeError, "does not support the generic type 'json'",
    ),
    "rhosocial.activerecord.backend.expression.types.json_.JsonBType": (
        TypeError, "does not support the generic type 'jsonb'",
    ),
    "rhosocial.activerecord.backend.expression.types.xml_.XmlType": (
        TypeError, "does not support the generic type 'xml'",
    ),

    # ---- type DDL: Firebird has no user-defined types ---------------------
    # Firebird's nearest equivalent is a DOMAIN, so `supports_create_type()` is
    # False and every CREATE TYPE / ALTER TYPE / DROP TYPE reports
    # UnsupportedFeatureError. That is the ordinary "this dialect lacks the
    # feature" branch, which needs no pin: the classifier accepts
    # UnsupportedFeatureError for any class it does not name.
    #
    # Note that this branch and a missing formatter now raise the *same* type,
    # which is why the entries above carry a fragment. They are distinguished by
    # message, not by class.

    # ---- a formatter name shared by two expression shapes ----------------
    #
    # Three pairs, each one formatter name reached by two incompatible classes.
    # This backend declares its own CREATE DATABASE / CREATE FUNCTION /
    # COMMENT ON expression classes because Firebird's operational DDL has
    # options the core statements do not carry (PAGE_SIZE, SQL SECURITY, PSQL
    # ``mode``, and a comment target that is still a string). Their
    # ``format_method`` values are the same strings the core statements use, so
    # ``to_sql()`` dispatches a core statement to a formatter written for the
    # Firebird subclass and the subclass's fields are absent from the base.
    #
    # The reads on the Firebird side are each self-consistent --
    # ``FirebirdCreateDatabaseExpression`` declares ``file_path``,
    # ``FirebirdCreateFunctionExpression`` declares ``mode``, and
    # ``FirebirdCommentExpression`` declares ``object_name`` -- so this is a
    # collision, not a mis-read. It predates this matrix. Each entry pins the
    # exact missing attribute, so it stops matching the moment either shape
    # changes and whoever fixes the collision finds the pin failing.
    #
    # These three keep ``AttributeError``, and they are why the pins in this file
    # cannot be re-typed in bulk. Core's dispatch now inspects what a formatter
    # *returns*, and that inspection sits after the call. Each colliding read is
    # inside the formatter body -- ``format_create_database_statement`` reading
    # ``expr.file_path``, ``format_create_function_statement`` reading
    # ``expr.mode``, ``format_comment_statement`` reading ``expr.object_name``
    # -- so the formatter never returns and the shape check is never reached.
    # The symptom is unmoved, which is what says the cause is still the collision
    # and not something new; had it become a ``TypeError`` from the shape check,
    # the diagnosis would have had to be rewritten.
    "rhosocial.activerecord.backend.expression.statements.ddl_database."
    "CreateDatabaseExpression": (
        AttributeError, "has no attribute 'file_path'",
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_function."
    "CreateFunctionExpression": (
        AttributeError, "has no attribute 'mode'",
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_comment."
    "CommentOnExpression": (
        AttributeError, "has no attribute 'object_name'",
    ),

    # ---- SQL/XML: Firebird 4 has no XML query functions -------------------
    # The dialect declares no `format_xml*_expression`, so each of these reports
    # a missing formatter rather than emitting SQL the parser would reject.
    #
    # The four that take an item list are pinned here rather than registered
    # above. They used to sit in UNCONSTRUCTIBLE instead, and that was a misread
    # annotation rather than a gap in any of them: `columns`, `attributes` and
    # `items` are annotated `Sequence[...]`, and the guess read the annotation's
    # own `__name__` -- "Sequence" -- as a request for a catalogue `Sequence`.
    # It now decides a parameterised alias first, so each builds, and the only
    # thing left to say about it is the formatter Firebird does not have.
    "rhosocial.activerecord.backend.expression.xml.XMLAggExpression": (
        UnsupportedFeatureError, _NO_DIALECT_METHOD,
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLAttributesExpression": (
        UnsupportedFeatureError, _NO_DIALECT_METHOD,
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLCommentExpression": (
        UnsupportedFeatureError, _NO_DIALECT_METHOD,
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLConcatExpression": (
        UnsupportedFeatureError, _NO_DIALECT_METHOD,
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLElementExpression": (
        UnsupportedFeatureError, _NO_DIALECT_METHOD,
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLExistsExpression": (
        UnsupportedFeatureError, _NO_DIALECT_METHOD,
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLForestExpression": (
        UnsupportedFeatureError, _NO_DIALECT_METHOD,
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLPIExpression": (
        UnsupportedFeatureError, _NO_DIALECT_METHOD,
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLParseExpression": (
        UnsupportedFeatureError, _NO_DIALECT_METHOD,
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLQueryExpression": (
        UnsupportedFeatureError, _NO_DIALECT_METHOD,
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLRootExpression": (
        UnsupportedFeatureError, _NO_DIALECT_METHOD,
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLSerializeExpression": (
        UnsupportedFeatureError, _NO_DIALECT_METHOD,
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLTableExpression": (
        UnsupportedFeatureError, _NO_DIALECT_METHOD,
    ),
}


# ---------------------------------------------------------------------------
# The local SQL assertion: classify the outcome instead of swallowing it
# ---------------------------------------------------------------------------


def assert_sql_roundtrip_classified(fqn, instance, dialect):
    """Assert an expression's SQL survives the round-trip, or say precisely why not.

    Four outcomes, each asserted:

    * **renders** -- all three encodings must restore byte-identical SQL *and*
      byte-identical bind parameters.
    * a member of :data:`LEGITIMATE_NON_RENDERS` -- unrenderable by design,
      asserted as its exact type *and* message fragment.
    * ``UnsupportedFeatureError`` from a class *not* named in the dict -- Firebird
      does not model the feature. Asserted as exactly that type, so a subclass
      raised for an unrelated reason is still visible rather than passing.
    * **anything else** -- a failure naming the class and the exception.

    The dict is consulted before the ``UnsupportedFeatureError`` branch, not
    after. Core reports a missing formatter as ``UnsupportedFeatureError`` too, so
    with the ``except`` clause in front a pinned dispatch-failure entry would
    never be looked up: its type and message would go unasserted on this path and
    the table would have stopped saying which of the two causes each class has.
    Checking the pin first keeps both halves of it load-bearing.

    Returns the branch taken, so a caller can report the classification
    distribution.

    Raises:
        AssertionError: On a round-trip mismatch, on an unexpected exception
            type, or when a class's rendering outcome changed.
    """
    try:
        expected_sql, expected_params = instance.to_sql()
    except Exception as exc:
        if fqn in LEGITIMATE_NON_RENDERS:
            expected_type, fragment = LEGITIMATE_NON_RENDERS[fqn]
            assert type(exc) is expected_type, (
                f"{fqn}: LEGITIMATE_NON_RENDERS pins this class as a legitimate "
                f"non-render raising {expected_type.__name__}, but it raised "
                f"{type(exc).__name__}: {exc}"
            )
            assert fragment in str(exc), (
                f"{fqn}: expected {expected_type.__name__} and was expected to say "
                f"{fragment!r}, but it said: {exc}"
            )
            return "non-render"
        if type(exc) is UnsupportedFeatureError:
            return "unsupported"
        raise AssertionError(
            f"{fqn}: to_sql() raised {type(exc).__name__}, which is neither a "
            f"render nor a classified non-render, and this is a defect.\n"
            f"  UnsupportedFeatureError means Firebird lacks the feature and "
            f"is always allowed.\n"
            f"  A class that cannot render for a reason belonging to its own "
            f"tree belongs in LEGITIMATE_NON_RENDERS.\n"
            f"  A class whose *constructor* guess is wrong belongs in "
            f"register_specials() instead.\n"
            f"  Exception: {exc}"
        ) from exc

    for channel, decoded in (
        ("dict", deserialize(serialize(instance), dialect)),
        ("json", deserialize_json(serialize_json(instance), dialect)),
        ("xml", deserialize_xml(serialize_xml(instance), dialect)),
    ):
        decoded_sql, decoded_params = decoded.to_sql()
        assert decoded_sql == expected_sql, (
            f"{fqn}: {channel} round-trip changed the SQL.\n"
            f"  original: {expected_sql!r}\n"
            f"  {channel}: {decoded_sql!r}"
        )
        assert decoded_params == expected_params, (
            f"{fqn}: {channel} round-trip changed the bind parameters.\n"
            f"  original: {expected_params!r}\n"
            f"  {channel}: {decoded_params!r}"
        )
    return "rendered"


@pytest.fixture(params=[fqn for fqn in sorted(REGISTERED)], ids=sorted(REGISTERED))
def expr_case(request, fb4_dialect):
    fqn = request.param
    cls = REGISTERED[fqn]
    instance, source = make_instance(cls, fb4_dialect)
    if instance is None:
        assert fqn in UNCONSTRUCTIBLE, (
            f"{fqn} cannot be built by the generic constructor ({source}) and is "
            f"not in UNCONSTRUCTIBLE. Either register a special constructor for "
            f"it or add it with a reason -- do not let it disappear into a skip."
        )
        pytest.skip(f"{fqn}: pinned in UNCONSTRUCTIBLE, cannot be constructed ({source})")
    return fqn, instance


class TestExpressionRoundtripAll:
    """All constructible expression classes round-trip through all encodings."""

    def test_get_params_roundtrip_across_encodings(self, expr_case, fb4_dialect):
        from rhosocial.activerecord.testsuite.utils.expression import roundtrip_expression

        fqn, instance = expr_case
        roundtrip_expression(fqn, instance, fb4_dialect)

    def test_to_sql_roundtrip_classified(self, expr_case, fb4_dialect):
        """A render must survive the round-trip; a non-render must be classified."""
        fqn, instance = expr_case
        assert_sql_roundtrip_classified(fqn, instance, fb4_dialect)


class TestMatrixIntegrity:
    """Guards on the matrix and its lists, so neither can quietly change."""

    def test_unconstructible_list_is_exact(self, fb4_dialect):
        """Pin the unconstructible mapping against what the constructor skips.

        Both directions are checked. A class named here that now builds has gained
        a constructor and the entry is stale; a class that fails to build without
        being named would become a silent skip. Both fail here.
        """
        ExpressionRegistry._auto_register_builtins()
        actual = {
            fqn
            for fqn in REGISTERED
            if make_instance(REGISTERED[fqn], fb4_dialect)[0] is None
        }
        assert actual == set(UNCONSTRUCTIBLE), (
            "the set of expression classes the generic constructor cannot build "
            "changed.\n"
            f"  now skipped but not named: {sorted(actual - set(UNCONSTRUCTIBLE))}\n"
            f"  named but now built: {sorted(set(UNCONSTRUCTIBLE) - actual)}\n"
            "Each new entry needs a reason in the comment above UNCONSTRUCTIBLE."
        )

    def test_unconstructible_entries_all_have_a_reason(self):
        """No entry is a bare name.

        A name with no reason is indistinguishable from a lazy skip, and an empty
        string would pass a truthiness check on the tuple while saying nothing.
        """
        missing = sorted(
            fqn for fqn, reason in UNCONSTRUCTIBLE.items() if not reason.strip()
        )
        assert not missing, f"UNCONSTRUCTIBLE entries without a reason: {missing}"

    def test_unconstructible_entries_are_real_classes(self):
        """Every entry names a class that was actually collected."""
        unknown = set(UNCONSTRUCTIBLE) - set(REGISTERED)
        assert not unknown, (
            f"UNCONSTRUCTIBLE names classes that were not registered: {sorted(unknown)}"
        )

    def test_legitimate_non_renders_are_real_classes(self):
        """Every pinned non-render names a class that was actually collected."""
        unknown = set(LEGITIMATE_NON_RENDERS) - set(REGISTERED)
        assert not unknown, (
            f"LEGITIMATE_NON_RENDERS names classes that were not registered: "
            f"{sorted(unknown)}"
        )

    def test_pinned_non_render_really_does_not_render(self, fb4_dialect):
        """Each pinned entry still raises what it claims, for the stated reason.

        Without this, an entry could sit in the mapping for a class that renders
        perfectly well, and the matrix would assert nothing about it.
        """
        for fqn, (expected_type, fragment) in LEGITIMATE_NON_RENDERS.items():
            instance, source = make_instance(REGISTERED[fqn], fb4_dialect)
            assert instance is not None, (
                f"{fqn} is pinned as a non-render but could not be constructed "
                f"({source})"
            )
            with pytest.raises(expected_type) as exc_info:
                instance.to_sql()
            assert fragment in str(exc_info.value), (
                f"{fqn}: expected the message to mention {fragment!r}, got: "
                f"{exc_info.value}"
            )

    def test_matrix_covers_both_packages(self):
        """The matrix covers every concrete class both packages define.

        Re-walked here rather than trusting the module-level collection, so a
        class that appeared after import is caught. The package walk is used
        rather than the registry because the registry also holds whatever
        backends other test modules happened to import.
        """
        ExpressionRegistry._auto_register_builtins()
        expected = set(_collect_matrix_classes())
        stray = [
            fqn
            for fqn in REGISTERED
            if not any(fqn.startswith(f"{pkg}.") for pkg in MATRIX_PACKAGES)
        ]
        assert not stray, f"classes outside both packages are in the matrix: {stray}"
        assert expected == set(REGISTERED), (
            "the set of classes the two packages define changed after "
            f"collection.\n  now defined but not covered: "
            f"{sorted(expected - set(REGISTERED))}\n"
            f"  covered but no longer defined: {sorted(set(REGISTERED) - expected)}"
        )

    def test_every_package_contributes(self, fb4_dialect):
        """Neither package is collected empty.

        The core package going missing is the exact failure that let a backend
        formatter read a removed field and stay green; the backend package going
        missing would leave this backend's own DDL uncovered. A bare length
        threshold would absorb that silently, so each side is named and counted.
        """
        core = [f for f in REGISTERED if f.startswith(f"{CORE_EXPR_PKG}.")]
        firebird = [f for f in REGISTERED if f.startswith(f"{FIREBIRD_EXPR_PKG}.")]
        assert core, "no core expression class was collected"
        assert firebird, "no Firebird expression class was collected"
        print(
            f"\nexpression matrix: {len(core)} core classes, "
            f"{len(firebird)} Firebird classes, {len(REGISTERED)} total"
        )

    def test_every_covered_class_is_registered_for_deserialization(self):
        """A class in the matrix can be found again when deserializing.

        Deserialization looks the class up by name, so a class the matrix renders
        but the registry cannot resolve would round-trip into the wrong thing or
        nothing at all.

        This is the one place the registry is read, and it is a membership check
        over an already-collected set -- never a source of tests. Discovery is
        the package walk in :func:`_collect_matrix_classes`, precisely because
        the registry is process-global and grows as sibling modules import their
        own backends.
        """
        ExpressionRegistry._auto_register_builtins()
        unresolved = sorted(set(REGISTERED) - set(ExpressionRegistry._registry))
        assert not unresolved, (
            f"the matrix covers classes the registry cannot resolve: {unresolved}"
        )

    def test_coverage_report(self, fb4_dialect):
        """Surface the classification, so coverage stays transparent.

        Counts each branch the matrix actually took, in this process, with this
        dialect -- not a number carried over from another run.
        """
        ExpressionRegistry._auto_register_builtins()
        census: Dict[str, int] = {}
        for fqn, cls in sorted(REGISTERED.items()):
            instance, _ = make_instance(cls, fb4_dialect)
            if instance is None:
                branch = "pinned-unconstructible"
            else:
                branch = assert_sql_roundtrip_classified(fqn, instance, fb4_dialect)
            census[branch] = census.get(branch, 0) + 1
        assert sum(census.values()) == len(REGISTERED)
        print(
            "\nexpression matrix: "
            + ", ".join(f"{count} {name}" for name, count in sorted(census.items()))
            + f" (of {len(REGISTERED)} collected)"
        )


# ---------------------------------------------------------------------------
# The clause-pair parameters round-trip
# ---------------------------------------------------------------------------
#
# The sweep above builds every class once with introspective defaults, which
# leaves every two-spelling pair unset. The fields the round split would
# therefore not be exercised by it. Each pair is instantiated here with one
# spelling set and round-tripped through all three encodings; ``get_params``
# reads the constructor signature, so a pair field the serializer dropped or
# normalized would surface as a parameter mismatch. Both spellings are built
# and their parameter maps compared, so a serializer that conflated them is
# caught even though the pair may be inexpressible on Firebird's server.

PAIR_BEARING_CASES = (
    (
        "CreateSequenceExpression.cycle",
        lambda d: ddl_sequence.CreateSequenceExpression(d, Sequence(d, "s"), cycle=True),
        lambda d: ddl_sequence.CreateSequenceExpression(d, Sequence(d, "s"), no_cycle=True),
        "cycle",
        "no_cycle",
        True,
        True,
    ),
    (
        "CreateSequenceExpression.cache",
        lambda d: ddl_sequence.CreateSequenceExpression(d, Sequence(d, "s"), cache=10),
        lambda d: ddl_sequence.CreateSequenceExpression(d, Sequence(d, "s"), no_cache=True),
        "cache",
        "no_cache",
        10,
        True,
    ),
    (
        "CreateSequenceExpression.order",
        lambda d: ddl_sequence.CreateSequenceExpression(d, Sequence(d, "s"), order=True),
        lambda d: ddl_sequence.CreateSequenceExpression(d, Sequence(d, "s"), no_order=True),
        "order",
        "no_order",
        True,
        True,
    ),
    (
        "AlterSequenceExpression.cycle",
        lambda d: ddl_sequence.AlterSequenceExpression(d, Sequence(d, "s"), cycle=True),
        lambda d: ddl_sequence.AlterSequenceExpression(d, Sequence(d, "s"), no_cycle=True),
        "cycle",
        "no_cycle",
        True,
        True,
    ),
    (
        "AlterSequenceExpression.cache",
        lambda d: ddl_sequence.AlterSequenceExpression(d, Sequence(d, "s"), cache=10),
        lambda d: ddl_sequence.AlterSequenceExpression(d, Sequence(d, "s"), no_cache=True),
        "cache",
        "no_cache",
        10,
        True,
    ),
    (
        "AlterSequenceExpression.order",
        lambda d: ddl_sequence.AlterSequenceExpression(d, Sequence(d, "s"), order=True),
        lambda d: ddl_sequence.AlterSequenceExpression(d, Sequence(d, "s"), no_order=True),
        "order",
        "no_order",
        True,
        True,
    ),
    (
        "IdentityClause.cycle",
        lambda d: ddl_table.IdentityClause(d, cycle=True),
        lambda d: ddl_table.IdentityClause(d, no_cycle=True),
        "cycle",
        "no_cycle",
        True,
        True,
    ),
    (
        "IdentityClause.cache",
        lambda d: ddl_table.IdentityClause(d, cache=10),
        lambda d: ddl_table.IdentityClause(d, no_cache=True),
        "cache",
        "no_cache",
        10,
        True,
    ),
    (
        "IdentityClause.order",
        lambda d: ddl_table.IdentityClause(d, order=True),
        lambda d: ddl_table.IdentityClause(d, no_order=True),
        "order",
        "no_order",
        True,
        True,
    ),
    (
        "ForeignKeyConstraint.deferrable",
        lambda d: ddl_table.ForeignKeyConstraint(
            d, columns=["a"], foreign_key_table=Table(d, "t2"),
            foreign_key_columns=["b"], deferrable=True,
        ),
        lambda d: ddl_table.ForeignKeyConstraint(
            d, columns=["a"], foreign_key_table=Table(d, "t2"),
            foreign_key_columns=["b"], not_deferrable=True,
        ),
        "deferrable",
        "not_deferrable",
        True,
        True,
    ),
    (
        "ForeignKeyConstraint.initially",
        lambda d: ddl_table.ForeignKeyConstraint(
            d, columns=["a"], foreign_key_table=Table(d, "t2"),
            foreign_key_columns=["b"], initially_deferred=True,
        ),
        lambda d: ddl_table.ForeignKeyConstraint(
            d, columns=["a"], foreign_key_table=Table(d, "t2"),
            foreign_key_columns=["b"], initially_immediate=True,
        ),
        "initially_deferred",
        "initially_immediate",
        True,
        True,
    ),
    (
        "TableConstraint.enforced",
        lambda d: ddl_table.TableConstraint(
            d, TableConstraintType.CHECK,
            check_condition=ComparisonPredicate(d, ">", Column(d, "a"), Column(d, "b")),
            enforced=True,
        ),
        lambda d: ddl_table.TableConstraint(
            d, TableConstraintType.CHECK,
            check_condition=ComparisonPredicate(d, ">", Column(d, "a"), Column(d, "b")),
            not_enforced=True,
        ),
        "enforced",
        "not_enforced",
        True,
        True,
    ),
    (
        "BeginTransactionExpression.deferrable",
        lambda d: BeginTransactionExpression(d, deferrable=True),
        lambda d: BeginTransactionExpression(d, not_deferrable=True),
        "deferrable",
        "not_deferrable",
        True,
        True,
    ),
    (
        "SetTransactionExpression.deferrable",
        lambda d: SetTransactionExpression(d, deferrable=True),
        lambda d: SetTransactionExpression(d, not_deferrable=True),
        "deferrable",
        "not_deferrable",
        True,
        True,
    ),
    (
        "DropTableExpression.cascade",
        lambda d: ddl_table.DropTableExpression(d, Table(d, "t"), cascade=True),
        lambda d: ddl_table.DropTableExpression(d, Table(d, "t"), restrict=True),
        "cascade",
        "restrict",
        True,
        True,
    ),
    (
        "DropViewExpression.cascade",
        lambda d: ddl_view.DropViewExpression(d, View(d, "v"), cascade=True),
        lambda d: ddl_view.DropViewExpression(d, View(d, "v"), restrict=True),
        "cascade",
        "restrict",
        True,
        True,
    ),
    (
        "DropFunctionExpression.cascade",
        lambda d: ddl_function.DropFunctionExpression(d, Function(d, "f"), cascade=True),
        lambda d: ddl_function.DropFunctionExpression(d, Function(d, "f"), restrict=True),
        "cascade",
        "restrict",
        True,
        True,
    ),
)

PAIR_BEARING_IDS = [case[0] for case in PAIR_BEARING_CASES]


class TestClausePairFieldsRoundTrip:
    """The round's new pair fields survive dict / JSON / XML serialization."""

    @pytest.mark.parametrize(
        "case_id,a_builder,b_builder,a,b,a_value,b_value",
        PAIR_BEARING_CASES,
        ids=PAIR_BEARING_IDS,
    )
    def test_a_spelling_round_trips(
        self, fb4_dialect, case_id, a_builder, b_builder, a, b, a_value, b_value
    ):
        instance = a_builder(fb4_dialect)
        params = instance.get_params()
        assert params[a] == a_value, f"{case_id}: {a} was not stored"
        assert not params[b], f"{case_id}: {b} must stay unset"
        roundtrip_expression(f"{case_id}.{a}", instance, fb4_dialect)

    @pytest.mark.parametrize(
        "case_id,a_builder,b_builder,a,b,a_value,b_value",
        PAIR_BEARING_CASES,
        ids=PAIR_BEARING_IDS,
    )
    def test_b_spelling_round_trips(
        self, fb4_dialect, case_id, a_builder, b_builder, a, b, a_value, b_value
    ):
        instance = b_builder(fb4_dialect)
        params = instance.get_params()
        assert params[b] == b_value, f"{case_id}: {b} was not stored"
        assert not params[a], f"{case_id}: {a} must stay unset"
        roundtrip_expression(f"{case_id}.{b}", instance, fb4_dialect)

    def test_the_two_spellings_do_not_share_a_parameter(self, fb4_dialect):
        """A serializer that conflated the pair would pass the tests above."""
        for case_id, a_builder, b_builder, a, b, a_value, b_value in PAIR_BEARING_CASES:
            params_a = a_builder(fb4_dialect).get_params()
            params_b = b_builder(fb4_dialect).get_params()
            assert params_a != params_b, case_id
            assert params_a[a] == a_value and params_b[b] == b_value, case_id
            assert params_a[b] != b_value and params_b[a] != a_value, case_id
