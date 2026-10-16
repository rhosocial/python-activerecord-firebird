# src/rhosocial/activerecord/backend/impl/firebird/expression/types.py
"""Firebird-specific DDL DataType subclasses."""

import re
from typing import Tuple

from rhosocial.activerecord.backend.expression.serialization import register_expression_class
from rhosocial.activerecord.backend.expression.types import (
    BigIntType,
    BinaryType,
    BooleanType,
    CharType,
    CustomType,
    DataType,
    DateType,
    DecimalType,
    DoubleType,
    FloatType,
    IntegerType,
    SmallIntType,
    TextType,
    TimeType,
    TimeTzType,
    TimestampType,
    TimestampTzType,
    VarBinaryType,
    VarCharType,
)


class FirebirdCharType(CharType):
    """Firebird ``CHAR(n) CHARACTER SET UTF8`` — fixed-length string with the
    character set stated on the column.

    Derives from :class:`CharType` because the character set is a *column*
    attribute in Firebird, not part of the type's identity: a ``CHAR`` column
    declared under the database default character set stores the same fixed
    length string as this one. Only the written form differs.
    """

    name = "firebird_char"


class FirebirdVarCharType(VarCharType):
    """Firebird ``VARCHAR(n) CHARACTER SET UTF8`` — variable-length string with
    the character set stated on the column.

    Derives from :class:`VarCharType` for the same reason as
    :class:`FirebirdCharType`: the storage is the generic concept's, and the
    character set belongs to the column.
    """

    name = "firebird_varchar"


#: Why the three date-time classes below refuse rather than honour the inherited
#: ``precision``. Assigned into each of their docstrings by
#: :func:`_with_temporal_precision_note`, because a class docstring has to be one
#: literal for ``help()`` and Sphinx to see it — a ``+``-concatenation compiles to
#: an expression and Python stops recording it as ``__doc__``.
_TEMPORAL_PRECISION_NOTE = """
    The inherited ``precision`` is **refused at render time, not honoured**.
    Firebird's declaration grammar has no precision production for any of these
    types — ``TIME [{WITHOUT | WITH} TIME ZONE]`` (§3.4.2), ``TIMESTAMP
    [{WITHOUT | WITH} TIME ZONE]`` (§3.4.3), and the same two productions in the
    §3.12 Data Type Declaration Syntax, identical in the 4.0 and 5.0 references —
    while ``FLOAT [(bin_prec)]`` and ``DECFLOAT [(dec_prec)]`` in that same
    production do have one. Fractional seconds are stored to ten-thousandths of a
    second whatever the declaration says (§3.4, *Fractions of Seconds*), so a
    declared precision could not change the column even if it were accepted.
    FirebirdSQL/firebird#4779 (CORE-4459) requests it and is still open.

    The field stays in ``PARAMETERS`` — core's tuple is not this backend's to
    narrow, and the concept really does carry a precision on a backend whose
    grammar has one. ``FirebirdTypeSupportMixin._check_firebird_temporal_
    precision`` is what refuses it *by name*, so flipping it cannot render a
    column that the framework's own equality calls different from the one asked
    for.
"""


def _with_temporal_precision_note(body: str) -> str:
    """Append :data:`_TEMPORAL_PRECISION_NOTE` to a class docstring body.

    Applied with ``cls.__doc__ = ...`` after each class rather than written out
    three times, because the three classes need the identical argument and a copy
    that drifts is how one of them ends up undocumented.
    """
    return body.rstrip("\n") + "\n" + _TEMPORAL_PRECISION_NOTE


class FirebirdTimeStampTzType(TimestampTzType):
    """Firebird ``TIMESTAMP WITH TIME ZONE`` (Firebird 4.0+).

    Stores the instant *and* the zone offset it was written with, and reads back
    in the session zone — which is why it is the zoned concept and not a flag on
    :class:`TimestampType`.

    This is also where Firebird's zoned timestamp is *reached from*: the generic
    :class:`TimestampTzType` has no ``format_data_type_`` on this dialect, because
    ``TIMESTAMP`` is Firebird's **unzoned** type (§3.4: *"TIME and TIMESTAMP are
    synonymous to their respective WITHOUT TIME ZONE data types"*) and rendering
    the generic concept with it would declare a column that silently drops the
    zone. The dialect names the unzoned concept as ``timestamptz``'s substitute in
    ``suggested_data_types`` and reaches this class by its Firebird name instead.
    """

    name = "firebird_timestamptz"


