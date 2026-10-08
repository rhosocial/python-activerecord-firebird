# tests/rhosocial/activerecord_firebird_test/feature/backend/dialect/test_qualified_names.py
"""Firebird names are rendered from schema objects, and a namespace is refused.

The two halves of the same contract:

* every relation, generator, domain, routine and trigger renders its name
  through one ``format_<kind>_object``, and every one of those asks
  ``validate_namespace`` and then ``format_qualified_name`` -- the check and the
  spelling, split -- so quoting and case folding have a single owner; and
* Firebird has no namespace, so a name that carries ``schema_name`` or
  ``catalog_name`` is **reported**, not rendered and not dropped. A dropped
  qualification produces SQL that names a different object than the caller
  asked for, which is the failure this layer exists to prevent.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.dialect.mixins import NamespaceMixin
from rhosocial.activerecord.backend.expression import Column, QueryExpression
from rhosocial.activerecord.backend.expression.objects import (
    Domain,
    Function,
    Index,
    Procedure,
    Sequence,
    Table,
    Trigger,
    View,
)
from rhosocial.activerecord.backend.expression.sources import (
    DerivedTableSource,
    NamedRelationRef,
)
from rhosocial.activerecord.backend.expression.statements import (
    ColumnDefinition,
    CreateTableExpression,
    DropTableExpression,
    ForeignKeyConstraint,
    ReferentialAction,
)
from rhosocial.activerecord.backend.expression.types import IntegerType
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.expression.dml import (
    UpdateOrInsertExpression,
)
from rhosocial.activerecord.backend.impl.firebird.introspection.async_introspector import (
    FirebirdAsyncIntrospectorMixin,
)
from rhosocial.activerecord.backend.impl.firebird.mixins.identifier import (
    FirebirdIdentifierMixin,
)
from rhosocial.activerecord.backend.impl.firebird.protocols import (
    FirebirdNamespaceSupport,
    FirebirdRowSourceSupport,
)


@pytest.fixture
def dialect():
    return FirebirdDialect(version=(4, 0, 0))


@pytest.fixture
def qualified(dialect):
    """A reference to ``orders`` carrying a schema Firebird cannot render."""
    return Table(dialect, "orders", schema_name="sales")


#: One formatter per object kind Firebird persists. Each returns
#: ``(sql, params)`` and each is the only place that kind becomes SQL.
OBJECT_FORMATTERS = [
    ("format_table_object", Table),
    ("format_view_object", View),
    ("format_sequence_object", Sequence),
    ("format_domain_object", Domain),
    ("format_function_object", Function),
    ("format_procedure_object", Procedure),
    ("format_trigger_object", Trigger),
    ("format_index_object", Index),
]


class TestRenderingFromSchemaObjects:
    """Every kind renders its name alone, through one entry point per kind."""

    def test_table_name_is_folded_to_upper_case(self, dialect):
        assert dialect.format_table_object(Table(dialect, "orders")) == ('"ORDERS"', ())

    def test_inner_double_quote_is_doubled(self, dialect):
        assert dialect.format_table_object(Table(dialect, 'we"ird')) == ('"WE""IRD"', ())

    @pytest.mark.parametrize("formatter,kind", OBJECT_FORMATTERS)
    def test_params_are_never_bound(self, dialect, formatter, kind):
        sql, params = getattr(dialect, formatter)(kind(dialect, "x"))
        assert params == ()
        assert sql.startswith('"')

    @pytest.mark.parametrize("formatter,kind", OBJECT_FORMATTERS)
    def test_every_kind_folds_case(self, dialect, formatter, kind):
        sql, _ = getattr(dialect, formatter)(kind(dialect, "lower_case"))
        assert sql == '"LOWER_CASE"'

    def test_table_reference_accepts_every_shape(self, dialect):
        assert dialect.format_table_reference("orders") == '"ORDERS"'
        assert dialect.format_table_reference(Table(dialect, "orders")) == '"ORDERS"'

    def test_named_relation_renders_its_alias(self, dialect):
        sql, params = dialect.format_named_relation(
            NamedRelationRef(dialect, Table(dialect, "orders"), alias="o")
        )
        assert sql == '"ORDERS" AS "O"'
        assert params == ()


class TestNamespacesAreRefused:
    """Firebird has one namespace; a carried slot is reported, never dropped."""

    def test_schema_slot_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError, match="schema-qualified"):
            dialect.format_table_object(Table(dialect, "orders", schema_name="sales"))

    def test_catalog_slot_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError, match="catalog-qualified"):
            dialect.format_table_object(Table(dialect, "orders", catalog_name="db"))

    @pytest.mark.parametrize("formatter,kind", OBJECT_FORMATTERS)
    def test_every_kind_refuses_a_schema(self, dialect, formatter, kind):
        with pytest.raises(UnsupportedFeatureError, match="schema-qualified"):
            getattr(dialect, formatter)(kind(dialect, "x", schema_name="sales"))

    @pytest.mark.parametrize("formatter,kind", OBJECT_FORMATTERS)
    def test_every_kind_refuses_a_catalog(self, dialect, formatter, kind):
        with pytest.raises(UnsupportedFeatureError, match="catalog-qualified"):
            getattr(dialect, formatter)(kind(dialect, "x", catalog_name="db"))

    def test_qualification_switches_are_false(self, dialect):
        # These are what validate_namespace reads; a dialect that answered True
        # here would render a qualifier its parser rejects.
        assert dialect.supports_schema_qualification() is False
        assert dialect.supports_catalog_qualification() is False
        assert dialect.supports_catalog() is False

    def test_reference_schema_slot_raises(self, dialect, qualified):
        with pytest.raises(UnsupportedFeatureError, match="schema-qualified"):
            dialect.format_table_reference(qualified)

    def test_named_relation_schema_slot_raises(self, dialect):
        with pytest.raises(UnsupportedFeatureError, match="schema-qualified"):
            dialect.format_named_relation(
                NamedRelationRef(dialect, Table(dialect, "orders", schema_name="sales"))
            )

    def test_temporal_options_are_refused(self, dialect):
        # Firebird has no time-travel clause; rendering the bare name would
        # silently read the wrong rows.
        ref = NamedRelationRef(
            dialect, Table(dialect, "orders"), temporal_options={"as_of": "2020-01-01"}
        )
        with pytest.raises(UnsupportedFeatureError, match="temporal"):
            dialect.format_named_relation(ref)

    def test_validate_methods_refuse_too(self, dialect):
        with pytest.raises(UnsupportedFeatureError):
            dialect.validate_schema_name(Table(dialect, "orders", schema_name="sales"))
        with pytest.raises(UnsupportedFeatureError):
            dialect.validate_catalog_name(Table(dialect, "orders", catalog_name="db"))


class TestStatementsGoThroughTheObjectLayer:
    """The DDL / DML statements a caller reaches most often."""

    def test_create_table_renders_the_accepted_reference(self, dialect):
        columns = [ColumnDefinition(dialect, "id", IntegerType(dialect))]
        expr = CreateTableExpression(dialect, Table(dialect, "orders"), columns)
        sql, params = expr.to_sql()
        assert sql == 'CREATE TABLE "ORDERS" ("ID" INTEGER)'
        assert params == ()

    def test_create_table_refuses_a_qualified_reference(self, dialect, qualified):
        columns = [ColumnDefinition(dialect, "id", IntegerType(dialect))]
        expr = CreateTableExpression(dialect, qualified, columns)
        with pytest.raises(UnsupportedFeatureError, match="schema-qualified"):
            expr.to_sql()

    def test_create_table_renders_a_references_target(self, dialect):
        columns = [
            ColumnDefinition(dialect, "id", IntegerType(dialect)),
            ColumnDefinition(dialect, "user_id", IntegerType(dialect)),
        ]
        fk = ForeignKeyConstraint(
            dialect,
            columns=["user_id"],
            foreign_key_table=Table(dialect, "users"),
            foreign_key_columns=["id"],
            on_delete=ReferentialAction.CASCADE,
            on_update=ReferentialAction.NO_ACTION,
        )
        expr = CreateTableExpression(
            dialect, Table(dialect, "orders"), columns, table_constraints=[fk]
        )
        sql, _ = expr.to_sql()
        assert 'REFERENCES "USERS" ("ID") ON DELETE CASCADE' in sql

    def test_drop_table_renders_and_refuses(self, dialect, qualified):
        assert DropTableExpression(
            dialect=dialect, table=Table(dialect, "orders")
        ).to_sql() == ('DROP TABLE "ORDERS"', ())
        with pytest.raises(UnsupportedFeatureError, match="schema-qualified"):
            DropTableExpression(dialect=dialect, table=qualified).to_sql()

    def test_select_from_a_qualified_relation_is_refused(self, dialect, qualified):
        query = QueryExpression(
            dialect, [Column(dialect, "id")], NamedRelationRef(dialect, qualified)
        )
        with pytest.raises(UnsupportedFeatureError, match="schema-qualified"):
            query.to_sql()

    def test_update_or_insert_renders_its_target(self, dialect):
        expr = UpdateOrInsertExpression(
            dialect, Table(dialect, "orders"), ["id"], [1], ["id"]
        )
        sql, params = expr.to_sql()
        assert sql == (
            'UPDATE OR INSERT INTO "ORDERS" ("ID") VALUES (?) MATCHING ("ID")'
        )
        assert params == (1,)

    def test_update_or_insert_refuses_a_qualified_target(self, dialect, qualified):
        expr = UpdateOrInsertExpression(
            dialect, qualified, ["id"], [1], ["id"]
        )
        with pytest.raises(UnsupportedFeatureError, match="schema-qualified"):
            expr.to_sql()


class TestRowSourceName:
    """The wildcard qualifier comes from the row source's type, not hasattr."""

    def test_relation_name_when_unaliased(self, dialect, qualified):
        assert dialect.row_source_name(NamedRelationRef(dialect, qualified)) == "orders"

    def test_alias_wins_when_present(self, dialect):
        ref = NamedRelationRef(dialect, Table(dialect, "orders"), alias="o")
        assert dialect.row_source_name(ref) == "o"

    def test_named_relation_ref(self, dialect):
        assert dialect.row_source_name(NamedRelationRef(dialect, Table(dialect, "orders"))) == "orders"
        assert dialect.row_source_name(
            NamedRelationRef(dialect, Table(dialect, "orders"), alias="z")
        ) == "z"

    def test_derived_table_is_known_only_by_its_alias(self, dialect):
        query = QueryExpression(
            dialect, [Column(dialect, "id")], NamedRelationRef(dialect, Table(dialect, "orders"))
        )
        assert dialect.row_source_name(DerivedTableSource(dialect, query)) is None
        assert dialect.row_source_name(
            DerivedTableSource(dialect, query, alias="sq")
        ) == "sq"

    @pytest.mark.parametrize("source", ["orders", None, 42])
    def test_non_sources_are_declined(self, dialect, source):
        assert dialect.row_source_name(source) is None


