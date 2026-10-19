# tests/rhosocial/activerecord_firebird_test/feature/basic/ddl/test_firebird_literal_defaults.py
"""What only a running Firebird can say about this dialect's literal spellings.

The expression tests pin what ``FirebirdLiteralValueMixin`` renders -- the
hex binary literal ``X'0102FF'``, the bare quoted UUID text, the base's
refusal of a ``timedelta`` -- and those assertions need no server. This file is
the other half: that the spellings are *accepted* and mean the same value
coming back.

It lives here, in the DDL feature area, rather than beside them because
expression-dialect 12 draws exactly that line: the expression layer does no
I/O, and a check that needs a connection is an integration check. The
scenarios are reachable from this machine (192.168.1.3, 19582 / 19583) but
the Firebird *client library* is not installed here, so the driver answers
"The location of Firebird Client Library could not be determined" and the
fixture skips rather than errors; these cases execute wherever the client
library is, and what they measure is the one thing no rendering assertion can
stand in for.

The read-back goes over raw SQL on purpose: the literal forms are this
dialect's own product, not something the ActiveRecord layer produces. The
binary case measures through ``OCTET_LENGTH`` so the verdict does not depend on
how the driver types an octets column on the way back -- three bytes is the
answer only if the server read ``X'0102FF'`` as binary, where the text
spelling would be eight characters long.
"""

import pytest

from rhosocial.activerecord.backend.impl.firebird.backend import FirebirdBackend


@pytest.fixture
def live_backend(fb_config):
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
    """The tier-2 answers re-measured end to end against a running server."""

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
