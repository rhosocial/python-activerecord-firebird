# src/rhosocial/activerecord/backend/impl/firebird/introspection/__init__.py
"""Firebird schema introspection support."""

from .introspector import SyncFirebirdIntrospector

__all__ = ["SyncFirebirdIntrospector"]