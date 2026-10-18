# tests/rhosocial/activerecord_firebird_test/feature/backend/test_firebird_typed_values.py
"""Firebird's spellings for the typed value literals.

Core's value nodes render through ``inline_params`` -- a class-level
strategy, never a per-instance flag -- so the DDL-position assertions below
use a test-local DDL-position class per kind, the same lift core itself
performs when it renders a ``DEFAULT`` / ``CHECK`` tree (``Literal`` ->
``DdlLiteral``). The data-position assertions run the node classes as they
ship, which bind.

The literal forms asserted by the offline classes are from the Firebird
language reference, not from a live server: the machine this wave was
written on has no Firebird client library at all (the driver answers "The
location of Firebird Client Library could not be determined"), so the
live-server class at the bottom -- the piece that re-measures the answers
end to end -- has never executed in this run and is skipped here. It runs
wherever the scenarios (192.168.1.3:19582 / 19583) are reachable, and
that run is what the tier-2 spellings still owe.

* binary -- ``X'0102FF'``, the hexadecimal binary string literal; the
  server reads it as bytes, which the live class measures through
  ``OCTET_LENGTH`` (3 for ``X'0102FF'``) so the answer does not depend on
  how the driver types an octets column coming back.
* UUID -- the bare quoted canonical text; Firebird has no UUID type, so a
  ``CHAR(36)`` column holding the hyphenated form is the whole spelling.
* INTERVAL -- no override on purpose: Firebird has no interval type and
  no interval literal (``DATEADD``/``DATEDIFF`` take the unit as a keyword
  argument of the call), so the base's explicit failure is the answer and
  this dialect defines no ``format_interval_value``.
* tier-1 -- nothing overridden: the base's ``NULL`` / ``TRUE`` / ``FALSE``
  / numeric text / doubled-quote strings / quoted ISO dates and times are
  each Firebird's own grammar (BOOLEAN and its literals exist since 3.0;
  the scenarios are 5.0 and 6.0). The backslash is *not* an escape
  character in Firebird, unlike MySQL, so the base's doubled single
  quotes are the whole string story.
"""

import datetime
import decimal
import uuid

import pytest

from rhosocial.activerecord.backend.expression.values import (
    BinaryValue,
    BooleanValue,
    DateValue,
    DecimalValue,
    FloatValue,
    IntegerValue,
    IntervalValue,
    NullValue,
    StringValue,
    TimeValue,
    TimestampValue,
    UUIDValue,
)
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect


@pytest.fixture
def dialect():
    return FirebirdDialect()


# -- the DDL-position lift ------------------------------------------------
#
# One class per kind, each declaring the strategy its position requires,
# exactly as core's own DdlLiteral does for Literal. The subclass adds no
# field and no kind: it only owns the position, which is the whole of the
# class-level inline strategy.

class DdlBinaryValue(BinaryValue):
    inline_params = True


class DdlUUIDValue(UUIDValue):
    inline_params = True


class DdlIntervalValue(IntervalValue):
    inline_params = True


class DdlNullValue(NullValue):
    inline_params = True


class DdlBooleanValue(BooleanValue):
    inline_params = True


class DdlIntegerValue(IntegerValue):
    inline_params = True


class DdlFloatValue(FloatValue):
    inline_params = True


class DdlDecimalValue(DecimalValue):
    inline_params = True


class DdlStringValue(StringValue):
    inline_params = True


class DdlDateValue(DateValue):
    inline_params = True


class DdlTimeValue(TimeValue):
    inline_params = True


class DdlTimestampValue(TimestampValue):
    inline_params = True


class TestBinaryValue:
    """``X'0102FF'`` -- the hex binary string literal."""

    def test_data_position_binds_the_bytes(self, dialect):
        sql, params = BinaryValue(dialect, b"\x01\x02").to_sql()
        assert sql == "?"
        assert params == (b"\x01\x02",)

    def test_ddl_position_spells_hex(self, dialect):
        sql, params = DdlBinaryValue(dialect, b"\x01\x02\xff").to_sql()
        assert sql == "X'0102FF'"
        assert params == ()

    def test_the_digits_are_uppercase(self, dialect):
        sql, _ = DdlBinaryValue(dialect, b"\xab\xcd\xef").to_sql()
        assert sql == "X'ABCDEF'"

    def test_an_empty_value_is_the_empty_literal(self, dialect):
        sql, _ = DdlBinaryValue(dialect, b"").to_sql()
        assert sql == "X''"

    def test_bytearray_is_normalised_before_rendering(self, dialect):
        sql, _ = DdlBinaryValue(dialect, bytearray(b"\x01")).to_sql()
        assert sql == "X'01'"


