# src/rhosocial/activerecord/backend/impl/firebird/protocols/__init__.py
"""Firebird's protocol declarations, one module per concern.

* :mod:`~.features` -- the Firebird-only capability switches and formatters.
* :mod:`~.namespace` -- Firebird's answer on namespaces: none exist.
* :mod:`~.sources` -- rendering a row source.

Everything is re-exported here so callers keep writing
``from .protocols import FirebirdSomeSupport`` whatever the internal split.
"""

from .features import (
    FirebirdBooleanSupport,
    FirebirdBlobSupport,
    FirebirdCTESupport,
    FirebirdCollationSupport,
    FirebirdContextVariableSupport,
    FirebirdCursorSupport,
    FirebirdDatabaseTriggerSupport,
    FirebirdDecFloatSupport,
    FirebirdDMLOperationSupport,
    FirebirdDomainSupport,
    FirebirdExceptionSupport,
    FirebirdExecuteBlockSupport,
    FirebirdExplainSupport,
    FirebirdFunctionSupport,
    FirebirdFullTextSearchSupport,
    FirebirdGeneratorSupport,
    FirebirdGlobalMappingSupport,
    FirebirdIntrospectionSupport,
    FirebirdLockingSupport,
    FirebirdMonitoringSupport,
    FirebirdPackageSupport,
    FirebirdPaginationSupport,
    FirebirdReturningSupport,
    FirebirdRoleSupport,
    FirebirdTableSupport,
    FirebirdTransactionSupport,
    FirebirdTriggerSupport,
    FirebirdUDFSupport,
    FirebirdWindowFunctionSupport,
)
from .namespace import FirebirdNamespaceSupport
from .sources import FirebirdRowSourceSupport

__all__ = [
    "FirebirdDMLOperationSupport",
    "FirebirdGeneratorSupport",
    "FirebirdBlobSupport",
    "FirebirdLockingSupport",
    "FirebirdTransactionSupport",
    "FirebirdTableSupport",
    "FirebirdDomainSupport",
    "FirebirdTriggerSupport",
    "FirebirdReturningSupport",
    "FirebirdIntrospectionSupport",
    "FirebirdExecuteBlockSupport",
    "FirebirdExplainSupport",
    "FirebirdFunctionSupport",
    "FirebirdBooleanSupport",
    "FirebirdDecFloatSupport",
    "FirebirdPaginationSupport",
    "FirebirdDatabaseTriggerSupport",
    "FirebirdWindowFunctionSupport",
    "FirebirdCTESupport",
    "FirebirdFullTextSearchSupport",
    "FirebirdUDFSupport",
    "FirebirdPackageSupport",
    "FirebirdGlobalMappingSupport",
    "FirebirdMonitoringSupport",
    "FirebirdRoleSupport",
    "FirebirdCursorSupport",
    "FirebirdCollationSupport",
    "FirebirdExceptionSupport",
    "FirebirdContextVariableSupport",
    "FirebirdNamespaceSupport",
    "FirebirdRowSourceSupport",
]
