# src/rhosocial/activerecord/backend/impl/firebird/protocols/namespace.py
"""What Firebird declares about namespaces.

The verdict, stated once: **Firebird has no namespace above the database
file.** Not "the dialect has not implemented it yet" -- the engine has no
such concept.

* There is no ``CREATE SCHEMA``; a Firebird database has exactly one object
  namespace.
* A relation name cannot be qualified. ``SELECT * FROM "PUBLIC"."USERS"`` is
  a syntax error; to read another user's relation you set ``SQL SECURITY
  DEFINER`` on the calling routine, not a qualified name.
* ``RDB$...`` system tables are a *naming convention*, not a namespace: they
  are ordinary relations whose names begin with ``RDB$``, filtered with
  ``RDB$SYSTEM_FLAG``, and they are reached unqualified like any other.
* Firebird's ownership metadata (``RDB$OWNER_NAME``, ``RDB$OWNER_TYPE``)
  records who created a relation. It is authorisation bookkeeping and cannot
  appear in a name, so it is not a namespace.

So every name Firebird renders carries no namespace slot, and there are **zero
levels to join** -- not two slots that happen to be empty. Three things express
that, and they are kept in step by
:class:`~...mixins.namespace.FirebirdNamespaceMixin`:

* the three naming switches answer ``False``, which is what the core's
  ``validate_namespace`` reads, so a ``schema_name`` or ``catalog_name`` on any
  object is reported rather than dropped, whatever statement is holding it;
* ``validate_schema_name`` / ``validate_catalog_name`` state the same refusal
  under the names callers reach for directly, so the answer is available
  without rendering; and
* ``format_qualified_name`` spells exactly one identifier and refuses a carried
  level itself, so no call order can produce a shorter name.

The core ``SchemaMixin`` still supplies the granular
``supports_create_schema()`` family -- all False -- because those are public DDL
switches and callers ask for them by name. Naming questions and DDL questions
have different owners, and an engine can answer the two differently; here it
answers both the same way, for the same reason.

:class:`FirebirdNamespaceSupport` is the single place this answer lives, so
that the switches and the renderer cannot drift apart.
"""

from typing import Tuple, Protocol, runtime_checkable

from rhosocial.activerecord.backend.expression.objects import SchemaObject


@runtime_checkable
class FirebirdNamespaceSupport(Protocol):
    """A dialect whose engine has one, unnamed namespace.

    Satisfied by
    :class:`~...mixins.namespace.FirebirdNamespaceMixin` together with the core
    ``SchemaMixin``: the switches answer the engine's question, so a caller that
    sees False knows the qualification cannot be rendered at all and does not
    have to try.
    """

    def validate_namespace(self, expr: SchemaObject) -> None:
        """Accept or refuse the namespace levels *expr* carries.

        The check the core's ``format_<kind>_object`` methods make before
        spelling a name. Inherited from the core ``NamespaceMixin``; declared
        here so a caller can ask for the capability by name.

        Raises rather than returning a verdict, so a caller cannot ignore it.
        """
        ...  # pragma: no cover

    def format_qualified_name(self, expr: SchemaObject) -> Tuple[str, tuple]:
        """Spell *expr*'s name: one identifier, no levels joined.

        The spelling half. Firebird has no ``separator`` to declare because it
        never joins anything.
        """
        ...  # pragma: no cover

    def supports_catalog(self) -> bool:
        """False: there is nothing above the database file."""
        ...  # pragma: no cover

    def supports_catalog_qualification(self) -> bool:
        """False: a name is never qualified with a catalog."""
        ...  # pragma: no cover

    def supports_schema_qualification(self) -> bool:
        """False: a name is never qualified with a schema."""
        ...  # pragma: no cover

    def supports_schema(self) -> bool:
        """False: a Firebird database is its own and only namespace."""
        ...  # pragma: no cover

    def supports_create_schema(self) -> bool:
        """False: Firebird has no ``CREATE SCHEMA``."""
        ...  # pragma: no cover

    def supports_drop_schema(self) -> bool:
        """False: Firebird has no ``DROP SCHEMA``."""
        ...  # pragma: no cover

    def validate_schema_name(self, obj: SchemaObject) -> None:
        """Reject an inner namespace a name carries.

        Raises rather than returning a verdict, so the refusal cannot be
        ignored by a caller that never checks the return value.
        """
        ...  # pragma: no cover

    def validate_catalog_name(self, obj: SchemaObject) -> None:
        """Reject an outer namespace a name carries."""
        ...  # pragma: no cover


__all__ = ["FirebirdNamespaceSupport"]
