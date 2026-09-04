# tests/rhosocial/activerecord_firebird_test/feature/backend/concurrency/test_concurrency_protocol.py
"""Tests for the ConcurrencyAware protocol implementation in the Firebird backend.

Verifies that :class:`FirebirdBackend` correctly implements the
``ConcurrencyAware`` protocol by fetching the connection limit during
``connect()`` and returning the appropriate concurrency hint.

Firebird 3/4 expose ``MON$MAX_CONNECTIONS`` on ``MON$DATABASE``; the column was
removed in Firebird 5+, so the hint falls back to the configured pool size or
``None`` (unlimited) when no limit is discoverable.
"""

from rhosocial.activerecord.backend.protocols import ConcurrencyAware, ConcurrencyHint


class TestFirebirdConcurrencyAware:
    """Test ConcurrencyAware protocol implementation for the Firebird backend."""

    def test_firebird_backend_implements_protocol(self, fb_backend):
        """Test that FirebirdBackend implements ConcurrencyAware protocol."""
        assert isinstance(fb_backend, ConcurrencyAware)

    def test_firebird_get_concurrency_hint(self, fb_backend):
        """Test FirebirdBackend returns a concurrency hint after connect.

        Without a configured pool size the hint may be None, meaning no
        concurrency constraint is known for the server.
        """
        hint = fb_backend.get_concurrency_hint()

        assert hint is None or isinstance(hint, ConcurrencyHint)
        if hint is not None:
            assert hint.max_concurrency is None or hint.max_concurrency > 0

    def test_firebird_concurrency_hint_with_pool_size(self, fb_backend):
        """Test that a configured pool size bounds the concurrency hint."""
        fb_backend.config.pool_size = 4
        fb_backend._fetch_concurrency_hint()

        hint = fb_backend.get_concurrency_hint()
        assert hint is not None
        assert hint.max_concurrency is not None
        assert hint.max_concurrency <= 4
        assert hint.max_concurrency > 0

    def test_firebird_concurrency_hint_reason(self, fb_backend):
        """Test that the hint reason describes the constraint source."""
        fb_backend.config.pool_size = 4
        fb_backend._fetch_concurrency_hint()

        hint = fb_backend.get_concurrency_hint()
        assert hint is not None
        assert "mon_max_connections" in hint.reason or "pool_size" in hint.reason

    def test_firebird_threadsafety(self, fb_backend):
        """Test that the backend reports DBAPI threadsafety level."""
        assert fb_backend.threadsafety == 2