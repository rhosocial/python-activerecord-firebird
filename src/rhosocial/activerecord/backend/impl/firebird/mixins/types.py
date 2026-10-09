# src/rhosocial/activerecord/backend/impl/firebird/mixins/types.py
"""Firebird DataType formatting mixin.

Covers the Firebird 4.0+ data types ``TIMESTAMP WITH TIME ZONE``, ``TIME
WITH TIME ZONE``, ``DECFLOAT(16|34)`` and ``INT128`` with a version gate of
 ``(4, 0, 0)`` — requesting any of them on an older dialect raises
``UnsupportedFeatureError``.

Zoned *core* concepts
---------------------
``timetz`` and ``timestamptz`` are the one pair of core concepts this dialect
does **not** render, and the reason is that it cannot: Firebird's ``TIME`` and
``TIMESTAMP`` are its **unzoned** types (§3.4 — *"TIME and TIMESTAMP are
synonymous to their respective WITHOUT TIME ZONE data types"*), so the only words
a formatter could write for a zoned concept would declare a column that discards
the zone offset. Both are named in :meth:`suggested_data_types` with the unzoned
concept of the same family as their substitute, and Firebird's own zoned columns
stay reachable under ``firebird_timetz`` / ``firebird_timestamptz``. See the
"timetz / timestamptz: deliberately absent" comment above
``format_data_type_timestamp``.

Spellings
---------
A concept that SQL spells several ways is one class with a ``spelling``
argument, so every formatter that can be handed one declares, through
:meth:`~...dialect.mixins.data_type.DataTypeMixin._check_spelling`, which of
those words Firebird's own grammar uses. The rule this dialect follows:

* a word **Firebird writes** is accepted and rendered as Firebird's canonical
  word for the concept — ``INT``, ``CHARACTER``, ``CHARACTER VARYING`` and
  ``NUMERIC``/``DEC`` are all in Firebird's own grammar, so a caller who wrote
  one of them gets the column they asked for, spelled the way Firebird spells
  it;
* a word **Firebird does not have** is refused, with the message naming it and
  listing what is accepted. ``INT2``/``INT8``/``BYTEA``/``CLOB``/``BOOL`` are
  other engines' or standard SQL's words for concepts Firebird already spells
  differently; quietly rendering one of them as its Firebird equivalent would
  turn a caller's explicit request into a different declaration without saying
  so;
* the concept's **default spelling always renders**. A backend may normalise it
  to its own word but never refuse it — otherwise the type would be
  unconstructible here and the refusal would say nothing about how to proceed.

Identity fields
---------------
A field in a type's :attr:`PARAMETERS` is part of that type's *identity*: it
goes into ``__eq__`` and ``__hash__``, so two declarations differing only in it
are two different columns. Every such field is either **honoured** — flipping it
changes the rendered SQL — or **refused** — flipping it raises, naming the
field and why. Silently dropping one is the failure this dialect refuses to
commit, because it creates a column that does not match the declaration and
reports success.

Three Firebird facts settle the fields that could not be honoured:

``unsigned``
    The language reference says it plainly, under Integer Data Types (chapter
    3, §3.1): *"Firebird does not support an unsigned integer data type."* It
    says so in the 2.5 reference too, and no Firebird version's ``SMALLINT`` /
    ``INTEGER`` / ``BIGINT`` / ``INT128`` declaration carries an ``UNSIGNED``
    modifier. So the field cannot be honoured and is refused by name:
    :meth:`_check_firebird_signed`.

    That is the whole of ``unsigned`` on Firebird, for **every** numeric
    concept and not only the integer ones. ``FLOAT [(bin_prec)]``, ``REAL``,
    ``DOUBLE PRECISION``, ``DECFLOAT [(dec_prec)]`` and
    ``{DECIMAL | DEC | NUMERIC} [(precision [, scale])]`` are the §3.12
    *Scalar Data Types Syntax* productions for the exact and approximate
    numerics, and none of them carries an ``UNSIGNED`` modifier or any other
    attribute — the very same production writes ``[CHARACTER SET charset]`` for
    the character types because Firebird *does* have a type attribute and states
    where it goes. There is nothing to honour the field with, so all seven
    numeric formatters — the four core ``decimal``/``float``/``real``/``double``
    keys and Firebird's own ``firebird_decimal``/``firebird_float``/
    ``firebird_double`` — route through :meth:`_check_firebird_signed` rather
    than each inventing its own answer.

    **This backend's answer is read from Firebird's documentation, not
    measured.** No Firebird client library is installed in this environment
    (``firebird_driver``, ``fdb`` and ``firebirdsql`` are all absent), so no
    statement could be sent to a server; every statement above is a quotation
    from, or an absence in, the Firebird language reference, and is cited as
    such rather than dressed up as a measurement.

``precision`` on ``FLOAT``
    Honoured, but only where it means one thing. Firebird 4.0 release notes,
    tracker CORE-6109: *"FLOAT(p) definition is changed to represent precision in
    binary digits ... rather than in decimal digits as before."* The same string
    therefore names different columns before and after 4.0, so a precision is
    written on 4.0+ and refused below it: :meth:`_validate_firebird_float`. Both
    ``format_data_type_float`` (core ``FloatType``) and
    ``format_data_type_firebird_float`` route through that one helper, because
    they are the same Firebird type under two dispatch keys.

``precision`` on ``TIME`` / ``TIMESTAMP``, zoned or not
    There is nothing to honour it with. The declaration grammar for these types
    has no precision production at all — ``TIME [{WITHOUT | WITH} TIME ZONE]``
    (§3.4.2) and ``TIMESTAMP [{WITHOUT | WITH} TIME ZONE]`` (§3.4.3), and the same
    two productions in the §3.12 "Data Type Declaration Syntax" of the 4.0 and 5.0
    references alike, where ``FLOAT [(bin_prec)]`` and ``DECFLOAT [(dec_prec)]``
    in the very same production *do* have one — while the storage is fixed:
    *"If fractions of seconds are stored in date and time data types, Firebird
    stores them to ten-thousandths of a second"* (§3.4, *Fractions of Seconds*),
    so a ``TIME`` column keeps four fractional digits whatever the declaration
    said. Coarser granularity is a *value* concern (how the literal or the
    function call is written), not a declared one. So the field is refused by
    name: :meth:`_check_firebird_temporal_precision`, and :meth:`parse_type`
    refuses the same string rather than reading a precision out of a production
    that has no place for one. FirebirdSQL/firebird#4779 (CORE-4459) asks for
    ``TIME(p)``/``TIMESTAMP(p)`` and is still open; an unmerged feature request is
    not a documented capability.
"""

from __future__ import annotations

import re
from typing import Dict, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.dialect.mixins import DDLTypeMixin
from rhosocial.activerecord.backend.dialect.protocols import DDLTypeSupport
from rhosocial.activerecord.backend.expression.types import (
    BigIntType,
    BinaryType,
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
    RealType,
    SmallIntType,
    TextType,
    # ``TimeTzType`` / ``TimestampTzType`` are deliberately **not** imported:
    # this dialect renders neither, and the substitutes it names for them are the
    # unzoned ``TimeType`` / ``TimestampType`` just above. See the "timetz /
    # timestamptz: deliberately absent" comment above ``format_data_type_timestamp``.
    TimeType,
    TimestampType,
    TinyIntType,
    UUIDType,
    VarBinaryType,
    VarCharType,
)

from .version_boundaries import _norm_version
from ..expression.types import (
    FirebirdCharType,
    FirebirdDecimalType,
    FirebirdDecFloatType,
    FirebirdDoubleType,
    FirebirdFloatType,
    FirebirdInt128Type,
    FirebirdBlobSubType,
    FirebirdTimeStampTzType,
    FirebirdTimeWithoutTimeZoneType,
    FirebirdTimeTzType,
    FirebirdVarCharType,
)


