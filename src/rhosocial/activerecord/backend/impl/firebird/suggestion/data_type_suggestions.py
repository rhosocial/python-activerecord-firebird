# src/rhosocial/activerecord/backend/impl/firebird/suggestion/data_type_suggestions.py
"""Firebird's **suggested data types**: the declaration a bare field gets here.

This is the DDL half of Firebird's type answer, and it is deliberately separate
from :mod:`.column_type`: that table says which *operations* a field's value
carries, this one says what a column's declaration is when a field writes only a
Python type. A geometry field, for instance, has no column class here (no
``ST_*`` surface to name) while still being perfectly storable -- and that
storage is answered here, as text.

What Firebird has and what it does not decide the table:

* **No interval, JSON, XML, range, bit-string, MAC-address or IP-address type.**
  Those concepts are carried as text. The text tier is ``BLOB SUB_TYPE TEXT``
  (:class:`~...expression.types.TextType`), which is Firebird's unbounded
  character string, except where a bounded width is the point (a MAC address is
  its canonical 17 characters, an IP address up to 45, a UUID its 36-character
  text form, an enum its label width) and a ``VARCHAR(n)`` records that width in
  the schema.
* **No UUID type.** The framework's ``uuid.UUID`` is stored as its 36-character
  text form. This dialect *can* declare a ``UUID`` concept as
  ``CHAR(16) CHARACTER SET OCTETS`` -- :meth:`format_data_type_uuid` does --
  but a bare field has no reason to prefer two bytes over a readable value, and
  the adapter binds either shape.
* **``VARCHAR`` requires a width.** Firebird has no default size ("the n
  argument is mandatory" in every reference this backend addresses), so the
  text suggestions that use it state one: 255 for ``str`` and for an enum's
  labels, 36 for a UUID, 17 for a MAC address, 45 for an IP address (the
  longest IPv6 text form, with a possible zone id).
* **Bare ``DECIMAL`` has scale 0.** Firebird stores a declaration that names
  no scale as ``DECIMAL(9, 0)``, which would drop the fractional digits of a
  bare ``Decimal`` field. The suggestion states a precision and scale instead
  (18 and 2), just as the text entries state a width.
* **``TIMESTAMP`` stores four fractional digits, not six.** That is
  :attr:`FirebirdTypeSupportMixin.FIREBIRD_FRACTION_DIGITS` -- 1/10000 second --
  and a precision of 4 is what this backend accepts; 3 would understate the
  column, 6 is refused. The declaration still renders the bare word
  ``TIMESTAMP``.
* **An instant gets the zoned column, not a bare ``TIMESTAMP``.** Firebird's
  bare ``TIMESTAMP`` is the *unzoned* type (§3.4), so it cannot carry an
  ``AwareDatetime``'s offset. The suggestion names
  :class:`FirebirdTimeStampTzType`, which renders ``TIMESTAMP WITH TIME ZONE``
  (4.0+) and refuses a declared precision. The generic ``TimestampTzType`` is
  substituted to the unzoned type on this dialect and would silently drop the
  very zone the annotation declares; "precision follows the backend" means the
  zoned column takes no precision argument here at all.
* **``dict``/``list``/``tuple``/``set``/``frozenset`` become text.** The
  adapters write them as strings, so the column is ``BLOB SUB_TYPE TEXT``;
  Firebird has no JSON column for that text to live in.
* **``bytes``/``bytearray`` become ``BLOB``** (sub-type 0, binary).
* **``bool`` becomes ``SMALLINT``.** Firebird's ``BOOLEAN`` arrived in 3.0 and
  its formatter is version-gated, while this table answers for the backend's
  whole version range (the language's pre-3.0 ``0``/``1`` storage is
  ``SMALLINT`` and 3.0+ still accepts it). A suggestion that only renders on
  some servers is worse than one that always does.

Every call returns a **fresh dict** whose values are this module's read-only
templates. A ``DataType``'s dialect is a mutable rendering attribute, so a
caller binds the dialect on a **copy of the one entry it uses** -- the table
itself is never rebound.
"""

import datetime
import decimal
import enum
import uuid
from typing import Any, Dict, Optional

