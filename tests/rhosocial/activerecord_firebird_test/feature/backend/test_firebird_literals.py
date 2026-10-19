# tests/rhosocial/activerecord_firebird_test/feature/backend/test_firebird_literals.py
"""Firebird's spellings for the inline value literals.

Core's one ``Literal`` node carries every value, and ``inline`` is the
per-position answer to "bind or write as text" (core ``239678e5``): a data
position binds the host value behind a placeholder, a DDL syntax position
writes it through the dialect's ``format_literal``. The twelve kinds the
wire still names are a property of the value (``LiteralKind``), not a
class each, so the offline classes below assert the two paths directly.

The literal forms asserted by the offline classes are from the Firebird
language reference, not from a live server: the machine this wave was
written on has no Firebird client library at all (the driver answers "The
location of Firebird Client Library could not be determined"). What only a
server can say -- that the spelling is accepted and means the same value
coming back -- is not here: expression-dialect 12 keeps a connected check out
of the expression tests, so the live re-measurement moved to
``feature/basic/ddl/test_firebird_literal_defaults.py`` in the integration
area, and the tier-2 spellings below still owe that run.

* binary -- ``X'0102FF'``, the hexadecimal binary string literal; the
  server reads it as bytes, which the live class measures through
  ``OCTET_LENGTH`` (3 for ``X'0102FF'``) so the answer does not depend on
  how the driver types an octets column coming back.
* UUID -- the bare quoted canonical text; Firebird has no UUID type, so a
  ``CHAR(36)`` column holding the hyphenated form is the whole spelling.
* INTERVAL -- no branch in this dialect's ``format_literal`` on purpose:
  Firebird has no interval type and no interval literal (``DATEADD`` /
  ``DATEDIFF`` take the unit as a keyword argument of the call), so the
  base's explicit ``TypeError`` is the answer.
* tier-1 -- nothing overridden: the base's ``NULL`` / ``TRUE`` / ``FALSE``
  / numeric text / doubled-quote strings / quoted ISO dates, times and
  timestamps are each Firebird's own grammar (BOOLEAN and its literals
  exist since 3.0; the scenarios run 5.0 and 6.0). The backslash is
  *not* an escape character in Firebird, unlike MySQL, so the base's
  doubled single quotes are the whole string story.
"""

import datetime
import decimal
import uuid

import pytest

from rhosocial.activerecord.backend.expression.core import Literal
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect


@pytest.fixture
def dialect():
    return FirebirdDialect()


class TestBinary:
    """``X'0102FF'`` -- the hex binary string literal."""

    def test_data_position_binds_the_bytes(self, dialect):
        sql, params = Literal(dialect, b"\x01\x02").to_sql()
        assert sql == "?"
        assert params == (b"\x01\x02",)

    def test_inline_position_spells_hex(self, dialect):
        sql, params = Literal(dialect, b"\x01\x02\xff", inline=True).to_sql()
        assert sql == "X'0102FF'"
        assert params == ()

    def test_the_digits_are_uppercase(self, dialect):
        assert dialect.format_literal(b"\xab\xcd\xef") == "X'ABCDEF'"

    def test_an_empty_value_is_the_empty_literal(self, dialect):
        assert dialect.format_literal(b"") == "X''"

    def test_bytearray_is_normalised_before_rendering(self, dialect):
        assert dialect.format_literal(bytearray(b"\x01")) == "X'01'"


class TestUUID:
    """The bare quoted canonical text -- Firebird has only a text home."""

    CANONICAL = "c73d9175-0a1d-48c6-8d30-df165461328b"

    def test_data_position_binds_the_uuid(self, dialect):
        value = uuid.UUID(self.CANONICAL)
        sql, params = Literal(dialect, value).to_sql()
        assert sql == "?"
        assert params == (value,)

    def test_inline_position_is_the_quoted_canonical_text(self, dialect):
        value = uuid.UUID(self.CANONICAL)
        sql, params = Literal(dialect, value, inline=True).to_sql()
        assert sql == f"'{self.CANONICAL}'"
        assert params == ()


class TestIntervalStaysRefused:
    """No ``timedelta`` branch in this dialect's ``format_literal``.

    Firebird has no interval literal (the unit is a keyword argument of
    ``DATEADD``/``DATEDIFF``, never a value), so the base's explicit
    refusal is the answer, and the structural absence is asserted rather
    than papered over.
    """

    def test_data_position_still_binds(self, dialect):
        span = datetime.timedelta(days=2, hours=3)
        sql, params = Literal(dialect, span).to_sql()
        assert sql == "?"
        assert params == (span,)

    def test_inline_position_keeps_the_base_refusal(self, dialect):
        with pytest.raises(TypeError, match="no inline SQL literal form"):
            Literal(dialect, datetime.timedelta(days=1), inline=True).to_sql()


class TestTierOneAgreesWithTheBase:
    """The audit: nothing overridden for the kinds Firebird spells like core.

    Each assertion is the base's spelling reached through this dialect,
    pinned here so a base change that breaks Firebird's grammar is caught
    by this file rather than in the matrix, where the row would only say
    "renders".
    """

    def test_null_renders_as_the_keyword(self, dialect):
        assert dialect.format_literal(None) == "NULL"

    def test_booleans_render_as_keywords(self, dialect):
        assert dialect.format_literal(True) == "TRUE"
        assert dialect.format_literal(False) == "FALSE"

    def test_integers_render_as_numeric_text(self, dialect):
        assert dialect.format_literal(18) == "18"
        assert dialect.format_literal(-7) == "-7"

    def test_floats_render_as_their_repr(self, dialect):
        assert dialect.format_literal(0.5) == "0.5"
        assert dialect.format_literal(15e-03) == "0.015"

    def test_decimals_render_exact(self, dialect):
        assert dialect.format_literal(decimal.Decimal("12.34")) == "12.34"

    def test_strings_double_the_quotes(self, dialect):
        assert dialect.format_literal("today's") == "'today''s'"

    def test_strings_do_not_escape_the_backslash(self, dialect):
        # Firebird is not MySQL: a backslash is a plain character in a
        # string literal, so the base's doubled quotes are all the
        # escaping there is.
        assert dialect.format_literal("a\\b") == "'a\\b'"

    def test_dates_render_as_quoted_iso(self, dialect):
        assert dialect.format_literal(datetime.date(2026, 10, 17)) == "'2026-10-17'"

    def test_times_render_as_quoted_iso(self, dialect):
        assert dialect.format_literal(datetime.time(10, 3, 56)) == "'10:03:56'"

    def test_timestamps_render_as_quoted_iso_with_a_space_separator(self, dialect):
        assert (
            dialect.format_literal(datetime.datetime(2024, 8, 15, 10, 59, 43))
            == "'2024-08-15 10:59:43'"
        )


class TestMROOrder:
    """The composed order is what resolves the override."""

    def test_the_local_mixin_wins_over_the_base(self, dialect):
        assert (
            dialect.format_literal.__func__.__qualname__.startswith(
                "FirebirdLiteralValueMixin"
            )
        )

    def test_the_base_answers_the_literal_expression_entry(self, dialect):
        # The node's own dispatch entry is the core ExpressionMixin's,
        # untouched by this backend: only the spelling of a tier-2 value
        # differs here, not how a position decides to bind or inline.
        assert (
            dialect.format_literal_expression.__func__.__qualname__.startswith(
                "ExpressionMixin"
            )
        )


