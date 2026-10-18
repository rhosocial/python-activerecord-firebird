# src/rhosocial/activerecord/backend/impl/firebird/mixins/literal.py
"""Firebird's tier-2 value literals.

``SQLDialectBase.format_literal`` is the single entry point for writing a
value as SQL text, and it resolves in three tiers: the portable scalars it
knows, the types a backend spells for itself, and the literal-construction
protocol. This module is Firebird's second tier.

Firebird agrees with the base on tier 1 -- measured on this dialect's own
grammar rather than a live server: a boolean literal is ``TRUE`` /
``FALSE`` / ``UNKNOWN`` and the ``BOOLEAN`` type accepts them since
Firebird 3.0; a date, time or timestamp literal is a quoted string in the
server's canonical form (``'2026-10-17'``, ``'10:30:00'``,
``'2026-10-17 10:00:00'``), which is exactly the ISO text the base
renders; and unlike MySQL the backslash is *not* an escape character, so
the base's doubled single quotes are the whole string story. **Not
server-verified in this run**: the machine this wave was written on has
no Firebird client library (the driver answers "The location of Firebird
Client Library could not be determined"), so the live read-back class in
``test_firebird_literals.py`` is the piece that re-measures these answers
wherever the scenarios are reachable.

Two host types have spellings of Firebird's own, and both are the
grammar's doing:

* **binary** -- ``X'0102FF'``, the hexadecimal binary string literal
  (upper- or lower-case ``x`` accepted; the upper-case spelling is what
  this dialect renders). Quoting the bytes as text would produce a string
  that reads back as text -- the wrong value in a ``BLOB`` column and the
  wrong length besides.
* **UUID** -- the bare quoted canonical text. Firebird has no UUID type:
  the storage conventions are ``CHAR(16) CHARACTER SET OCTETS`` for the
  raw bytes or a text column for the hyphenated form, and neither has a
  literal shape other than the text.

**INTERVAL stays unimplemented on purpose.** Firebird has no interval
type and no interval literal: spans are arithmetic -- ``DATEADD`` and
``DATEDIFF`` take the unit as a keyword argument of the call, never a
value with a literal form. This module handles no ``timedelta``, so the
base's explicit refusal is the answer -- the same fail-closed choice this
dialect makes for ILIKE and ordered-set aggregates.
"""

import uuid
from typing import Any


class FirebirdLiteralValueMixin:
    """Firebird's tier-2 branches of :meth:`format_literal`.

    Stands alone rather than inheriting anything, like every other
    Firebird mixin: the dialect composes it ahead of ``SQLDialectBase``,
    and the override wins by that position.
    """

    def format_literal(self, value: Any) -> str:
        """Render *value* as inline SQL text, Firebird's spelling where it
        has one.

        Args:
            value: The host value to write into the statement.

        Returns:
            The escaped literal text, without a bind parameter.

        Raises:
            TypeError: The base implementation refuses a type Firebird has
                no literal form for (``timedelta`` among them -- see the
                module docstring), and this adds nothing on top of it.
        """
        if isinstance(value, (bytes, bytearray)):
            return f"X'{bytes(value).hex().upper()}'"
        if isinstance(value, uuid.UUID):
            # All Firebird has is a text home, so the canonical form quoted
            # as text is the whole spelling; a ::uuid-style suffix would
            # not parse.
            return super().format_literal(str(value))
        return super().format_literal(value)
