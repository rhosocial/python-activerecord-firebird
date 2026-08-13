# tests/rhosocial/activerecord_firebird_test/feature/backend/test_concurrency_protocol.py
"""Tests for the ConcurrencyAware protocol implementation in the Firebird backend.

Verifies that :class:`FirebirdBackend` correctly implements the
``ConcurrencyAware`` protocol by fetching ``MON$MAX_CONNECTIONS`` during
``connect()`` and returning the appropriate concurrency hint.
"""

from rhosocial.activerecord.backend.protocols import ConcurrencyAware, ConcurrencyHint


class TestFirebirdConcurrencyAware:
    """Test ConcurrencyAware protocol implementation for the Firebird backend."""

    def test_firebird_backend_implements_protocol(self, fb_backend):
        """Test that FirebirdBackend implements ConcurrencyAware protocol."""
        assert isinstance(fb_backend, ConcurrencyAware)

    def test_firebird_get_concurrency_hint(self, fb_backend):
        """Test FirebirdBackend returns a concurrency hint after connect."""
        hint = fb_backend.get_concurrency_hint()

        assert hint is not None
        assert isinstance(hint, ConcurrencyHint)
        assert hint.max_concurrency is not None
        assert hint.max_concurrency > 0

    def test_firebird_concurrency_hint_value_bounded(self, fb_backend):
        """Test that the concurrency hint is bounded by the configured pool size."""
        pool_size = getattr(fb_backend.config, "pool_size", None) or 5
        hint = fb_backend.get_concurrency_hint()

        assert hint.max_concurrency <= pool_size
        assert hint.max_concurrency > 0

    def test_firebird_concurrency_hint_populated_after_connect(self, fb_backend):
        """Test that the hint is populated once connected."""
        assert fb_backend._connection is not None
        assert fb_backend.get_concurrency_hint() is not None

    def test_firebird_concurrency_hint_reason(self, fb_backend):
        """Test that the hint reason describes the constraint source."""
        hint = fb_backend.get_concurrency_hint()
        assert "mon_max_connections" in hint.reason or "pool_size" in hint.reason

    def test_firebird_threadsafety(self, fb_backend):
        """Test that the backend reports DBAPI threadsafety level."""
        assert fb_backend.threadsafety == 2