# src/rhosocial/activerecord/backend/impl/firebird/introspection/type_parser.py
"""Firebird's type-spelling parser (read direction, introspection-only).

Core's ``DataType.parse_data_type_str`` has been downgraded to returning a bare
``CustomType``, and the dialect protocol no longer exposes ``parse_type``.
Parsing a server-reported Firebird type spelling back into a ``DataType`` is
therefore a backend-local, introspection-only concern: it lives here, used only
when reading a column's declared type off the catalog (and by the public
``query_nodes.cast`` helper, which takes the same raw spelling).
"""
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.types import (
    BigIntType,
    BlobType,
    BooleanType,
    CharType,
    CustomType,
    DataType,
    DateType,
    DateTimeType,
    DecimalType,
    DoubleType,
    FloatType,
    IntegerType,
    SmallIntType,
    TextType,
    TimeType,
    TinyIntType,
    VarCharType,
)

from .._scan import (
    contains_word,
    find_digit_runs,
    find_parenthesised_number,
    is_word_boundary,
    match_word_sequence,
    read_head_with_precision,
    starts_with_any_word,
    starts_with_phrase,
    starts_with_word,
)
from ..expression.types import (
    FirebirdDecFloatType,
    FirebirdInt128Type,
    FirebirdTimeStampTzType,
    FirebirdTimeTzType,
    FirebirdTimeWithoutTimeZoneType,
)


def _match_decfloat(upper: str) -> tuple[bool, str | None]:
    """``^DECFLOAT(?:\\s*\\(\\s*(\\d+)\\s*\\))?(?![A-Za-z0-9_$])``.

    Returns ``(matched, precision)``. A precision of ``None`` means the bare
    word matched. The optional group is abandoned when its own lookahead fails,
    which is where the pattern's backtracking would leave the scan.
    """
    head = read_head_with_precision(upper, "DECFLOAT")
    if head is None:
        return False, None
    precision, word_end, end = head
    if precision is not None and is_word_boundary(upper, end, excludes="$"):
        return True, precision
    if is_word_boundary(upper, word_end, excludes="$"):
        return True, None
    return False, None