class FirebirdTimeTzType(TimeTzType):
    """Firebird ``TIME WITH TIME ZONE`` (Firebird 4.0+).

    Firebird's zoned *time*: the offset travels with the value, so a time read
    back is not the same clock reading it went in as. Six bytes — four for the
    time plus two for either an offset in minutes or the id of a named zone
    (§3.1 Table 3.1; §3.4, *Storage of Time Zone Types*) — held at UTC so two
    values in different zones compare and index correctly.

    As with :class:`FirebirdTimeStampTzType`, this is how Firebird's zoned time is
    reached: the generic :class:`TimeTzType` is substituted, not rendered, because
    ``TIME`` is Firebird's unzoned type.
    """

    name = "firebird_timetz"


class FirebirdTimeWithoutTimeZoneType(TimeType):
    """Firebird ``TIME WITHOUT TIME ZONE`` (Firebird 4.0+).

    The spelled-out long form of :class:`TimeType`, which Firebird requires
    alongside its zoned ``TIME WITH TIME ZONE`` because ``TIME`` on its own was
    already taken (§3.4.2: *"For a bare TIME, WITHOUT TIME ZONE is assumed"*). The
    storage is the generic concept's — a time of day with no offset — so this
    derives from it rather than sitting beside it. The clause is rendered rather
    than the bare word because saying it is the entire point of having a class
    for it.
    """

    name = "firebird_time_without_time_zone"


for _temporal_class in (
    FirebirdTimeStampTzType,
    FirebirdTimeTzType,
    FirebirdTimeWithoutTimeZoneType,
):
    _temporal_class.__doc__ = _with_temporal_precision_note(_temporal_class.__doc__)
del _temporal_class


class FirebirdDecFloatType(DecimalType):
    """Firebird ``DECFLOAT(16|34)`` — exact decimal, up to 34 significant
    digits (Firebird 4.0+).

    **Not** a variant of the binary approximate types. ``DECFLOAT`` is IEEE 754
    decimal floating-point: every value is held exactly as a coefficient times a
    power of ten, so ``0.1`` is the same number as the literal ``0.1`` — which is
    the property :class:`DecimalType` exists for. :class:`FloatType` and
    :class:`DoubleType` are binary approximate and hold a *different*
    number than their decimal-looking literals, so deriving from
    :class:`FloatType` would put this on the wrong side of that line.

    What ``DECFLOAT`` has and ``NUMERIC`` does not is an exponent: the declared
    precision (16 or 34) counts significant digits across the whole decimal
    range rather than fixing a fractional digit count. Firebird exposes no scale
    parameter, so ``scale`` stays ``None`` and ``PARAMETERS`` names only
    the precision — two ``DECFLOAT`` columns are the same declaration exactly
    when their precisions agree.

    The concept's ``spelling`` list is deliberately not exposed here: ``DECFLOAT``
    is one word, and accepting ``numeric``/``dec`` would claim Firebird writes
    them for this type, which it does not.

    **The default width is 34, on the reference's authority.**  The language
    reference, §3.2.2.1 *DECFLOAT*, gives the parameter as *"Precision in decimal
    digits, either 16 or 34. Default is 34."* — §3.1 Table 3.1 says the same from
    the other end (*"If the precision is not specified, 34 is used by default"*)
    — and §3.12's ``scalar_datatype`` production spells it
    ``DECFLOAT [(dec_prec)]``. This constructor used to default to 16, which meant
    a bare ``FirebirdDecFloatType()`` declared a *different column* from the one
    ``FirebirdDialect.parse_type("DECFLOAT")`` resolved to (34, and correctly so).
    Two answers to "what does a bare ``DECFLOAT`` mean" on one backend is the same
    defect as two answers to "what does ``DECFLOAT(16)`` mean", so the default
    follows the documentation and ``parse_type`` and the constructor agree.
    """

    name = "firebird_decfloat"

    def __init__(self, dialect=None, precision: int = 34):
        super().__init__(dialect)
        if precision not in (16, 34):
            raise ValueError(f"DECFLOAT precision must be 16 or 34, got {precision}")
        self.precision: int = precision

    PARAMETERS = ("precision",)

