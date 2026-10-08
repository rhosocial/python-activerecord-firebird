# src/rhosocial/activerecord/backend/impl/firebird/mixins/namespace.py
"""Firebird's rendering of named things, and its refusal of namespaces it lacks.

Firebird has one namespace and no way to name it, so the refusal is the point.
A Firebird name renders as its own quoted identifier or not at all: a qualified
name Firebird's parser cannot read resolves to some other object or to nothing,
and the two easy alternatives -- drop the schema, or pretend the engine has
schemas -- are exactly the failures this layer exists to remove.

**Zero levels, said out loud.** The core builds a qualified name by joining
whichever namespace levels the object carries with :attr:`separator`. On Firebird
both outer levels are permanently empty, so the core's spelling works here only
by the accident that an empty list joins to its own single element. This mixin
overrides :meth:`format_qualified_name` to spell the one level Firebird has --
one identifier, no join -- and to refuse a carried level itself rather than
relying on the caller having validated first. That is the difference between a
dialect that *declares* zero levels and one that happens to have two empty slots.

**The refusal lives under three names, on purpose.** The switches
(:meth:`supports_catalog`, :meth:`supports_catalog_qualification`,
:meth:`supports_schema_qualification`) are what the core's
:meth:`~rhosocial.activerecord.backend.dialect.mixins.schema_namespace.NamespaceMixin.validate_namespace`
reads, so declaring them False is what makes rendering refuse.
:meth:`validate_schema_name` and :meth:`validate_catalog_name` answer the same
refusal under the name a caller reaches for directly, and
:meth:`format_qualified_name` repeats it so that no call order can produce a
dropped qualification. See :mod:`..protocols.namespace` for the engine-level
argument.

Object rendering itself is not overridden here. Every ``format_<kind>_object``
comes from the core ``*NameMixin`` classes mixed into the dialect; what Firebird
contributes is :meth:`~...identifier.FirebirdIdentifierMixin.format_identifier`,
which every one of them reaches through, so quoting and case folding have a
single owner.

What *is* Firebird's own is the ``FROM`` side, which is also naming: a relation
reference may not carry temporal options, because Firebird has no time-travel
clause and rendering the bare name would silently read the wrong rows; and the
name a row source can be qualified by is read from the source's type.

* :class:`Table` for relations -- ``CREATE TABLE``, ``REFERENCES``,
  ``UPDATE OR INSERT``, a trigger's ``ON`` relation, ``COMMENT ON TABLE`` /
  ``COLUMN``;
* :class:`Sequence` for generators -- ``CREATE GENERATOR`` / ``SEQUENCE``,
  ``GEN_ID(...)``, ``NEXT VALUE FOR``, ``COMMENT ON GENERATOR``;
* :class:`Domain`, :class:`Procedure` / :class:`Function` and
  :class:`Trigger` for the other object kinds the engine persists.

A view is the same kind of object as a table as far as a name is concerned,
so both go through the same formatter.
"""

from typing import Any, Optional, Tuple, Union

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.dialect.mixins.relation_source import (
    RelationSourceMixin,
)
from rhosocial.activerecord.backend.expression.objects import (
    SchemaObject,
    Table,
)
from rhosocial.activerecord.backend.expression.sources import NamedRelationRef, TableSource


