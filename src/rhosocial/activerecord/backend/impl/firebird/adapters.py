# src/rhosocial/activerecord/backend/impl/firebird/adapters.py
"""Firebird type adapter implementations.

Provides type conversion between Python types and Firebird database types.
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, List, Optional, Tuple, Type, Union
from uuid import UUID

from rhosocial.activerecord.backend.type_adapter import BaseSQLTypeAdapter


class FirebirdBlobAdapter(BaseSQLTypeAdapter):
    """Adapter for Firebird BLOB SUB_TYPE BINARY <=> bytes."""

    def to_database(self, value: bytes) -> bytes:
        if value is None:
            return None
        if isinstance(value, bytes):
            return value
        if isinstance(value, bytearray):
            return bytes(value)
        raise ValueError(f"Cannot convert {type(value).__name__} to BLOB")

    def to_python(self, value: Any) -> bytes:
        if value is None:
            return None
        if isinstance(value, bytes):
            return value
        if isinstance(value, bytearray):
            return bytes(value)
        if isinstance(value, str):
            return value.encode('utf-8')
        return bytes(value)

    @property
    def py_types(self) -> tuple:
        return (bytes, bytearray)

    @property
    def db_types(self) -> tuple:
        return (bytes,)


class FirebirdTextBlobAdapter(BaseSQLTypeAdapter):
    """Adapter for Firebird BLOB SUB_TYPE TEXT <=> str."""

    def to_database(self, value: str) -> str:
        if value is None:
            return None
        return str(value)

    def to_python(self, value: Any) -> str:
        if value is None:
            return None
        if isinstance(value, bytes):
            return value.decode('utf-8')
        if isinstance(value, bytearray):
            return value.decode('utf-8')
        return str(value)

    @property
    def py_types(self) -> tuple:
        return (str,)

    @property
    def db_types(self) -> tuple:
        return (str,)


class FirebirdBooleanAdapter(BaseSQLTypeAdapter):
    """Adapter for Firebird BOOLEAN (FB 3.0+) <=> bool.

    For FB < 3.0, booleans are stored as CHAR(1) 'T'/'F' or SMALLINT 0/1.
    """

    def __init__(self, use_char: bool = False):
        self.use_char = use_char

    def to_database(self, value: bool) -> Any:
        if value is None:
            return None
        if self.use_char:
            return 'T' if value else 'F'
        return value

    def to_python(self, value: Any) -> bool:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return bool(value)
        if isinstance(value, str):
            return value.upper() in ('T', 'TRUE', 'Y', 'YES', '1')
        if isinstance(value, bytes):
            return value.upper() in (b'T', b'TRUE', b'Y', b'YES', b'1')
        return bool(value)

    @property
    def py_types(self) -> tuple:
        return (bool,)

    @property
    def db_types(self) -> tuple:
        return (bool, int, str)


class FirebirdDecimalAdapter(BaseSQLTypeAdapter):
    """Adapter for Firebird DECIMAL/NUMERIC <=> Decimal."""

    def to_database(self, value: Decimal) -> Union[Decimal, float, str]:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        if isinstance(value, str):
            return Decimal(value)
        raise ValueError(f"Cannot convert {type(value).__name__} to DECIMAL")

    def to_python(self, value: Any) -> Decimal:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        if isinstance(value, float):
            return Decimal(str(value))
        if isinstance(value, int):
            return Decimal(value)
        if isinstance(value, str):
            return Decimal(value)
        if isinstance(value, bytes):
            return Decimal(value.decode('utf-8'))
        raise ValueError(f"Cannot convert {type(value).__name__} to Decimal")

    @property
    def py_types(self) -> tuple:
        return (Decimal,)

    @property
    def db_types(self) -> tuple:
        return (Decimal, float, int, str)


class FirebirdDateAdapter(BaseSQLTypeAdapter):
    """Adapter for Firebird DATE <=> datetime.date."""

    def to_database(self, value: date) -> date:
        if value is None:
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            from datetime import datetime as dt
            try:
                return dt.strptime(value, '%Y-%m-%d').date()
            except ValueError:
                return dt.fromisoformat(value).date()
        raise ValueError(f"Cannot convert {type(value).__name__} to DATE")

    def to_python(self, value: Any) -> date:
        if value is None:
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            from datetime import datetime as dt
            try:
                return dt.strptime(value, '%Y-%m-%d').date()
            except ValueError:
                return dt.fromisoformat(value).date()
        if isinstance(value, bytes):
            return self.to_python(value.decode('utf-8'))
        raise ValueError(f"Cannot convert {type(value).__name__} to date")

    @property
    def py_types(self) -> tuple:
        return (date,)

    @property
    def db_types(self) -> tuple:
        return (date, str, bytes)


class FirebirdTimeAdapter(BaseSQLTypeAdapter):
    """Adapter for Firebird TIME <=> datetime.time."""

    def to_database(self, value: time) -> time:
        if value is None:
            return None
        if isinstance(value, time):
            return value
        if isinstance(value, datetime):
            return value.time()
        if isinstance(value, str):
            from datetime import datetime as dt
            return dt.strptime(value, '%H:%M:%S').time()
        if isinstance(value, timedelta):
            total_seconds = int(value.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return time(hours, minutes, seconds)
        raise ValueError(f"Cannot convert {type(value).__name__} to TIME")

    def to_python(self, value: Any) -> time:
        if value is None:
            return None
        if isinstance(value, time):
            return value
        if isinstance(value, timedelta):
            total_seconds = int(value.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return time(hours, minutes, seconds)
        if isinstance(value, datetime):
            return value.time()
        if isinstance(value, str):
            from datetime import datetime as dt
            try:
                return dt.strptime(value, '%H:%M:%S').time()
            except ValueError:
                return dt.fromisoformat(value).time()
        if isinstance(value, bytes):
            return self.to_python(value.decode('utf-8'))
        raise ValueError(f"Cannot convert {type(value).__name__} to time")

    @property
    def py_types(self) -> tuple:
        return (time,)

    @property
    def db_types(self) -> tuple:
        return (time, str, bytes, int)


class FirebirdDatetimeAdapter(BaseSQLTypeAdapter):
    """Adapter for Firebird TIMESTAMP <=> datetime.datetime.

    Handles timezone-naive and timezone-aware datetime conversions.
    Firebird does not natively store timezone information.
    """

    def __init__(self, store_as_utc: bool = True):
        self.store_as_utc = store_as_utc

    def to_database(self, value: datetime) -> datetime:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is not None and self.store_as_utc:
                return value.astimezone(datetime.timezone.utc).replace(tzinfo=None)
            return value.replace(tzinfo=None)
        if isinstance(value, str):
            from datetime import datetime as dt
            try:
                return dt.strptime(value, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                return dt.fromisoformat(value)
        raise ValueError(f"Cannot convert {type(value).__name__} to TIMESTAMP")

    def to_python(self, value: Any) -> datetime:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time())
        if isinstance(value, str):
            from datetime import datetime as dt
            try:
                return dt.strptime(value, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                return dt.fromisoformat(value)
        if isinstance(value, bytes):
            return self.to_python(value.decode('utf-8'))
        if isinstance(value, (int, float)):
            from datetime import datetime as dt
            return dt.fromtimestamp(value)
        raise ValueError(f"Cannot convert {type(value).__name__} to datetime")

    @property
    def py_types(self) -> tuple:
        return (datetime,)

    @property
    def db_types(self) -> tuple:
        return (datetime, date, str, bytes, int, float)


class FirebirdUUIDAdapter(BaseSQLTypeAdapter):
    """Adapter for Firebird CHAR(16) CHARACTER SET OCTETS <=> uuid.UUID.

    Firebird stores UUIDs as CHAR(16) OCTETS or VARCHAR(36) for string representation.
    """

    def __init__(self, use_string_format: bool = False):
        self.use_string_format = use_string_format

    def to_database(self, value: UUID) -> Any:
        if value is None:
            return None
        if isinstance(value, UUID):
            if self.use_string_format:
                return str(value)
            return value.bytes
        if isinstance(value, str):
            return UUID(value).bytes if not self.use_string_format else value
        if isinstance(value, bytes):
            if len(value) == 16:
                return value
            return UUID(bytes=value).bytes if not self.use_string_format else value.decode('ascii')
        raise ValueError(f"Cannot convert {type(value).__name__} to UUID")

    def to_python(self, value: Any) -> UUID:
        if value is None:
            return None
        if isinstance(value, UUID):
            return value
        if isinstance(value, str):
            return UUID(value)
        if isinstance(value, bytes):
            if len(value) == 16:
                return UUID(bytes=value)
            return UUID(value.decode('ascii'))
        raise ValueError(f"Cannot convert {type(value).__name__} to UUID")

    @property
    def py_types(self) -> tuple:
        return (UUID,)

    @property
    def db_types(self) -> tuple:
        return (str, bytes)


# List of (adapter_class, python_type, db_type) for registration
firebird_adapters = [
    (FirebirdBlobAdapter, bytes, bytes),
    (FirebirdTextBlobAdapter, str, str),
    (FirebirdBooleanAdapter, bool, bool),
    (FirebirdDateAdapter, date, date),
    (FirebirdTimeAdapter, time, time),
    (FirebirdDatetimeAdapter, datetime, datetime),
    (FirebirdDecimalAdapter, Decimal, (Decimal, float, int)),
    (FirebirdUUIDAdapter, UUID, (str, bytes)),
]

__all__ = [
    "FirebirdBlobAdapter",
    "FirebirdTextBlobAdapter",
    "FirebirdBooleanAdapter",
    "FirebirdDateAdapter",
    "FirebirdTimeAdapter",
    "FirebirdDatetimeAdapter",
    "FirebirdDecimalAdapter",
    "FirebirdUUIDAdapter",
    "firebird_adapters",
]