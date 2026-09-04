# tests/rhosocial/activerecord_firebird_test/feature/backend/backend/test_connection_resilience.py
"""Connection resilience tests for the Firebird backend.

Tests the backend's ability to handle connection lifecycle scenarios that are
supported by the synchronous ``firebird-driver``:
1. ``is_connected`` state accuracy across connect/disconnect
2. Reconnection via ``ping(reconnect=True)`` after connection loss
3. ``ping(reconnect=False)`` reports a dead connection without reconnecting
4. ``_get_cursor()`` raises when not connected
"""

from decimal import Decimal

import pytest

from rhosocial.activerecord.backend import errors as exc


class TestIsConnected:
    def test_is_connected_when_connected(self, fb_backend):
        assert fb_backend._is_connected is True
        assert fb_backend.ping(reconnect=False) is True

    def test_is_connected_after_disconnect(self, fb_backend):
        fb_backend.disconnect()
        assert fb_backend._is_connected is False
        with pytest.raises(exc.ConnectionError):
            fb_backend._get_cursor()

    def test_reconnect_after_disconnect(self, fb_backend):
        fb_backend.disconnect()
        fb_backend.connect()
        assert fb_backend._is_connected is True
        assert fb_backend.ping(reconnect=False) is True


class TestPingReconnect:
    def test_ping_after_disconnect_reconnects(self, fb_backend):
        fb_backend.disconnect()
        assert fb_backend.ping(reconnect=True) is True
        assert fb_backend._is_connected is True

    def test_ping_reconnect_false_keeps_disconnected(self, fb_backend):
        fb_backend.disconnect()
        assert fb_backend.ping(reconnect=False) is False
        assert fb_backend._is_connected is False

    def test_query_after_reconnect(self, fb_backend, setup_test_table):
        table = setup_test_table
        fb_backend.insert(table, {"name": "reconnect_ok", "amount": Decimal("7")})
        fb_backend.disconnect()
        fb_backend.connect()
        rows = fb_backend.execute(
            f'SELECT name FROM {table} WHERE name = ?',
            ("reconnect_ok",),
            fetch=True,
        ).data
        assert rows[0]["name"] == "reconnect_ok"


class TestCursorHandling:
    def test_get_cursor_when_not_connected_raises(self, fb_backend):
        fb_backend.disconnect()
        with pytest.raises(exc.ConnectionError):
            fb_backend._get_cursor()