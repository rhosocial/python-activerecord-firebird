import json
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Type, Union
from uuid import UUID

from rhosocial.activerecord.backend.type_adapter import SQLTypeAdapter


class FirebirdBlobAdapter(SQLTypeAdapter):
    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {bytes: [bytes]}

    def to_database(self, value: Any, target_type: Type, options: Optional[Dict] = None) -> Any:
        if value is None:
            return None
        if isinstance(value, (bytes, bytearray)):
            return bytes(value)
        raise ValueError(f"Cannot convert {type(value).__name__} to BLOB")

    def from_database(self, value: Any, target_type: Type, options: Optional[Dict] = None) -> Optional[bytes]:
        if value is None:
            return None
        if isinstance(value, bytes):
            return value
        if isinstance(value, bytearray):
            return bytes(value)
        if isinstance(value, str):
            return value.encode('utf-8')
        return bytes(value)


class FirebirdTextBlobAdapter(SQLTypeAdapter):
    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {str: [str]}

    def to_database(self, value: Any, target_type: Type, options: Optional[Dict] = None) -> Any:
        if value is None:
            return None
        return str(value)

    def from_database(self, value: Any, target_type: Type, options: Optional[Dict] = None) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, bytes):
            return value.decode('utf-8')
        if isinstance(value, bytearray):
            return value.decode('utf-8')
        # Preserve trailing whitespace: Firebird VARCHAR values keep trailing
        # spaces/newlines, so values like "admin'-- " must round-trip exactly.
        # (rstrip() here would corrupt whitespace-sensitive payloads.)
        return str(value)


class FirebirdBooleanAdapter(SQLTypeAdapter):
    def __init__(self, use_char: bool = False):
        self._use_char = use_char

    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {bool: [bool, int, str]}

    def to_database(self, value: Any, target_type: Type, options: Optional[Dict] = None) -> Any:
        if value is None:
            return None
        if self._use_char:
            return 'T' if value else 'F'
        # Firebird 3+ supports a native BOOLEAN type and the driver accepts
        # integer 0/1 for BOOLEAN columns; binding a raw Python bool is
        # rejected by the driver (it stringifies to 'True'/'False'). Using an
        # integer also stores cleanly into small VARCHAR columns used by custom
        # adapters that target str (e.g. YesOrNo adapters storing 'yes'/'no').
        return 1 if value else 0

    def from_database(self, value: Any, target_type: Type, options: Optional[Dict] = None) -> Optional[bool]:
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


class FirebirdDecimalAdapter(SQLTypeAdapter):
    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {Decimal: [Decimal, float, int, str]}

    def to_database(self, value: Any, target_type: Type, options: Optional[Dict] = None) -> Any:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        if isinstance(value, str):
            return Decimal(value)
        raise ValueError(f"Cannot convert {type(value).__name__} to DECIMAL")

    def from_database(self, value: Any, target_type: Type, options: Optional[Dict] = None) -> Optional[Decimal]:
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


class FirebirdDateAdapter(SQLTypeAdapter):
    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {date: [date, str, bytes]}

    def to_database(self, value: Any, target_type: Type, options: Optional[Dict] = None) -> Any:
        if value is None:
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            return datetime.strptime(value, '%Y-%m-%d').date()
        raise ValueError(f"Cannot convert {type(value).__name__} to DATE")

    def from_database(self, value: Any, target_type: Type, options: Optional[Dict] = None) -> Optional[date]:
        if value is None:
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            return datetime.strptime(value, '%Y-%m-%d').date()
        if isinstance(value, bytes):
            return self.from_database(value.decode('utf-8'), target_type, options)
        raise ValueError(f"Cannot convert {type(value).__name__} to date")


