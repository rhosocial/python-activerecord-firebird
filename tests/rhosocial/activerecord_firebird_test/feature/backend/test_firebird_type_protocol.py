# tests/rhosocial/activerecord_firebird_test/feature/backend/test_firebird_type_protocol.py
"""
Firebird type protocol conformance tests.

Verifies the two-level data-type contract between the core ``DataType``
system and the Firebird backend:

- ``supports_data_type_<name>`` / ``format_data_type_<name>`` 1:1
  correspondence on ``FirebirdDialect``, and that ``INT`` has no family of
  its own because it is a spelling of ``integer``;
- ``supports_data_types()`` merges the ``firebird_*`` namespaced family
  with the core family;
- ``suggested_data_types()`` values are real ``DataType`` classes this dialect
  can render, its keys are disjoint from the supported keys, and **every core
  concept is either rendered or suggested** — silence is the one answer D9
  does not allow;
- the spelling gates: a word Firebird writes is accepted and normalised to
  Firebird's word, a word it does not write is refused by name, and the
  concept's default spelling always renders;
- the two zoned **core** concepts, ``timetz`` and ``timestamptz``: Firebird's
  ``TIME``/``TIMESTAMP`` are its unzoned types, so neither is rendered and both
  name the unzoned concept as their substitute — while Firebird's *own* zoned
  columns stay reachable under ``firebird_timetz`` / ``firebird_timestamptz``;
- the date-time ``precision`` fields, which no Firebird ``TIME``/``TIMESTAMP``
  declaration can carry and which are therefore refused by name, in both the core
  and the Firebird-named concepts, and in ``parse_type``;
- ``FirebirdTypeSupport`` — the Protocol that states the shape of the
  ``firebird_*`` family the Firebird dialect owns;
- the base classes each Firebird type is anchored to, with ``DECFLOAT`` on the
  exact-decimal side and ``INT128`` deliberately on none of the integer widths;
- Firebird-specific range checks live in the formatters (DECIMAL/FLOAT
  precision) and ``dialect`` is the first positional parameter everywhere;
- **identity fields are honoured or refused, never dropped**: the sweep over
  every rendered formatter must find an *empty* set — ``unsigned`` is refused by
  name everywhere an integer renders, ``BLOB SUB_TYPE`` carries an empty
  ``PARAMETERS`` because a sub-type tag has no signedness,
  ``FirebirdFloatType``'s ``precision`` reaches the rendered ``FLOAT(bin_prec)``,
  and every date-time ``precision`` is refused by name because Firebird's grammar
  has no argument for it. There is no allowlist of known-unread fields;
- the two Firebird 4 catalog codes that were missing from ``FB_FIELD_TYPES``
  (24/25 ``DECFLOAT``, 26 ``INT128``), end to end;
- ``dialect_options`` forwards through construction and participates in
  equality.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.dialect.mixins.ddl_type import DDLTypeMixin
from rhosocial.activerecord.backend.dialect.protocols import DataTypeSupport
from rhosocial.activerecord.backend.expression.types import (
    BigIntType,
    BlobType,
    BooleanType,
    CharType,
    CustomType,
    DataType,
    DateTimeType,
    DecimalType,
    DoubleType,
    FloatType,
    IntegerType,
    RealType,
    SmallIntType,
    TextType,
    TimeType,
    TimestampType,
    TinyIntType,
    VarCharType,
)
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.mixins.types import (
    FirebirdTypeSupportMixin,
)
from rhosocial.activerecord.backend.impl.firebird.expression.types import (
    FirebirdBlobSubType,
    FirebirdCharType,
    FirebirdDecimalType,
    FirebirdDecFloatType,
    FirebirdDoubleType,
    FirebirdFloatType,
    FirebirdInt128Type,
    FirebirdTimeStampTzType,
    FirebirdTimeTzType,
    FirebirdTimeWithoutTimeZoneType,
    FirebirdVarCharType,
)
from rhosocial.activerecord.backend.impl.firebird.protocols import (
    FirebirdTypeSupport,
)


@pytest.fixture
def dialect():
    return FirebirdDialect((4, 0, 0))


@pytest.fixture
def dialect_3():
    return FirebirdDialect((3, 0, 0))


class TestSupportFormatCorrespondence:
    """Every format_data_type_<name> has supports_data_type_<name>, 1:1."""

    def test_format_family_equals_supports_family(self, dialect):
        format_names = {
            member[len("format_data_type_"):]
            for member in dir(FirebirdDialect)
            if member.startswith("format_data_type_")
        }
        support_names = {
            member[len("supports_data_type_"):]
            for member in dir(FirebirdDialect)
            if member.startswith("supports_data_type_")
        }
        assert format_names, "FirebirdDialect must implement format_data_type_* members"
        assert format_names == support_names

    def test_int_has_no_family_of_its_own(self, dialect):
        """``INT`` is the second spelling of the ``integer`` concept.

        One concept, one class, one dispatch key: a ``format_data_type_int``
        alongside ``format_data_type_integer`` would make ``INT`` a type the
        framework models separately from ``INTEGER`` when it is the same storage
        written two ways.
        """
        assert not hasattr(FirebirdDialect, "format_data_type_int")
        assert not hasattr(FirebirdDialect, "supports_data_type_int")
        assert dialect.format_data_type(IntegerType())[0] == "INTEGER"

    def test_supports_data_types_covers_every_formatter(self, dialect):
        format_names = {
            member[len("format_data_type_"):]
            for member in dir(FirebirdDialect)
            if member.startswith("format_data_type_")
        }
        supported = dialect.supports_data_types()
        assert set(supported) == format_names

    def test_supports_data_types_returns_classes(self, dialect):
        for name, klass in dialect.supports_data_types().items():
            assert isinstance(klass, type), name
            assert issubclass(klass, DataType), name

    def test_inherits_mixin_scan_implementation(self, dialect):
        assert FirebirdDialect.supports_data_types is DDLTypeMixin.supports_data_types


class TestSupportsDataTypesMapping:
    """supports_data_types() merges firebird_* namespaced and core entries."""

    def test_includes_firebird_namespaced_entries(self, dialect):
        supported = dialect.supports_data_types()
        assert "firebird_decimal" in supported
        assert "firebird_float" in supported
        assert "firebird_double" in supported
        assert "firebird_blob_subtype" in supported
        assert "firebird_timestamptz" in supported
        assert "firebird_timetz" in supported
        assert "firebird_decfloat" in supported
        assert "firebird_int128" in supported

    def test_includes_core_entries(self, dialect):
        supported = dialect.supports_data_types()
        assert "integer" in supported
        assert supported["integer"] is IntegerType
        assert "varchar" in supported
        assert "decimal" in supported
        assert "float" in supported
        assert "double" in supported
        assert "boolean" in supported
        assert "date" in supported
        assert "timestamp" in supported
        assert "text" in supported
        assert "blob" in supported
        assert "uuid" in supported

    def test_per_type_support_methods_are_truthful(self, dialect):
        supported = dialect.supports_data_types()
        for name in supported:
            checker = getattr(dialect, f"supports_data_type_{name}")
            assert checker() is True, name


class TestSuggestedDataTypes:
    """suggested_data_types(): real classes, disjoint from supported keys."""

    def test_returns_dict(self, dialect):
        result = dialect.suggested_data_types()
        assert isinstance(result, dict)

    def test_values_are_data_type_classes(self, dialect):
        suggestions = dialect.suggested_data_types()
        for key, klass in suggestions.items():
            assert isinstance(klass, type), key
            assert issubclass(klass, DataType), key

    def test_keys_disjoint_from_supported(self, dialect):
        suggestions = dialect.suggested_data_types()
        supported = dialect.supports_data_types()
        assert not (set(suggestions) & set(supported))

    def test_values_name_a_type_this_dialect_renders(self, dialect):
        """A suggestion that cannot be written is worse than no suggestion.

        It would trade a clear "not supported here" for one whose advice does not
        work.
        """
        supported = dialect.supports_data_types()
        for key, klass in dialect.suggested_data_types().items():
            assert klass.name in supported, f"{key} -> {klass.__name__}"

    def test_zoned_core_concepts_are_substituted_not_rendered(self, dialect):
        """``timetz`` / ``timestamptz``: no formatter, a named substitute.

        Firebird *has* zoned time and zoned timestamps — §3.1 Table 3.1 lists
        ``TIME WITH TIME ZONE`` (6 bytes) and ``TIMESTAMP WITH TIME ZONE`` (10
        bytes), both Firebird 4.0+. What it does not have is any way to spell them
        from the generic concepts, because the short words are the **unzoned**
        types: §3.4, *"TIME and TIMESTAMP are synonymous to their respective
        WITHOUT TIME ZONE data types."*

        So a ``format_data_type_timestamptz`` returning ``"TIMESTAMP"`` was not a
        coarser rendering of the zoned concept — it rendered a different column,
        one that discards the zone offset, while reporting success. The substitute
        names the unzoned concept, which is what this backend renders when the
        zone does not matter.
        """
        for name, substitute in (("timetz", TimeType), ("timestamptz",
                                                         TimestampType)):
            assert not hasattr(FirebirdDialect, f"format_data_type_{name}")
            assert not hasattr(FirebirdDialect, f"supports_data_type_{name}")
            assert name not in dialect.supports_data_types()
            assert dialect.suggested_data_types()[name] is substitute

    def test_the_substitution_does_not_collide_with_a_formatter(self, dialect):
        """D9: rendered and suggested keys are disjoint.

        A key that appeared in both would say "I render this" and "use that
        instead" at once. The mechanical half is
        :meth:`test_keys_disjoint_from_supported`; this states the intent for the
        two keys that could plausibly have gone either way.
        """
        rendered = set(dialect.supports_data_types())
        for name in ("timetz", "timestamptz"):
            assert name in dialect.suggested_data_types()
            assert name not in rendered

    def test_the_zoned_columns_are_reachable_under_their_firebird_names(self,
                                                                       dialect):
        """The substitution is not a claim that Firebird lacks zoned types.

        It is reached instead through the concepts this dialect owns:
        ``firebird_timetz`` and ``firebird_timestamptz`` render Firebird's own
        words. Those are also what ``parse_type`` answers with for
        ``RDB$FIELD_TYPE`` 28 and 29, which is the whole reason the generic
        concepts are substitutes — a ``timestamptz`` renderer would emit words
        that parse straight back into a different class.
        """
        assert dialect.format_data_type(FirebirdTimeTzType()) == (
            "TIME WITH TIME ZONE", (),
        )
        assert dialect.format_data_type(FirebirdTimeStampTzType()) == (
            "TIMESTAMP WITH TIME ZONE", (),
        )
        assert type(dialect.parse_type("TIMESTAMP WITH TIME ZONE")) is (
            FirebirdTimeStampTzType
        )
        assert type(dialect.parse_type("TIME WITH TIME ZONE")) is FirebirdTimeTzType

    def test_the_substituted_type_carries_no_precision(self, dialect):
        """``precision`` on the substitute is refused, not dropped.

        ``TimestampType`` / ``TimeType`` reach
        :meth:`_check_firebird_temporal_precision` in the formatter, so a
        ``TimestampTzType(precision=6)`` is answered twice and loudly: first
        "this dialect does not render ``timestamptz``, it suggests
        ``TimestampType``", then — once the caller follows the advice with the
        precision still attached — "a ``TIMESTAMP`` takes no precision argument".
        """
        for cls in (TimeType, TimestampType, DateTimeType):
            assert dialect.format_data_type(cls()) == dialect.format_data_type(
                cls()
            )
            with pytest.raises(UnsupportedFeatureError, match="precision"):
                dialect.format_data_type(cls(precision=6))

    def test_json_suggested_as_text(self, dialect):
        suggestions = dialect.suggested_data_types()
        assert "json" in suggestions
        assert suggestions["json"] is TextType

    def test_jsonb_suggested_as_text(self, dialect):
        suggestions = dialect.suggested_data_types()
        assert "jsonb" in suggestions
        assert suggestions["jsonb"] is TextType

    def test_enum_suggested_as_varchar(self, dialect):
        suggestions = dialect.suggested_data_types()
        assert "enum" in suggestions
        assert suggestions["enum"] is VarCharType

    def test_xml_suggested_as_text(self, dialect):
        """Firebird has no XML type — no document model, no XPath, no schema
        validation — so the document is stored as text."""
        suggestions = dialect.suggested_data_types()
        assert "xml" in suggestions
        assert suggestions["xml"] is TextType

    def test_array_is_not_suggested_as_a_blob(self, dialect):
        """Firebird *has* array column types, so a BLOB is not what it stores.

        The language reference has a section on them — "3.8. Array Types", in
        the 2.5, 4.0 and 5.0 references alike — and shows ``ARR_INT INTEGER
        [4]``, with ``INTEGER [0:3, 0:3]`` for two dimensions. The value is
        kept in a BLOB sub-type, but the *type* is an array, so suggesting
        ``BlobType`` was a false statement about the engine rather than a
        fallback.
        """
        suggestions = dialect.suggested_data_types()
        assert "array" in suggestions
        assert suggestions["array"] is not BlobType

    def test_array_falls_back_to_the_named_declaration(self, dialect):
        """The substitute is ``CustomType`` — the same door Oracle uses.

        It cannot be rendered here, and the reason is the bounds: Firebird's
        grammar makes them part of the type (``array_type:
        non_charset_simple_type '[' array_spec ']'``, every dimension needing at
        least one integer) while ``ArrayType`` carries only a dimension count.
        Writing ``INTEGER [1]`` would silently create a one-element column, so
        the declaration is written by name instead — and ``custom`` is a key
        this dialect really renders, which is what the D9 substitute contract
        requires.
        """
        from rhosocial.activerecord.backend.expression.types import CustomType

        suggestions = dialect.suggested_data_types()
        assert suggestions["array"] is CustomType
        assert CustomType.name in dialect.supports_data_types()
        assert dialect.format_data_type(CustomType(raw="T")) == ("T", ())

    def test_array_capability_flag_agrees_with_the_type_table(self, dialect):
        """The flag and the table must not contradict each other.

        ``supports_array_type()`` is ``True`` because the feature exists, so the
        table must not claim Firebird substitutes a BLOB for it; and because the
        table no longer claims a substitute, D9's "no silence" is satisfied by
        naming the door a caller has to write the declaration through.
        """
        assert dialect.supports_array_type() is True
        assert "array" in dialect.suggested_data_types()
        assert "array" not in dialect.supports_data_types()

    def test_interval_suggested_as_bigint(self, dialect):
        """Firebird has no INTERVAL type; its own idiom for a duration is a
        64-bit integer counting 1/10000-second units."""
        suggestions = dialect.suggested_data_types()
        assert "interval" in suggestions
        assert suggestions["interval"] is BigIntType


class TestEveryCoreConceptIsDeclared:
    """D9 — silence is the one answer that is not allowed."""

    @staticmethod
    def _core_concepts():
        import inspect
        found, seen, stack = {}, {DataType}, [DataType]
        while stack:
            klass = stack.pop()
            if klass in seen:
                continue
            seen.add(klass)
            stack.extend(klass.__subclasses__())
            if (
                klass is not DataType
                and not inspect.isabstract(klass)
                and klass.__module__.startswith(
                    "rhosocial.activerecord.backend.expression.types"
                )
            ):
                found[klass.name] = klass
        return found

    def test_every_core_concept_is_rendered_or_suggested(self, dialect):
        supported = dialect.supports_data_types()
        suggested = dialect.suggested_data_types()
        undeclared = sorted(
            name
            for name in self._core_concepts()
            if name not in supported and name not in suggested
        )
        assert not undeclared, f"undeclared core concepts: {undeclared}"


class TestSpellingGates:
    """A spelling Firebird does not write is an error, not a silent rewrite."""

    @pytest.mark.parametrize("cls,spelling", [
        (BigIntType, "int8"),
        (SmallIntType, "int2"),
        (BooleanType, "bool"),
        (BlobType, "bytea"),
        (TextType, "clob"),
    ])
    def test_spelling_firebird_does_not_write_is_refused(self, dialect, cls,
                                                          spelling):
        with pytest.raises(TypeError, match=spelling):
            dialect.format_data_type(cls(dialect, spelling=spelling))

    @pytest.mark.parametrize("cls,spelling", [
        (IntegerType, "integer"),
        (IntegerType, "int"),
        (BigIntType, "bigint"),
        (SmallIntType, "smallint"),
        (TinyIntType, "tinyint"),
        (TinyIntType, "int1"),
        (CharType, "char"),
        (CharType, "character"),
        (VarCharType, "varchar"),
        (VarCharType, "character varying"),
        (TextType, "text"),
        (DecimalType, "decimal"),
        (DecimalType, "numeric"),
        (DecimalType, "dec"),
        (DoubleType, "double"),
        (DoubleType, "double precision"),
        (BooleanType, "boolean"),
        (BlobType, "blob"),
    ])
    def test_spelling_firebird_does_write_is_accepted(self, dialect, cls, spelling):
        sql, _ = dialect.format_data_type(cls(dialect, spelling=spelling))
        assert sql

    @pytest.mark.parametrize("cls", [
        IntegerType, TinyIntType, SmallIntType, BigIntType,
        CharType, VarCharType, TextType, DecimalType, DoubleType,
        BooleanType, BlobType,
    ])
    def test_the_default_spelling_always_renders(self, dialect, cls):
        """A type built the ordinary way must work here.

        A dialect may normalise the default spelling to its own word; refusing it
        would make the concept unconstructible on this backend, and the refusal
        would say nothing about how to proceed.
        """
        assert cls(dialect).spelling == cls.SPELLINGS[0]
        assert dialect.format_data_type(cls(dialect))[0]

    def test_normalised_spelling_still_renders_firebirds_word(self, dialect):
        """``INT`` is Firebird's own abbreviation and it renders ``INTEGER``."""
        assert dialect.format_data_type(IntegerType(dialect, spelling="int")) == (
            "INTEGER", (),
        )
        assert dialect.format_data_type(
            VarCharType(dialect, length=10, spelling="character varying")
        ) == ("VARCHAR(10)", ())
        assert dialect.format_data_type(
            CharType(dialect, length=4, spelling="character")
        ) == ("CHAR(4)", ())

    def test_tinyint_is_widened_not_refused(self, dialect):
        """Firebird has no 1-byte integer, so the concept becomes the next size
        that exists rather than an error."""
        for spelling in TinyIntType.SPELLINGS:
            assert dialect.format_data_type(
                TinyIntType(dialect, spelling=spelling)
            ) == ("SMALLINT", ())