class TestDeclarationMatchesReality:
    """The switches and the protocols say the same thing."""

    def test_schema_is_never_declared_as_a_capability(self, dialect):
        assert dialect.supports_schema() is False
        assert dialect.supports_create_schema() is False
        assert dialect.supports_drop_schema() is False

    def test_view_switches_match_the_renderer(self, dialect):
        # Firebird has neither CREATE OR REPLACE VIEW nor WITH CHECK OPTION;
        # Firebird 4.0's CREATE OR ALTER VIEW is a different statement.
        assert dialect.supports_or_replace_view() is False
        assert dialect.supports_view_check_option() is False

    def test_firebird_namespace_protocol_is_satisfied(self, dialect):
        assert isinstance(dialect, FirebirdNamespaceSupport)
        assert isinstance(dialect, FirebirdRowSourceSupport)

    def test_format_identifier_has_exactly_one_definition(self, dialect):
        owners = [k for k in type(dialect).__mro__ if "format_identifier" in vars(k)]
        # The first owner is the backend's single mixin -- the dialect class
        # itself defines no formatter of its own, which is the point -- and no
        # other Firebird class may carry a competing copy. The core
        # SQLDialectBase still defines one further down the MRO; it loses.
        assert owners[0] is FirebirdIdentifierMixin
        firebird_owners = [
            klass.__name__
            for klass in owners
            if klass.__module__.startswith(
                "rhosocial.activerecord.backend.impl.firebird"
            )
        ]
        assert firebird_owners == [FirebirdIdentifierMixin.__name__]

    @pytest.mark.parametrize("formatter,kind", OBJECT_FORMATTERS)
    def test_object_formatter_has_exactly_one_implementation(
        self, dialect, formatter, kind
    ):
        # The body lives in one core mixin; the *ObjectSupport protocol below it
        # only declares that the method exists. If the protocol's `...` ever won
        # the MRO, every object would render as None -- so this is asserted, not
        # assumed.
        owners = [k for k in type(dialect).__mro__ if formatter in vars(k)]
        assert owners[0].__name__.endswith("NameMixin")
        assert getattr(dialect, formatter)(kind(dialect, "x"))[0].startswith('"')


