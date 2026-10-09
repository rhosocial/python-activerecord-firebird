# src/rhosocial/activerecord/backend/impl/firebird/mixins/column_suggestion.py
"""Firebird's answer to "what does this Python type mean *as a column* here".

The sibling of :meth:`FirebirdTypeSupportMixin.suggested_data_types`, and a
different question from it. That one names the ``DataType`` a column is
**created** with; this one names the **column class** whose operations a field's
value carries. The two are deliberately separate objects -- a model decides
which storage a column gets and which operations its expressions may use, and
neither infers the other -- so a Firebird answer here says nothing about which
Firebird type the column will be declared as, and a version gate on that
declaration says nothing about the operations below.

Two entries are **:data:`UNSUPPORTED`**, and they are the whole reason this
table is not a copy of core's default. Both are measured facts about the two
servers this backend was verified against -- **Firebird 5.0.4** and
**Firebird 6.0.0** (``tests/config/firebird_scenarios.yaml``, ``firebird_5`` /
``firebird_6``) -- and neither is a version question, which is why they are
plain ``UNSUPPORTED`` rather than a branch on ``self.version``.

``dict`` -- no JSON functions at all
    ``JSON_VALUE`` / ``JSON_QUERY`` are an *open proposal* on Firebird
    (FirebirdSQL/firebird#5431, "SQL-compliant JSON functions", pending in the
    v6 roadmap), and no released server has them. Measured on both servers:
    ``JSON_EXTRACT`` answers ``-804 Function unknown`` and ``JSON_VALUE`` is
    unknown as well, and the arrow spellings the core's
    :class:`JSONAccessorMixin` renders for ``json_path`` (``->>``) and
    ``json_value`` (``->``) answer ``-104 Token unknown - ->``.
    ``JSON_ARRAY`` / ``JSON_OBJECT`` / ``JSON_ARRAYAGG`` / ``JSON_OBJECTAGG``
    do exist -- construction, not reading a path out of a document, which is
    the operation an annotated ``dict`` field actually needs.

    **The consequence, stated plainly:** a model field annotated ``dict`` **fails
    at model-definition time** on Firebird, with a
    :class:`~...expression.column_suggestions.ColumnTypeResolutionError` that
    names ``UseColumnType``. The escape hatch works -- the declaration is
    backend-independent -- but it buys a *text* column and nothing more: what
    the measurements do support on a ``BLOB SUB_TYPE TEXT`` document is whole-
    document equality (``doc = ?``, comparing the stored text) and reading it
    back through ``CAST(doc AS VARCHAR(4000)) = ?``. ``JSON_CONTAINS_PATH``,
    ``JSON_ARRAY_LENGTH`` and ``JSON_IS_VALID`` are all ``-804`` as well, so
    path, has-key, array-length and validity are not available at any nesting
    depth. A caller who declares ``UseColumnType(JSONColumn)`` here has bought
    a column whose *honest* operations are comparison and CAST.

``list`` / ``tuple`` / ``set`` / ``frozenset`` -- nothing to declare one with
    The plan row says "no array type", and the honest version of that sentence
    is worth more than the short one: **Firebird does have array columns** --
    §3.8 "Array Types" of the 2.5 / 4.0 / 5.0 references alike, declared as
    ``ARR_INT INTEGER [4]``, ``INTEGER [0:3, 0:3]`` for two dimensions, subscripts
    1-based -- and the language has had them since Firebird 2. What is missing is
    any way for *this framework* to declare or reach one:

    * Firebird's grammar makes the bounds part of the type --
      ``array_type: non_charset_simple_type '[' array_spec ']'``, with every
      dimension needing at least one integer -- while core's ``ArrayType``
      carries only ``dimensions``. There is no bound in the type to write and
      none this dialect may invent: writing ``INTEGER [1]`` would silently create
      a one-element column.
    * ``supports_array_constructor()`` and ``supports_array_access()`` are both
      ``False`` (see :class:`FirebirdArrayMixin`), and
      :meth:`FirebirdUnsupportedFeaturesMixin.format_array_expression` refuses
      rather than emitting the cross-vendor ``ARRAY[...]`` spelling Firebird's
      grammar does not have. Firebird reaches an array element with a subscript
      (``arr[1]``), which no core array operation expresses.

    So the answer is not "another column class" and not "the storage family
    (JSON text)" -- it is a definition-time failure, because every other answer
    would hand back a column whose declared operations cannot be rendered here.

What is **not** narrowed, and why
    ``ilike`` is the one operation this table refuses (below). Beyond that the
    surface is left alone on purpose. In particular ``length`` is *not*
    narrowed: Firebird's ``CHAR_LENGTH``/``OCTET_LENGTH`` both exist and count
    **characters for a column that declares a character set**. That the answer
    flips to bytes when the column declares none is a property of the column's
    charset -- a column attribute that the type string does not carry, measured
    as ``VARCHAR(5)`` rejecting 9 bytes with no ``CHARACTER SET`` and accepting
    them with ``CHARACTER SET UTF8`` (议题 F in ``data-type-system.md``). That
    belongs to the column *declaration*, so it is recorded here and **not**
    silently resolved by narrowing an operation that does work.
"""