class TestFirebirdTypeSupportProtocol:
    """D9 — the types Firebird owns state their own shape."""

    def test_dialect_satisfies_it(self, dialect):
        assert isinstance(dialect, FirebirdTypeSupport)

    def test_protocol_declares_every_firebird_owned_name(self):
        protocol_formats = {
            member[len("format_data_type_"):]
            for member in vars(FirebirdTypeSupport)
            if member.startswith("format_data_type_firebird_")
        }
        dialect_formats = {
            member[len("format_data_type_"):]
            for member in dir(FirebirdDialect)
            if member.startswith("format_data_type_firebird_")
        }
        assert protocol_formats == dialect_formats

    def test_protocol_declares_the_matching_support_flags(self):
        protocol_supports = {
            member[len("supports_data_type_"):]
            for member in vars(FirebirdTypeSupport)
            if member.startswith("supports_data_type_firebird_")
        }
        protocol_formats = {
            member[len("format_data_type_"):]
            for member in vars(FirebirdTypeSupport)
            if member.startswith("format_data_type_firebird_")
        }
        assert protocol_supports == protocol_formats

    def test_protocol_is_a_data_type_protocol(self):
        assert issubclass(FirebirdTypeSupport, DataTypeSupport)

    def test_protocol_does_not_shadow_the_real_implementations(self, dialect):
        """A dialect's bases resolve left to right, so a Protocol that restated
        the concrete members with empty bodies ahead of the mixin would make
        every one of them answer ``None``."""
        assert dialect.suggested_data_types() is not None
        assert dialect.format_data_type(FirebirdInt128Type()) == ("INT128", ())