class FirebirdNamespaceMixin(RelationSourceMixin):
    """Renders Firebird names, and refuses the namespaces Firebird has none of."""

    # ------------------------------------------------------------------ #
    # The namespace spelling: exactly one level
    # ------------------------------------------------------------------ #

    def format_qualified_name(self, expr: SchemaObject) -> Tuple[str, tuple]:
        """Spell *expr*'s name as its single quoted identifier.

        Firebird declares no namespace above the database file, so there is
        nothing to join and no ``separator`` to choose: the name is one
        identifier. Saying that here rather than letting the core's
        "join whatever levels are present" happen to produce one element is the
        point of overriding -- a dialect that renders correctly because two slots
        are empty is a dialect that would render wrongly the moment one of them
        was not.

        The level check is repeated even though
        :meth:`~rhosocial.activerecord.backend.dialect.mixins.schema_namespace.NamespaceMixin.validate_namespace`
        has already made it, so that this method cannot be reached in an order
        that drops a qualification. A caller who skips the validation gets an
        error, never a shorter name.

        Raises:
            UnsupportedFeatureError: The object carries a namespace level this
                dialect declares it cannot express.
        """
        if expr.catalog_name or expr.schema_name:
            self._refuse_namespace(expr)
        return self.format_identifier(expr.name, expr.name_need_quote), ()

    # ------------------------------------------------------------------ #
    # The namespace refusals, under the names callers use directly
    # ------------------------------------------------------------------ #

    def validate_schema_name(self, obj: Any) -> None:
        """Reject an inner namespace; Firebird has none.

        An explicit refusal, so the answer is available under the name callers
        use rather than only as a side effect of rendering. Rendering reaches the
        same verdict through :meth:`supports_schema_qualification`, which is
        ``False`` for this dialect; this method is the direct route, and a caller
        that asks first is not made to render to find out.
        """
        if getattr(obj, "schema_name", None):
            raise UnsupportedFeatureError(
                self.name,
                "schema-qualified names",
                suggestion=(
                    "Firebird has a single unnamed namespace; a schema cannot "
                    "be qualified on a name."
                ),
            )

    def validate_catalog_name(self, obj: Any) -> None:
        """Reject an outer namespace; there is nothing above the database file."""
        if getattr(obj, "catalog_name", None):
            raise UnsupportedFeatureError(
                self.name,
                "catalog-qualified names",
                suggestion=(
                    "Firebird has nothing above the database file; a catalog "
                    "cannot be qualified on a name."
                ),
            )

    def _refuse_namespace(self, expr: SchemaObject) -> None:
        """The refusal both :meth:`format_qualified_name` and the core's
        :meth:`validate_namespace` reach, in one place so the message and the
        feature named are the same whichever route the caller took."""
        if getattr(expr, "catalog_name", None):
            self.validate_catalog_name(expr)
        # validate_catalog_name always raises when it is reached, so anything
        # still standing here carries the inner level.
        self.validate_schema_name(expr)

    # ------------------------------------------------------------------ #
    # Relation references
    # ------------------------------------------------------------------ #

    def format_table_reference(self, ref: Union[Table, str]) -> str:
        """Render whatever a statement hands over as a table reference.

        Accepts a :class:`Table` schema object or a bare ``str``. A
        :class:`Table` is rendered as itself, so a ``schema_name`` it carries is
        reported rather than dropped; a ``str`` becomes a quoted table, because
        the ORM layer hands the backend a bare name and there is nothing else it
        could mean.

        The alias is **not** rendered: this renders the *object*, so a
        reference that also carries one is still a valid argument -- an
        ``INSERT`` target must not grow ``AS "alias"``. A ``FROM`` clause that
        does want the alias goes through :meth:`format_named_relation`.

        Raises:
            TypeError: *ref* is neither a Table nor a ``str``. Any other object
                kind would have had its own name rendered as the relation's,
                because it carries its own ``format_method`` -- so a generator
                passed here would produce a well-formed statement naming a
                sequence where a relation was meant.
        """
        if isinstance(ref, Table):
            return self.format_table_object(ref)[0]
        if isinstance(ref, str):
            return self.format_table_object(Table(self, ref))[0]
        raise TypeError(
            f"format_table_reference must take a Table or a str, "
            f"got {type(ref).__name__}"
        )

    def format_named_relation(self, ref: NamedRelationRef) -> Tuple[str, tuple]:
        """Render a ``FROM`` reference to a named relation.

        The name and the alias are the core's business -- the relation renders
        itself and the alias belongs to the query. What Firebird adds is the
        refusal: there is no time-travel clause, so a reference that asks for
        one is reported rather than rendered as the bare name, which would
        silently read the wrong rows.

        Raises:
            UnsupportedFeatureError: The reference carries temporal options.
        """
        if ref.temporal_options:
            raise UnsupportedFeatureError(
                self.name,
                "temporal table options",
                suggestion=(
                    "Firebird has no time-travel clause; the reference asked "
                    "for one and it cannot be rendered."
                ),
            )
        return super().format_named_relation(ref)

    # ------------------------------------------------------------------ #
    # Row sources
    # ------------------------------------------------------------------ #

    def row_source_name(self, source: Any) -> Optional[str]:
        """The name a single row source is known by, or ``None``.

        Firebird rejects ``SELECT *, other ...`` (Token unknown, error -104)
        and wants the wildcard qualified, so :meth:`format_query_statement`
        asks here what to qualify by.

        The answer is read from the source's type rather than probed for with
        ``hasattr``. Probing matched anything carrying an ``alias`` or a
        ``name`` attribute, which a derived table satisfies without naming any
        relation; the type check below says what each source can actually be
        known by.
        """
        if isinstance(source, NamedRelationRef):
            return source.alias or source.relation.name
        if isinstance(source, TableSource):
            # Derived tables and table functions have no catalogue relation,
            # so the alias is the only name they can be reached by.
            return source.alias or None
        return None