class TestUUIDValue:
    """The bare quoted canonical text -- Firebird has only a text home."""

    CANONICAL = "c73d9175-0a1d-48c6-8d30-df165461328b"

    def test_data_position_binds_the_uuid(self, dialect):
        value = uuid.UUID(self.CANONICAL)
        sql, params = UUIDValue(dialect, value).to_sql()
        assert sql == "?"
        assert params == (value,)

    def test_ddl_position_is_the_quoted_canonical_text(self, dialect):
        sql, params = DdlUUIDValue(dialect, uuid.UUID(self.CANONICAL)).to_sql()
        assert sql == f"'{self.CANONICAL}'"
        assert params == ()


class TestIntervalValueStaysRefused:
    """No ``format_interval_value`` on this dialect, on purpose.

    Firebird has no interval literal (the unit is a keyword argument of
    ``DATEADD``/``DATEDIFF``, never a value), so the base's explicit
    failure is the answer, and the structural absence is asserted rather
    than papered over.
    """

    def test_data_position_still_binds(self, dialect):
        span = datetime.timedelta(days=2, hours=3)
        sql, params = IntervalValue(dialect, span).to_sql()
        assert sql == "?"
        assert params == (span,)

    def test_ddl_position_keeps_the_base_refusal(self, dialect):
        with pytest.raises(NotImplementedError, match="INTERVAL literals"):
            DdlIntervalValue(dialect, datetime.timedelta(days=1)).to_sql()


class TestTierOneAgreesWithTheBase:
    """The audit: nothing overridden for the kinds Firebird spells like core.

    Each assertion is the base's spelling reached through this dialect,
    pinned here so a base change that breaks Firebird's grammar is caught
    by this file rather than in the matrix, where the row would only say
    "renders".
    """

    def test_null_binds_then_renders_as_the_keyword(self, dialect):
        assert NullValue(dialect).to_sql() == ("?", (None,))
        assert DdlNullValue(dialect).to_sql() == ("NULL", ())

    def test_booleans_render_as_keywords(self, dialect):
        assert DdlBooleanValue(dialect, True).to_sql() == ("TRUE", ())
        assert DdlBooleanValue(dialect, False).to_sql() == ("FALSE", ())

    def test_integers_render_as_numeric_text(self, dialect):
        assert DdlIntegerValue(dialect, 18).to_sql() == ("18", ())
        assert DdlIntegerValue(dialect, -7).to_sql() == ("-7", ())

    def test_floats_render_as_their_repr(self, dialect):
        assert DdlFloatValue(dialect, 0.5).to_sql() == ("0.5", ())
        assert DdlFloatValue(dialect, 15e-03).to_sql() == ("0.015", ())

    def test_decimals_render_exact(self, dialect):
        value = decimal.Decimal("12.34")
        assert DdlDecimalValue(dialect, value).to_sql() == ("12.34", ())

    def test_strings_double_the_quotes(self, dialect):
        sql, _ = DdlStringValue(dialect, "today's").to_sql()
        assert sql == "'today''s'"

    def test_strings_do_not_escape_the_backslash(self, dialect):
        # Firebird is not MySQL: a backslash is a plain character in a
        # string literal, so the base's doubled quotes are all the
        # escaping there is.
        sql, _ = DdlStringValue(dialect, "a\\b").to_sql()
        assert sql == "'a\\b'"

    def test_dates_render_as_quoted_iso(self, dialect):
        sql, _ = DdlDateValue(dialect, datetime.date(2026, 10, 17)).to_sql()
        assert sql == "'2026-10-17'"

    def test_times_render_as_quoted_iso(self, dialect):
        sql, _ = DdlTimeValue(dialect, datetime.time(10, 3, 56)).to_sql()
        assert sql == "'10:03:56'"

    def test_timestamps_render_as_quoted_iso_with_a_space_separator(self, dialect):
        sql, _ = DdlTimestampValue(
            dialect, datetime.datetime(2024, 8, 15, 10, 59, 43)
        ).to_sql()
        assert sql == "'2024-08-15 10:59:43'"


class TestMROOrder:
    """The composed order is what resolves the two overrides."""

    def test_the_local_mixin_wins_over_the_base(self, dialect):
        assert dialect.format_binary_value.__func__.__qualname__.startswith(
            "FirebirdTypedValueMixin"
        )
        assert dialect.format_uuid_value.__func__.__qualname__.startswith(
            "FirebirdTypedValueMixin"
        )

    def test_the_base_answers_the_kinds_the_local_mixin_leaves_alone(self, dialect):
        assert dialect.format_null_value.__func__.__qualname__.startswith(
            "TypedValueMixin"
        )
        assert dialect.format_interval_value.__func__.__qualname__.startswith(
            "TypedValueMixin"
        )