class TestFirebirdDecFloatIsAnExactDecimal:
    """``DECFLOAT`` is IEEE 754 decimal — exact, like ``NUMERIC``, not binary
    approximate like ``FLOAT``."""

    def test_is_a_decimal(self):
        assert issubclass(FirebirdDecFloatType, DecimalType)

    def test_is_not_an_approximate_numeric(self):
        """Putting it under ``FloatType`` would put it on the wrong side of the
        line that matters: ``DECFLOAT`` holds ``0.1`` exactly, and a binary
        float does not."""
        assert not issubclass(FirebirdDecFloatType, FloatType)

    def test_an_explicit_width_still_renders_that_width(self, dialect):
        assert dialect.format_data_type(FirebirdDecFloatType(precision=16)) == (
            "DECFLOAT(16)", (),
        )
        assert dialect.format_data_type(FirebirdDecFloatType(precision=34)) == (
            "DECFLOAT(34)", (),
        )

    def test_the_default_width_is_the_documented_34(self, dialect):
        """§3.2.2.1, *DECFLOAT*: *"Precision in decimal digits, either 16 or 34.
        Default is 34."*

        A bare ``DECFLOAT`` is legal Firebird, so "what does it mean" has exactly
        one documented answer, and this constructor used to say 16 while
        ``FirebirdDialect.parse_type("DECFLOAT")`` said 34. Two answers on one
        backend is the same defect as two answers to "what does ``DECFLOAT(16)``
        mean", so the constructor follows the reference.
        """
        assert FirebirdDecFloatType(dialect=dialect).to_sql() == ("DECFLOAT(34)", ())

    def test_the_constructor_and_parse_type_agree_on_a_bare_decfloat(self,
                                                                    dialect):
        """One declaration, one answer, whichever way it is reached."""
        assert FirebirdDecFloatType().precision == dialect.parse_type(
            "DECFLOAT"
        ).precision == 34

    def test_equality_is_unchanged_by_the_base_class(self):
        """``DECFLOAT`` has no scale, so the base's ``(precision, scale,
        unsigned)`` declaration must not leak in and make two identical columns
        differ.

        The base grew a third field when ``unsigned`` arrived on core's exact and
        approximate numerics, and ``FirebirdDecFloatType`` — a fixed-precision
        decimal with no scale *and* no signedness to declare, since Firebird has
        neither concept — still narrows the tuple to the one field that is its
        own. That is the third honest answer to the paradigm rule and the reason it
        is an answer at all: **the field does not belong to this concept, so it
        must not be in ``PARAMETERS`` at all.**
        """
        assert DecimalType.PARAMETERS == ("precision", "scale", "unsigned")
        assert FirebirdDecFloatType.PARAMETERS == ("precision",)
        assert FirebirdDecFloatType(precision=16).identity() == (16,)
        assert FirebirdDecFloatType(precision=16).scale is None
        assert FirebirdDecFloatType(precision=16) == FirebirdDecFloatType(precision=16)
        assert FirebirdDecFloatType(precision=16) != FirebirdDecFloatType(precision=34)
        assert hash(FirebirdDecFloatType(precision=16)) == hash(
            FirebirdDecFloatType(precision=16)
        )

    def test_no_scale_is_reported(self):
        assert FirebirdDecFloatType(precision=34).scale is None


class TestFirebirdInt128StaysOnDataType:
    """``INT128`` is 128-bit; core's integer family stops at 64."""

    def test_is_not_a_bigint(self):
        assert not issubclass(FirebirdInt128Type, BigIntType)
        assert not issubclass(FirebirdInt128Type, IntegerType)

    def test_is_a_data_type(self):
        assert issubclass(FirebirdInt128Type, DataType)

    def test_docstring_states_why(self):
        """D7 — sitting on ``DataType`` is legitimate but must be written down."""
        doc = FirebirdInt128Type.__doc__ or ""
        assert "BigIntType" in doc and "128" in doc


class TestDialectIsTheFirstConstructorArgument:
    """``dialect`` is the first positional parameter of every ``DataType``.

    A signature that puts the semantically interesting field first fails
    *silently*: the dialect object is stored as the precision, and the error only
    shows up when the column is rendered.
    """

    @pytest.mark.parametrize("cls,kwargs,attr,value", [
        (FirebirdDecFloatType, {"precision": 34}, "precision", 34),
    ])
    def test_dialect_first_lands_in_the_right_field(self, cls, kwargs, attr, value):
        instance = cls(FirebirdDialect((4, 0, 0)), **kwargs)
        assert getattr(instance, attr) == value
        assert instance.dialect is not None

    @pytest.mark.parametrize("cls", [
        FirebirdCharType,
        FirebirdVarCharType,
        FirebirdTimeStampTzType,
        FirebirdTimeTzType,
        FirebirdTimeWithoutTimeZoneType,
        FirebirdDecimalType,
        FirebirdFloatType,
        FirebirdDoubleType,
        FirebirdBlobSubType,
        FirebirdInt128Type,
    ])
    def test_dialect_only_classes_keep_the_dialect(self, cls):
        instance = cls(FirebirdDialect((4, 0, 0)))
        assert instance.dialect is not None
        assert instance.to_sql()[0]


class TestDialectRangeValidation:
    """Dialect-specific range checks live inside the formatters."""

    def test_decimal_precision_over_18_raises(self, dialect):
        data_type = DecimalType(precision=19, scale=2)
        with pytest.raises(ValueError, match="between 1 and 18"):
            dialect.format_data_type(data_type)

    def test_decimal_scale_over_18_raises(self, dialect):
        data_type = DecimalType(precision=18, scale=19)
        with pytest.raises(ValueError, match="between 0 and 18"):
            dialect.format_data_type(data_type)

    def test_decimal_scale_over_precision_raises(self, dialect):
        data_type = DecimalType(precision=10, scale=11)
        with pytest.raises(ValueError, match="cannot exceed"):
            dialect.format_data_type(data_type)

    def test_decimal_valid_range_renders(self, dialect):
        sql, _ = dialect.format_data_type(DecimalType(precision=18, scale=2))
        assert sql == "DECIMAL(18, 2)"

    def test_float_precision_outside_1_to_53_raises(self, dialect):
        """``bin_prec`` is 1..53 — §3.2.1.1, Table 3.2.

        This test used to pin 1..24 and assert that ``FloatType(precision=25)``
        raised. 25 is not out of bounds: it is the documented *double precision*
        half ("25 - 53: 64-bit double precision"), so the old assertion refused a
        column Firebird declares while
        :meth:`TestFirebirdFloatHonoursItsPrecision` — checking the same range
        against ``FirebirdFloatType`` — accepted it. One Firebird type, two
        answers, and the stricter one was simply wrong.
        """
        for precision in (0, 54):
            with pytest.raises(ValueError, match="between 1 and 53"):
                dialect.format_data_type(FloatType(precision=precision))

    def test_float_double_precision_half_renders(self, dialect):
        """25..53 is the 64-bit half and is written like any other."""
        assert dialect.format_data_type(FloatType(precision=25)) == ("FLOAT(25)", ())
        assert dialect.format_data_type(FloatType(precision=53)) == ("FLOAT(53)", ())

    def test_float_single_precision_half_renders(self, dialect):
        sql, _ = dialect.format_data_type(FloatType(precision=24))
        assert sql == "FLOAT(24)"

    def test_float_no_precision_renders(self, dialect):
        sql, _ = dialect.format_data_type(FloatType(dialect))
        assert sql == "FLOAT"

    def test_float_precision_is_refused_below_firebird_4(self, dialect_3):
        """CORE-6109, and the reason the core path is gated at all.

        The 3.0 reference's declaration syntax is ``FLOAT | DOUBLE PRECISION``
        with no argument; on 4.0 ``FLOAT(bin_prec)`` arrived counting *binary*
        digits where it had counted *decimal* ones. So ``FLOAT(10)`` names two
        different columns either side of that boundary, and the generic
        ``FloatType`` renderer refuses the argument below 4.0 exactly as
        ``FirebirdFloatType`` does.
        """
        with pytest.raises(UnsupportedFeatureError, match="FLOAT"):
            dialect_3.format_data_type(FloatType(precision=24))

    def test_both_float_renderers_agree_on_every_precision(self, dialect,
                                                            dialect_3):
        """The defect: two renderers, one Firebird type, two answers.

        Checked against the whole accepted range and both sides of the version
        boundary rather than case by case, because the way this failed was a
        single case disagreeing — ``FloatType(precision=25)`` raising while
        ``FirebirdFloatType(precision=25)`` rendered.
        """
        for precision in (1, 12, 24, 25, 40, 53):
            assert dialect.format_data_type(FloatType(precision=precision)) == (
                dialect.format_data_type(
                    FirebirdFloatType(precision=precision)
                )
            )
        for precision in (0, 54):
            with pytest.raises(ValueError):
                dialect.format_data_type(FloatType(precision=precision))
            with pytest.raises(ValueError):
                dialect.format_data_type(FirebirdFloatType(precision=precision))
        for precision in (24, 53):
            with pytest.raises(UnsupportedFeatureError):
                dialect_3.format_data_type(FloatType(precision=precision))
            with pytest.raises(UnsupportedFeatureError):
                dialect_3.format_data_type(FirebirdFloatType(precision=precision))
        # Bare FLOAT means the same thing in both renderers and needs no gate:
        # 32-bit single precision, 4 bytes, in every Firebird version.
        assert dialect_3.format_data_type(FloatType()) == ("FLOAT", ())
        assert dialect_3.format_data_type(FloatType()) == dialect_3.format_data_type(
            FirebirdFloatType()
        )