class FirebirdInt128Type(DataType):
    """Firebird ``INT128`` — signed 128-bit integer (Firebird 4.0+).

    Deliberately **not** derived from :class:`BigIntType`. ``BIGINT`` is 64-bit;
    ``INT128`` holds -2**127 .. 2**127-1, a range that differs by two orders of
    magnitude, and an index built for ``BIGINT`` is not an index built for this.
    Core's integer family stops at 64 bits because no other supported backend
    goes wider — a class per width is the family's axis, and the family simply
    has no 128-bit member to sit under.

    On ``DataType`` for the same reason: SQL:2016 has no 128-bit integer type,
    and ``INT128`` is Firebird 4's own addition. It is not a ``FloatType`` and
    not a ``DecimalType``, so there is nothing else in core it could be.
    """

    name = "firebird_int128"


_DATA_TYPE_TEXT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_$.,() \t]*")
_QUALIFIED_IDENTIFIER_RE = re.compile(
    r"[A-Za-z_][A-Za-z0-9_$]*(?:\.[A-Za-z_][A-Za-z0-9_$]*)?"
)
_INTEGER_RE = re.compile(r"INTEGER|INT|BIGINT|SMALLINT", re.IGNORECASE)
_FLOAT_RE = re.compile(r"FLOAT(?:\s*\(\s*(\d+)\s*\))?", re.IGNORECASE)
_REAL_RE = re.compile(r"REAL", re.IGNORECASE)
_DOUBLE_RE = re.compile(r"DOUBLE\s+PRECISION", re.IGNORECASE)
_DECIMAL_RE = re.compile(
    r"(?:DECIMAL|NUMERIC)(?:\s*\(\s*(\d+)\s*(?:,\s*(\d+)\s*)?\))?",
    re.IGNORECASE,
)
_VARCHAR_RE = re.compile(
    r"(?:VARCHAR|CHARACTER\s+VARYING|CHAR\s+VARYING)"
    r"(?:\s*\(\s*(\d+)\s*\))?",
    re.IGNORECASE,
)
_CHAR_RE = re.compile(
    r"(?:CHAR|CHARACTER)(?:\s*\(\s*(\d+)\s*\))?",
    re.IGNORECASE,
)
_BINARY_VARCHAR_RE = re.compile(
    r"(?:VARCHAR|CHARACTER\s+VARYING|CHAR\s+VARYING)"
    r"\s*\(\s*(\d+)\s*\)\s+CHARACTER\s+SET\s+OCTETS",
    re.IGNORECASE,
)
_BINARY_CHAR_RE = re.compile(
    r"(?:CHAR|CHARACTER)\s*\(\s*(\d+)\s*\)\s+CHARACTER\s+SET\s+OCTETS",
    re.IGNORECASE,
)
_UTF8_VARCHAR_RE = re.compile(
    r"(?:VARCHAR|CHARACTER\s+VARYING|CHAR\s+VARYING)"
    r"\s*\(\s*(\d+)\s*\)\s+CHARACTER\s+SET\s+UTF8",
    re.IGNORECASE,
)
_UTF8_CHAR_RE = re.compile(
    r"(?:CHAR|CHARACTER)\s*\(\s*(\d+)\s*\)\s+CHARACTER\s+SET\s+UTF8",
    re.IGNORECASE,
)
_BLOB_TEXT_RE = re.compile(r"BLOB\s+SUB_TYPE\s+TEXT", re.IGNORECASE)
_BLOB_BINARY_RE = re.compile(
    r"BLOB(?:\s+SUB_TYPE\s+BINARY|\s+CHARACTER\s+SET\s+OCTETS)?",
    re.IGNORECASE,
)
_DATE_RE = re.compile(r"DATE", re.IGNORECASE)
_TIME_RE = re.compile(r"TIME", re.IGNORECASE)
_TIMESTAMP_RE = re.compile(r"TIMESTAMP", re.IGNORECASE)
_BOOLEAN_RE = re.compile(r"BOOLEAN", re.IGNORECASE)
_DECFLOAT_RE = re.compile(
    r"DECFLOAT(?:\s*\(\s*(16|34)\s*\))?",
    re.IGNORECASE,
)
_INT128_RE = re.compile(r"INT128", re.IGNORECASE)
# Firebird's zoned date-time declarations, as the grammar writes them: no
# precision argument anywhere (language reference §3.4.2, §3.4.3 and §3.12,
# "TIMESTAMP [{WITHOUT | WITH} TIME ZONE]" / "TIME [{WITHOUT | WITH} TIME
# ZONE]"). The optional precision group is matched so that a declaration naming
# one can be *refused by name* instead of parsed into a class whose renderer
# raises — the same decision FirebirdTypeSupportMixin._check_firebird_temporal_
# precision reaches from the other direction, and the same reason
# FirebirdSQL/firebird#4779 (CORE-4459) is not treated as a capability.
_TIMESTAMP_WITH_TIME_ZONE_RE = re.compile(
    r"TIMESTAMP(?:\s*\(\s*(\d+)\s*\))?\s+WITH\s+TIME\s+ZONE",
    re.IGNORECASE,
)
_TIME_WITH_TIME_ZONE_RE = re.compile(
    r"TIME(?:\s*\(\s*(\d+)\s*\))?\s+WITH\s+TIME\s+ZONE",
    re.IGNORECASE,
)
_TIME_WITHOUT_TIME_ZONE_RE = re.compile(
    r"TIME(?:\s*\(\s*(\d+)\s*\))?\s+WITHOUT\s+TIME\s+ZONE",
    re.IGNORECASE,
)

