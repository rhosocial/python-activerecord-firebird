# src/rhosocial/activerecord/backend/impl/firebird/mixins/comment.py
"""Firebird COMMENT ON statement formatting mixin.

``COMMENT ON`` annotates metadata objects (tables, columns, views, routines,
domains, exceptions, triggers, generators, ...) and is available since
Firebird 2.5, gated here at ``(2, 5, 0)``.

Firebird names a wider set of things than the framework's object taxonomy
covers -- a role, a user, an exception, a package, a collation -- so the target
arrives as a plain string and the *kind* is what decides how it is spelled.
Every target that does correspond to a catalogue object is rendered by building
that object and letting it render itself, so a name carrying a namespace slot
is reported rather than dropped, and quoting has the same owner as everywhere
else.
"""

from typing import Tuple

from .version_boundaries import _norm_version
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.objects import (
    Domain,
    Function,
    Procedure,
    Sequence,
    Table,
    Trigger,
)

from ..expression.comment import FirebirdCommentObjectType


class FirebirdCommentMixin:

    #: COMMENT ON target kinds that name a catalogue object, and the kind of
    #: object each one is. A view is the same kind of name as a table, and a
    #: generator is a sequence -- Firebird 3.0 renamed one to the other and kept
    #: both spellings. ``PARAMETER`` has no entry of its own: it is handled
    #: below, because it names a member of a routine rather than a routine.
    #: Targets not listed here (DATABASE, ROLE, USER, EXCEPTION, PACKAGE, INDEX,
    #: FILTER, CHARACTER SET, COLLATION, GLOBAL MAPPING, EXTERNAL FUNCTION) are
    #: not schema-object kinds in this framework's taxonomy and fall back to a
    #: plain identifier.
    _COMMENT_OBJECT_KINDS = {
        FirebirdCommentObjectType.TABLE.value: Table,
        FirebirdCommentObjectType.VIEW.value: Table,
        FirebirdCommentObjectType.GENERATOR.value: Sequence,
        FirebirdCommentObjectType.SEQUENCE.value: Sequence,
        FirebirdCommentObjectType.DOMAIN.value: Domain,
        FirebirdCommentObjectType.PROCEDURE.value: Procedure,
        FirebirdCommentObjectType.FUNCTION.value: Function,
        FirebirdCommentObjectType.TRIGGER.value: Trigger,
    }

    def supports_comment_on(self) -> bool:
        return _norm_version(self.version) >= (2, 5, 0)

    def format_comment_statement(self, expr) -> Tuple[str, tuple]:
        """Format COMMENT ON <object> IS 'text' (or IS NULL to remove).

        Accepts any comment expression carrying ``object_type``,
        ``object_name`` and ``comment``.
        """
        self._check_comment_version("COMMENT ON")

        object_type = getattr(expr.object_type, "value", expr.object_type)
        name = self._format_comment_object_name(expr)
        if expr.comment is None:
            return f"COMMENT ON {object_type} {name} IS NULL", ()
        return (
            f"COMMENT ON {object_type} {name} IS {self._quote_literal(expr.comment)}",
            (),
        )

    def _format_comment_object_name(self, expr) -> str:
        """Render the object a comment is attached to.

        Two targets are *qualified* rather than named: ``COLUMN`` names a
        column of a relation and ``PARAMETER`` names a parameter of a routine.
        Both arrive as ``owner.member``, and each half is rendered as what it
        is -- the owner as the catalogue object it is, the member as a plain
        identifier, since a column and a parameter are not catalogue objects.
        """
        object_type = getattr(expr.object_type, "value", expr.object_type)

        if object_type == FirebirdCommentObjectType.COLUMN.value:
            owner, _, member = expr.object_name.rpartition(".")
            if owner:
                return f"{Table(self, owner).to_sql()[0]}.{self.format_identifier(member)}"
            return self.format_identifier(member)

        if object_type == FirebirdCommentObjectType.PARAMETER.value:
            owner, _, member = expr.object_name.rpartition(".")
            if owner:
                # Firebird's COMMENT ON PARAMETER does not say which routine
                # kind it is, and rendering does not depend on it.
                return (
                    f"{Procedure(self, owner).to_sql()[0]}"
                    f".{self.format_identifier(member)}"
                )
            return self.format_identifier(member)

        kind = self._COMMENT_OBJECT_KINDS.get(object_type)
        if kind is None:
            return self.format_identifier(expr.object_name)
        return kind(self, expr.object_name).to_sql()[0]

    def _quote_literal(self, value: str) -> str:
        """Inline a string literal with Firebird single-quote escaping."""
        return f"'{value.replace(chr(39), chr(39) * 2)}'"

    def _check_comment_version(self, feature: str) -> None:
        version = getattr(self, 'version', (2, 5, 0))
        if _norm_version(version) < (2, 5, 0):
            raise UnsupportedFeatureError(
                self.name,
                feature,
                "Firebird 2.5 or later is required for COMMENT ON statements.",
            )