class TestFB4TypeGating:
    """FB4-gated types must render on 4.0+ and raise on older."""

    def test_fb4_types_render_on_4_0(self, dialect):
        assert dialect.format_data_type(FirebirdTimeStampTzType()) == (
            "TIMESTAMP WITH TIME ZONE", ()
        )
        assert dialect.format_data_type(FirebirdTimeTzType()) == (
            "TIME WITH TIME ZONE", ()
        )
        assert dialect.format_data_type(FirebirdDecFloatType(precision=16)) == (
            "DECFLOAT(16)", ()
        )
        assert dialect.format_data_type(FirebirdDecFloatType(precision=34)) == (
            "DECFLOAT(34)", ()
        )
        assert dialect.format_data_type(FirebirdInt128Type()) == (
            "INT128", ()
        )

    def test_fb4_types_raise_on_3_0(self, dialect_3):
        for data_type in (
            FirebirdTimeStampTzType(),
            FirebirdTimeTzType(),
            FirebirdDecFloatType(),
            FirebirdInt128Type(),
        ):
            with pytest.raises(Exception):
                dialect_3.format_data_type(data_type)

    def test_fb4_support_flags_gated(self, dialect, dialect_3):
        assert dialect.supports_data_type_firebird_timestamptz() is True
        assert dialect_3.supports_data_type_firebird_timestamptz() is False
        assert dialect.supports_data_type_firebird_timetz() is True
        assert dialect_3.supports_data_type_firebird_timetz() is False
        assert dialect.supports_data_type_firebird_decfloat() is True
        assert dialect_3.supports_data_type_firebird_decfloat() is False
        assert dialect.supports_data_type_firebird_int128() is True
        assert dialect_3.supports_data_type_firebird_int128() is False


class TestZonedTypesRoundTripThroughParseType:
    """What the catalog says, what ``parse_type`` returns, and what re-renders.

    The chain under test is the one an introspected column takes: Firebird
    reports ``RDB$FIELDS.RDB$FIELD_TYPE``, the introspector maps that code to
    the words Firebird writes, and ``parse_type`` turns those words back into
    the class whose renderer produces them. Every link is checked here, because
    the defect this replaces showed up only where two links disagreed.
    """

    @pytest.mark.parametrize("field_type,expected", [
        (28, "TIME WITH TIME ZONE"),
        (29, "TIMESTAMP WITH TIME ZONE"),
    ])
    def test_introspector_knows_the_firebird_4_zoned_codes(self, field_type,
                                                           expected):
        """RDB$FIELD_TYPE 28/29 are the zoned columns (language reference, D.11).

        Without these entries the introspector produced ``UNKNOWN(28)``, which
        is a ``CustomType`` that renders ``UNKNOWN(28)`` straight back into DDL.
        """
        from rhosocial.activerecord.backend.impl.firebird.introspection.async_introspector import (
            FB_FIELD_TYPES,
        )

        assert FB_FIELD_TYPES[field_type] == expected

    @pytest.mark.parametrize("expected,klass", [
        ("TIME WITH TIME ZONE", FirebirdTimeTzType),
        ("TIMESTAMP WITH TIME ZONE", FirebirdTimeStampTzType),
    ])
    def test_parse_then_render_is_the_identity(self, dialect, expected, klass):
        """A parsed zoned column must render back to the words it was read as."""
        parsed = dialect.parse_type(expected)
        assert type(parsed) is klass
        assert dialect.format_data_type(parsed) == (expected, ())

    @pytest.mark.parametrize("field_type,expected", [
        (28, "TIME WITH TIME ZONE"),
        (29, "TIMESTAMP WITH TIME ZONE"),
    ])
    def test_catalog_code_to_render_is_the_identity(self, dialect, field_type,
                                                    expected):
        """The whole introspect-then-redeclare chain, with no database."""
        from rhosocial.activerecord.backend.impl.firebird.introspection.async_introspector import (
            FB_FIELD_TYPES,
        )

        type_name = FB_FIELD_TYPES[field_type]
        assert dialect.format_data_type(dialect.parse_type(type_name)) == (
            expected, ()
        )

    def test_zoned_and_unzoned_are_distinct_columns(self, dialect):
        """The point of the fix: the differ compares parsed types with ``!=``.

        If a zoned column parsed as its unzoned twin, changing a column from
        ``TIMESTAMP`` to ``TIMESTAMP WITH TIME ZONE`` would produce no diff.
        """
        zoned = dialect.parse_type("TIMESTAMP WITH TIME ZONE")
        unzoned = dialect.parse_type("TIMESTAMP")
        assert zoned != unzoned
        assert dialect.format_data_type(zoned)[0] != dialect.format_data_type(unzoned)[0]

    def test_the_gate_is_the_same_one_the_renderers_use(self, dialect, dialect_3):
        """Parsing and rendering must not disagree about whether FB4 is there."""
        for version_dialect, expected_supported in ((dialect, True), (dialect_3, False)):
            parsed = version_dialect.parse_type("TIMESTAMP WITH TIME ZONE")
            if expected_supported:
                assert version_dialect.supports_data_type_firebird_timestamptz() is True
                assert type(parsed) is FirebirdTimeStampTzType
            else:
                assert version_dialect.supports_data_type_firebird_timestamptz() is False
                assert type(parsed) is CustomType


class TestDialectOptions:
    """The data-type value objects no longer carry a dialect_options bag."""

    def test_constructor_rejects_dialect_options(self, dialect):
        with pytest.raises(TypeError):
            FirebirdDecFloatType(precision=16, dialect_options={"x": 1})

    def test_equality_ignores_dialect(self, dialect):
        other = FirebirdDialect()
        assert FirebirdDecFloatType(precision=16) == FirebirdDecFloatType(precision=16)

    def test_semantic_params_drive_equality(self, dialect):
        assert FirebirdDecFloatType(precision=16) != FirebirdDecFloatType(precision=34)