class FirebirdTypeParser:
    """Parse a raw Firebird type spelling into a ``DataType`` bound to a dialect.

    One concept in, one class out: every member of a concept's ``SPELLINGS``
    maps to that concept's class, so ``character varying`` is a ``VarCharType``
    and never a ``CharType``. Every returned type is bound to the dialect so
    it can be rendered straight back into a column definition.
    """

    def __init__(self, dialect):
        self.dialect = dialect

    #: Spellings of one concept, written upper-case because *upper* is what
    #: every scan below sees. Each tuple is matched as a leading word with a
    #: word boundary after it; a multi-word spelling always begins with its
    #: first word, so the one-word member covers it for matching purposes.
    _TINYINT_TYPES = ("TINYINT", "INT1")
    # ``UNSIGNED`` as a whole word anywhere in a type string. Every branch
    # below matches on the word *in front of* the attribute, so this is what
    # stops ``INTEGER UNSIGNED`` from parsing to a signed ``IntegerType``.
    _UNSIGNED_ATTRIBUTE = "UNSIGNED"
    _INTEGER_TYPES = ("SMALLINT", "INT2", "INTEGER", "INT", "BIGINT", "INT8")
    _FLOAT_TYPES = ("FLOAT", "DOUBLE", "REAL")
    _DECIMAL_TYPES = ("DECIMAL", "NUMERIC", "DEC")
    _STRING_TYPES = ("VARCHAR", "CHARACTER", "CHAR")
    _BLOB_TEXT_TYPES = ("BLOB", "SUB_TYPE", "TEXT")
    _BLOB_TYPES = ("BLOB", "BYTEA")
    _TEXT_TYPES = ("TEXT", "CLOB")
    _DATE_TYPES = ("DATE", "TIMESTAMP", "TIME")
    _BOOLEAN_TYPES = ("BOOLEAN", "BOOL")

    # Firebird 4.0's zoned date-time types. These must be matched *before*
    # ``_DATE_TYPES``, whose scan stops at the first word and so would read
    # a zoned column back as the unzoned concept -- which the schema differ
    # compares with ``!=``, making the zone invisible to it. The words are the
    # ones Firebird writes: ``TIME [{WITHOUT | WITH} TIME ZONE]`` /
    # ``TIMESTAMP [{WITHOUT | WITH} TIME ZONE]``.
    #
    # The optional precision group is matched **so it can be refused**, not so
    # it can be read: no Firebird ``TIME``/``TIMESTAMP`` declaration carries
    # one, so ``TIMESTAMP(4) WITH TIME ZONE`` is not a Firebird type name and
    # turning it into a class whose renderer then raises would leave the
    # parser accepting a declaration it cannot render back.
    _ZONED_TIME_TYPES = (
        ("TIMESTAMP", ("WITH", "TIME", "ZONE"), FirebirdTimeStampTzType),
        ("TIME", ("WITH", "TIME", "ZONE"), FirebirdTimeTzType),
        ("TIME", ("WITHOUT", "TIME", "ZONE"), FirebirdTimeWithoutTimeZoneType),
    )

    #: A precision on a bare ``DATE``/``TIME``/``TIMESTAMP``, recognised in
    #: order to be refused. ``_DATE_TYPES`` stops after the first word, so
    #: without this the tail -- ``(4)`` -- was simply ignored and
    #: ``TIMESTAMP(4)`` parsed as a plain ``TIMESTAMP``, a different column.
    _TEMPORAL_TYPES = ("DATE", "TIMESTAMP", "TIME")

    # Firebird 4.0's DECFLOAT and INT128 -- codes the introspector reads out of
    # RDB$FIELDS.RDB$FIELD_TYPE that the scans above do not claim. Reading
    # a DECFLOAT as CustomType used to lose its precision, a silent identity
    # loss because FirebirdDecFloatType carries precision in PARAMETERS. The
    # precision is read out of the name, never defaulted except for the bare
    # word, whose documented default is 34 (language reference 3.2.2.1).
    _DECFLOAT_DEFAULT_PRECISION = 34

    def _reject_temporal_precision(self, raw: str, declared) -> None:
        """Raise if a TIME/TIMESTAMP/DATE declaration names a precision."""
        if declared is None:
            return
        raise ValueError(
            f"{raw!r} is not a Firebird data type declaration: Firebird's TIME "
            f"and TIMESTAMP take no precision argument (language reference, "
            f"chapter 3, sections 3.4.2 and 3.4.3, and the section 3.12 Data "
            f"Type Declaration Syntax: 'TIME [{{WITHOUT | WITH}} TIME ZONE]' and "
            f"'TIMESTAMP [{{WITHOUT | WITH}} TIME ZONE]' — identical in the 4.0 "
            f"and 5.0 references). Firebird stores fractional seconds to "
            f"ten-thousandths of a second whatever the declaration says, so a "
            f"lower granularity belongs in the value. Requested upstream as "
            f"FirebirdSQL/firebird#4779 (CORE-4459)."
        )

    def _refuse_unsigned_type_string(self, raw: str) -> None:
        """Refuse a type string carrying an ``UNSIGNED`` attribute.

        Firebird has no unsigned numeric type, so no server can have written
        such a string; the branch guards the caller-supplied path and refuses
        to return a signed type object for a declaration that says otherwise.
        """
        raise UnsupportedFeatureError(
            self.dialect.name,
            f"an UNSIGNED attribute in a type string ({raw!r}) "
            f"(Firebird does not support an unsigned numeric data type: language "
            f"reference chapter 3, section 3.1 says 'Firebird does not support "
            f"an unsigned integer data type', and section 3.12's Scalar Data "
            f"Types Syntax gives no numeric type an attribute after it. Reading "
            f"the attribute off and returning a signed type would compare equal "
            f"to the signed column, which is the silent loss this refuses. Read "
            f"from the documentation: no Firebird client library is installed "
            f"here, so no statement could be sent to a server.)",
            suggestion=(
                "Declare the column signed and state the range with a CHECK "
                "constraint -- Firebird's own col_constraint grammar admits "
                "'CHECK ( check_condition )'."
            ),
        )

    def parse(self, raw: str) -> DataType:
        """Parse *raw* into a dialect-bound ``DataType``."""
        stripped = raw.strip()
        upper = stripped.upper()

        if contains_word(stripped, self._UNSIGNED_ATTRIBUTE):
            self._refuse_unsigned_type_string(stripped)

        if starts_with_any_word(upper, *self._TINYINT_TYPES):
            return TinyIntType(dialect=self.dialect)

        # INT128 before the integer family: ``INT128`` is a different column
        # from ``INTEGER`` by 96 bits of range, not a spelling difference.
        if starts_with_word(upper, "INT128", lookahead_excludes="$"):
            if not self.dialect._fb4_available():
                return CustomType(dialect=self.dialect, raw=stripped)
            return FirebirdInt128Type(dialect=self.dialect)

        if starts_with_any_word(upper, *self._INTEGER_TYPES):
            if upper.startswith("BIGINT") or upper.startswith("INT8"):
                return BigIntType(dialect=self.dialect)
            if upper.startswith("SMALLINT") or upper.startswith("INT2"):
                return SmallIntType(dialect=self.dialect)
            return IntegerType(dialect=self.dialect)

        # DECFLOAT before the decimal family: DECFLOAT(16) must never be read
        # as DecimalType(precision=16), a different column with a scale rule.
        decfloat, declared = _match_decfloat(upper)
        if decfloat:
            if not self.dialect._fb4_available():
                return CustomType(dialect=self.dialect, raw=stripped)
            return FirebirdDecFloatType(
                dialect=self.dialect,
                precision=int(declared) if declared else self._DECFLOAT_DEFAULT_PRECISION,
            )

        if starts_with_any_word(upper, *self._FLOAT_TYPES):
            if upper.startswith("DOUBLE"):
                return DoubleType(dialect=self.dialect)
            return FloatType(dialect=self.dialect)

        if starts_with_any_word(upper, *self._DECIMAL_TYPES):
            nums = find_digit_runs(stripped)
            if len(nums) >= 2:
                return DecimalType(dialect=self.dialect, precision=int(nums[0]), scale=int(nums[1]))
            if len(nums) == 1:
                return DecimalType(dialect=self.dialect, precision=int(nums[0]))
            return DecimalType(dialect=self.dialect)

        if starts_with_any_word(upper, *self._STRING_TYPES):
            found = find_parenthesised_number(stripped)
            length = int(found) if found is not None else None
            char_length = self.dialect._FB_CHAR_DEFAULT_LENGTH
            varchar_length = self.dialect._FB_RENDERED_VARCHAR_LENGTH
            # CHARACTER VARYING is SQL's long form of VARCHAR -- variable length.
            # Testing it before CHARACTER keeps the varying form out of the
            # fixed-length branch on "CHARACTER".
            if upper.startswith("CHARACTER VARYING") or upper.startswith("CHAR VARYING"):
                return VarCharType(dialect=self.dialect, length=length or varchar_length,
                                   spelling="character varying")
            if upper.startswith("VARCHAR"):
                return VarCharType(dialect=self.dialect, length=length or varchar_length)
            if upper.startswith("CHARACTER"):
                return CharType(dialect=self.dialect, length=length or char_length, spelling="character")
            if upper.startswith("CHAR"):
                return CharType(dialect=self.dialect, length=length or char_length)
            return TextType(dialect=self.dialect)

        if starts_with_phrase(upper, self._BLOB_TEXT_TYPES):
            return TextType(dialect=self.dialect)

        if starts_with_any_word(upper, *self._BLOB_TYPES):
            return BlobType(dialect=self.dialect)

        if starts_with_any_word(upper, *self._TEXT_TYPES):
            return TextType(dialect=self.dialect)

        # Zoned date-times, matched before the DATE/TIMESTAMP/TIME family below.
        for head, clause, zoned_class in self._ZONED_TIME_TYPES:
            found = read_head_with_precision(upper, head)
            if found is None:
                continue
            precision, _word_end, end = found
            if match_word_sequence(upper, end, clause, leading_space=True) is None:
                continue
            self._reject_temporal_precision(stripped, precision)
            if not self.dialect._fb4_available():
                return CustomType(dialect=self.dialect, raw=stripped)
            return zoned_class(dialect=self.dialect)

        # Same refusal for the bare spellings, checked before _DATE_TYPES so
        # the ``(4)`` tail is seen rather than discarded.
        declared = None
        for head in self._TEMPORAL_TYPES:
            found = read_head_with_precision(upper, head)
            if found is not None and found[0] is not None:
                declared = found[0]
                break
        self._reject_temporal_precision(stripped, declared)

        if starts_with_any_word(upper, *self._DATE_TYPES):
            # TIMESTAMP before TIME: "TIMESTAMP".startswith("TIME") is True.
            if upper.startswith("TIMESTAMP"):
                return DateTimeType(dialect=self.dialect)
            if upper.startswith("TIME"):
                return TimeType(dialect=self.dialect)
            if upper.startswith("DATE"):
                if upper.strip() == "DATE":
                    return DateType(dialect=self.dialect)
                return DateTimeType(dialect=self.dialect)
            return DateTimeType(dialect=self.dialect)

        if starts_with_any_word(upper, *self._BOOLEAN_TYPES):
            return BooleanType(dialect=self.dialect)

        return CustomType(dialect=self.dialect, raw=stripped)


__all__ = ["FirebirdTypeParser"]
