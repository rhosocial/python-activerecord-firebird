# src/rhosocial/activerecord/backend/impl/firebird/examples/named_connections/__init__.py
"""Named connection examples for Firebird backend.

This module provides example named connection configurations
that can be used with the named connection system.

Examples:
    >>> from rhosocial.activerecord.backend.impl.firebird.examples.named_connections import local_dev
    >>> config = local_dev()
"""

__all__ = ["local_dev", "prod_db", "prod_db_ssl"]

from rhosocial.activerecord.backend.impl.firebird.examples.named_connections.development import local_dev
from rhosocial.activerecord.backend.impl.firebird.examples.named_connections.production import prod_db, prod_db_ssl