class TestIdentityFieldsAreHonouredOrRefused:
    """A field in ``PARAMETERS`` is identity: honour it or refuse it.

    ``PARAMETERS`` feeds ``__eq__`` and ``__hash__``, so two declarations that
    differ only in one of its fields are *different columns* by the framework's
    own definition. A dialect that renders one of them as the other reports
    success while creating a column that does not match the declaration. There
    are exactly three legal answers — the field reaches the SQL, flipping it
    raises naming the field, or the field does not belong to the concept on this
    backend and is removed from ``PARAMETERS`` — and these are the tests for all
    three.

    Firebird has no unsigned **numeric** type at all — not just the integers. The
    language reference says so in chapter 3, Integer Data Types: "Firebird does not
    support an unsigned integer data type" (the same sentence is in the 2.5
    reference), and §3.12's *Scalar Data Types Syntax* gives ``REAL | FLOAT
    [(bin_prec)] | DOUBLE PRECISION``, ``DECFLOAT [(dec_prec)]`` and ``{DECIMAL |
    DEC | NUMERIC} [(precision [, scale])]`` no attribute at all — the same
    production writes ``[CHARACTER SET charset]`` after ``VARCHAR (length)``, so
    the slot is documented exactly where Firebird has one. So the field cannot be
    honoured anywhere a numeric renders, and is refused everywhere.

    **Documentation-based.** No Firebird client library is installed in this
    environment (``firebird_driver``, ``fdb`` and ``firebirdsql`` all fail to
    import), so no statement could be sent to a server. Every Firebird claim in
    this file is a quotation from, or an absence in, the language reference, and
    says so rather than dressing itself up as a measurement.

    The date-time family needed the same answer for a different reason: no
    Firebird ``TIME``/``TIMESTAMP`` declaration takes a precision argument at all
    (§3.4.2, §3.4.3, and the §3.12 Data Type Declaration Syntax), so
    ``precision`` is refused there too rather than dropped.

    **There is no allowlist.**  An earlier state of this file carried a
    ``KNOWN_UNREAD_IDENTITY_FIELDS`` frozenset listing the five date-time fields
    that no formatter read, with the sweep below comparing against it. It was a
    written-down statement of what was still broken rather than a licence, and
    once the five were fixed it was empty — and an empty allowlist is worse than
    no allowlist, because it reads as permission. The sweep therefore asserts
    that the unread set is *empty*, and a newly dropped field fails the test
    instead of joining a list nobody reads.
    """

    @pytest.mark.parametrize("cls", [
        TinyIntType, SmallIntType, IntegerType, BigIntType,
    ])
    def test_unsigned_is_refused_by_name(self, dialect, cls):
        """The refusal must name the field and say why, so a caller can act."""
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            dialect.format_data_type(cls(unsigned=True))
        message = str(excinfo.value)
        assert "UNSIGNED" in message
        assert "unsigned integer data type" in message

    @pytest.mark.parametrize("cls", [
        TinyIntType, SmallIntType, IntegerType, BigIntType,
    ])
    def test_signed_renders_exactly_as_before(self, dialect, cls):
        """The refusal is the whole change: ``unsigned=False`` is untouched."""
        assert dialect.format_data_type(cls()) == dialect.format_data_type(
            cls(unsigned=False)
        )

    #: Every exact/approximate numeric formatter on this backend — the four core
    #: dispatch keys and Firebird's own three, which are the same three storages
    #: under three more names. All seven must refuse.
    _NUMERIC_CONCEPTS = [
        ("decimal", DecimalType, "DECIMAL"),
        ("float", FloatType, "FLOAT"),
        ("real", RealType, "FLOAT"),
        ("double", DoubleType, "DOUBLE PRECISION"),
        ("firebird_decimal", FirebirdDecimalType, "DECIMAL"),
        ("firebird_float", FirebirdFloatType, "FLOAT"),
        ("firebird_double", FirebirdDoubleType, "DOUBLE PRECISION"),
    ]

    @pytest.mark.parametrize("name,cls,signed_sql", _NUMERIC_CONCEPTS,
                             ids=[row[0] for row in _NUMERIC_CONCEPTS])
    def test_unsigned_float_and_decimal_are_refused_by_name(self, dialect, name,
                                                            cls, signed_sql):
        """The field is real on these four concepts, so it cannot be dropped.

        It used to be: ``FloatType.PARAMETERS`` was ``("precision",)`` and
        ``DecimalType``'s was ``("precision", "scale")``, so there was nothing to
        honour *or* refuse and an unsigned declaration rendered the signed column
        while the framework's own ``==`` called the two different columns. Core now
        puts ``unsigned`` on all four exact/approximate numerics for the same
        reason it puts it on the integer widths, so all seven of these formatters
        refuse instead.
        """
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            dialect.format_data_type(cls(unsigned=True))
        message = str(excinfo.value)
        assert "UNSIGNED" in message
        assert "unsigned numeric data type" in message

    def test_unsigned_is_the_last_entry_on_every_numeric_identity(self, dialect):
        """Appended, never inserted: the order of ``PARAMETERS`` is what
        ``identity()`` reads, so it is what ``__eq__`` and ``__hash__`` read, and
        reordering it would change the hash of every existing instance."""
        assert FloatType.PARAMETERS == ("precision", "unsigned")
        assert DecimalType.PARAMETERS == ("precision", "scale", "unsigned")
        assert DoubleType.PARAMETERS == ("unsigned",)
        assert RealType.PARAMETERS == ("unsigned",)
        for cls in (FloatType, RealType, DoubleType, DecimalType):
            assert cls.PARAMETERS[-1] == "unsigned", cls.PARAMETERS
            assert cls(dialect) != cls(dialect, unsigned=True)

    @pytest.mark.parametrize("name,cls,signed_sql", _NUMERIC_CONCEPTS,
                             ids=[row[0] for row in _NUMERIC_CONCEPTS])
    def test_every_signed_numeric_renders_exactly_as_before(self, dialect, name,
                                                             cls, signed_sql):
        """The refusal is the whole change: ``unsigned=False`` is untouched, and
        the Firebird-named keys keep rendering the same words as the core ones."""
        assert dialect.format_data_type(cls()) == (signed_sql, ())
        assert dialect.format_data_type(cls(unsigned=False)) == (signed_sql, ())

    def test_no_numeric_formatter_drops_the_flag_silently(self, dialect):
        """The paradigm rule in one assertion over all seven: either the flag
        changes the rendered SQL or it raises. Byte-identical SQL for both signs is
        the violation."""
        for name, cls, signed_sql in self._NUMERIC_CONCEPTS:
            signed = dialect.format_data_type(cls())[0]
            try:
                unsigned = dialect.format_data_type(cls(unsigned=True))[0]
            except UnsupportedFeatureError:
                continue  # refused — the other permitted answer
            assert unsigned != signed, (
                f"{name}: unsigned=True renders {unsigned!r}, the same as "
                f"unsigned=False — the flag is silently dropped"
            )

    @pytest.mark.parametrize("case,expected", [
        # the pre-existing ValueErrors, still firing for a *signed* declaration
        ("decimal_precision", ValueError),
        ("decimal_scale", ValueError),
        ("decimal_scale_over_precision", ValueError),
        # ... and the version gate, which is not a ValueError
        ("float_precision_below_fb4", UnsupportedFeatureError),
    ])
    def test_every_pre_existing_check_still_fires_for_a_signed_declaration(
            self, dialect, case, expected):
        """The gate is additive: nothing it could mask may have stopped working.

        The cases are named rather than constructed in the ``parametrize`` list
        because a ``DataType`` needs a real dialect and ``dialect`` is a fixture
        at class-body time. Pinned by *type*, because the point is that each of
        these still raises what it always raised.
        """
        fb4 = FirebirdDialect(version=(4, 0, 0))
        fb3 = FirebirdDialect(version=(3, 0, 0))
        built, target = {
            "decimal_precision": (DecimalType(fb4, precision=99), fb4),
            "decimal_scale": (DecimalType(fb4, scale=99), fb4),
            "decimal_scale_over_precision": (DecimalType(fb4, 2, 5), fb4),
            "float_precision_below_fb4": (FloatType(fb3, precision=10), fb3),
        }[case]
        with pytest.raises(expected):
            target.format_data_type(built)

    def test_the_signedness_gate_runs_before_the_precision_and_scale_checks(
            self, dialect):
        """A request wrong in two ways is told about the right one first.

        Signedness is a declaration this grammar cannot express **at all**, which is
        a stronger and less recoverable statement than an out-of-range number, so
        the refusal comes first. Not observable any other way: every assertion
        above and below passes with either order.
        """
        fb4 = FirebirdDialect(version=(4, 0, 0))
        for built in (DecimalType(fb4, precision=99, unsigned=True),
                      DecimalType(fb4, scale=99, unsigned=True),
                      DecimalType(fb4, 2, 5, unsigned=True),
                      FloatType(fb4, precision=999, unsigned=True),
                      RealType(fb4, unsigned=True)):
            with pytest.raises(UnsupportedFeatureError) as excinfo:
                fb4.format_data_type(built)
            assert "UNSIGNED" in str(excinfo.value), built

    def test_a_type_string_carrying_unsigned_is_refused_rather_than_read(
            self, dialect):
        """The same rule in the *reading* direction.

        Every ``parse_type`` branch matches on the word in front of the attribute,
        so without a check ``"INTEGER UNSIGNED"`` came back as a plain
        ``IntegerType`` — a signed value object for a declaration that says
        otherwise, which ``==`` calls equal to the signed column. This is the same
        decision the file already makes for a temporal ``precision`` string.
        """
        for raw in ("INTEGER UNSIGNED", "SMALLINT UNSIGNED", "BIGINT UNSIGNED",
                    "DECIMAL(10,2) UNSIGNED", "FLOAT(24) UNSIGNED",
                    "DOUBLE PRECISION UNSIGNED", "REAL UNSIGNED"):
            with pytest.raises(UnsupportedFeatureError) as excinfo:
                dialect.parse_type(raw)
            assert "UNSIGNED" in str(excinfo.value), raw
        # ... and unsigned-free strings of the same shapes are untouched.
        assert dialect.parse_type("DECIMAL(10,2)") == DecimalType(precision=10,
                                                                 scale=2)
        assert dialect.parse_type("INTEGER") == IntegerType()

    def test_the_refusal_is_not_a_value_error(self, dialect):
        """The cross-backend exception convention, stated as a test: a wrong value
        is ``ValueError``; a declaration this grammar cannot express at all is
        ``UnsupportedFeatureError``; the two do not share a base class."""
        assert not issubclass(UnsupportedFeatureError, ValueError)
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_data_type(DecimalType(dialect, unsigned=True))

    def test_blob_sub_type_declares_an_empty_identity(self, dialect):
        """``BLOB SUB_TYPE TEXT`` has no field that can make two of them differ.

        A sub-type tag is a non-negative integer (0 untyped/binary, 1 text, the
        rest reserved) stored in ``RDB$FIELDS.RDB$FIELD_SUB_TYPE``; the Firebird
        BLOB grammar — ``BLOB [SUB_TYPE {subtype_num | subtype_name}] [SEGMENT
        SIZE seglen] [CHARACTER SET charset]`` — carries no modifier of any kind.
        So ``PARAMETERS`` is narrowed from the base's ``("unsigned",)`` to
        ``()``: a text blob has neither a width that varies nor a sign bit.
        """
        assert IntegerType.PARAMETERS == ("unsigned",)
        assert FirebirdBlobSubType.PARAMETERS == ()
        assert FirebirdBlobSubType().identity() == ()

    def test_blob_sub_type_still_renders_unchanged(self, dialect):
        assert dialect.format_data_type(FirebirdBlobSubType()) == (
            "BLOB SUB_TYPE TEXT", ()
        )

    def test_blob_sub_type_unsigned_is_refused_not_ignored(self, dialect):
        """The inherited constructor still accepts ``unsigned``; this stops it.

        Narrowing ``PARAMETERS`` alone would have removed the field from equality
        while leaving the constructor accepting and discarding it — the same
        silent drop, one level down. Rendering must raise instead.
        """
        assert FirebirdBlobSubType(unsigned=True) == FirebirdBlobSubType(
            unsigned=False
        ), "with an empty identity these are the same declaration"
        with pytest.raises(UnsupportedFeatureError, match="UNSIGNED"):
            dialect.format_data_type(FirebirdBlobSubType(unsigned=True))

    def test_every_identity_field_is_read(self, dialect):
        """The general form of the rule, checked over every formatter.

        For each type this dialect renders, every name in ``PARAMETERS`` must
        appear in that formatter's own source or in the source of a helper it
        calls. A field that is declared and never read *is* the defect, whatever
        it is called — so this is the sweep, and the set it finds must be empty.

        The sweep walks a formatter plus three levels of ``self._helper()``
        delegation through :class:`FirebirdTypeSupportMixin`, so a shared refusal
        helper satisfies every caller that reaches it. A field that moves out of
        reach that way fails here rather than disappearing.
        """
        import inspect
        import re

        def formatter_and_helpers(key, depth=3):
            """The formatter's source plus the helpers it delegates to."""
            sources = [inspect.getsource(
                getattr(FirebirdDialect, f"format_data_type_{key}")
            )]
            seen = {key}
            frontier = [key]
            for _ in range(depth):
                body = "\n".join(sources)
                following = []
                for helper in set(re.findall(r"self\.(_[A-Za-z0-9_]+)\(", body)):
                    if helper in seen:
                        continue
                    member = getattr(FirebirdTypeSupportMixin, helper, None)
                    if member is None:
                        continue
                    sources.append(inspect.getsource(member))
                    following.append(helper)
                    seen.add(helper)
                frontier = following
            return "\n".join(sources)

        keys = (
            member[len("format_data_type_"):]
            for member in dir(FirebirdDialect)
            if member.startswith("format_data_type_")
        )
        unread = set()
        for key in keys:
            klass = dialect._type_class_for(key)
            if klass is None:
                continue
            body = formatter_and_helpers(key)
            unread.update(
                f"{key}.{field}" for field in klass.PARAMETERS
                if field not in body
            )
        assert not unread, (
            "these identity fields are declared and no formatter reads them, so "
            f"a declaration differing only in one of them renders as the column "
            f"the caller did not ask for while the call reports success: "
            f"{sorted(unread)}. Each one must be honoured (flipping it changes "
            "the rendered SQL), refused (flipping it raises naming the field), "
            "or removed from PARAMETERS with the reason in the class docstring. "
            "Do not add an exemption list for these; the empty assertion is the "
            "point."
        )

    def test_only_the_firebird_types_whose_concept_has_signedness_declare_it(
            self, dialect):
        """A ``firebird_*`` concept may not *invent* a signedness, and may not
        *drop* one its base declares.

        The two halves of that are now different facts and used to be one, which is
        why this test changed shape. When only the integer concepts carried
        ``unsigned``, "no ``firebird_*`` type declares it" was a single assertion.
        Core now puts ``unsigned`` on ``DecimalType``, ``FloatType``,
        ``DoubleType`` and ``RealType`` as well, and
        :class:`FirebirdDecimalType`, :class:`FirebirdFloatType` and
        :class:`FirebirdDoubleType` inherit it — correctly, because they *are*
        those concepts under this backend's own dispatch keys, and Firebird refuses
        the flag on each of them rather than pretending.

        What must stay true is the narrower, stronger statement: the one
        Firebird-owned concept whose base has **no** signedness must not have one
        put into it — exactly what
        :meth:`test_blob_sub_type_declares_an_empty_identity` removes from
        ``firebird_blob_subtype`` — and every ``firebird_*`` type which *does*
        declare it must refuse it rather than drop it.
        """
        keys = (
            member[len("format_data_type_"):]
            for member in dir(FirebirdDialect)
            if member.startswith("format_data_type_firebird_")
        )
        declaring, silent = set(), set()
        for key in keys:
            klass = dialect._type_class_for(key) or DataType
            if "unsigned" not in klass.PARAMETERS:
                continue
            declaring.add(key)
            try:
                dialect.format_data_type(klass(dialect, unsigned=True))
            except UnsupportedFeatureError:
                continue                       # refused — the other legal answer
            silent.add(key)
        # These three *are* the core concepts, under this backend's own words, so
        # they are expected to carry the field and to refuse it.
        assert declaring == {"firebird_decimal", "firebird_double",
                             "firebird_float"}, sorted(declaring)
        assert not silent, (
            f"these declare unsigned in identity and render it as nothing: "
            f"{sorted(silent)}"
        )


