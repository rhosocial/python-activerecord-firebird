# src/rhosocial/activerecord/backend/impl/firebird/introspection/__init__.py
"""Firebird schema introspection support."""

from .async_introspector import AsyncFirebirdIntrospector

try:
    from .introspector import SyncFirebirdIntrospector
except ImportError:
    SyncFirebirdIntrospector = None

__all__ = ["SyncFirebirdIntrospector", "AsyncFirebirdIntrospector"]