from rhosocial.activerecord.backend.adapters import (
    AwareDatetime,
    BitString,
    Geometry,
    IPAddress,
    MacAddress,
    Multirange,
    Range,
    Vector,
)
from rhosocial.activerecord.backend.suggestion.definitions import (
    DataTypeSuggestion,
    ExtraDataTypeSuggestion,
)
from rhosocial.activerecord.backend.expression.types import (
    BlobType,
    DateType,
    DecimalType,
    DoubleType,
    IntegerType,
    SmallIntType,
    TextType,
    TimestampType,
    TimeType,
    VarCharType,
)

from rhosocial.activerecord.backend.impl.firebird.expression.types import (
    FirebirdTimeStampTzType,
    FirebirdVarCharType,
)

#: Firebird's suggested storage declaration per framework-modelled Python type.
FIREBIRD_DATA_TYPE_SUGGESTIONS: Dict[Any, Optional[Any]] = {
    # ``BOOLEAN`` is 3.0+ and version-gated; ``SMALLINT`` is the ``0``/``1``
    # column Firebird has always stored and is accepted by every version above.
    bool: SmallIntType(),
    int: IntegerType(),
    float: DoubleType(),
    # A bare ``DECIMAL`` is ``DECIMAL(9, 0)`` in Firebird -- the server supplies
    # scale 0 -- so a bare ``Decimal`` field would silently lose every fraction
    # (``Decimal("12.34")`` round-trips as ``Decimal("12")``). State a scale the
    # way the VARCHAR entries state a width: 18 is the largest precision
    # Firebird's DECIMAL accepts, and 2 fractional digits cover the values the
    # framework models as money-like quantities. A field that needs another
    # scale says so with UseSqlType(DecimalType(...)).
    decimal.Decimal: DecimalType(precision=18, scale=2),
    # ``VARCHAR`` has no default width in Firebird, and the backend's own text
    # type writes the database character set (UTF8) on the column as well.
    str: FirebirdVarCharType(length=255),
    bytes: BlobType(),
    bytearray: BlobType(),
    datetime.date: DateType(),
    datetime.time: TimeType(),
    # An instant needs the zoned column: the bare ``TIMESTAMP`` below is the
    # unzoned type and would discard the offset that makes this annotation
    # distinct. Firebird's zoned concept is Firebird-named and takes no
    # precision argument (the module docstring explains both decisions).
    AwareDatetime: FirebirdTimeStampTzType(),
    # 1/10000 second: the fractional-digits ceiling this backend accepts and the
    # resolution a ``TIMESTAMP`` column stores.
    datetime.datetime: TimestampType(precision=4),
    # No ``INTERVAL`` type: a duration is carried as text, which its adapter
    # writes as an ISO 8601 value.
    datetime.timedelta: TextType(),
    # No UUID type; the framework value is its 36-character text form.
    uuid.UUID: VarCharType(length=36),
    # Containers are written as text by the adapters, and Firebird has no JSON
    # column for that text to live in.
    dict: TextType(),
    list: TextType(),
    tuple: TextType(),
    set: TextType(),
    frozenset: TextType(),
    # A label set is a ``VARCHAR(255)`` plus a CHECK constraint; the width is the
    # part a declaration can record.
    enum.Enum: VarCharType(length=255),
    # Complex families: no native type, carried as the text their adapters
    # render (WKT for geometry, digits for a bit string, JSON text for a vector
    # or a range).
    Geometry: TextType(),
    Vector: TextType(),
    BitString: TextType(),
    Range: TextType(),
    Multirange: TextType(),
    MacAddress: VarCharType(length=17),
    # No native IP type; 45 covers the longest IPv6 text form, zone id included.
    IPAddress: VarCharType(length=45),
}


class FirebirdDataTypeSuggestionsMixin:
    """Firebird's answer to "what declaration does a bare field get here"."""

    def suggest_data_types(self) -> DataTypeSuggestion:
        return DataTypeSuggestion(table=dict(FIREBIRD_DATA_TYPE_SUGGESTIONS))

    def suggest_extra_data_types(self) -> ExtraDataTypeSuggestion:
        """No backend-owned extra data types."""
        return ExtraDataTypeSuggestion(table={})


__all__ = ["FIREBIRD_DATA_TYPE_SUGGESTIONS", "FirebirdDataTypeSuggestionsMixin"]