class TestFirebirdFloatHonoursItsPrecision:
    """``FLOAT(bin_prec)`` is Firebird's own grammar, so ``precision`` is honoured.

    Documentation-based, not measured: no ``fbclient`` is installed on this
    machine, so nothing here was run against a server. The authorities are the
    Firebird 4.0 language reference §3.12.1 (``REAL | FLOAT [(bin_prec)] |
    DOUBLE PRECISION``) and §3.2.1.1 (``bin_prec``: "precision in binary digits,
    default is 24; 1 - 24: 32-bit single precision; 25 - 53: 64-bit double
    precision"), plus Firebird 4.0 release notes CORE-6109 for the meaning
    change.
    """

    def test_bare_float_is_firebirds_own_real(self, dialect):
        """``precision=None`` renders ``FLOAT`` — 32-bit single precision.

        The reference's type overview (§3.1, Table 3.1) gives ``FLOAT`` as "32
        bits ... Single-precision IEEE, ~7 digits" and ``REAL`` as "Synonym for
        FLOAT", and ``bin_prec`` a default of 24, which is the same thing said
        three ways.
        """
        assert dialect.format_data_type(FirebirdFloatType()) == ("FLOAT", ())
        assert dialect.format_data_type(FirebirdFloatType(precision=None)) == (
            "FLOAT", ()
        )

    @pytest.mark.parametrize("precision", [1, 12, 24, 25, 40, 53])
    def test_precision_reaches_the_rendered_sql(self, dialect, precision):
        """The point of the fix: flipping the field changes the declaration."""
        assert dialect.format_data_type(
            FirebirdFloatType(precision=precision)
        ) == (f"FLOAT({precision})", ())

    def test_flipping_the_precision_changes_the_column(self, dialect):
        """Before the fix both rendered ``FLOAT`` while ``__eq__`` called them
        different columns — the identity object and the DDL disagreeing."""
        single = FirebirdFloatType(precision=24)
        double = FirebirdFloatType(precision=53)
        assert single != double
        assert dialect.format_data_type(single)[0] != dialect.format_data_type(
            double
        )[0]

    @pytest.mark.parametrize("precision", [0, 54, -1])
    def test_precision_outside_the_documented_range_raises(self, dialect,
                                                           precision):
        with pytest.raises(ValueError, match="between 1 and 53"):
            dialect.format_data_type(FirebirdFloatType(precision=precision))

    def test_no_scale_is_declared_or_expected(self, dialect):
        """``FLOAT`` takes a precision, a signedness and nothing else.

        Checked because a ``scale`` field would be the same defect wearing a
        different hat: Firebird's grammar for ``FLOAT`` is
        ``REAL | FLOAT [(bin_prec)] | DOUBLE PRECISION`` with no second argument,
        so there is nothing to honour and nothing to refuse.

        ``unsigned`` **is** declared — core puts it on ``FloatType`` and this class
        inherits both the field and the constructor — and it is refused, because
        Firebird's grammar gives ``FLOAT`` no attribute either. That is the whole
        distinction the two fields show: a field with a slot in the grammar is
        honoured, a field without one is refused, and neither is dropped.
        """
        assert FirebirdFloatType.PARAMETERS == ("precision", "unsigned")
        assert not hasattr(FirebirdFloatType(), "scale")
        with pytest.raises(UnsupportedFeatureError, match="UNSIGNED"):
            dialect.format_data_type(FirebirdFloatType(unsigned=True))

    def test_precision_is_refused_below_firebird_4(self, dialect_3):
        """CORE-6109: before 4.0, ``FLOAT(p)`` counted *decimal* digits.

        So ``FLOAT(10)`` named a ten-decimal-digit float on Firebird 3 and names
        a ten-*bit* float on Firebird 4 — the same text, two different columns.
        Emitting one without knowing the server would declare a column whose
        meaning is a coin toss, so the field is refused below 4.0 by name.
        """
        with pytest.raises(UnsupportedFeatureError, match="FLOAT"):
            dialect_3.format_data_type(FirebirdFloatType(precision=24))

    def test_bare_float_needs_no_version_gate(self, dialect_3):
        """``FLOAT`` alone means single precision on both sides of 4.0."""
        assert dialect_3.format_data_type(FirebirdFloatType()) == ("FLOAT", ())
        assert dialect_3.format_data_type(FirebirdFloatType()) == (
            FirebirdDialect((4, 0, 0)).format_data_type(FirebirdFloatType())
        )

    def test_the_support_flag_stays_ungated(self, dialect, dialect_3):
        """The flag is about the *type*, and ``FLOAT`` exists on Firebird 3.

        Only the argument needs 4.0, and gating the flag would drop ``firebird
        _float`` from ``supports_data_types()`` on an older dialect even though
        it renders there.
        """
        assert dialect.supports_data_type_firebird_float() is True
        assert dialect_3.supports_data_type_firebird_float() is True
        assert "firebird_float" in dialect_3.supports_data_types()

    def test_docstring_records_the_documentation_facts(self):
        """The reasoning must be written down, with the version boundary in it."""
        doc = FirebirdFloatType.__doc__ or ""
        assert "bin_prec" in doc
        assert "CORE-6109" in doc