# -- the live re-measurement ---------------------------------------------
#
# The offline classes above pin what this dialect renders. What only a
# server can say is that the spelling is accepted and means the same value
# coming back. This machine has no Firebird client library (see the module
# docstring), so the fixture skips rather than erroring -- the connected
# environments this suite runs in (scenarios firebird_5 / firebird_6) are
# where these cases actually execute.


@pytest.fixture
def live_backend(fb_config):
    from rhosocial.activerecord.backend.impl.firebird.backend import FirebirdBackend

    backend = FirebirdBackend(connection_config=fb_config)
    try:
        backend.connect()
    except Exception as exc:
        pytest.skip(f"no reachable Firebird server: {exc}")
    yield backend
    try:
        backend.disconnect()
    except Exception:
        pass


class TestLiveServerReadsTheLiteralsBack:
    """The tier-2 answers re-measured end to end against a running server.

    The read-back goes over raw SQL on purpose: the literal forms are this
    dialect's own product. The binary case measures through
    ``OCTET_LENGTH`` so the verdict does not depend on how the driver
    types an octets column on the way back -- three bytes is the answer
    only if the server read ``X'0102FF'`` as binary, where the text
    spelling would be eight characters long.
    """

    def _drop(self, backend, table):
        try:
            backend.execute(f"DROP TABLE {table}", fetch=False)
        except Exception:
            pass

    def test_binary_default_is_read_back_as_bytes(self, live_backend):
        self._drop(live_backend, "ar_fb_typed_bin")
        try:
            live_backend.execute(
                "CREATE TABLE ar_fb_typed_bin ("
                "id INT, v VARCHAR(8) CHARACTER SET OCTETS DEFAULT X'0102FF')",
                fetch=False,
            )
            live_backend.execute(
                "INSERT INTO ar_fb_typed_bin (id) VALUES (1)", fetch=False
            )
            rows = live_backend.execute(
                "SELECT OCTET_LENGTH(v) FROM ar_fb_typed_bin", fetch=True
            ).data
            assert rows[0]["octet_length"] == 3
        finally:
            self._drop(live_backend, "ar_fb_typed_bin")

    def test_uuid_default_roundtrips_as_the_canonical_text(self, live_backend):
        canonical = "550e8400-e29b-41d4-a716-446655440000"
        self._drop(live_backend, "ar_fb_typed_uuid")
        try:
            live_backend.execute(
                f"CREATE TABLE ar_fb_typed_uuid ("
                f"id INT, v CHAR(36) DEFAULT '{canonical}')",
                fetch=False,
            )
            live_backend.execute(
                "INSERT INTO ar_fb_typed_uuid (id) VALUES (1)", fetch=False
            )
            rows = live_backend.execute(
                "SELECT v FROM ar_fb_typed_uuid", fetch=True
            ).data
            assert rows[0]["v"] == canonical
        finally:
            self._drop(live_backend, "ar_fb_typed_uuid")

    def test_interval_default_is_refused(self, live_backend):
        self._drop(live_backend, "ar_fb_typed_iv")
        try:
            with pytest.raises(Exception):  # noqa: B017 - the refusal is the point
                live_backend.execute(
                    "CREATE TABLE ar_fb_typed_iv (v INT DEFAULT INTERVAL 1 DAY)"
                )
        finally:
            self._drop(live_backend, "ar_fb_typed_iv")

    def test_tier_one_defaults_are_accepted(self, live_backend):
        self._drop(live_backend, "ar_fb_typed_t1")
        try:
            live_backend.execute(
                "CREATE TABLE ar_fb_typed_t1 ("
                " b BOOLEAN DEFAULT TRUE,"
                " n INT DEFAULT 42,"
                " f DOUBLE PRECISION DEFAULT 1.5,"
                " s VARCHAR(16) DEFAULT 'x''y',"
                " d DATE DEFAULT '2026-10-17',"
                " ts TIMESTAMP DEFAULT '2026-10-17 10:00:00'"
                ")",
                fetch=False,
            )
            live_backend.execute(
                "INSERT INTO ar_fb_typed_t1 DEFAULT VALUES", fetch=False
            )
            rows = live_backend.execute(
                "SELECT COUNT(*) FROM ar_fb_typed_t1", fetch=True
            ).data
            assert rows[0]["count"] == 1
        finally:
            self._drop(live_backend, "ar_fb_typed_t1")