class TestNamespaceDeclaration:
    """The declaration is the contract, not a validate method's return value.

    ``validate_schema_name`` used to be where Firebird's refusal lived, and it
    still answers it -- an explicit refusal, available under the name callers
    reach for, is better than a validation they have to remember to call. But
    the *rendering* path no longer depends on it: the core's
    ``validate_namespace`` consults ``supports_schema_qualification()``, which is
    ``False``, and refuses before any ``validate_*`` runs. So what a caller -- or
    a test -- should assert is the declaration.
    """

    @pytest.mark.parametrize("switch", ["supports_catalog",
                                        "supports_catalog_qualification",
                                        "supports_schema_qualification"])
    def test_the_declaration_answers_false(self, dialect, switch):
        assert getattr(dialect, switch)() is False, (
            f"{switch}() is not False; the core's validate_namespace would then "
            f"render a qualifier Firebird's parser rejects"
        )

    @pytest.mark.parametrize("slot", ["schema_name", "catalog_name"])
    def test_render_path_refuses_because_of_the_declaration(self, dialect, slot):
        """The refusal comes from the switch, not from a ``validate_*`` override.

        Calling the core's own ``validate_namespace`` directly is the cleanest
        evidence: it is not a Firebird method, so anything it refuses it refused
        by reading a declaration.
        """
        obj = Table(dialect, "orders", **{slot: "sales"})
        with pytest.raises(UnsupportedFeatureError, match="schema-qualified|catalog-qualified"):
            NamespaceMixin.validate_namespace(dialect, obj)

    @pytest.mark.parametrize("slot", ["schema_name", "catalog_name"])
    def test_the_core_validate_namespace_is_the_one_that_runs(self, dialect, slot):
        """The check in the render path is the core's, unmodified.

        If Firebird had shadowed it, the refusal would be coming from somewhere
        this declaration does not describe, and the two could drift apart.
        """
        owner = next(
            klass
            for klass in type(dialect).__mro__
            if "validate_namespace" in vars(klass)
        )
        assert owner is NamespaceMixin, (
            f"validate_namespace resolves to {owner.__name__}; the core's is "
            f"expected so the declaration below is the single source"
        )

    def test_one_naming_side_mixin_only(self, dialect):
        """At most one naming-side mixin, and it is Firebird's.

        Three other backends kept a ``QualifiedNameMixin``-style class next to a
        dozen per-kind ``*NameMixin`` classes; the suffix was not consistent
        across nine repositories for one job. Converging on a single
        ``<Backend>NamespaceMixin`` means a reader looking for "how does this
        dialect spell a name" finds one file.
        """
        owners = [
            klass
            for klass in type(dialect).__mro__
            if "format_qualified_name" in vars(klass)
            and klass.__module__.startswith("rhosocial.activerecord.backend.impl.firebird")
        ]
        assert [k.__name__ for k in owners] == ["FirebirdNamespaceMixin"], (
            f"expected exactly one Firebird class defining format_qualified_name, "
            f"found {[k.__name__ for k in owners]}"
        )

    def test_format_qualified_name_spells_one_level(self, dialect):
        """Zero levels to join, said by the dialect rather than by empty slots.

        The core's spelling joins whatever levels the object carries, so with two
        empty slots it happens to produce one identifier. That is the accident
        this override removes: here the absence of a join is the stated answer,
        and the test below shows what changes if a level ever appears.
        """
        sql, params = dialect.format_qualified_name(Table(dialect, "orders"))
        assert (sql, params) == ('"ORDERS"', ())
        assert "." not in sql, "a separator appeared, so levels were joined"

    @pytest.mark.parametrize("slot", ["schema_name", "catalog_name"])
    def test_format_qualified_name_refuses_a_level_without_being_asked_to(self, dialect, slot):
        """The spelling refuses a carried level on its own.

        The render path validates first, so this is the second line of defence.
        It matters because a caller who reaches ``format_qualified_name``
        directly -- which is a public method on the dialect -- would otherwise
        get a name one level short, and a name one level short names a different
        object. That is the exact failure this layer exists to prevent, so it
        must not be reachable by skipping one call.
        """
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_qualified_name(Table(dialect, "orders", **{slot: "sales"}))

    def test_the_name_actually_comes_from_the_object(self, dialect):
        """Not vacuous: two names, two SQL. A test that cannot fail proves nothing."""
        first = dialect.format_table_object(Table(dialect, "orders"))
        second = dialect.format_table_object(Table(dialect, "invoices"))
        assert first != second
        assert first == ('"ORDERS"', ())
        assert second == ('"INVOICES"', ())

    def test_the_refused_slot_is_not_recoverable_from_the_name(self, dialect):
        """A namespace in the object name is not a namespace slot.

        ``Table(dialect, "sales.orders")`` is one identifier whose text happens
        to contain a dot, not a qualified name. Firebird will render it -- it is
        a legal quoted identifier -- and that is correct: the caller asked for an
        object called ``sales.orders``. What it must not do is read the dot as a
        schema, or invent a qualification from it. Asserted so a future "helpfully
        parse qualified names" change is caught rather than welcomed.
        """
        sql, _ = dialect.format_table_object(Table(dialect, "sales.orders"))
        assert sql == '"SALES.ORDERS"'
        assert "." in sql, "the dot is part of the identifier, so this guards the shape"


