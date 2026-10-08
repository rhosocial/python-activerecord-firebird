# src/rhosocial/activerecord/backend/impl/firebird/protocols/sources.py
"""What Firebird declares about row sources.

A ``FROM`` clause in Firebird reads an unqualified relation, optionally under
an alias. There is no schema to qualify the relation with, no temporal clause
to render after the name, and no special source syntax beyond the core set.

:func:`FirebirdRowSourceSupport.format_named_relation` is the core
``RelationSourceMixin`` rendering with Firebird's one addition: a reference that
carries temporal options is refused, because there is no time-travel clause to
render and dropping it would read the wrong rows. The relation's own name comes
from the object; the alias is the query's, and both are the core's business.

:func:`FirebirdRowSourceSupport.row_source_name` exists because
``SELECT *, extra ...`` is a Firebird syntax error: the wildcard must be
qualified with the single row source's name. That name is a property of the
*row source*, not of the catalogue, so it is read off the source -- an alias
when it has one, otherwise the relation's own name -- rather than off a schema
object.
"""

from typing import Optional, Protocol, Tuple, runtime_checkable


@runtime_checkable
class FirebirdRowSourceSupport(Protocol):
    """Rendering contract for a Firebird row source."""

    def format_named_relation(self, ref: object) -> Tuple[str, tuple]:
        """Render a ``FROM`` reference to a named relation."""
        ...  # pragma: no cover

    def row_source_name(self, source: object) -> Optional[str]:
        """The name a single row source is known by inside its query.

        Returns ``None`` for anything that is not a named relation -- a
        derived table, a join, a stored function, ``JSON_TABLE`` -- because
        Firebird can only qualify a wildcard by a real relation or alias.
        """
        ...  # pragma: no cover


__all__ = ["FirebirdRowSourceSupport"]