import datetime
import decimal
import enum
import uuid
from typing import Any, Dict, FrozenSet, Set, Tuple, Type

from rhosocial.activerecord.backend.dialect.mixins import ColumnSuggestionMixin
from rhosocial.activerecord.backend.expression.column_suggestions import UNSUPPORTED
from rhosocial.activerecord.backend.expression.column_types import (
    BinaryColumn,
    BooleanColumn,
    ColumnBase,
    DateTimeColumn,
    DecimalColumn,
    FloatColumn,
    IntegerColumn,
    NumericColumn,
    StringColumn,
    UUIDColumn,
)


class FirebirdColumnSuggestionMixin(ColumnSuggestionMixin):
    """Firebird's full table, and the operations it refuses.

    Composed into :class:`~...impl.firebird.dialect.FirebirdDialect` next to
    :class:`FirebirdTypeSupportMixin`, so the two halves of the protocol sit
    side by side: that mixin answers *what the column is declared as*, this one
    answers *what the field's value can do*.

    **Every one of the protocol's eighteen entries is answered**, and an entry
    this backend cannot express answers
    :data:`~...expression.column_suggestions.UNSUPPORTED` rather than going
    missing: the difference between "Firebird has nothing for a ``dict``" and
    "nobody filled that cell in" is the difference between a decision a caller
    can act on and a hole, and only the first survives a rewrite of this file.

    **No cell changes with the dialect version**, and that is a finding rather
    than an omission. The two Firebird version gates this backend really has --
    ``BOOLEAN`` from 3.0 and ``TIMESTAMP WITH TIME ZONE`` from 4.0 -- are both
    statements about *storage*, and storage is the other mixin's question: below
    3.0 ``supports_data_type_boolean()`` is ``False`` and the ``BOOLEAN``
    formatter raises, and the zoned timestamp is
    :class:`~...impl.firebird.expression.FirebirdTimeStampTzType` rather than a
    different column class. A column class names an operation set, and Firebird's
    operations on a truth value, a whole number, a document or a timestamp do
    not change shape when the storage behind them widens. So
    :meth:`suggested_column_types` inherits core's method rather than
    overriding it with a branch that would have to invent a difference to look
    version-aware.

    The baseline cells carry the Firebird-specific notes inline below; the ones
    worth reading rather than scanning are ``str`` (charset decides
    chars-vs-bytes), ``bytes`` (the server will *not* refuse a string function
    on a binary BLOB), ``timedelta`` (there is no ``INTERVAL``) and
    ``datetime`` (``TIMESTAMP`` is Firebird's synonym for the *unzoned* type).
    """

    COLUMN_TYPE_SUGGESTIONS: Dict[Any, Type[ColumnBase]] = {
        bool: BooleanColumn,
        int: IntegerColumn,
        # `float` and `Decimal` are separated here, where core's dialect-less
        # default still answers NumericColumn for both: an amount that must add
        # up exactly is not one that may drift, and the two classes exist to say
        # so in the name a caller reads. The Firebird storage families behind
        # them (FLOAT, DECFLOAT from 4.0, NUMERIC/DEC) are the DDL side's
        # answer, not this one.
        float: FloatColumn,
        decimal.Decimal: DecimalColumn,
        str: StringColumn,
        # Firebird's binary storage is `BLOB SUB_TYPE BINARY`. Measured on 5.0.4
        # and 6.0.0: the string functions do NOT refuse it -- CHAR_LENGTH,
        # UPPER, SUBSTRING, POSITION, `||` and CAST all run and return bytes.
        # So the column layer must never lean on the server to catch a string
        # operation on a binary column; "a binary column cannot run string
        # functions" is false here, and the difference is byte-wise semantics
        # rather than an error.
        bytes: BinaryColumn,
        bytearray: BinaryColumn,
        # Firebird's DATE carries a time component, and TIME / TIMESTAMP are
        # exact temporal types; all four entries (date, time, datetime, and the
        # same datetime with a tzinfo) answer the one temporal column class,
        # whose operations -- comparison, EXTRACT, DATEADD/DATEDIFF -- are the
        # same across the three. The zone is the one thing that differs and it
        # is a storage fact: `TIMESTAMP` is Firebird's synonym for the WITHOUT
        # TIME ZONE type (see FirebirdTypeSupportMixin._LOSSY_SUBSTITUTIONS),
        # so a tz-aware field on this backend stores a local time unless the
        # author declares FirebirdTimeStampTzType, which is 4.0+ anyway.
        datetime.date: DateTimeColumn,
        datetime.time: DateTimeColumn,
        datetime.datetime: DateTimeColumn,
        # Firebird has no INTERVAL type; its own idiom for a duration is a
        # 64-bit count of 1/10000-second units, which is what the server's date
        # arithmetic uses internally. The driver also refuses a Python timedelta
        # outright, so the value layer has to bind a number regardless -- a
        # fact about binding, and no reason to refuse the entry here.
        datetime.timedelta: NumericColumn,
        # Equality and IN only, which is the portable guarantee set for UUID;
        # Firebird has no UUID function and does not need one. `CHAR(16)
        # CHARACTER SET OCTETS` (or 36 hex characters) is the DDL side's choice.
        uuid.UUID: UUIDColumn,
        # UNSUPPORTED: no JSON functions on any released server. See the module
        # docstring for the measured errors and what an explicit declaration
        # buys instead.
        dict: UNSUPPORTED,
        # UNSUPPORTED: Firebird's array columns cannot be declared from
        # ArrayType (bounds are part of the type) and the array operations are
        # refused by format_array_expression. See the module docstring.
        list: UNSUPPORTED,
        tuple: UNSUPPORTED,
        set: UNSUPPORTED,
        frozenset: UNSUPPORTED,
        # Firebird has no enum type: a set of labels is VARCHAR(n) plus a CHECK
        # constraint, and the CHECK is what enforces it. The column class is the
        # string one because that is what the value compares and sorts as.
        enum.Enum: StringColumn,
    }

    #: Operations Firebird cannot honour, as ``{(column class name, operation
    #: name)}`` -- the protocol's own granularity, so a contract test can check
    #: each name with ``hasattr`` against the class it names.
    #:
    #: Both members of each pair are spelled the way the protocol requires: the
    #: column class by ``type(column).__name__`` and the operation by the public
    #: method that provides it. Nothing here is inferred from a version -- every
    #: entry is an absence in the language itself, present on 5.0.4 and 6.0.0
    #: alike.
    UNAVAILABLE_COLUMN_OPERATIONS: FrozenSet[Tuple[str, str]] = frozenset(
        {
            # ILIKE has no Firebird spelling: measured `-104 Token unknown` on
            # 5.0.4 and 6.0.0. The two dialect-native substitutes are
            # `CONTAINING` (case-insensitive substring) and, from 4.0,
            # `SIMILAR TO` -- and `SIMILAR TO` is SQL wildcard syntax (`%`, `_`),
            # not a regular expression, so neither is "ilike with another name".
            # `like` stays available: LIKE is measured working on both servers.
            ("StringColumn", "ilike"),
            # The whole JSON path surface, unreachable because the two entries
            # the framework would resolve a `dict` or `list` through are
            # UNSUPPORTED above -- but an author who declares
            # UseColumnType(JSONColumn) gets this class, so the narrowing is
            # stated rather than implied. Measured: `->>` / `->` answer
            # `-104 Token unknown - ->`, and the function route answers
            # `-804 Function unknown` on both servers.
            ("JSONColumn", "json_path"),
            ("JSONColumn", "json_value"),
            # The array surface, for the same reason and against the same
            # evidence as the `list` entry: Firebird has no UNNEST and no
            # ARRAY[...] constructor, so these two operations reach
            # format_array_expression, which this dialect refuses rather than
            # rendering SQL Firebird's grammar does not have. A Firebird array
            # column, if declared by name through CustomType, is read with a
            # subscript -- which no core array operation expresses.
            ("ArrayColumn", "array_length"),
            ("ArrayColumn", "unnest"),
        }
    )

    def supports_column_operation(self, column_name: str, op: str) -> bool:
        """Whether *op* is available on *column_name* here.

        Refusals are enumerated in
        :attr:`UNAVAILABLE_COLUMN_OPERATIONS` and everything else inherits
        core's "available" answer. An exhaustive set rather than a handful of
        ``if`` branches so that adding a narrowing is a visible edit to the
        evidence, and so a test can assert the whole set at once -- a narrowing
        nobody asserted is the one this mechanism exists to prevent.

        Args:
            column_name: ``type(column).__name__`` -- ``"StringColumn"``.
            op: The public method name -- ``"ilike"``.

        Returns:
            False for a pair in
            :attr:`UNAVAILABLE_COLUMN_OPERATIONS`, True otherwise.
        """
        return (column_name, op) not in self.UNAVAILABLE_COLUMN_OPERATIONS

    @property
    def unsupported_column_entries(self) -> Set[Any]:
        """The entries this table answers :data:`UNSUPPORTED` for.

        A reader for callers that want to report the whole picture rather than
        one field's failure: it reads the table, so it cannot drift from it.
        """
        return {entry for entry, column_class in self.suggested_column_types().items() if column_class is UNSUPPORTED}


__all__ = ["FirebirdColumnSuggestionMixin"]