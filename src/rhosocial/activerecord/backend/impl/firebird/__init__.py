# src/rhosocial/activerecord/backend/impl/firebird/__init__.py
"""
Firebird backend implementation for ActiveRecord.

This module provides a Firebird-specific implementation including:
- Firebird backend with connection management and query execution
- Firebird dialect with version-aware feature detection
- Firebird-specific type definitions and adapters
- Support for RETURNING clause, generators/sequences,
  EXECUTE BLOCK, and other Firebird-specific features

SQL Function Support
--------------------
All SQL expression factory functions from the core library
(rhosocial.activerecord.backend.expression.functions) are fully usable with
the Firebird backend. No Firebird-specific function overrides are required.

Fully supported functions (all categories):
  Aggregate: count, sum_, avg, min_, max_
  String: concat, coalesce, length, substring, trim, replace, upper,
      lower, initcap, left, right, lpad, rpad, reverse, strpos,
      concat_op, chr_, ascii, octet_length, bit_length, position,
      overlay, translate, repeat, space
  Math: abs_, round_, ceil, floor, sqrt, power, exp, log, sin, cos,
      tan, mod, sign, truncate
  Date/Time: now, current_date, current_time, year, month, day, hour,
      minute, second, date_part, date_trunc, interval, date_add,
      date_sub, date_diff, current_timestamp, localtimestamp, extract
  Conditional: case, nullif, greatest, least
  Window: row_number, rank, dense_rank, lag, lead, first_value,
      last_value, nth_value (Firebird 3.0+)
  JSON: json_extract, json_extract_text, json_build_object,
      json_array_elements, json_objectagg, json_arrayagg
  Array: array_agg, unnest, array_length
  Type conversion: cast, to_char, to_number, to_date
  Grouping: grouping_sets, rollup, cube
  System: current_user, session_user, system_user

Firebird-specific functions (see FIREBIRD_FUNCTION_VERSIONS):
  gen_uuid, uuid_to_char, char_to_uuid, list, dateadd, datediff,
  iif, decode

Not supported:
  SQL/XML functions (xmlagg, xmlattributes, xmlcomment, xmlconcat,
      xmlelement, xmlexists, xmlforest, xmlparse, xmlpi, xmlquery,
      xmlroot, xmlserialize, xmltable) are excluded from Firebird's
      function support check as Firebird does not implement SQL/XML.

For version-dependent function availability, see
FirebirdDialect.supports_functions() and FIREBIRD_FUNCTION_VERSIONS.
"""

__version__ = "1.0.0.dev1"

from .backend import FirebirdBackend
from .dialect import FirebirdDialect
from .transaction import FirebirdTransactionManager
from .config import FirebirdConnectionConfig
from .collation import FirebirdCollation
from .types import FirebirdBlobType, FirebirdArrayType, FirebirdDomainType
from .explain.types import FirebirdExplainResult

from .mixins import (
    FIREBIRD_VERSION_BOUNDARIES,
    FirebirdTransactionMixin,
    FirebirdBackendMixin,
    FirebirdConcurrencyMixin,
    FirebirdDMLOperationMixin,
    FirebirdLockingMixin,
    FirebirdTableMixin,
    FirebirdTriggerMixin,
    FirebirdSequenceMixin,
    FirebirdBlobMixin,
    FirebirdIntrospectionMixin,
    FirebirdTypeSupportMixin,
)

from .function_versions import FIREBIRD_FUNCTION_VERSIONS

from .expression.types import (
    FirebirdDecimalType,
    FirebirdFloatType,
    FirebirdDoubleType,
    FirebirdBlobSubType,
)

from .schema import FirebirdSchemaDiffer

from .type_compatibility import (
    DIRECT_COMPATIBLE_CASTS,
    check_cast_compatibility,
    get_compatible_types,
)

__all__ = [
    "FirebirdBackend",
    "FirebirdConnectionConfig",
    "FirebirdDialect",
    "FirebirdCollation",
    "FIREBIRD_VERSION_BOUNDARIES",
    "FirebirdTransactionManager",
    "FirebirdTransactionMixin",
    "FirebirdBackendMixin",
    "FirebirdConcurrencyMixin",
    "FirebirdDMLOperationMixin",
    "FirebirdLockingMixin",
    "FirebirdTableMixin",
    "FirebirdTriggerMixin",
    "FirebirdSequenceMixin",
    "FirebirdBlobMixin",
    "FirebirdIntrospectionMixin",
    "FirebirdTypeSupportMixin",
    "FIREBIRD_FUNCTION_VERSIONS",
    "FirebirdBlobType",
    "FirebirdArrayType",
    "FirebirdDomainType",
    "FirebirdExplainResult",
    # DDL DataType subclasses
    "FirebirdDecimalType",
    "FirebirdFloatType",
    "FirebirdDoubleType",
    "FirebirdBlobSubType",
    # Schema differ
    "FirebirdSchemaDiffer",
    # Type compatibility
    "DIRECT_COMPATIBLE_CASTS",
    "check_cast_compatibility",
    "get_compatible_types",
]