class FirebirdTypeSupportMixin(DDLTypeMixin, DDLTypeSupport):

    # --- Precision / scale validation helpers ---

    def _validate_numeric(self, precision, scale) -> None:
        """Validate Firebird NUMERIC/DECIMAL precision and scale.

        Firebird: precision 1-18, scale 0-18.
        """
        if precision is not None and not 1 <= precision <= 18:
            raise ValueError(
                f"Firebird DECIMAL precision must be between 1 and 18, "
                f"got {precision}."
            )
        if scale is not None and not 0 <= scale <= 18:
            raise ValueError(
                f"Firebird DECIMAL scale must be between 0 and 18, "
                f"got {scale}."
            )
        if (precision is not None and scale is not None
                and scale > precision):
            raise ValueError(
                f"Firebird DECIMAL scale ({scale}) cannot exceed "
                f"precision ({precision})."
            )

    def _check_firebird_signed(self, data_type, declaration: str = "integer") -> None:
        """Refuse ``unsigned=True`` — Firebird has no unsigned numeric type.

        ``unsigned`` is part of the numeric family's identity, so a caller
        asking for it is asking for a *different column*: half the range of the
        signed one, and values above ``2**31 - 1`` that a signed ``INTEGER``
        column cannot hold at all. A dialect has two legal answers, honour the
        field by writing the modifier, or refuse it by naming it; there is no
        third. Writing ``INTEGER`` for ``IntegerType(unsigned=True)`` — or
        ``DECIMAL(10, 2)`` for ``DecimalType(10, 2, unsigned=True)`` — would
        take the second option's message away while still producing the first
        option's silent wrong column.

        There is nothing to honour it with, for **either** half of the family,
        and this is the one gate for all of it:

        * **The integers**, from the reference's own sentence under Integer Data
          Types (chapter 3, §3.1): *"Firebird does not support an unsigned
          integer data type"* — the same sentence appears in the 2.5 reference,
          so this is not a recent omission. None of ``SMALLINT`` /
          ``INTEGER`` / ``BIGINT`` / ``INT128`` carries an ``UNSIGNED``
          modifier.
        * **The exact and approximate numerics**, from §3.12's *Scalar Data Types
          Syntax*, which is the production that states the whole grammar:
          ``REAL | FLOAT [(bin_prec)] | DOUBLE PRECISION``,
          ``DECFLOAT [(dec_prec)]`` and
          ``{DECIMAL | DEC | NUMERIC} [(precision [, scale])]``. There is no
          attribute after any of them, and that is a statement about the
          production rather than an inference from silence — the *same*
          production writes ``[CHARACTER SET charset]`` after
          ``VARCHAR (length)``, so Firebird does have a type attribute and says
          exactly where it goes; signedness is not one of them.

        **Documentation-based, deliberately.** No Firebird client library is
        installed here (``firebird_driver``, ``fdb`` and ``firebirdsql`` all
        fail to import), so no statement could be sent to a server and none of
        the above is a measurement. Every other backend in this family has its
        refusal backed by a live server; this one is backed by the reference,
        and says so rather than implying otherwise.

        Called from **every** numeric formatter — the four core
        ``decimal``/``float``/``real``/``double`` dispatch keys and Firebird's own
        ``firebird_decimal``/``firebird_float``/``firebird_double``, which are the
        same three storages under three more keys — because a per-formatter
        check is a per-formatter bug waiting to happen. It also covers
        :class:`~...expression.types.FirebirdBlobSubType`, which narrows
        ``PARAMETERS`` to ``()`` precisely because ``unsigned`` is not a field of
        its concept: narrowing removes it from equality, and this is what keeps
        the inherited constructor from quietly ignoring it.

        It is called **first** in every one of those formatters, ahead of
        ``_check_spelling``, the 4.0 version gate and every precision and scale
        ``ValueError``. That ordering is the point: a declaration this grammar
        cannot express at all is a stronger and less recoverable statement than
        a misspelled word or an out-of-range number, so it is the one the caller
        is told first — and every one of those existing checks still fires
        unchanged for a signed declaration.

        ``declaration`` is the kind of type being declared, so the message can
        say which family the caller reached for; it defaults to ``"integer"``
        because that is what every caller but the three float/decimal paths
        passes, and this is a pre-existing helper whose callers must not all have
        to change to accommodate a new kind.
        """
        if getattr(data_type, "unsigned", False):
            raise UnsupportedFeatureError(
                self.name,
                f"the UNSIGNED modifier on an {declaration} column "
                f"(Firebird does not support an unsigned numeric data type: "
                f"language reference chapter 3 section 3.1 says 'Firebird does "
                f"not support an unsigned integer data type', and section "
                f"3.12's Scalar Data Types Syntax writes REAL | FLOAT "
                f"[(bin_prec)] | DOUBLE PRECISION, DECFLOAT [(dec_prec)] and "
                f"{{DECIMAL | DEC | NUMERIC}} [(precision [, scale])] with no "
                f"attribute of any kind after them -- the same production does "
                f"write [CHARACTER SET charset] after VARCHAR (length), so the "
                f"slot is documented where Firebird has one. Read from the "
                f"documentation: no Firebird client library is installed here, "
                f"so no statement could be sent to a server.)",
                suggestion=(
                    "Declare the column signed and state the range with a CHECK "
                    "constraint -- Firebird's own col_constraint grammar admits "
                    "'CHECK ( check_condition )' -- or, for an integer, declare "
                    "the next wider signed type that holds the column's range."
                ),
            )

    def _validate_firebird_float(self, precision) -> None:
        """Validate and gate Firebird ``FLOAT(bin_prec)``.

        ``precision=None`` returns: bare ``FLOAT`` is 32-bit single precision in
        every Firebird version this backend targets, so it needs no gate.

        A precision needs two checks.

        **The version.**  Firebird 4.0 release notes, tracker CORE-6109: *``FLOAT(p)
        definition is changed to represent precision in binary digits (as defined
        by the SQL specification) rather than in decimal digits as before.*  The
        3.0 reference's declaration syntax is ``SMALLINT | INT[EGER] | BIGINT |
        FLOAT | DOUBLE PRECISION | BOOLEAN | DATE | TIME | TIMESTAMP | ...``
        (§3.11.1, *Scalar Data Types Syntax*) — ``FLOAT`` with no argument at all,
        where the 4.0 one is ``REAL | FLOAT [(bin_prec)] | DOUBLE PRECISION``
        (§3.12).  So ``FLOAT(10)`` named a ten-decimal-digit float on 3.0 and
        names a ten-*bit* float on 4.0 — different columns from the same text.
        Writing one without knowing the server version would declare a column whose
        meaning is a coin toss, so below 4.0 the field is refused by name. (The
        4.0 reference's own compatibility note confirms the 3.0 semantics:
        *"Firebird 3.0 and earlier supported FLOAT(dec_prec) where dec_prec was
        the approximate precision in decimal digits, with 0 <= dec_prec <= 7
        mapped to 32-bit single precision and P > 7 mapped to 64-bit double
        precision. This syntax was never documented."*)

        **The range.**  ``bin_prec`` is 1-24 for 32-bit single precision and
        25-53 for 64-bit double precision, which the reference calls a synonym of
        ``DOUBLE PRECISION`` (§3.2.1.1, Table 3.2, and §3.1 Table 3.1).  Both
        halves are real declarations, so both are accepted; anything outside 1-53
        is not a column Firebird can be asked for and writing it would put a
        declaration the server rejects into the statement.

        Both the generic ``format_data_type_float`` and
        ``format_data_type_firebird_float`` come through here, because they are
        the same Firebird type under two dispatch keys and must not disagree.
        """
        if precision is None:
            return
        self._check_fb4_type("FLOAT(bin_prec)")
        if not 1 <= precision <= 53:
            raise ValueError(
                f"Firebird FLOAT binary precision must be between 1 and 53 "
                f"(1-24 is 32-bit single precision, 25-53 is 64-bit double "
                f"precision), got {precision}."
            )

    #: The date-time declarations this dialect refuses a ``precision`` on, in the
    #: form the refusal message names. Every one of them is a Firebird word for a
    #: column whose declaration grammar carries no precision production.
    #: One check for the whole family, called from every date-time formatter that
    #: renders one of them — a per-formatter check is a per-formatter bug waiting
    #: to happen.
    def _check_firebird_temporal_precision(self, data_type, declaration: str) -> None:
        """Refuse ``precision=`` on any Firebird ``TIME``/``TIMESTAMP`` column.

        ``precision=None`` returns — that is a plain declaration and nothing
        about it is in question. A declared precision has nowhere to go, so it is
        refused **by name** rather than dropped.

        **There is no grammar for it.**  The Firebird 4.0 and 5.0 references
        give the same declaration syntax for these types in two places, and
        neither has a precision argument:

        * §3.4, *Data Types for Dates and Times* — ``TIME [{WITHOUT | WITH} TIME
          ZONE]`` (§3.4.2) and ``TIMESTAMP [{WITHOUT | WITH} TIME ZONE]``
          (§3.4.3), each followed by *"For a bare TIME/TIMESTAMP, WITHOUT TIME
          ZONE is assumed."*
        * §3.12, *Data Type Declaration Syntax* — ``TIME [{WITHOUT | WITH} TIME
          ZONE]`` and ``TIMESTAMP [{WITHOUT | WITH} TIME ZONE]`` in the
          ``scalar_datatype`` production.

        Compare the two types that *do* take an argument in the same production:
        ``FLOAT [(bin_prec)]`` and ``DECFLOAT [(dec_prec)]``. The absence is the
        documentation's, not an omission in this rendering.

        **And there is nothing it would mean if it were there.**  §3.4, *Fractions
        of Seconds*: *"If fractions of seconds are stored in date and time data
        types, Firebird stores them to ten-thousandths of a second. If a lower
        granularity is preferred, the fraction can be specified explicitly as
        thousandths, hundredths or tenths of a second, or second, in Dialect 3
        databases of ODS 11 or higher."*  That last sentence is about how a
        *value* is written — ``CURRENT_TIMESTAMP(3)`` and the like — not about
        what a column may declare. The column stores four fractional digits
        whatever the declaration said, so honouring the field would write a
        number into DDL and a different column into the database.

        **The request exists and is unmerged.**  FirebirdSQL/firebird#4779
        (CORE-4459), *"Add precision specification to TIME and TIMESTAMP in
        datatype and cast"*, is open: ``state: "open"``, no closing date. Until
        it merges the field stays refused, and if it ever does merge this method
        is the single place that has to change.
        """
        if data_type.precision is None:
            return
        raise UnsupportedFeatureError(
            self.name,
            f"a fractional-seconds precision on {declaration}",
            f"Firebird's {declaration} declaration takes no precision argument "
            f"(language reference, chapter 3 Data Types and Subtypes: "
            f"'TIME [{{WITHOUT | WITH}} TIME ZONE]' in section 3.4.2 and "
            f"'TIMESTAMP [{{WITHOUT | WITH}} TIME ZONE]' in section 3.4.3, and "
            f"the same two productions in the section 3.12 Data Type Declaration "
            f"Syntax — identical in the 4.0 and 5.0 references). The field is "
            f"refused rather than dropped because a declared precision would not "
            f"reach the database: Firebird stores fractional seconds to "
            f"ten-thousandths of a second whatever the declaration says, so a "
            f"lower granularity belongs in the value, not in the type. Requested "
            f"upstream as FirebirdSQL/firebird#4779 (CORE-4459).",
        )

    # --- Core types (pure names) rendered to real Firebird SQL ---
    #
    # ``INT`` is not a type of its own: it is the second spelling of
    # ``IntegerType``'s concept, so there is no ``format_data_type_int`` and no
    # ``supports_data_type_int``. One class, one dispatch key, one rendering.

    def format_data_type_integer(self, data_type: IntegerType) -> Tuple[str, tuple]:
        """``INTEGER`` and ``INT`` are both words Firebird's grammar uses for
        this 32-bit integer, and Firebird's own word is ``INTEGER``, so both
        render ``INTEGER``.

        ``unsigned`` is refused rather than rendered, and refused **before** the
        spelling check — see :meth:`_check_firebird_signed`.
        """
        self._check_firebird_signed(data_type)
        self._check_spelling(data_type, IntegerType)
        return "INTEGER", ()

    def format_data_type_bigint(self, data_type: BigIntType) -> Tuple[str, tuple]:
        """``BIGINT`` only.

        ``INT8`` is how MySQL and PostgreSQL name this concept; Firebird calls it
        ``BIGINT``, so asking for the ``INT8`` spelling is refused rather than
        silently answered with a ``BIGINT`` — the two words are the same storage,
        but only one of them is a word Firebird writes.

        ``unsigned`` is refused rather than rendered, and refused **before** the
        spelling check — see :meth:`_check_firebird_signed`.
        """
        self._check_firebird_signed(data_type)
        self._check_spelling(data_type, ("bigint",))
        return "BIGINT", ()

    def format_data_type_smallint(self, data_type: SmallIntType) -> Tuple[str, tuple]:
        """``SMALLINT`` only.

        ``INT2`` is the MySQL/PostgreSQL spelling and is not Firebird's; see
        :meth:`format_data_type_bigint`. ``unsigned`` is refused rather than
        rendered, before the spelling check — see
        :meth:`_check_firebird_signed`.
        """
        self._check_firebird_signed(data_type)
        self._check_spelling(data_type, ("smallint",))
        return "SMALLINT", ()

    def format_data_type_tinyint(self, data_type: TinyIntType) -> Tuple[str, tuple]:
        """Firebird has no 1-byte integer, so the concept is *widened* to the
        next size that exists and the column is a ``SMALLINT``. Both spellings
        are accepted because the caller asked for one concept — refusing either
        would leave ``TinyIntType`` unusable here without telling them anything
        the widened column does not already say.

        ``unsigned`` is refused rather than rendered, before the spelling check —
        see :meth:`_check_firebird_signed`.
        """
        self._check_firebird_signed(data_type)
        self._check_spelling(data_type, TinyIntType)
        return "SMALLINT", ()

    def format_data_type_float(self, data_type: FloatType) -> Tuple[str, tuple]:
        """``FLOAT`` or ``FLOAT(bin_prec)`` — **the same validation as
        :meth:`format_data_type_firebird_float`**, deliberately.

        Core's ``FloatType`` and this backend's
        :class:`~...expression.types.FirebirdFloatType` both end up writing
        ``FLOAT[(bin_prec)]``, because Firebird has exactly one ``FLOAT`` and it
        is a precision-bearing approximate numeric (§3.2.1.1: ``bin_prec`` is
        *"precision in binary digits, default is 24; 1 - 24: 32-bit single
        precision; 25 - 53: 64-bit double precision"*). Two renderers for one
        Firebird type is the same arrangement as ``decimal`` /
        ``firebird_decimal`` and ``char`` / ``firebird_char`` in this file: the
        generic concept keeps its pure dispatch key, the Firebird-named concept
        has its own, and both name the same storage.

        Which is why they cannot disagree. The earlier state of this method took
        the argument unconditionally and range-checked it to 1..24, and both
        halves of that were wrong against the reference:

        * **the range.**  25..53 is not out of bounds, it is the documented
          *double precision* half: 25-53 is a synonym for ``DOUBLE PRECISION``.
          Rejecting it refused a column Firebird declares, while
          :meth:`format_data_type_firebird_float` accepted it.
        * **the gate.**  Firebird 4.0 release notes, CORE-6109: ``FLOAT(p)``
          *"definition is changed to represent precision in binary digits ...
          rather than in decimal digits as before"*, and the 3.0 reference's
          declaration syntax is ``FLOAT | DOUBLE PRECISION`` with no argument at
          all. Unconditionally writing ``FLOAT(10)`` on a 3.0 dialect would
          declare a ten-decimal-digit float where a 4.0 server would read ten
          *bits*.

        So both paths call :meth:`_validate_firebird_float`, which is where the
        version boundary and the range live now.

        ``unsigned`` is refused rather than rendered, before that call — see
        :meth:`_check_firebird_signed`.
        """
        self._check_firebird_signed(data_type, "approximate numeric (FLOAT)")
        self._validate_firebird_float(data_type.precision)
        if data_type.precision is None:
            return "FLOAT", ()
        return f"FLOAT({data_type.precision})", ()

    def format_data_type_real(self, data_type: RealType) -> Tuple[str, tuple]:
        """``REAL`` renders ``FLOAT`` — Firebird's *own* synonym, so nothing is
        widened and nothing is lost.

        The language reference says so outright (§3.2.1.2, *REAL*): *"The data
        type REAL is a synonym for FLOAT, and is provided for syntax
        compatibility. When used to define a column or parameter, it's
        indistinguishable from using FLOAT or FLOAT(1) - FLOAT(24)."* Table 3.1
        in §3.1 agrees from the other end: ``REAL`` is 32 bits, *"Synonym for
        FLOAT"*, and ``FLOAT`` itself is *"32 bits ... Single-precision, IEEE-754
        binary32, ~7 digits"*. A bare ``FLOAT`` is therefore ``bin_prec`` 24 —
        single precision, 4 bytes — which is what the docstring for
        :meth:`format_data_type_firebird_float` reads off the same row.

        An earlier version of this docstring justified the rendering by claiming
        the opposite, that "Firebird's unqualified ``FLOAT`` is *double*
        precision". That is inverted, and it mattered: read as written it said a
        bare ``FLOAT`` silently widened a 4-byte single-precision ``REAL`` to an
        8-byte double, which would have made this renderer a lossy substitution
        rather than the exact one it is. Firebird spells the 64-bit type
        ``DOUBLE PRECISION``, and only ``FLOAT(25)``-``FLOAT(53)`` reaches it.

        Core's :class:`RealType` carries exactly one field, ``unsigned``, and
        :meth:`_check_firebird_signed` is what answers it; the 24-bit mantissa is
        otherwise the whole of the concept and the whole of the column, since
        Firebird's ``REAL`` is its own synonym for the bare ``FLOAT`` and
        ``PARAMETERS`` is ``("unsigned",)``.

        ``unsigned`` is refused rather than rendered — see
        :meth:`_check_firebird_signed`.
        """
        self._check_firebird_signed(data_type, "approximate numeric (REAL)")
        return "FLOAT", ()

    def format_data_type_double(self, data_type: DoubleType) -> Tuple[str, tuple]:
        """``double`` and ``double precision`` are one Firebird type written two
        ways, and Firebird writes the long one, so both render
        ``DOUBLE PRECISION``.

        ``unsigned`` is refused rather than rendered, before the spelling check —
        see :meth:`_check_firebird_signed`.
        """
        self._check_firebird_signed(data_type, "approximate numeric (DOUBLE PRECISION)")
        self._check_spelling(data_type, DoubleType)
        return "DOUBLE PRECISION", ()

    def format_data_type_decimal(self, data_type: DecimalType) -> Tuple[str, tuple]:
        """Firebird's grammar spells this concept ``NUMERIC``, ``DECIMAL`` and
        ``DEC``, and all three name the same exact fixed-point storage, so all
        three are accepted and the declared one is rendered as Firebird's
        canonical ``DECIMAL``.

        ``unsigned`` is refused rather than rendered, before the spelling check
        and before both ``ValueError`` s in :meth:`_validate_numeric` — see
        :meth:`_check_firebird_signed`. Those two are untouched and still fire
        for a signed declaration.
        """
        self._check_firebird_signed(data_type, "exact numeric (DECIMAL)")
        self._check_spelling(data_type, DecimalType)
        self._validate_numeric(data_type.precision, data_type.scale)
        if data_type.precision is not None and data_type.scale is not None:
            return f"DECIMAL({data_type.precision}, {data_type.scale})", ()
        if data_type.precision is not None:
            return f"DECIMAL({data_type.precision})", ()
        return "DECIMAL", ()

    def format_data_type_boolean(self, data_type: BooleanType) -> Tuple[str, tuple]:
        """``BOOLEAN`` only.

        ``BOOL`` is an abbreviation no Firebird version's grammar contains —
        Firebird 3 introduced the type as ``BOOLEAN`` and has no alias for it —
        so the spelling is refused instead of being answered with a declaration
        the server would reject."""
        self._check_spelling(data_type, ("boolean",))
        self._check_fb3_type("BOOLEAN")
        return "BOOLEAN", ()

    def format_data_type_varchar(self, data_type: VarCharType) -> Tuple[str, tuple]:
        """``VARCHAR``, and ``CHARACTER VARYING`` — SQL's long form of the same
        variable-length character string, which Firebird's own parser accepts and
        which is therefore a legitimate thing to find in a type string read back
        from a schema. Both render Firebird's word, ``VARCHAR(n)``.

        Declaring no width is this dialect's ``VARCHAR(255)``, and 255 is **a
        choice of this backend, not a Firebird default** — Firebird has none, and
        says so in all four references it publishes ("There is no default size:
        the n argument is mandatory"); see
        :attr:`_FB_RENDERED_VARCHAR_LENGTH` for the citations and for the open
        tracker issue that adds 255 after 5.0. The number is read from there
        rather than written here so this fallback and :meth:`parse_type` cannot
        drift apart on it, and so the reason it is not a
        :meth:`type_parameter_defaults` entry — a server that will not create the
        column supplies nothing to read back — stays attached to the number.
        """
        self._check_spelling(data_type, VarCharType)
        length = data_type.length
        if length is None:
            length = self._FB_RENDERED_VARCHAR_LENGTH
        return f"VARCHAR({length})", ()

    def format_data_type_char(self, data_type: CharType) -> Tuple[str, tuple]:
        """``CHAR`` and ``CHARACTER`` are the same fixed-length character
        string in Firebird's grammar; both render ``CHAR(n)``, Firebird's own
        word for it.

        Declaring no length is ``CHAR(1)``, and here that is also Firebird's own
        documented default — *"If the number of characters is not specified, 1 is
        used by default"*, the same sentence in the 2.5, 3.0, 4.0 and 5.0
        references — so the server stores it and reports it back in
        ``RDB$CHARACTER_LENGTH`` and :meth:`type_parameter_defaults` declares it.
        A type bound to this dialect has already resolved to that 1 in its own
        ``length``; the fallback reads the one declaration so a type built
        without a dialect renders the same number.
        """
        self._check_spelling(data_type, CharType)
        length = data_type.length
        if length is None:
            length = self.type_parameter_defaults()["char"]["length"]
        return f"CHAR({length})", ()

    def format_data_type_text(self, data_type: TextType) -> Tuple[str, tuple]:
        """``TEXT`` — rendered as ``BLOB SUB_TYPE TEXT``, which is how Firebird
        spells unbounded character data.

        ``CLOB`` is in the concept's spelling list but Firebird has no CLOB type:
        its unbounded text is a ``BLOB`` carrying a sub-type, and that is a
        different type in Firebird's own catalog from a ``CHAR`` large object.
        Asking for that spelling is therefore an error rather than a quiet rewrite.
        The default spelling must always render, or the concept would be
        unusable on this backend.
        """
        self._check_spelling(data_type, ("text",))
        return "BLOB SUB_TYPE TEXT", ()

    def format_data_type_datetime(self, data_type: DateTimeType) -> Tuple[str, tuple]:
        """``DATETIME`` is not a Firebird type name; Firebird's is ``TIMESTAMP``,
        and in Dialect 3 it is exactly the date-and-time column this concept
        means. So this is a *rename*, not a widening or a narrowing, and the
        rendered column is the one the caller asked for.

        ``precision`` is refused rather than rendered or dropped — see
        :meth:`_check_firebird_temporal_precision`. That matters more here than
        on a type Firebird spells the same way, because the substitute shares the
        unzoned ``TimestampType``'s grammar and so cannot carry the field either.
        """
        self._check_firebird_temporal_precision(data_type, "TIMESTAMP")
        return "TIMESTAMP", ()

    def format_data_type_date(self, data_type: DateType) -> Tuple[str, tuple]:
        """``DATE``.

        ``DateType`` declares no identity field, so there is nothing here to
        honour or refuse. Firebird's ``DATE`` is date-only in Dialect 3 (§3.4.1),
        which is the whole of the concept.
        """
        return "DATE", ()

    def format_data_type_time(self, data_type: TimeType) -> Tuple[str, tuple]:
        """``TIME`` — §3.4.2: *"For a bare TIME, WITHOUT TIME ZONE is assumed"*,
        so the short word names the unzoned column exactly, and
        :class:`FirebirdTimeWithoutTimeZoneType` renders the long spelling of the
        same storage when a caller wants to say so.

        ``precision`` is refused rather than rendered or dropped — see
        :meth:`_check_firebird_temporal_precision`.
        """
        self._check_firebird_temporal_precision(data_type, "TIME")
        return "TIME", ()

    # --- timetz / timestamptz: deliberately absent ---------------------------
    #
    # There is no ``format_data_type_timetz`` and no ``format_data_type_timestamptz``.
    # Both concepts are **substituted** in :meth:`suggested_data_types` instead,
    # and the reason is that Firebird's grammar makes the two impossible to render
    # from the generic concepts:
    #
    # * ``TIME`` and ``TIMESTAMP`` are Firebird's *unzoned* types — §3.4: *"TIME
    #   and TIMESTAMP are synonymous to their respective WITHOUT TIME ZONE data
    #   types."* Writing either for a zoned concept does not render a coarser
    #   version of what was asked for; it renders a **different column**, one that
    #   discards the very zone offset that made the concept distinct.
    # * The zoned columns do exist, but under their own words — ``TIME WITH TIME
    #   ZONE`` and ``TIMESTAMP WITH TIME ZONE``, Firebird 4.0+ — and this dialect
    #   already owns a concept for each: :class:`FirebirdTimeTzType` and
    #   :class:`FirebirdTimeStampTzType`, reached through
    #   ``format_data_type_firebird_timetz`` and
    #   ``format_data_type_firebird_timestamptz`. Two dispatch keys naming one
    #   Firebird column would make ``name`` — which D3 makes the concept's
    #   identity — a lie for one of them, and would break the round trip the
    #   catalog relies on: ``parse_type("TIMESTAMP WITH TIME ZONE")`` answers with
    #   ``FirebirdTimeStampTzType``, so a ``timestamptz`` renderer would emit words
    #   that parse back into a *different* class.
    # * Neither zoned declaration takes a precision argument (§3.4, §3.12), so
    #   ``precision`` could not be honoured either — which is why the substitute is
    #   the unzoned concept *and* that concept refuses a precision by name. See
    #   :meth:`_check_firebird_temporal_precision`.

    def format_data_type_timestamp(self, data_type: TimestampType) -> Tuple[str, tuple]:
        """``TIMESTAMP`` — §3.4.3: *"For a bare TIMESTAMP, WITHOUT TIME ZONE is
        assumed"*, so the short word names the unzoned column exactly.

        ``precision`` is refused rather than rendered or dropped — see
        :meth:`_check_firebird_temporal_precision`.
        """
        self._check_firebird_temporal_precision(data_type, "TIMESTAMP")
        return "TIMESTAMP", ()

    def format_data_type_blob(self, data_type: BlobType) -> Tuple[str, tuple]:
        """``BLOB`` — the concept's default spelling and Firebird's own name for
        unbounded binary storage.

        ``BYTEA`` is in the concept's spelling list because it is PostgreSQL's
        word for it. Firebird has no ``BYTEA``, so that spelling is refused
        rather than silently answered with a ``BLOB``: the request named a
        PostgreSQL declaration, and quietly substituting this backend's is
        exactly the substitution the gate exists to catch.
        """
        self._check_spelling(data_type, ("blob",))
        return "BLOB", ()

    def format_data_type_binary(self, data_type: BinaryType) -> Tuple[str, tuple]:
        return (f"CHAR({data_type.length}) CHARACTER SET OCTETS" if data_type.length is not None else "BLOB"), ()

    def format_data_type_varbinary(self, data_type: VarBinaryType) -> Tuple[str, tuple]:
        return (f"VARCHAR({data_type.length}) CHARACTER SET OCTETS" if data_type.length is not None else "BLOB"), ()

    def format_data_type_uuid(self, data_type: UUIDType) -> Tuple[str, tuple]:
        return "CHAR(16) CHARACTER SET OCTETS", ()

    def format_data_type_custom(self, data_type: CustomType) -> Tuple[str, tuple]:
        return data_type.raw, ()

    # --- Firebird-specific type formatters (dispatch key = type name) ---

    def format_data_type_firebird_decimal(self, data_type: FirebirdDecimalType) -> Tuple[str, tuple]:
        """``DECIMAL`` under its own dispatch key. Same spelling rule as
        :meth:`format_data_type_decimal` — ``NUMERIC`` and ``DEC`` name the same
        Firebird storage and are accepted; the declared one renders as
        ``DECIMAL``.

        ``unsigned`` is refused rather than rendered, before the spelling check
        and before both ``ValueError`` s — see :meth:`_check_firebird_signed`.
        The class does not narrow ``PARAMETERS``, so it genuinely carries the
        field: :class:`~...expression.types.FirebirdDecimalType` inherits core's
        constructor, which is why its formatter needs the gate as much as the
        core ``decimal`` one does."""
        self._check_firebird_signed(data_type, "exact numeric (DECIMAL)")
        self._check_spelling(data_type, DecimalType)
        self._validate_numeric(data_type.precision, data_type.scale)
        if data_type.precision is not None and data_type.scale is not None:
            return f"DECIMAL({data_type.precision}, {data_type.scale})", ()
        if data_type.precision is not None:
            return f"DECIMAL({data_type.precision})", ()
        return "DECIMAL", ()

    def format_data_type_firebird_float(self, data_type: FirebirdFloatType) -> Tuple[str, tuple]:
        """``FLOAT`` or ``FLOAT(bin_prec)`` — the binary precision is **honoured**.

        Firebird's grammar really does take the argument. The 4.0 reference's
        declaration syntax is ``REAL | FLOAT [(bin_prec)] | DOUBLE PRECISION``
        (§3.12.1) and its numeric-types entry gives ``FLOAT (bin_prec)`` as
        "32 bits or 64 bits", with ``bin_prec`` documented as "precision in
        binary digits, default is 24; 1 - 24: 32-bit single precision; 25 - 53:
        64-bit double precision" (§3.2.1.1). Emitting a fixed ``FLOAT``
        regardless of ``precision`` would make ``FLOAT(24)`` and ``FLOAT(53)``
        the same column while ``__eq__`` calls them different — precisely the
        silent identity loss the rule exists to prevent — so the precision is
        written.

        ``precision=None`` renders bare ``FLOAT``, which the server reads as
        ``bin_prec`` 24: 32-bit single precision, 4 bytes — Firebird's own
        ``REAL`` (§3.2.1.2: *"The data type REAL is a synonym for FLOAT"*).

        A precision is refused below Firebird 4.0 and range-checked 1..53 on 4.0+
        — see :meth:`_validate_firebird_float` for why the *same* string means
        different columns on the two sides of that boundary, and for why the
        generic :meth:`format_data_type_float` shares this method's validation
        rather than keeping its own.

        ``unsigned`` is refused rather than rendered, before the 4.0 gate and the
        range check — see :meth:`_check_firebird_signed`. Like
        :class:`~...expression.types.FirebirdFloatType`'s siblings, the class
        inherits core's constructor, so it really does carry the field.
        """
        self._check_firebird_signed(data_type, "approximate numeric (FLOAT)")
        self._validate_firebird_float(data_type.precision)
        if data_type.precision is None:
            return "FLOAT", ()
        return f"FLOAT({data_type.precision})", ()

    def format_data_type_firebird_double(self, data_type: FirebirdDoubleType) -> Tuple[str, tuple]:
        """``DOUBLE PRECISION`` — the same Firebird type
        :meth:`format_data_type_double` writes, under this backend's own dispatch
        key.

        ``unsigned`` is refused rather than rendered; see
        :meth:`_check_firebird_signed`.
        """
        self._check_firebird_signed(data_type, "approximate numeric (DOUBLE PRECISION)")
        return "DOUBLE PRECISION", ()

    def format_data_type_firebird_blob_subtype(self, data_type: FirebirdBlobSubType) -> Tuple[str, tuple]:
        """``BLOB SUB_TYPE TEXT``.

        The integer here is the sub-type tag Firebird stores for a ``BLOB``
        column, so ``INTEGER``/``INT`` — Firebird's own two words for a 32-bit
        integer — are both accepted; the word written is the BLOB clause either
        way, because that clause is what declares the column.

        ``unsigned`` is refused rather than rendered, and refused **before** the
        spelling check like every other gate in this file. The class narrows
        ``PARAMETERS`` to ``()`` — a BLOB sub-type tag has no signedness to
        differ in — and this is what keeps the inherited constructor from
        quietly accepting and discarding it; see
        :meth:`_check_firebird_signed`.
        """
        self._check_firebird_signed(data_type)
        self._check_spelling(data_type, IntegerType)
        return "BLOB SUB_TYPE TEXT", ()

    def format_data_type_firebird_char(self, data_type: FirebirdCharType) -> Tuple[str, tuple]:
        """``CHAR(n) CHARACTER SET UTF8`` — the fixed-length concept with the
        column's character set written out, so the declaration does not depend on
        the database default. ``CHARACTER`` is accepted for the same reason as in
        :meth:`format_data_type_char`.

        The unsized case is the same ``CHAR(1)`` that concept declares, read from
        the one declaration rather than repeated; see :meth:`format_data_type_char`
        for why Firebird's 1 is a documented default and not a choice of this
        backend."""
        self._check_spelling(data_type, CharType)
        length = data_type.length
        if length is None:
            length = self.type_parameter_defaults()["firebird_char"]["length"]
        return f"CHAR({length}) CHARACTER SET UTF8", ()

    def format_data_type_firebird_varchar(self, data_type: FirebirdVarCharType) -> Tuple[str, tuple]:
        """``VARCHAR(n) CHARACTER SET UTF8``; see
        :meth:`format_data_type_firebird_char` for why the character set is part
        of the rendered declaration, and :meth:`format_data_type_varchar` for why
        the unsized ``VARCHAR(255)`` here is a decision of this backend rather
        than a Firebird default — it is the same number, named once in
        :attr:`_FB_RENDERED_VARCHAR_LENGTH`."""
        self._check_spelling(data_type, VarCharType)
        length = data_type.length
        if length is None:
            length = self._FB_RENDERED_VARCHAR_LENGTH
        return f"VARCHAR({length}) CHARACTER SET UTF8", ()

    def format_data_type_firebird_timestamptz(self, data_type: FirebirdTimeStampTzType) -> Tuple[str, tuple]:
        """``TIMESTAMP WITH TIME ZONE`` — Firebird 4.0+, and the whole declaration.

        No precision is written, and a declared one is **refused** — see
        :meth:`_check_firebird_temporal_precision`, which is where the grammar
        and the ten-thousandths-of-a-second storage are cited. The previous state
        of this method emitted ``TIMESTAMP(6) WITH TIME ZONE`` for
        ``precision=6``: the production in §3.4.3 and in the §3.12 Data Type
        Declaration Syntax is ``TIMESTAMP [{WITHOUT | WITH} TIME ZONE]``, with no
        argument of any kind, and the identical lines appear in the 4.0 and 5.0
        references. FirebirdSQL/firebird#4779 (CORE-4459) asks for
        ``TIMESTAMP(p)`` in datatype declarations and is still open, so it is not
        a capability this backend may write.
        """
        self._check_fb4_type("TIMESTAMP WITH TIME ZONE")
        self._check_firebird_temporal_precision(data_type, "TIMESTAMP WITH TIME ZONE")
        return "TIMESTAMP WITH TIME ZONE", ()

    def format_data_type_firebird_timetz(self, data_type: FirebirdTimeTzType) -> Tuple[str, tuple]:
        """``TIME WITH TIME ZONE`` — Firebird 4.0+.

        Six bytes: the four of a ``TIME`` plus two for either an offset in minutes
        or the id of a named zone (§3.1 Table 3.1; §3.4, *Storage of Time Zone
        Types*). Values are held at UTC so two of them in different zones compare
        and index correctly.

        No precision is written, and a declared one is refused — see
        :meth:`_check_firebird_temporal_precision` and
        :meth:`format_data_type_firebird_timestamptz`.
        """
        self._check_fb4_type("TIME WITH TIME ZONE")
        self._check_firebird_temporal_precision(data_type, "TIME WITH TIME ZONE")
        return "TIME WITH TIME ZONE", ()

    def format_data_type_firebird_time_without_time_zone(
        self,
        data_type: FirebirdTimeWithoutTimeZoneType,
    ) -> Tuple[str, tuple]:
        """``TIME WITHOUT TIME ZONE`` — Firebird 4.0+'s spelled-out long form of
        the bare ``TIME``, which Firebird required alongside its zoned ``TIME WITH
        TIME ZONE`` because ``TIME`` on its own was already taken (§3.4.2:
        *"For a bare TIME, WITHOUT TIME ZONE is assumed"*).

        The long spelling is rendered rather than the short one because the whole
        point of this concept is to say the clause; a column declared this way and
        a column declared ``TIME`` are the same storage, and rendering the bare
        word would throw away the one thing the caller asked to be explicit about.

        No precision is written, and a declared one is refused — see
        :meth:`_check_firebird_temporal_precision` and
        :meth:`format_data_type_firebird_timestamptz`.
        """
        self._check_fb4_type("TIME WITHOUT TIME ZONE")
        self._check_firebird_temporal_precision(data_type, "TIME WITHOUT TIME ZONE")
        return "TIME WITHOUT TIME ZONE", ()

    def format_data_type_firebird_decfloat(self, data_type: FirebirdDecFloatType) -> Tuple[str, tuple]:
        """``DECFLOAT(dec_prec)`` — Firebird 4.0+, with the width always written.

        The width is written even when the caller did not name one, because the
        identity field is what makes ``DECFLOAT(16)`` and ``DECFLOAT(34)``
        different columns and Firebird encodes the width in the catalog code as
        well as in ``RDB$FIELD_LENGTH`` (8 bytes against 16; D.11 ``RDB$FIELDS``,
        codes 24 and 25). Writing the bare word would re-introduce the collision
        the two codes were split to avoid.

        Which width the *bare* word means is settled by the reference, and it is
        34, not 16 — §3.2.2.1, *DECFLOAT*: ``dec_prec`` is *"Precision in decimal
        digits, either 16 or 34. Default is 34."* See
        :class:`~...expression.types.FirebirdDecFloatType`, whose constructor
        default follows the same line.
        """
        self._check_fb4_type("DECFLOAT")
        return f"DECFLOAT({data_type.precision})", ()

    def format_data_type_firebird_int128(self, data_type: FirebirdInt128Type) -> Tuple[str, tuple]:
        """Format INT128 (Firebird 4.0+)."""
        self._check_fb4_type("INT128")
        return "INT128", ()

    def _check_fb3_type(self, feature: str) -> None:
        version = getattr(self, 'version', (3, 0, 0))
        if _norm_version(version) < (3, 0, 0):
            raise UnsupportedFeatureError(
                self.name,
                feature,
                f"Firebird 3.0 or later is required for the {feature} data type.",
            )

    def _fb4_available(self) -> bool:
        """Whether this dialect targets a Firebird that has the 4.0 data types.

        Single source of truth for every Firebird 4.0 gate in this mixin —
        :meth:`_check_fb4_type`, the ``supports_data_type_firebird_*`` probes
        and the zoned spellings :meth:`parse_type` recognises — so parsing and
        rendering cannot disagree about whether the type exists.

        The default is 4.0 because a dialect built with no version at all is
        the "latest this backend knows about" case; FirebirdDialect only sets
        ``version`` when one is passed.
        """
        return _norm_version(getattr(self, 'version', (4, 0, 0))) >= (4, 0, 0)

    def _check_fb4_type(self, feature: str) -> None:
        """Raise unless the dialect targets Firebird 4.0 or later.

        TIME ZONE / DECFLOAT / INT128 data types were all introduced in
        Firebird 4.0.
        """
        if not self._fb4_available():
            raise UnsupportedFeatureError(
                self.name,
                feature,
                f"Firebird 4.0 or later is required for the {feature} data type.",
            )

    # ------------------------------------------------------------------
    # DDLTypeSupport — per-type support declarations
    #
    # 1:1 correspondence with format_data_type_* family (protocol contract).
    # ------------------------------------------------------------------

    def supports_data_type_integer(self) -> bool:
        return True

    def supports_data_type_bigint(self) -> bool:
        return True

    def supports_data_type_smallint(self) -> bool:
        return True

    def supports_data_type_tinyint(self) -> bool:
        return True

    def supports_data_type_float(self) -> bool:
        return True

    def supports_data_type_real(self) -> bool:
        return True

    def supports_data_type_double(self) -> bool:
        return True

    def supports_data_type_decimal(self) -> bool:
        return True

    def supports_data_type_boolean(self) -> bool:
        return _norm_version(getattr(self, 'version', (3, 0, 0))) >= (3, 0, 0)

    def supports_data_type_varchar(self) -> bool:
        return True

    def supports_data_type_char(self) -> bool:
        return True

    def supports_data_type_text(self) -> bool:
        return True

    def supports_data_type_datetime(self) -> bool:
        return True

    def supports_data_type_date(self) -> bool:
        return True

    def supports_data_type_time(self) -> bool:
        return True

    def supports_data_type_timestamp(self) -> bool:
        return True

    # ``timetz`` and ``timestamptz`` have no ``supports_data_type_*`` here, and
    # that is the whole answer rather than an omission: neither concept is
    # rendered, because Firebird's ``TIME`` and ``TIMESTAMP`` are the *unzoned*
    # types (§3.4: "TIME and TIMESTAMP are synonymous to their respective
    # WITHOUT TIME ZONE data types"). The zoned columns are Firebird's own words
    # — ``TIME WITH TIME ZONE`` / ``TIMESTAMP WITH TIME ZONE``, 4.0+ — and they
    # are rendered by ``firebird_timetz`` and ``firebird_timestamptz`` below.
    # Naming the unzoned substitute is ``suggested_data_types``' job; see the
    # "timetz / timestamptz: deliberately absent" comment above
    # ``format_data_type_timestamp``.

    def supports_data_type_blob(self) -> bool:
        return True

    def supports_data_type_binary(self) -> bool:
        return True

    def supports_data_type_varbinary(self) -> bool:
        return True

    def supports_data_type_uuid(self) -> bool:
        return True

    def supports_data_type_custom(self) -> bool:
        return True

    def supports_data_type_firebird_decimal(self) -> bool:
        return True

    def supports_data_type_firebird_float(self) -> bool:
        # Deliberately ungated, unlike its Firebird 4.0 neighbours. Bare ``FLOAT``
        # is 32-bit single precision in every version this backend targets, so
        # ``firebird_float`` *is* renderable on Firebird 3; only the ``bin_prec``
        # argument needs 4.0, and that gate lives in the formatter
        # (``_validate_firebird_float``) because it is the argument that needs it.
        return True

    def supports_data_type_firebird_double(self) -> bool:
        return True

    def supports_data_type_firebird_blob_subtype(self) -> bool:
        return True

    def supports_data_type_firebird_char(self) -> bool:
        return True

    def supports_data_type_firebird_varchar(self) -> bool:
        return True

    def supports_data_type_firebird_timestamptz(self) -> bool:
        return _norm_version(getattr(self, 'version', (4, 0, 0))) >= (4, 0, 0)

    def supports_data_type_firebird_timetz(self) -> bool:
        return _norm_version(getattr(self, 'version', (4, 0, 0))) >= (4, 0, 0)

    def supports_data_type_firebird_time_without_time_zone(self) -> bool:
        return _norm_version(getattr(self, 'version', (4, 0, 0))) >= (4, 0, 0)

    def supports_data_type_firebird_decfloat(self) -> bool:
        return _norm_version(getattr(self, 'version', (4, 0, 0))) >= (4, 0, 0)

    def supports_data_type_firebird_int128(self) -> bool:
        return _norm_version(getattr(self, 'version', (4, 0, 0))) >= (4, 0, 0)

    # ------------------------------------------------------------------
    # suggested_data_types() — D9
    #
    # Every concept the framework models must be either rendered here or named
    # here. Firebird renders the scalar types and its own ``firebird_*`` family;
    # what it cannot spell it says so, rather than letting a caller discover the
    # gap from a bare "unsupported".
    # ------------------------------------------------------------------

    def suggested_data_types(self) -> Dict[str, type]:
        """Cross-backend type-consistency suggestions for Firebird.

        Values are the suggested replacement ``DataType`` **classes**, each one a
        type this dialect really renders — suggesting a class it cannot write
        would trade a clear "not supported" for a worse one whose advice does not
        work.

        ``json`` / ``jsonb``
            Firebird has no JSON type. ``BLOB SUB_TYPE TEXT`` holding JSON text is
            the documented way to store it — hence :class:`TextType`, which is
            exactly what ``format_data_type_text`` writes. The content has to be
            validated by the application; Firebird will not check it.

        ``enum``
            Firebird has no enum type. A set of labels enforced by hand is a
            ``VARCHAR(n)`` plus a CHECK constraint, and the length part is what a
            schema can actually record, so the substitute is
            :class:`VarCharType` rather than ``CustomType``.

        ``xml``
            Firebird has no XML type either: no document model, no XPath over it,
            no schema validation. The document is stored as text, so the
            substitute is :class:`TextType` — the same answer as for JSON, and for
            the same reason. This dialect also renders ``CustomType``, so a caller
            who wants a hand-written declaration can reach for that instead.

        ``array``
            Firebird **has** array columns — the language reference has a
            section on them ("3.8. Array Types", in the 2.5, 4.0 and 5.0
            references alike) and one is declared as ``ARR_INT INTEGER [4]``,
            with ``INTEGER [0:3, 0:3]`` for two dimensions and subscripts
            defaulting to 1-based. The storage is a BLOB sub-type, but the
            *type* is an array, so naming :class:`BlobType` here would be the
            one claim in this method that is simply untrue.

            What cannot be done instead is to render it, and the reason is
            worth writing down: Firebird's grammar makes the bounds part of
            the type — ``array_type: non_charset_simple_type '[' array_spec
            ']'``, where every dimension needs at least one integer — while
            :class:`ArrayType` carries only ``dimensions``. There is no bound
            in the type to write and none the dialect may invent; declaring
            ``INTEGER [1]`` would silently create a one-element column. The
            escape hatch is the same one Oracle uses for ``array``: the
            declaration written by name through :class:`CustomType`, because a
            declaration is a name here and ``format_data_type_custom`` renders
            one unchanged. Note the gap that leaves — ``validate_type_name``
            admits only *empty* ``[]`` array markers, so ``INTEGER [4]`` does
            not validate and the door is narrower than it should be. That is a
            core fix, not a Firebird one.

        ``interval``
            Firebird has no ``INTERVAL`` type. Its own idiom for a duration is a
            64-bit integer counting units of 1/10000 second, which is what the
            server's date arithmetic uses internally, so the substitute is
            :class:`BigIntType`.

        ``timetz`` / ``timestamptz``
            **Firebird does have zoned time and zoned timestamps.** They arrived in
            4.0, they are 6 and 10 bytes, and §3.1 Table 3.1 lists them as ``TIME
            WITH TIME ZONE`` and ``TIMESTAMP WITH TIME ZONE``. What is missing is
            any way to spell them *from these concepts*: the two short words are
            Firebird's **unzoned** types — §3.4, in a note under the chapter
            heading: *"TIME and TIMESTAMP are synonymous to their respective
            WITHOUT TIME ZONE data types."* So a renderer here could only have
            answered with a column that discards the zone offset, which is the one
            property that made these concepts distinct, and it would have done so
            while reporting success.

            The substitute is therefore the unzoned concept of the same family —
            :class:`TimeType` for ``timetz``, :class:`TimestampType` for
            ``timestamptz`` — which is what this backend will render if the zone
            does not matter. **It is lossy and the loss is the zone**: Firebird
            stores the zoned forms at UTC plus two bytes of offset-or-named-zone
            (§3.4, *Storage of Time Zone Types*), and the unzoned form stores
            neither, converting through the session zone on the way in and out.

            A caller who needs the zone does not get a substitute at all — it gets
            a Firebird-named concept, which this dialect owns and renders:
            :class:`~...expression.types.FirebirdTimeTzType` and
            :class:`~...expression.types.FirebirdTimeStampTzType`, i.e.
            ``FirebirdTimeTzType()`` and ``FirebirdTimeStampTzType()``. That is
            also what ``parse_type`` answers with for the words the catalog
            reports (``RDB$FIELD_TYPE`` 28 and 29), which is why these two keys
            are substitutes rather than renderers: a ``timestamptz`` renderer
            would emit words that parse straight back into a different class.

            Neither concept's ``precision`` survives the substitution, and it could
            not be honoured on this backend in the first place: no Firebird
            ``TIME``/``TIMESTAMP`` declaration takes one (§3.4, §3.12). The
            unzoned concepts refuse a declared precision by name, so a
            ``TimestampTzType(precision=6)`` is answered twice and loudly — first
            "this dialect does not render ``timestamptz``, it suggests
            ``TimestampType``", then "a ``TIMESTAMP`` takes no precision argument".
            Nothing is dropped.
        """
        return {
            "json": TextType,
            "jsonb": TextType,
            "xml": TextType,
            "enum": VarCharType,
            "array": CustomType,
            "interval": BigIntType,
            "timetz": TimeType,
            "timestamptz": TimestampType,
        }

    # Every substitution above loses something, and the caller is the only one
    # who can act on it — so each caveat goes into the error they are already
    # reading. Core's advice text deliberately does not claim a substitute holds
    # the same meaning (it usually does; "usually" is why it must not say so),
    # which leaves the specific loss to be stated here.
    _LOSSY_SUBSTITUTIONS = {
        "json": "Firebird has no JSON type, so the document is stored as text "
                "and nothing on the server validates it; that is the "
                "application's job now.",
        "jsonb": "Firebird has no JSON type, so the document is stored as text "
                 "and nothing on the server validates it; that is the "
                 "application's job now.",
        "xml": "Firebird has no XML type, so the document is stored as text and "
               "nothing on the server validates it.",
        "enum": "Firebird has no enum type, so the set of labels is not enforced "
                "by the server — a CHECK constraint is what makes it true.",
        "array": "Firebird has array types, but its grammar makes the bounds part "
                 "of the type and this class carries only a dimensionality, so "
                 "the array's extents cannot be declared through it.",
        "interval": "Firebird has no interval type, so the span is stored as a "
                    "count and the unit has nowhere to live in the column.",
        "timetz": "This drops the zone. Firebird's own reference says ``TIME`` "
                  "is a synonym for its WITHOUT TIME ZONE type, so the stored "
                  "value is a local time. If the offset matters, declare "
                  "``FirebirdTimeTzType`` explicitly instead.",
        "timestamptz": "This drops the zone. Firebird's own reference says "
                       "``TIMESTAMP`` is a synonym for its WITHOUT TIME ZONE "
                       "type, so the stored value is a local time. If the "
                       "offset matters, declare ``FirebirdTimeStampTzType`` "
                       "explicitly instead.",
    }

    def substitute_advice(self, name: str) -> str:
        """State what this substitution gives up, in the caller's error.

        Firebird's two zoned concepts are the sharp case: the stand-in is a
        *different value*, not another spelling of the same one, because the
        Firebird reference makes ``TIME`` and ``TIMESTAMP`` synonyms of their
        unzoned types. A caller who reads only "it suggests ``TimeType``
        instead" would create a column that silently lost an offset.
        """
        caveat = self._LOSSY_SUBSTITUTIONS.get(name)
        return f"Note: {caveat}" if caveat else ""

    # ------------------------------------------------------------------
    # type_parameter_defaults() — what this server supplies for a
    # parameter a declaration left undeclared
    # ------------------------------------------------------------------

    #: Firebird's documented size for a ``CHAR`` declared without one: *"If the
    #: number of characters is not specified, 1 is used by default."*
    #:
    #: Quoted from the **Data Types and Subtypes** chapter, and it is the same
    #: sentence in all four references this backend can address — 2.5 §3 Table 1
    #: under ``CHAR(n), CHARACTER(n)``, and 3.0 / 4.0 / 5.0 likewise (5.0 §3.5.6
    #: puts it in the ``CHAR`` parameter table as "Length in characters, defaults
    #: to 1"). §3.12's Scalar Data Types Syntax carries the matching production
    #: ``{CHAR | CHARACTER} [(length)]`` — the brackets round ``length`` here and
    #: not round it for ``VARCHAR``, which is the whole of the next paragraph.
    _FB_CHAR_DEFAULT_LENGTH = 1

    #: The width this dialect writes when a declaration names none, for the one
    #: concept Firebird has **no** documented default for. Read it as a decision
    #: of this backend and not as a server fact, because the server has no
    #: opinion here:
    #:
    #: * Firebird 2.5, 3.0, 4.0 and 5.0 all say the same thing about
    #:   ``VARCHAR(n), CHAR VARYING(n), CHARACTER VARYING(n)`` — *"There is no
    #:   default size: the n argument is mandatory."* §3.12 spells the grammar
    #:   the same way, ``{VARCHAR | {CHAR | CHARACTER} VARYING} (length)``, with
    #:   the parentheses round and no square brackets, and §3.5.6's ``VARCHAR``
    #:   parameter table gives ``length`` with no default clause at all.
    #: * Firebird's own tracker agrees and puts a date on it: FirebirdSQL/
    #:   firebird#8909, *"Support VARCHAR/VARBINARY without explicit length"*,
    #:   opens with *"Currently, Firebird doesn't have a default length for
    #:   VARCHAR/CHARACTER VARYING, { NCHAR | NATIONAL {CHAR|CHARACTER} }
    #:   VARYING, and VARBINARY/BINARY VARYING"* and adds 255 to all of them. The
    #:   grammar is ``VARCHAR [(length)]`` there and the ``[ ]`` are what that
    #:   issue adds — so 255 is a Firebird **6** change, not a rule this backend
    #:   may write for a 3, 4 or 5 server, and not a rule it may report a server
    #:   having applied.
    #:
    #: A bare ``VARCHAR`` is therefore a syntax error on every version this
    #: backend addresses (``-104 Token unknown``), which is the same answer
    #: MariaDB gives for its bare ``VARCHAR`` and the reason
    #: :meth:`type_parameter_defaults` declares no ``varchar`` entry: a server
    #: that will not create the column supplies nothing to report back, and the
    #: number this dialect writes has to be one it chose. 255 is that choice and
    #: it is unchanged — it is what both renderers have always written, it is
    #: Firebird's own future default rather than an arbitrary figure, and it is
    #: named here so :meth:`parse_type` and the two ``VARCHAR`` formatters cannot
    #: drift apart on it.
    _FB_RENDERED_VARCHAR_LENGTH = 255

    def type_parameter_defaults(self) -> Dict[str, Dict[str, object]]:
        """The widths Firebird supplies for a declaration that named none.

        **One entry, and the reason there is only one is the point.**
        ``CharType.length`` resolves against this, so ``CharType(d)`` and the
        ``CharType(length=1)`` that :meth:`parse_type` reads out of a ``CHAR``
        column are the same column rather than two that render identically and
        compare unequal.

        ``char`` **and** ``firebird_char`` are declared side by side because
        :class:`~...expression.types.FirebirdCharType` is the same concept
        through this backend's own entry point — it adds ``CHARACTER SET UTF8``
        to the written form and nothing to the storage — and it carries its own
        ``name``, so it keys its own entry. Two names, one width; a dialect that
        let them drift apart would be describing one column two ways.

        **What is deliberately absent is the pair that used to be two literals
        here**, and it is worth being exact about why:

        ``varchar`` / ``firebird_varchar`` — **not declared, because Firebird has
        no default to declare.** All four references this backend can address say
        *"There is no default size: the n argument is mandatory"*, §3.12's
        production puts the parentheses round ``length`` rather than in square
        brackets, and FirebirdSQL/firebird#8909 is the open request that adds
        255 — after 5.0. So a ``VarCharType`` bound to this dialect keeps
        ``None``, which is the honest answer for a declaration the server
        rejects, and the 255 both formatters write is
        :attr:`_FB_RENDERED_VARCHAR_LENGTH`: a decision of *this* backend,
        stated as one, with the vendor's own statement that contradicts any
        default attached to it. The difference from ``char`` is not degree, it
        is kind: a bare ``CHAR`` is accepted and stored, a bare ``VARCHAR`` is
        not accepted at all, and only the first can be read back off a catalog
        row.
        https://firebirdsql.org/file/documentation/html/en/refdocs/fblangref50/firebird-50-language-reference.html
        """
        return {
            "char": {"length": self._FB_CHAR_DEFAULT_LENGTH},
            "firebird_char": {"length": self._FB_CHAR_DEFAULT_LENGTH},
        }

    # --- Parsing ---
    #
    # Canonical over the framework's spelling vocabulary: one concept in, one
    # class out. A synonym never yields a different class, so ``character
    # varying`` is a ``VarCharType`` and never a ``CharType``.
    #
    # The two long standard forms a Firebird DDL string may legitimately carry —
    # ``CHARACTER`` and ``CHARACTER VARYING`` — are recorded as the spelling that
    # was read, so the instance says which word it came from. Nothing else is:
    # for every other concept Firebird has one word, and recording a synonym
    # would make an introspected column compare unequal to the same column
    # declared with that synonym, for no informational gain.
    #
    # A word Firebird does not spell — ``INT2``, ``BYTEA``, ``CLOB``, ``BOOL`` —
    # is still recognised and still yields the concept's class, because a caller
    # reading a schema may well be handed a type string produced elsewhere. The
    # instance then carries the canonical spelling, which is the word Firebird
    # writes, so a parsed value always renders back to a valid column.

    _FB_TINYINT_TYPES = re.compile(r"^(?:TINYINT|INT1)\b", re.IGNORECASE)
    # ``UNSIGNED`` as a whole word anywhere in a type string.  Every branch below
    # matches on the word *in front of* the attribute, so this is what stops
    # ``INTEGER UNSIGNED`` from parsing to a signed ``IntegerType``.  No Firebird
    # server can have written such a string; see ``_refuse_unsigned_type_string``
    # for why the branch exists anyway.
    _UNSIGNED_ATTRIBUTE = re.compile(r"\bUNSIGNED\b", re.IGNORECASE)
    _FB_INTEGER_TYPES = re.compile(
        r"^(?:SMALLINT|INT2|INTEGER|INT|BIGINT|INT8)\b", re.IGNORECASE
    )
    _FB_FLOAT_TYPES = re.compile(
        r"^(?:FLOAT|DOUBLE\s+PRECISION|DOUBLE|REAL)\b", re.IGNORECASE
    )
    _FB_DECIMAL_TYPES = re.compile(r"^(?:DECIMAL|NUMERIC|DEC)\b", re.IGNORECASE)
    _FB_STRING_TYPES = re.compile(
        r"^(?:CHARACTER\s+VARYING|CHAR\s+VARYING|VARCHAR|CHARACTER|CHAR)\b",
        re.IGNORECASE,
    )
    _FB_BLOB_TEXT_TYPES = re.compile(r"^BLOB\s+SUB_TYPE\s+TEXT\b", re.IGNORECASE)
    _FB_BLOB_TYPES = re.compile(r"^(?:BLOB|BYTEA)\b", re.IGNORECASE)
    _FB_TEXT_TYPES = re.compile(r"^(?:TEXT|CLOB)\b", re.IGNORECASE)
    _FB_DATE_TYPES = re.compile(r"^(?:DATE|TIMESTAMP|TIME)\b", re.IGNORECASE)
    _FB_BOOLEAN_TYPES = re.compile(r"^(?:BOOLEAN|BOOL)\b", re.IGNORECASE)

    # Firebird 4.0's zoned date-time types. These must be matched *before*
    # ``_FB_DATE_TYPES``, whose pattern stops at the first word and so used to
    # read a zoned column back as the unzoned concept — which the schema differ
    # compares with ``!=``, so the zone was invisible to it rather than
    # reported. The words are the ones Firebird writes: its grammar is
    # ``TIME [{WITHOUT | WITH} TIME ZONE]`` (§3.4.2) /
    # ``TIMESTAMP [{WITHOUT | WITH} TIME ZONE]`` (§3.4.3), the same two
    # productions in the §3.12 Data Type Declaration Syntax, and
    # RDB$FIELDS.RDB$FIELD_TYPE reports 28 and 29 for the two zoned columns
    # (language reference, D.11). Firebird's 4.0 pre-release carried
    # ``RDB$TYPES.RDB$TYPE_NAME`` as ``... WITH TIMEZONE`` without the space
    # (FirebirdSQL/firebird#6805, fixed for 4.0.0); only the unspaced form is
    # not recognised here, because the released server never writes it and
    # RDB$FIELD_TYPE — which is what this dialect reads — is 28/29 either way.
    #
    # The optional precision group is matched **so it can be refused**, not so it
    # can be read: no Firebird ``TIME``/``TIMESTAMP`` declaration carries one, so
    # ``TIMESTAMP(4) WITH TIME ZONE`` is not a Firebird type name and turning it
    # into a class whose renderer then raises would leave ``parse_type`` accepting
    # an input it cannot render back. See
    # :meth:`_check_firebird_temporal_precision` and
    # :meth:`_parse_temporal_declaration`.
    _FB_TIMESTAMP_TZ_TYPES = re.compile(
        r"^TIMESTAMP(?:\s*\(\s*(\d+)\s*\))?\s+WITH\s+TIME\s+ZONE\b", re.IGNORECASE
    )
    _FB_TIME_TZ_TYPES = re.compile(
        r"^TIME(?:\s*\(\s*(\d+)\s*\))?\s+WITH\s+TIME\s+ZONE\b", re.IGNORECASE
    )
    _FB_TIME_WITHOUT_TZ_TYPES = re.compile(
        r"^TIME(?:\s*\(\s*(\d+)\s*\))?\s+WITHOUT\s+TIME\s+ZONE\b", re.IGNORECASE
    )

    #: A precision on a bare ``DATE``/``TIME``/``TIMESTAMP``, in the same
    #: "recognised in order to be refused" spirit as the three zoned patterns
    #: above. ``_FB_DATE_TYPES`` stops after the first word, so without this the
    #: tail — ``(4)`` — was simply ignored and ``TIMESTAMP(4)`` parsed as a plain
    #: ``TIMESTAMP``, i.e. a *different* column than the one that was read.
    _FB_TEMPORAL_PRECISION = re.compile(
        r"^(?:DATE|TIMESTAMP|TIME)\s*\(\s*\d+\s*\)", re.IGNORECASE
    )

    #: The Firebird 4.0 date-time spellings and the class each one renders to.
    _FB_ZONED_TIME_TYPES = (
        (_FB_TIMESTAMP_TZ_TYPES, FirebirdTimeStampTzType),
        (_FB_TIME_TZ_TYPES, FirebirdTimeTzType),
        (_FB_TIME_WITHOUT_TZ_TYPES, FirebirdTimeWithoutTimeZoneType),
    )

    #: Firebird 4.0's ``DECFLOAT`` and ``INT128`` — the other two codes the
    #: introspector reads out of ``RDB$FIELDS.RDB$FIELD_TYPE`` that no pattern
    #: above claimed. Unrecognised, a real ``DECFLOAT`` column arrived as
    #: ``CustomType(raw="DECFLOAT")`` and a real ``INT128`` column as
    #: ``CustomType(raw="INT128")``: opaque names that render themselves
    #: straight back into DDL. For ``DECFLOAT`` that also lost the declared
    #: precision, which is a silent identity loss rather than merely an
    #: unmodelled type — ``FirebirdDecFloatType`` carries ``precision`` in
    #: :attr:`PARAMETERS`, so a ``DECFLOAT(16)`` column compared equal to a
    #: ``DECFLOAT(34)`` one and the differ had nothing to report.
    #:
    #: The precision is read *out of the name* rather than defaulted, because
    #: Firebird encodes it there: ``RDB$FIELD_TYPE`` splits the two widths into
    #: separate codes (24 for ``DECFLOAT(16)``, 25 for ``DECFLOAT(34)`` —
    #: language reference, D.11) and the introspector writes the matching
    #: ``DECFLOAT(16)``/``DECFLOAT(34)``. A bare ``DECFLOAT`` is legal Firebird
    #: and its default is documented — ``dec_prec``, "either 16 or 34; Default is
    #: 34" (§3.2.2.1) — so that is what a bare one resolves to. Nothing else is
    #: guessed: ``DECFLOAT(20)`` is rejected by
    #: :class:`FirebirdDecFloatType`'s constructor rather than rounded to a width
    #: the declaration never named.
    _FB_DECFLOAT_TYPES = re.compile(
        r"^DECFLOAT(?:\s*\(\s*(\d+)\s*\))?(?![A-Za-z0-9_$])", re.IGNORECASE
    )
    _FB_INT128_TYPES = re.compile(r"^INT128(?![A-Za-z0-9_$])", re.IGNORECASE)

    #: The documented default for a bare ``DECFLOAT`` — "either 16 or 34; Default
    #: is 34" (language reference §3.2.2.1, *DECFLOAT*; the parameter is spelled
    #: ``dec_prec`` there from 5.0 on and ``precision`` in 4.0, with the same
    #: default in both). Named so the resolution below is one fact written once,
    #: and so :class:`FirebirdDecFloatType`'s constructor default and this method
    #: cannot drift apart on it.
    _FB_DECFLOAT_DEFAULT_PRECISION = 34

    def _reject_temporal_precision(self, raw: str, declared) -> None:
        """Raise if a ``TIME``/``TIMESTAMP``/``DATE`` declaration names a precision.

        Returns ``None`` — and so is a no-op — when *declared* is ``None``.
        Kept next to the patterns it serves so the zoned branch and the bare
        branch cannot disagree about whether a precision is a Firebird thing.

        The message names the field and the two sections that say it is not
        there, because the caller who wrote ``TIMESTAMP(4) WITH TIME ZONE`` has
        plainly been told by some other engine that this is legal DDL and needs to
        be told specifically why it is not. The same fact, from the rendering
        side, is in :meth:`_check_firebird_temporal_precision`.
        """
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
        """Refuse a type string that carries an ``UNSIGNED`` attribute.

        :meth:`_check_firebird_signed` closes the door on the way *in* — a
        declaration.  This closes it on the way *out*: a string.  The same field
        and the same loss in the other direction, and the reason this file
        already refuses a temporal ``precision`` string rather than reading one
        out of a production that has no place for it (see
        :meth:`_check_firebird_temporal_precision`) applies unchanged here: the
        branches below match on the word *in front of* the attribute, so without
        this ``parse_type("INTEGER UNSIGNED")`` would be a plain
        :class:`IntegerType` — a signed value object for a declaration that says
        otherwise, and ``==`` would call it equal to the signed column.

        Nothing here claims a catalog row is at stake: Firebird's §3.1 says it
        does not support an unsigned data type at all and §3.12's *Scalar Data
        Types Syntax* gives no numeric type an attribute, so no server can have
        written this string.  The branch guards the caller-supplied path —
        ``parse_type`` is a documented reader of hand-written DDL — and says so.
        Documentation-based, like the rest of this backend's signedness answer:
        no Firebird client library is installed here, so no statement could be
        sent to a server.
        """
        raise UnsupportedFeatureError(
            self.name,
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

    def parse_type(self, raw: str) -> DataType:
        """Parse a Firebird data-type declaration into the framework's concept.

        One concept in, one class out: every member of a concept's ``SPELLINGS``
        maps to that concept's class, so ``character varying`` is a
        ``VarCharType`` and never a ``CharType``.

        A string carrying an ``UNSIGNED`` attribute is **refused** rather than
        read, for the reason :meth:`_check_firebird_temporal_precision` gives for
        a temporal ``precision``: Firebird's grammar has nowhere to put either,
        and quietly dropping one would return a value object the string does not
        describe. See :meth:`_refuse_unsigned_type_string`.

        Every constructor below passes ``dialect=self``: a parsed type that
        cannot re-render is invisible to the schema differ's callers and to
        the round-trip sweep — asking ``parsed.dialect`` raises, and
        ``parsed.to_sql()`` raises with it — and every other backend binds
        the dialect at exactly this place, so a dialect-less return here is
        this backend's defect even when the parsed string happens to match.
        """
        stripped = raw.strip()
        upper = stripped.upper()

        if self._UNSIGNED_ATTRIBUTE.search(stripped):
            self._refuse_unsigned_type_string(stripped)

        if self._FB_TINYINT_TYPES.match(upper):
            return TinyIntType(dialect=self)

        # INT128 before the integer family. ``_FB_INTEGER_TYPES`` ends its
        # alternatives in ``\b``, so ``INT128`` does not match it — after ``INT``
        # comes ``1``, a word character, so there is no boundary — but the
        # ordering is deliberate rather than incidental: ``INT128`` is a
        # different column from ``INTEGER`` by 96 bits of range, and reading a
        # 128-bit column as a 32-bit one is not a spelling difference.
        int128 = self._FB_INT128_TYPES.match(upper)
        if int128:
            if not self._fb4_available():
                # INT128 arrived in Firebird 4.0, so a dialect targeting 3.0 has
                # no such type in its grammar and will not name one. The
                # declaration is kept verbatim instead of being answered with a
                # narrower integer, which would render a *different* column and
                # say nothing about why.
                return CustomType(dialect=self, raw=stripped)
            return FirebirdInt128Type(dialect=self)

        if self._FB_INTEGER_TYPES.match(upper):
            if upper.startswith("BIGINT") or upper.startswith("INT8"):
                return BigIntType(dialect=self)
            if upper.startswith("SMALLINT") or upper.startswith("INT2"):
                return SmallIntType(dialect=self)
            return IntegerType(dialect=self)

        # DECFLOAT before the decimal family. ``_FB_DECIMAL_TYPES`` also cannot
        # match it — its shortest alternative is ``DEC`` and the ``\b`` after it
        # fails on the ``F`` of ``FLOAT`` — so this is not a rescue for an
        # ordering bug; it is here because ``DECFLOAT`` is an exact decimal and
        # belongs with the decimals, and because ``DECFLOAT(16)`` must never be
        # read as ``DecimalType(precision=16)``, which is a *different* column
        # with a different scale rule.
        decfloat = self._FB_DECFLOAT_TYPES.match(upper)
        if decfloat:
            if not self._fb4_available():
                # DECFLOAT arrived in Firebird 4.0. Same reasoning as INT128
                # above: an older dialect's grammar has no such type, so the
                # declaration is kept verbatim rather than downgraded to
                # NUMERIC, which is a different column.
                return CustomType(dialect=self, raw=stripped)
            declared = decfloat.group(1)
            return FirebirdDecFloatType(
                dialect=self,
                precision=int(declared) if declared
                else self._FB_DECFLOAT_DEFAULT_PRECISION
            )

        if self._FB_FLOAT_TYPES.match(upper):
            if upper.startswith("DOUBLE"):
                return DoubleType(dialect=self)
            return FloatType(dialect=self)

        if self._FB_DECIMAL_TYPES.match(upper):
            nums = re.findall(r"\d+", stripped)
            if len(nums) >= 2:
                return DecimalType(dialect=self, precision=int(nums[0]), scale=int(nums[1]))
            if len(nums) == 1:
                return DecimalType(dialect=self, precision=int(nums[0]))
            return DecimalType(dialect=self)

        if self._FB_STRING_TYPES.match(upper):
            length_match = re.search(r"\((\d+)", stripped)
            length = int(length_match.group(1)) if length_match else None
            # A completion for an unsized word comes from
            # ``type_parameter_defaults`` where this dialect has one, and from
            # the one named constant where it has not — so the number a bare
            # word means is written down once and the parser and the formatters
            # cannot disagree about it. ``or`` rather than ``is not None``
            # deliberately, because that is the test the four branches below
            # have always used and ``CHAR(0)`` is not a Firebird declaration
            # anyway.
            char_length = self.type_parameter_defaults()["char"]["length"]
            varchar_length = self._FB_RENDERED_VARCHAR_LENGTH
            # CHARACTER VARYING is SQL's long form of VARCHAR — variable length.
            # Testing it before CHARACTER is what keeps the varying form from
            # falling into the fixed-length branch on "CHARACTER".
            if upper.startswith("CHARACTER VARYING") or upper.startswith("CHAR VARYING"):
                return VarCharType(dialect=self, length=length or varchar_length,
                                   spelling="character varying")
            if upper.startswith("VARCHAR"):
                return VarCharType(dialect=self, length=length or varchar_length)
            if upper.startswith("CHARACTER"):
                return CharType(dialect=self, length=length or char_length, spelling="character")
            if upper.startswith("CHAR"):
                return CharType(dialect=self, length=length or char_length)
            # Unreachable with the patterns above; the safe answer for any
            # character-family word added later.
            return TextType(dialect=self)

        if self._FB_BLOB_TEXT_TYPES.match(upper):
            # Firebird's own word for unbounded character data. It is a BLOB
            # carrying a sub-type, so it is text and not the BLOB concept.
            return TextType(dialect=self)

        if self._FB_BLOB_TYPES.match(upper):
            return BlobType(dialect=self)

        if self._FB_TEXT_TYPES.match(upper):
            return TextType(dialect=self)

        # Firebird 4.0's zoned date-time spellings, matched before the
        # DATE/TIMESTAMP/TIME family below — whose pattern stops at the first
        # word, and so used to read a zoned column back as the *unzoned*
        # concept. That was not a cosmetic loss: the schema differ compares
        # parsed types with ``!=``, so a column declared WITH TIME ZONE and a
        # column declared without it parsed equal and the zone was invisible.
        for pattern, zoned_class in self._FB_ZONED_TIME_TYPES:
            zoned = pattern.match(upper)
            if not zoned:
                continue
            # A precision is refused here, before anything else about the
            # declaration, because no Firebird ``TIME``/``TIMESTAMP`` carries one
            # — so ``TIMESTAMP(4) WITH TIME ZONE`` is not a Firebird type name at
            # all and answering with a class whose renderer would raise would leave
            # parsing and rendering disagreeing about the same string. Returning
            # ``zoned_class(precision=4)``, as this used to, made ``parse_type``
            # accept a declaration it could not render back.
            self._reject_temporal_precision(stripped, zoned.group(1))
            if not self._fb4_available():
                # A dialect targeting Firebird 3 has no such type in its
                # grammar, so it will not name one. The declaration is kept
                # verbatim instead — CustomType admits these four names as
                # multi-word built-ins — because returning the unzoned class
                # would render a *different* column and say nothing about why.
                return CustomType(dialect=self, raw=stripped)
            return zoned_class(dialect=self)

        # Same refusal for the bare spellings. ``_FB_DATE_TYPES`` stops at the
        # first word, so ``TIMESTAMP(4)`` used to match and the ``(4)`` was
        # discarded — a different column than the one that was named, read as if
        # it were the same. Checked before that pattern so the tail is seen.
        self._reject_temporal_precision(stripped, self._FB_TEMPORAL_PRECISION.match(upper))

        if self._FB_DATE_TYPES.match(upper):
            # TIMESTAMP must be tested before TIME: "TIMESTAMP".startswith("TIME")
            # is True, so the reversed order mis-parsed TIMESTAMP as TimeType.
            if upper.startswith("TIMESTAMP"):
                return DateTimeType(dialect=self)
            if upper.startswith("TIME"):
                return TimeType(dialect=self)
            if upper.startswith("DATE"):
                if upper.strip() == "DATE":
                    return DateType(dialect=self)
                return DateTimeType(dialect=self)
            return DateTimeType(dialect=self)

        if self._FB_BOOLEAN_TYPES.match(upper):
            return BooleanType(dialect=self)

        return CustomType(dialect=self, raw=stripped)