#: A precision on a bare ``TIME``/``TIMESTAMP``/``DATE``, matched for the same
#: reason: ``_TIME_RE`` / ``_TIMESTAMP_RE`` / ``_DATE_RE`` use ``fullmatch`` and
#: would otherwise simply not match, leaving ``TIMESTAMP(4)`` to fall through to
#: the qualified-identifier branch as ``CustomType(raw="TIMESTAMP(4)")`` — an
#: opaque name that renders itself straight back into the invalid DDL.
_TEMPORAL_PRECISION_RE = re.compile(
    r"(?:DATE|TIMESTAMP|TIME)\s*\(\s*\d+\s*\)", re.IGNORECASE
)


def _reject_temporal_precision(name: str) -> None:
    """Raise for a ``TIME``/``TIMESTAMP``/``DATE`` declaration naming a precision.

    Firebird's grammar has no precision production for these types and its storage
    is fixed at ten-thousandths of a second, so a declared precision is not a
    column that can be created — see
    ``FirebirdTypeSupportMixin._check_firebird_temporal_precision`` for the
    documentation and the upstream request. Refusing it here means the domain
    ``SET TYPE`` path, which has no dialect and so no formatter to delegate to,
    gives the same answer as ``format_data_type`` would.
    """
    raise ValueError(
        f"{name!r} is not a Firebird data type declaration: Firebird's TIME and "
        f"TIMESTAMP take no precision argument (language reference, chapter 3, "
        f"sections 3.4.2 and 3.4.3, and the section 3.12 Data Type Declaration "
        f"Syntax: 'TIME [{{WITHOUT | WITH}} TIME ZONE]' and 'TIMESTAMP "
        f"[{{WITHOUT | WITH}} TIME ZONE]' — identical in the 4.0 and 5.0 "
        f"references). Firebird stores fractional seconds to ten-thousandths of "
        f"a second whatever the declaration says. Requested upstream as "
        f"FirebirdSQL/firebird#4779 (CORE-4459)."
    )
_ACTION_WORDS = {
    "ADD",
    "ALTER",
    "CHECK",
    "COLLATE",
    "CONSTRAINT",
    "CREATE",
    "DEFAULT",
    "DROP",
    "NOT",
    "NULL",
    "SET",
    "TO",
    "WITHOUT",
}


def _normalize_firebird_data_type_name(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"data_type_name must be a string, got {type(value).__name__}")
    normalized = " ".join(value.strip().split())
    if not normalized or _DATA_TYPE_TEXT_RE.fullmatch(normalized) is None:
        raise ValueError("data_type_name must be a valid Firebird data type declaration")
    return normalized