class TestFirebirdFourCatalogCodes:
    """``RDB$FIELDS.RDB$FIELD_TYPE`` 24, 25 and 26, from code to column.

    Documentation-based, not measured: no ``fbclient`` on this machine, so this
    exercises the chain the catalog drives — code → type name → ``parse_type`` →
    rendered SQL — with no database. The authority is the Firebird 4.0 language
    reference, D.11 ``RDB$FIELDS``, which documents ``RDB$FIELD_TYPE`` (and
    ``RDB$EXTERNAL_TYPE`` with the same codes):

        23 - BOOLEAN      24 - DECFLOAT(16)   25 - DECFLOAT(34)
        26 - INT128       27 - DOUBLE PRECISION
    """

    @staticmethod
    def _field_types():
        from rhosocial.activerecord.backend.impl.firebird.introspection.async_introspector import (
            FB_FIELD_TYPES,
        )
        return FB_FIELD_TYPES

    @pytest.mark.parametrize("code,expected", [
        (24, "DECFLOAT(16)"),
        (25, "DECFLOAT(34)"),
        (26, "INT128"),
    ])
    def test_introspector_knows_the_firebird_4_codes(self, code, expected):
        assert self._field_types()[code] == expected

    def test_decfloat_is_two_codes_not_one(self):
        """24 and 25 are ``DECFLOAT(16)`` and ``DECFLOAT(34)``.

        There is no bare ``DECFLOAT`` code: Firebird encodes the width in the
        code itself (``RDB$FIELD_LENGTH`` agrees — 8 bytes for
        ``DECFLOAT(16)``, 16 for ``DECFLOAT(34)``). Mapping both codes to the
        unqualified word would make the two widths report the same name and,
        because ``FirebirdDecFloatType`` carries ``precision`` in
        ``PARAMETERS``, compare *equal* as well.
        """
        field_types = self._field_types()
        assert field_types[24] != field_types[25]
        assert field_types[24].startswith("DECFLOAT(")
        assert field_types[25].startswith("DECFLOAT(")

    @pytest.mark.parametrize("code,expected_class,precision", [
        (24, FirebirdDecFloatType, 16),
        (25, FirebirdDecFloatType, 34),
        (26, FirebirdInt128Type, None),
    ])
    def test_catalog_code_to_render_is_the_identity(self, dialect, code,
                                                    expected_class, precision):
        """The whole introspect-then-redeclare chain, with no database."""
        type_name = self._field_types()[code]
        parsed = dialect.parse_type(type_name)
        assert type(parsed) is expected_class
        if precision is not None:
            assert parsed.precision == precision
        else:
            assert expected_class.PARAMETERS == (), "INT128 declares no identity"
        assert dialect.format_data_type(parsed) == (type_name, ())

    def test_the_two_decfloat_widths_are_different_columns(self, dialect):
        """The identity point: 16 digits and 34 digits are not one column.

        Before, both codes mapped to the bare word ``DECFLOAT``, so a
        ``DECFLOAT(16)`` column and a ``DECFLOAT(34)`` one introspected as the
        same ``CustomType`` and the differ — which compares with ``!=`` — had
        nothing to report when one changed into the other.
        """
        narrow = dialect.parse_type(self._field_types()[24])
        wide = dialect.parse_type(self._field_types()[25])
        assert narrow != wide
        assert dialect.format_data_type(narrow)[0] != dialect.format_data_type(
            wide
        )[0]

    def test_int128_is_not_read_as_an_integer_of_another_width(self, dialect):
        """``INT128`` holds -2**127..2**127-1; ``INTEGER`` holds 32 bits.

        The two are not spellings of one column, so reading a 128-bit column as
        a 32-bit one is not a normalisation.
        """
        parsed = dialect.parse_type(self._field_types()[26])
        assert isinstance(parsed, FirebirdInt128Type)
        assert not isinstance(parsed, IntegerType)
        assert not isinstance(parsed, BigIntType)

    def test_decfloat_is_not_read_as_a_fixed_point_decimal(self, dialect):
        """``DECFLOAT(16)`` is not ``DECIMAL(16)``.

        The names start with the same three letters and the classes are both
        "decimal", so a dispatch that tested ``startswith("DEC")`` would answer
        with :class:`DecimalType` — which has a scale rule and a 1..18 precision
        range, and is a different column from a 34-significant-digit decimal
        float.
        """
        parsed = dialect.parse_type(self._field_types()[25])
        assert isinstance(parsed, FirebirdDecFloatType)
        assert parsed.scale is None
        assert dialect.parse_type("DECIMAL(16)") == DecimalType(precision=16)
        assert dialect.parse_type("DECFLOAT(16)") != DecimalType(precision=16)

    def test_precision_outside_16_or_34_is_not_rounded_to_a_nearby_width(self,
                                                                         dialect):
        """The dialect must not invent a width the declaration never named.

        ``DECFLOAT(20)`` is not a Firebird column; guessing 16 or 34 for it would
        be the same class of error as declaring ``INTEGER [1]`` for an array.
        """
        with pytest.raises(ValueError, match="16 or 34"):
            dialect.parse_type("DECFLOAT(20)")

    def test_bare_decfloat_uses_the_documented_default(self, dialect):
        """``DECFLOAT`` with no argument is legal Firebird and defaults to 34."""
        parsed = dialect.parse_type("DECFLOAT")
        assert isinstance(parsed, FirebirdDecFloatType)
        assert parsed.precision == 34

    def test_the_codes_use_the_same_single_gate_as_the_renderers(self, dialect,
                                                                 dialect_3):
        """Parsing and rendering must not disagree about whether FB4 is there."""
        for raw, feature in (
            ("DECFLOAT(34)", "DECFLOAT"),
            ("INT128", "INT128"),
        ):
            assert dialect.supports_data_type_firebird_decfloat() is True
            assert dialect.supports_data_type_firebird_int128() is True
            assert not isinstance(dialect.parse_type(raw), CustomType)
            assert isinstance(dialect_3.parse_type(raw), CustomType)

    def test_the_constructor_default_matches_the_catalog(self, dialect):
        """Code 25 is ``DECFLOAT(34)``, so a bare instance is the 34 column.

        Worth pinning next to the code table because it is the check that would
        have caught the constructor's old default of 16: the catalog never
        reports a bare ``DECFLOAT``, so a class whose default disagreed with the
        reference would still render *something* Firebird accepts, and only the
        width would be wrong.
        """
        assert type(dialect.parse_type(self._field_types()[25])) is (
            FirebirdDecFloatType
        )
        assert FirebirdDecFloatType().precision == 34
        assert FirebirdDecFloatType(precision=16).precision == 16

    def test_no_firebird_4_code_produces_an_unknown_name(self):
        """An unmapped code becomes ``UNKNOWN(24)``, which renders back into DDL.

        Worth asserting as the contrast with a *wrongly* mapped code: a missing
        entry is loud, and a wrong one is not — which is why 24 could have been
        wrong and still have looked like it worked.
        """
        from rhosocial.activerecord.backend.impl.firebird.introspection.async_introspector import (
            FB_FIELD_TYPES,
        )

        values = FB_FIELD_TYPES.values()
        for code in (24, 25, 26, 28, 29):
            assert f"UNKNOWN({code})" not in values


