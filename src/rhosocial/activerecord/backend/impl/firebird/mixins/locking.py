# src/rhosocial/activerecord/backend/impl/firebird/mixins/locking.py
"""Firebird locking mixin."""

from typing import Tuple

from .version_boundaries import _norm_version


class FirebirdLockingMixin:

    def format_for_update(self, expr) -> Tuple[str, tuple]:
        version = getattr(self, 'version', (3, 0, 0))
        parts = ["FOR UPDATE"]

        with_lock = getattr(expr, 'with_lock', False)
        skip_locked = getattr(expr, 'skip_locked', False)
        nowait = getattr(expr, 'nowait', False)

        if with_lock:
            parts.append("WITH LOCK")
        if skip_locked:
            if _norm_version(version) >= (4, 0, 0):
                parts.append("SKIP LOCKED")
        if nowait:
            parts.append("WITH LOCK")

        return ' '.join(parts), ()

    def supports_for_update_with_lock(self) -> bool:
        version = getattr(self, 'version', (3, 0, 0))
        return _norm_version(version) >= (3, 0, 0)

    def supports_skip_locked(self) -> bool:
        version = getattr(self, 'version', (3, 0, 0))
        return _norm_version(version) >= (4, 0, 0)