def _parse_firebird_data_type_name(value: str) -> DataType:
    normalized = _normalize_firebird_data_type_name(value)
    upper = normalized.upper()
    match = _BINARY_VARCHAR_RE.fullmatch(upper)
    if match:
        return VarBinaryType(length=int(match.group(1)))
    match = _BINARY_CHAR_RE.fullmatch(upper)
    if match:
        return BinaryType(length=int(match.group(1)))
    match = _UTF8_VARCHAR_RE.fullmatch(upper)
    if match:
        return FirebirdVarCharType(length=int(match.group(1)))
    match = _UTF8_CHAR_RE.fullmatch(upper)
    if match:
        return FirebirdCharType(length=int(match.group(1)))
    if _BLOB_TEXT_RE.fullmatch(upper):
        return TextType()
    if _BLOB_BINARY_RE.fullmatch(upper):
        return BinaryType()
    match = _TIMESTAMP_WITH_TIME_ZONE_RE.fullmatch(upper)
    if match:
        if match.group(1):
            _reject_temporal_precision(normalized)
        return FirebirdTimeStampTzType()
    match = _TIME_WITH_TIME_ZONE_RE.fullmatch(upper)
    if match:
        if match.group(1):
            _reject_temporal_precision(normalized)
        return FirebirdTimeTzType()
    match = _TIME_WITHOUT_TIME_ZONE_RE.fullmatch(upper)
    if match:
        if match.group(1):
            _reject_temporal_precision(normalized)
        return FirebirdTimeWithoutTimeZoneType()
    match = _DECFLOAT_RE.fullmatch(upper)
    if match:
        # No argument means the documented default: "either 16 or 34; Default is
        # 34" (language reference §3.2.2.1, DECFLOAT). The same default the
        # FirebirdDecFloatType constructor now uses, so a bare DECFLOAT names one
        # column whichever way it is reached.
        precision = int(match.group(1)) if match.group(1) else 34
        return FirebirdDecFloatType(precision=precision)
    if upper.startswith("DECFLOAT"):
        raise ValueError("DECFLOAT precision must be 16 or 34")
    if _INT128_RE.fullmatch(upper):
        return FirebirdInt128Type()
    if _TEMPORAL_PRECISION_RE.fullmatch(upper):
        _reject_temporal_precision(normalized)
    if _TIMESTAMP_RE.fullmatch(upper):
        return TimestampType()
    if _TIME_RE.fullmatch(upper):
        return TimeType()
    if _DATE_RE.fullmatch(upper):
        return DateType()
    if _BOOLEAN_RE.fullmatch(upper):
        return BooleanType()
    if _DOUBLE_RE.fullmatch(upper):
        return DoubleType()
    if _REAL_RE.fullmatch(upper):
        return FloatType()
    match = _FLOAT_RE.fullmatch(upper)
    if match:
        return FloatType(precision=int(match.group(1)) if match.group(1) else None)
    match = _DECIMAL_RE.fullmatch(upper)
    if match:
        return DecimalType(
            precision=int(match.group(1)) if match.group(1) else None,
            scale=int(match.group(2)) if match.group(2) else None,
        )
    match = _VARCHAR_RE.fullmatch(upper)
    if match:
        return VarCharType(length=int(match.group(1)) if match.group(1) else None)
    match = _CHAR_RE.fullmatch(upper)
    if match:
        return CharType(length=int(match.group(1)) if match.group(1) else None)
    if _INTEGER_RE.fullmatch(upper):
        if upper == "BIGINT":
            return BigIntType()
        if upper == "SMALLINT":
            return SmallIntType()
        return IntegerType()
    if _QUALIFIED_IDENTIFIER_RE.fullmatch(normalized):
        if normalized.upper() in _ACTION_WORDS:
            raise ValueError("data_type_name contains an unsupported action word")
        return CustomType(raw=normalized)
    raise ValueError("data_type_name contains unsupported Firebird type syntax")


register_expression_class(FirebirdCharType)
register_expression_class(FirebirdVarCharType)
register_expression_class(FirebirdTimeStampTzType)
register_expression_class(FirebirdTimeTzType)
register_expression_class(FirebirdTimeWithoutTimeZoneType)
register_expression_class(FirebirdDecFloatType)
register_expression_class(FirebirdInt128Type)


__all__ = [
    "FirebirdCharType",
    "FirebirdVarCharType",
    "FirebirdTimeStampTzType",
    "FirebirdTimeTzType",
    "FirebirdTimeWithoutTimeZoneType",
    "FirebirdDecFloatType",
    "FirebirdInt128Type",
]
