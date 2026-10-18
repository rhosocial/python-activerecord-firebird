# src/rhosocial/activerecord/backend/impl/firebird/mixins/typed_value.py
"""Firebird's spellings for the value types whose literal form is its own.

Firebird agrees with the base on NULL, booleans, numbers, strings and
date/time values, so nothing is overridden for those. The agreements, per
the Firebird language reference rather than a live server: a boolean
literal is ``TRUE`` / ``FALSE`` / ``UNKNOWN`` and the ``BOOLEAN`` type
accepts them since Firebird 3.0; a date, time or timestamp literal is a
quoted string in the server's canonical form (``'2026-10-17'``,
``'10:30:00'``, ``'2026-10-17 10:00:00'``), which is exactly the ISO
text the base renders; and unlike MySQL the backslash is *not* an escape
character, so the base's doubled single quotes are the whole string
story. **Not server-verified in this run**: the machine this wave was
written on has no Firebird client library (the driver answers "The
location of Firebird Client Library could not be determined"), so the
live read-back class in ``test_firebird_typed_values.py`` is the piece
that re-measures these answers wherever the scenarios are reachable.

Two value types differ, and both differ because Firebird's grammar says
so:

* **binary** -- ``X'0102FF'``, the hexadecimal binary string literal.
  Firebird's literal grammar carries binary data as an ``X'...'`` hex
  string (upper- or lower-case ``x`` accepted; the upper-case spelling is
  what this dialect renders). Quoting the bytes as text would produce a
  string that reads back as text -- the wrong value in a ``BLOB`` column
  and the wrong length besides.
* **UUID** -- the bare quoted canonical text. Firebird has no UUID type:
  the storage conventions are ``CHAR(16) CHARACTER SET OCTETS`` for the
  raw bytes or a text column for the hyphenated form, and neither has a
  literal shape other than the text. A ``::uuid``-style suffix would not
  parse.

**INTERVAL stays unimplemented on purpose.** Firebird has no interval
type and no interval literal: spans are arithmetic -- ``DATEADD`` and
``DATEDIFF`` take the unit as a keyword argument of the call, never a
value with a literal form -- so a DDL position that needs one cannot be
written for this engine. That is the same fail-closed choice this dialect
makes for ILIKE and ordered-set aggregates, and it is why this mixin
defines no ``format_interval_value`` -- leaving the method absent is what
makes the base's explicit failure the answer here.
"""

from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.expression.values import TypedValue


class FirebirdTypedValueMixin:
    """Firebird's tier-2 value literals.

    Stands alone rather than inheriting :class:`TypedValueMixin`, like
    every other Firebird mixin: the dialect composes the specific mixin
    ahead of the generic one, and these two methods win by that position.
    Inheriting would put the base ahead of the other generic mixins and
    make the ordering the dialect has to reason about depend on this
    class instead.
    """

    def format_binary_value(self, expr: "TypedValue") -> Tuple[str, tuple]:
        """A binary literal: ``X'0102FF'``, upper-case hex.

        Rendered from the bytes rather than from any other form the value
        might travel in, because this conversion has to happen somewhere
        and a dialect is the only layer that knows which form its engine
        accepts.
        """
        if not type(expr).inline_params:
            return self._bind_value(expr)
        return f"X'{bytes(expr.value).hex().upper()}'", ()

    def format_uuid_value(self, expr: "TypedValue") -> Tuple[str, tuple]:
        """A UUID as the bare quoted canonical text.

        Firebird has no UUID type and no literal other than the text, so
        the quoted canonical form is the whole spelling; a text column
        holding it reads the hyphenated form back verbatim.
        """
        if not type(expr).inline_params:
            return self._bind_value(expr)
        return self.format_literal(str(expr.value)), ()