class TestWhatFirebirdSuppliesForAnUndeclaredWidth:
    """``type_parameter_defaults()`` — the one width Firebird supplies, and the
    one it does not.

    The asymmetry being pinned is not "which numbers", it is **which side of the
    declaration a number belongs on**.  ``CHAR`` has a default that the server
    stores and reports back; ``VARCHAR`` has no default at all — Firebird rejects
    the bare declaration — so the 255 this dialect writes is a choice of the
    backend and must never appear as a server fact. Declaring the second as if it
    were the first would be the same defect in a new place: the parser would be
    inventing a width for a column that cannot exist.
    """

    def test_only_char_is_declared(self, dialect):
        assert dialect.type_parameter_defaults() == {
            "char": {"length": 1},
            "firebird_char": {"length": 1},
        }

    def test_the_declared_char_width_is_the_documented_one(self, dialect):
        """1, and it is *Firebird's* default, not a width chosen here.

        The reference says "If the number of characters is not specified, 1 is
        used by default" — the same sentence in 2.5 §3 Table 1 and in the 3.0, 4.0
        and 5.0 references — so this entry asserts nothing against the vendor.
        """
        assert dialect.type_parameter_defaults()["char"]["length"] == 1

    def test_varchar_is_absent_because_firebird_has_no_default(self, dialect):
        """The absence *is* the statement, and there is a citation for it.

        All four references say "There is no default size: the n argument is
        mandatory" for ``VARCHAR``, §3.12's production puts the parentheses round
        ``length`` rather than in square brackets, and FirebirdSQL/firebird#8909
        is the open request that adds 255 — after 5.0. So a bare ``VARCHAR`` is a
        syntax error on every release this backend addresses and there is nothing
        for a catalog to report back.
        """
        declared = dialect.type_parameter_defaults()
        assert "varchar" not in declared
        assert "firebird_varchar" not in declared

    def test_an_unbound_varchar_keeps_none(self, dialect):
        """Silence is the honest answer, so the type carries ``None``.

        This is the property that makes the absence load-bearing rather than
        decorative: a ``VarCharType`` bound to this dialect must not gain a width
        it was never given.
        """
        assert VarCharType(dialect).length is None

    def test_a_bound_char_resolves_to_the_declared_width(self, dialect):
        """The resolution the declaration exists for: read time, not build time."""
        assert CharType(dialect).length == 1
        assert CharType(dialect, length=10).length == 10

    def test_deferred_binding_resolves_identically(self, dialect):
        """Binding after construction gives the same answer, because the lookup
        happens on the attribute rather than in ``__init__``.

        Worth pinning separately from the bound case: a dialect that cached the
        default at construction time would pass the previous test and fail this
        one, and ``CharType()`` is built without a dialect all over the codebase.
        """
        deferred = CharType()
        assert deferred.length is None
        deferred.dialect = dialect
        assert deferred.length == 1

    def test_a_bare_declaration_and_its_own_introspection_now_agree(self, dialect):
        """The defect this closes: same rendered SQL, unequal objects.

        ``CharType(d)`` used to carry ``length=None`` while
        ``parse_type("CHAR")`` produced ``CharType(length=1)``. Both rendered
        ``CHAR(1)``, and ``length`` is in ``PARAMETERS``, so the declared column
        and the catalog row for the very column it produced compared **unequal**
        and the differ invented a change on every undeclared ``CHAR`` column.
        """
        assert CharType(dialect) == dialect.parse_type("CHAR")
        assert CharType(dialect) == dialect.parse_type("CHARACTER")
        assert CharType(dialect) == dialect.parse_type("CHAR(1)")

    def test_a_bare_varchar_does_not_claim_to_agree(self, dialect):
        """The contrast case, and the reason the two are handled differently.

        ``VarCharType(d)`` renders ``VARCHAR(255)`` — this backend's choice — and
        ``parse_type("VARCHAR")`` reads the same 255 back, so the two objects are
        still unequal. That is correct: the 255 is not something Firebird
        supplied, so ``None`` is what the declaration must keep saying. Making
        them equal would require adopting a width the server never reported.
        """
        assert dialect.format_data_type(VarCharType(dialect))[0] == "VARCHAR(255)"
        assert VarCharType(dialect) != dialect.parse_type("VARCHAR")
        assert VarCharType(dialect, length=255) == dialect.parse_type("VARCHAR")

    @pytest.mark.parametrize("klass,expected", [
        (CharType, "CHAR(1)"),
        (VarCharType, "VARCHAR(255)"),
        (FirebirdCharType, "CHAR(1) CHARACTER SET UTF8"),
        (FirebirdVarCharType, "VARCHAR(255) CHARACTER SET UTF8"),
    ])
    def test_no_rendering_changed(self, dialect, klass, expected):
        """The number moved from two literals to one declaration; the SQL did not.

        Every row here is byte-identical to what this dialect wrote before the
        declaration existed, which is the whole reason the step was safe.
        """
        assert dialect.format_data_type(klass(dialect))[0] == expected

    def test_the_parser_and_the_formatter_read_one_number(self, dialect):
        """Drift is the failure this step removes, so probe both directions.

        ``parse_type`` completing an unsized word and the formatter filling an
        absent width are two code paths that used to carry their own copies of
        255 and 1. Any future edit to one and not the other now shows up as a
        failed round trip instead of as a schema diff nobody notices.
        """
        for raw, klass, declared in (
            ("VARCHAR", VarCharType, VarCharType(length=255)),
            ("CHARACTER VARYING", VarCharType, VarCharType(length=255)),
            ("CHAR", CharType, CharType(length=1)),
            ("CHARACTER", CharType, CharType(length=1)),
        ):
            parsed = dialect.parse_type(raw)
            assert parsed == declared, raw
            assert dialect.format_data_type(parsed)[0] == dialect.format_data_type(
                klass(dialect)
            )[0], raw

    def test_an_explicit_width_still_wins(self, dialect):
        for raw, klass, length in (
            ("CHAR(10)", CharType, 10),
            ("VARCHAR(50)", VarCharType, 50),
            ("CHARACTER(7)", CharType, 7),
            ("CHARACTER VARYING(7)", VarCharType, 7),
        ):
            assert dialect.parse_type(raw).length == length, raw


# ---------------------------------------------------------------------------
# parse_type: the dialect it now binds, and the round-trip sweep
# ---------------------------------------------------------------------------


class TestParsedTypesCarryTheDialect:
    """Every parsed type binds the dialect, as every other backend's does.

    A dialect-less return could not re-render -- ``parsed.dialect`` raised
    with "has no dialect bound" and ``to_sql()`` raised with it -- which made
    the parsed value invisible to the round-trip sweep and to any caller that
    renders what it read. Equality never noticed, because the dialect is
    deliberately not part of a DataType's identity; only rendering did.
    """

    @pytest.mark.parametrize("raw", [
        "VARCHAR(255)", "CHAR(1)", "SMALLINT", "DECIMAL(10, 2)", "BLOB",
        "TIMESTAMP", "DATE", "BOOLEAN",
    ])
    def test_a_parsed_type_renders_back(self, dialect, raw):
        parsed = dialect.parse_type(raw)
        assert parsed.dialect is dialect
        sql, _ = dialect.format_data_type(parsed)
        assert sql, raw

    def test_the_round_trip_is_stable(self, dialect):
        first = dialect.parse_type("VARCHAR(255)")
        sql, _ = dialect.format_data_type(first)
        assert dialect.parse_type(sql) == first


class TestParseRoundTripSweep:
    """The shared sweep across this backend's whole declared surface.

    Asserts the two invariants at once: **string stability** and **class
    honesty** -- the answer is the declared instance, or the documented
    answer recorded below. The tuple entries are the answers whose re-render
    deliberately differs, and each is a claim this backend already documents:
    the character set is a *column* attribute and only the written form
    differs (FirebirdCharType / FirebirdVarCharType say so in their own
    docstrings), and the UUID concept is substituted with a CHAR(16) OCTETS
    column, whose storage word is a char column.
    """

    WIDENING_ANSWERS = {
        # The byte-string concepts share Firebird's one BLOB storage.
        "BinaryType": "BlobType",
        "VarBinaryType": "BlobType",
        # The timestamp concept and the datetime concept share TIMESTAMP.
        "TimestampType": "DateTimeType",
        # No 1-byte integer: the concept is widened to SMALLINT.
        "TinyIntType": "SmallIntType",
        # REAL is a 4-byte FLOAT here.
        "RealType": "FloatType",
        # A parameter normalisation on the same class (the default length).
        "VarCharType": "VarCharType",
        # The backend's own classes parse back to the concept that shares
        # their storage; each re-renders the identical string.
        "FirebirdBlobSubType": "TextType",
        "FirebirdDecimalType": "DecimalType",
        "FirebirdDoubleType": "DoubleType",
        "FirebirdFloatType": "FloatType",
        # The documented written-form differences: the character set is a
        # column attribute in Firebird, not part of the type's identity, so
        # the parse answers the concept and the re-render states the default
        # written form.
        "FirebirdCharType": ("CharType", "CHAR(1)"),
        "FirebirdVarCharType": ("VarCharType", "VARCHAR(255)"),
        # The UUID concept is substituted with a CHAR(16) OCTETS column;
        # the catalog's word for that storage is a char column.
        "UUIDType": ("CharType", "CHAR(16)"),
    }

    @pytest.fixture(scope="class")
    def registry(self):
        """The round-trip module's registry, loaded from beside this file.

        Executing it also registers its special constructors, which the
        sweep's ``make_instance`` consults -- the same registrations the
        full suite performs at collection time.
        """
        import importlib.util
        from pathlib import Path

        path = Path(__file__).with_name("test_expression_roundtrip_all.py")
        spec = importlib.util.spec_from_file_location(
            "firebird_rt_registry",
            path,
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        registry = getattr(module, "ALL_CLASSES", None) or module.REGISTERED
        assert registry, "the round-trip module exposes no registry"
        return registry

    def test_every_rendered_type_parses_back_coherently(self, dialect, registry):
        from rhosocial.activerecord.testsuite.utils.parse_contract import (
            parse_roundtrip_failures,
        )

        failures = parse_roundtrip_failures(
            dialect,
            registry,
            widening=self.WIDENING_ANSWERS,
        )
        assert failures == [], "\n".join(failures)