class TestIntrospectionNamespace:
    """Introspection takes the core's ``schema`` argument and refuses it."""

    class _Probe(FirebirdAsyncIntrospectorMixin):
        def __init__(self, dialect):
            self._backend = type("_B", (), {"dialect": dialect})()

    @pytest.mark.parametrize("schema", [None, ""])
    def test_absent_namespace_is_fine(self, dialect, schema):
        probe = self._Probe(dialect)
        assert probe._make_table_list_sql(schema, False, True, None)[1] == ()
        assert probe._make_column_list_sql("orders", schema)[1] == ("orders",)
        assert probe._make_index_list_sql("orders", schema)[1] == ("orders",)
        assert probe._make_foreign_key_sql("orders", schema)[1] == ("orders",)
        assert probe._make_view_list_sql(schema)[1] == ()
        assert probe._build_primary_key_sql("orders", schema)[1] == ("orders",)

    @pytest.mark.parametrize(
        "call",
        [
            lambda p: p._make_table_list_sql("sales", False, True, None),
            lambda p: p._make_column_list_sql("orders", "sales"),
            lambda p: p._make_index_list_sql("orders", "sales"),
            lambda p: p._make_foreign_key_sql("orders", "sales"),
            lambda p: p._make_view_list_sql("sales"),
            lambda p: p._build_primary_key_sql("orders", "sales"),
            lambda p: p._build_table_list_sql("sales", False, True, None),
        ],
    )
    def test_named_namespace_raises(self, dialect, call):
        probe = self._Probe(dialect)
        with pytest.raises(UnsupportedFeatureError, match="schema-scoped introspection"):
            call(probe)

    def test_default_schema_is_empty(self, dialect):
        assert self._Probe(dialect)._get_default_schema() == ""
