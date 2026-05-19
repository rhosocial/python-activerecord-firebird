# src/rhosocial/activerecord/backend/impl/firebird/__init__.py
"""
Firebird backend implementation for ActiveRecord.

This module provides a Firebird-specific implementation including:
- Firebird backend with connection management and query execution
- Firebird dialect with version-aware feature detection
- Firebird-specific type definitions and adapters
- Support for RETURNING clause, generators/sequences,
  EXECUTE BLOCK, and other Firebird-specific features
"""

__version__ = "1.0.0.dev1"

from .backend import FirebirdBackend
from .dialect import FirebirdDialect
from .transaction import FirebirdTransactionManager
from .config import FirebirdConnectionConfig
from .types import FirebirdBlobType, FirebirdArrayType, FirebirdDomainType
from .explain.types import FirebirdExplainResult

from .mixins import (
    FIREBIRD_VERSION_BOUNDARIES,
    FirebirdTransactionMixin,
    FirebirdBackendMixin,
    FirebirdDMLOperationMixin,
    FirebirdLockingMixin,
    FirebirdTableMixin,
    FirebirdTriggerMixin,
    FirebirdSequenceMixin,
    FirebirdBlobMixin,
    FirebirdIntrospectionMixin,
    FirebirdConcurrencyMixin,
)

from .function_versions import FIREBIRD_FUNCTION_VERSIONS

__all__ = [
    'FirebirdBackend',
    'FirebirdConnectionConfig',
    'FirebirdDialect',
    'FIREBIRD_VERSION_BOUNDARIES',
    'FirebirdTransactionManager',
    'FirebirdTransactionMixin',
    'FirebirdBackendMixin',
    'FirebirdDMLOperationMixin',
    'FirebirdLockingMixin',
    'FirebirdTableMixin',
    'FirebirdTriggerMixin',
    'FirebirdSequenceMixin',
    'FirebirdBlobMixin',
    'FirebirdIntrospectionMixin',
    'FirebirdConcurrencyMixin',
    'FIREBIRD_FUNCTION_VERSIONS',
    'FirebirdBlobType',
    'FirebirdArrayType',
    'FirebirdDomainType',
    'FirebirdExplainResult',
]