class FirebirdTimeAdapter(SQLTypeAdapter):
    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {time: [time, str, bytes, int]}

    def to_database(self, value: Any, target_type: Type, options: Optional[Dict] = None) -> Any:
        if value is None:
            return None
        if isinstance(value, time):
            return value
        if isinstance(value, datetime):
            return value.time()
        if isinstance(value, str):
            return datetime.strptime(value, '%H:%M:%S').time()
        if isinstance(value, timedelta):
            s = int(value.total_seconds())
            h, r = divmod(s, 3600)
            m, sec = divmod(r, 60)
            return time(h, m, sec)
        raise ValueError(f"Cannot convert {type(value).__name__} to TIME")

    def from_database(self, value: Any, target_type: Type, options: Optional[Dict] = None) -> Optional[time]:
        if value is None:
            return None
        if isinstance(value, time):
            return value
        if isinstance(value, timedelta):
            s = int(value.total_seconds())
            h, r = divmod(s, 3600)
            m, sec = divmod(r, 60)
            return time(h, m, sec)
        if isinstance(value, datetime):
            return value.time()
        if isinstance(value, str):
            return datetime.strptime(value, '%H:%M:%S').time()
        if isinstance(value, bytes):
            return self.from_database(value.decode('utf-8'), target_type, options)
        raise ValueError(f"Cannot convert {type(value).__name__} to time")


class FirebirdDatetimeAdapter(SQLTypeAdapter):
    def __init__(self, store_as_utc: bool = True):
        self._store_as_utc = store_as_utc

    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {datetime: [datetime, date, str, bytes, int, float]}

    def to_database(self, value: Any, target_type: Type, options: Optional[Dict] = None) -> Any:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is not None and self._store_as_utc:
                value = value.astimezone(timezone.utc)
            return value.replace(tzinfo=None)
        if isinstance(value, str):
            return datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        raise ValueError(f"Cannot convert {type(value).__name__} to TIMESTAMP")

    def from_database(self, value: Any, target_type: Type, options: Optional[Dict] = None) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time()).replace(tzinfo=timezone.utc)
        if isinstance(value, str):
            return datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        if isinstance(value, bytes):
            return self.from_database(value.decode('utf-8'), target_type, options)
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value)
        raise ValueError(f"Cannot convert {type(value).__name__} to datetime")


class FirebirdUUIDAdapter(SQLTypeAdapter):
    def __init__(self, use_string_format: bool = False):
        self._use_string_format = use_string_format

    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {UUID: [str, bytes]}

    def to_database(self, value: Any, target_type: Type, options: Optional[Dict] = None) -> Any:
        if value is None:
            return None
        if isinstance(value, UUID):
            return str(value) if self._use_string_format else value.bytes
        if isinstance(value, str):
            return UUID(value).bytes if not self._use_string_format else value
        if isinstance(value, bytes):
            if len(value) == 16:
                return value
            return UUID(bytes=value).bytes if not self._use_string_format else value.decode('ascii')
        raise ValueError(f"Cannot convert {type(value).__name__} to UUID")

    def from_database(self, value: Any, target_type: Type, options: Optional[Dict] = None) -> Optional[UUID]:
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


class FirebirdJsonAdapter(SQLTypeAdapter):
    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {dict: [dict, list, str, bytes], list: [list, str, bytes]}

    def to_database(self, value: Any, target_type: Type, options: Optional[Dict] = None) -> Any:
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, default=str)
        if isinstance(value, str):
            return value
        if isinstance(value, bytes):
            return value.decode('utf-8')
        return str(value)

    def from_database(self, value: Any, target_type: Type, options: Optional[Dict] = None) -> Any:
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, (str, bytes)):
            if isinstance(value, bytes):
                value = value.decode('utf-8')
            try:
                return json.loads(value)
            except (json.JSONDecodeError, ValueError):
                return value
        return value


firebird_adapters = [
    (FirebirdBlobAdapter, bytes, bytes),
    (FirebirdTextBlobAdapter, str, str),
    (FirebirdBooleanAdapter, bool, bool),
    (FirebirdDateAdapter, date, date),
    (FirebirdTimeAdapter, time, time),
    (FirebirdDatetimeAdapter, datetime, datetime),
    (FirebirdDecimalAdapter, Decimal, (Decimal, float, int)),
    (FirebirdUUIDAdapter, UUID, (str, bytes)),
    (FirebirdJsonAdapter, dict, dict),
]

__all__ = [
    "FirebirdBlobAdapter", "FirebirdTextBlobAdapter", "FirebirdBooleanAdapter",
    "FirebirdDateAdapter", "FirebirdTimeAdapter", "FirebirdDatetimeAdapter",
    "FirebirdDecimalAdapter", "FirebirdUUIDAdapter", "FirebirdJsonAdapter",
    "firebird_adapters",
]
