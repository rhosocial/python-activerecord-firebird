import json
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Type
from uuid import UUID

from rhosocial.activerecord.backend.adapters import (
    BitString,
    BitStringAdapterBase,
    Geometry,
    GeometryAdapterBase,
    MacAddress,
    MacAddressAdapterBase,
    Multirange,
    Range,
    RangeAdapterBase,
    Vector,
    VectorAdapterBase,
)
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
            value = value.replace(tzinfo=None)
            if value.microsecond % 100:
                # Firebird TIMESTAMP stores 1/10000 s, i.e. 100-microsecond
                # units; truncate the excess microseconds so the stored value
                # round-trips exactly. Truncating to 10000 would coarsen the
                # value a hundredfold (10 ms) and lose sub-10ms differences.
                value = value.replace(microsecond=(value.microsecond // 100) * 100)
            return value
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
    """Adapts ``UUID`` to Firebird's text and binary UUID carriers.

    The *target* decides the wire form: ``str`` emits the canonical
    ``xxxxxxxx-xxxx-...`` text (what a ``VARCHAR``/``CHAR`` column stores and
    what the driver accepts for one), ``bytes`` emits the 16-byte value
    (``BINARY(16)``/``CHAR(16)`` carriers). ``use_string_format`` remains as
    the fallback preference for callers that pass no explicit target.
    """

    def __init__(self, use_string_format: bool = False):
        self._use_string_format = use_string_format

    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {UUID: [str, bytes]}

    @staticmethod
    def _as_uuid(value: Any) -> UUID:
        if isinstance(value, UUID):
            return value
        if isinstance(value, str):
            return UUID(value)
        if isinstance(value, bytes):
            if len(value) == 16:
                return UUID(bytes=value)
            return UUID(value.decode('ascii'))
        raise ValueError(f"Cannot convert {type(value).__name__} to UUID")

    def to_database(self, value: Any, target_type: Type, options: Optional[Dict] = None) -> Any:
        if value is None:
            return None
        uuid_value = self._as_uuid(value)
        if target_type is str:
            return str(uuid_value)
        if target_type is bytes:
            return uuid_value.bytes
        raise ValueError(
            f"UUID values can only be bound as str or bytes, got {target_type.__name__}"
        )

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
    """JSON adapter for Firebird TEXT/BLOB columns.

    ``default`` / ``object_hook`` are forwarded to ``json.dumps`` / ``json.loads``
    so callers can plug in neutral-type codecs (see
    ``rhosocial.activerecord.backend.adapters.json_codec``) without changing the
    default behaviour. ``default=None`` keeps the historical ``default=str``
    fallback, so unsupported objects still serialize as their ``str()`` form.
    """

    def __init__(self, default=None, object_hook=None):
        self._json_default = default
        self._json_object_hook = object_hook

    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {dict: [dict, list, str, bytes], list: [list, str, bytes]}

    def to_database(self, value: Any, target_type: Type, options: Optional[Dict] = None) -> Any:
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            default = self._json_default if self._json_default is not None else str
            return json.dumps(value, ensure_ascii=False, default=default)
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
                return json.loads(value, object_hook=self._json_object_hook)
            except (json.JSONDecodeError, ValueError):
                return value
        return value


class FirebirdGeometryAdapter(GeometryAdapterBase):
    """WKT-text adapter for Firebird VARCHAR / BLOB SUB_TYPE TEXT columns.

    Firebird has no spatial type. A neutral
    :class:`~rhosocial.activerecord.backend.adapters.Geometry` is stored as
    plain WKT text and decoded from text or UTF-8 bytes. Because plain WKT
    carries no SRID, a decoded geometry always has ``srid=None``; use
    ``SRID=...;`` WKT on decode when the SRID is known out of band.
    """

    def __init__(self):
        super().__init__()
        self.register_type(Geometry, str)
        self.register_type(Geometry, bytes)

    def _encode(
        self, geometry: Geometry, target_type: Type, options: Optional[Dict] = None
    ) -> Any:
        wkt = geometry.to_wkt()
        if target_type is bytes:
            return wkt.encode('utf-8')
        return wkt

    def _decode(self, value: Any, options: Optional[Dict] = None) -> Geometry:
        if isinstance(value, (bytes, bytearray)):
            value = bytes(value).decode('utf-8')
        wkt = self._require_text(value)
        return Geometry.from_wkt(wkt)


class FirebirdVectorAdapter(VectorAdapterBase):
    """JSON-text adapter for Firebird vector columns.

    Firebird has no native vector type, so a neutral
    :class:`~rhosocial.activerecord.backend.adapters.Vector` is stored as a
    JSON array in ``VARCHAR`` or ``BLOB SUB_TYPE TEXT`` and decoded from JSON
    text, UTF-8 bytes, or an already-decoded list/tuple.
    """

    def __init__(self):
        super().__init__()
        self.register_type(Vector, str)
        self.register_type(Vector, bytes)

    def _encode(self, vector: Vector, target_type: Type, options: Optional[Dict] = None) -> Any:
        text = json.dumps(vector.to_json_value(), ensure_ascii=False)
        if target_type is bytes:
            return text.encode('utf-8')
        return text

    def _decode(self, value: Any, options: Optional[Dict] = None) -> Vector:
        if isinstance(value, (list, tuple)):
            return Vector.from_json_value(value)
        if isinstance(value, (bytes, bytearray)):
            value = bytes(value).decode('utf-8')
        if not isinstance(value, str):
            raise TypeError(f"expected JSON array text or a list, got {type(value).__name__}")
        return Vector.from_json_value(json.loads(value))


class FirebirdBitStringAdapter(BitStringAdapterBase):
    """Text/binary adapter for neutral bit strings.

    Firebird carries bit strings either as bit text (``'10101'``) in a
    ``VARCHAR`` / ``BLOB SUB_TYPE TEXT`` column, or as raw bytes in a
    ``BLOB SUB_TYPE BINARY`` column. Raw bytes can only represent whole
    bytes, so a bit string whose ``bit_length`` is not a multiple of 8 loses
    its exact length in the binary representation; the text form keeps it.
    """

    def __init__(self):
        super().__init__()
        self.register_type(BitString, bytes)
        self.register_type(BitString, str)

    def _encode(self, bits: BitString, target_type: Type, options: Optional[Dict] = None) -> Any:
        if target_type is bytes:
            return bits.data
        if target_type is str:
            return bits.to_bits()
        raise TypeError(
            f"bit strings can only be bound as str or bytes, got {target_type.__name__}"
        )

    def _decode(self, value: Any, options: Optional[Dict] = None) -> BitString:
        if isinstance(value, BitString):
            return value
        if isinstance(value, (bytes, bytearray)):
            return BitString.from_bytes(bytes(value))
        if isinstance(value, str):
            return BitString.from_bits(value)
        raise TypeError(f"expected bytes or a bit-string text, got {type(value).__name__}")


class FirebirdRangeAdapter(RangeAdapterBase):
    """JSON-text adapter for neutral ranges stored as ``BLOB SUB_TYPE TEXT``.

    Firebird has no range/multirange type. The neutral
    :class:`~rhosocial.activerecord.backend.adapters.Range` /
    :class:`~rhosocial.activerecord.backend.adapters.Multirange` value is stored
    as JSON text in a text BLOB (or VARCHAR) using the canonical representation.
    """

    def __init__(self):
        super().__init__()
        self.register_type(Range, str)
        self.register_type(Multirange, str)
        self.register_type(Range, bytes)
        self.register_type(Multirange, bytes)

    def _encode(self, value: Any, target_type: Type, options: Optional[Dict] = None) -> Any:
        text = json.dumps(value.to_json_value(), ensure_ascii=False)
        if target_type is bytes:
            return text.encode('utf-8')
        return text

    def _decode(
        self, value: Any, target_type: Type, options: Optional[Dict] = None
    ) -> Any:
        if isinstance(value, (bytes, bytearray)):
            value = bytes(value).decode('utf-8')
        if not isinstance(value, str):
            raise TypeError(f"expected JSON text, got {type(value).__name__}")
        payload = json.loads(value)
        if target_type is Multirange:
            return Multirange.from_json_value(payload)
        if target_type is Range:
            return Range.from_json_value(payload)
        if isinstance(payload, list):
            return Multirange.from_json_value(payload)
        return Range.from_json_value(payload)


class FirebirdMacAddressAdapter(MacAddressAdapterBase):
    """Canonical-text adapter for MAC addresses.

    Firebird has no MAC address type; the value is stored as the canonical
    lowercase colon-separated text (``01:23:45:67:89:ab``) in a ``VARCHAR`` or
    ``CHAR`` column. A ``BLOB SUB_TYPE BINARY`` column is also accepted when
    the raw value is exactly 6 or 8 octets.
    """

    def __init__(self):
        super().__init__()
        self.register_type(MacAddress, str)
        self.register_type(MacAddress, bytes)

    def _encode(
        self, mac: MacAddress, target_type: Type, options: Optional[Dict] = None
    ) -> Any:
        if target_type is bytes:
            return mac.octets
        return str(mac)

    def _decode(self, value: Any, options: Optional[Dict] = None) -> MacAddress:
        if isinstance(value, bytearray):
            value = bytes(value)
        if isinstance(value, bytes) and len(value) not in (6, 8):
            try:
                value = value.decode('utf-8')
            except UnicodeDecodeError as exc:
                raise ValueError("MAC address bytes must be 6 or 8 octets") from exc
        return MacAddress.parse(value)


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
    (FirebirdGeometryAdapter, Geometry, str),
    (FirebirdVectorAdapter, Vector, str),
    (FirebirdBitStringAdapter, BitString, (bytes, str)),
    (FirebirdRangeAdapter, (Range, Multirange), str),
    (FirebirdMacAddressAdapter, MacAddress, str),
]

__all__ = [
    "FirebirdBlobAdapter", "FirebirdTextBlobAdapter", "FirebirdBooleanAdapter",
    "FirebirdDateAdapter", "FirebirdTimeAdapter", "FirebirdDatetimeAdapter",
    "FirebirdDecimalAdapter", "FirebirdUUIDAdapter", "FirebirdJsonAdapter",
    "FirebirdGeometryAdapter", "FirebirdVectorAdapter", "FirebirdBitStringAdapter",
    "FirebirdRangeAdapter", "FirebirdMacAddressAdapter",
    "firebird_adapters",
]
