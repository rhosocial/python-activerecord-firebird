# tests/test_scan_helpers.py
"""The regex-free scanners answer what the patterns they replaced answered.

Each case names the construct the helper stands in for (version triplet,
declaration text, qualified identifier, parenthesised length, word presence),
and the pattern is kept here as the oracle. The library holds the scan; the
tests hold the regex.
"""

import re

import pytest

from rhosocial.activerecord.backend.impl.firebird._scan import (
    contains_word,
    find_parenthesised_number,
    find_version_triplet,
    is_declaration_text,
    is_qualified_identifier,
    starts_with_any_word,
    starts_with_phrase,
    starts_with_word,
)

#: Version strings Firebird actually reports, plus shapes that must not parse.
VERSION_STRINGS = [
    "Firebird 5.0.4 (1234)",
    "LI-V5.0.2.1234 Firebird 5.0",
    "Firebird 4.0.0.1234",
    "3.0.7",
    "10.2.13.4",
    "1.2x3.4.5",
    "v1.2.3",
    "Firebird 2.5",
    "",
    "no version here",
]


@pytest.mark.parametrize("text", VERSION_STRINGS)
def test_version_triplet_matches_search_reading(text):
    duties = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
    expected = tuple(int(part) for part in duties.groups()) if duties else None
    assert find_version_triplet(text) == expected


#: Declarations the domain ``data_type_name`` path accepts or refuses.
DECLARATIONS = [
    "INTEGER",
    "VARCHAR(40) CHARACTER SET UTF8",
    "DECIMAL(10, 2)",
    "DECIMAL ( 10 , 2 )",
    "TIMESTAMP WITH TIME ZONE",
    "APP.MY_DOMAIN",
    "SOMETHING_WEIRD",
    "BLOB SUB_TYPE TEXT",
    "INTEGER; DROP DOMAIN D",
    "INTEGER DROP DOMAIN D",
    "VARCHAR(20)\tEXTRA",
    "1INTEGER",
    "_INT",
    "ÉCLAIR",
    "",
    " ",
]


@pytest.mark.parametrize("text", DECLARATIONS)
def test_declaration_text_matches_the_character_set(text):
    expected = re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$.,() \t]*", text) is not None
    assert is_declaration_text(text) is expected


#: Names the qualified-identifier branch accepts or hands to CustomType.
IDENTIFIERS = [
    "SOMETHING_WEIRD",
    "APP.MY_DOMAIN",
    "A.B",
    "A.B.C",
    ".A",
    "A.",
    "1A",
    "_A",
    "A$B",
    "A B",
    "",
]


@pytest.mark.parametrize("text", IDENTIFIERS)
def test_qualified_identifier_matches_the_name_pattern(text):
    expected = (
        re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*(?:\.[A-Za-z_][A-Za-z0-9_$]*)?", text) is not None
    )
    assert is_qualified_identifier(text) is expected


#: Lengths the string families read out of a spelling.
PARENTHESISED = [
    "VARCHAR(40)",
    "VARCHAR( 40 )",
    "VARCHAR (40)",
    "CHAR(5) CHARACTER SET UTF8",
    "VARCHAR(40) CHARACTER SET UTF8",
    "DECIMAL(10, 2)",
    "TIMESTAMP WITH TIME ZONE",
    "VARCHAR",
]


@pytest.mark.parametrize("text", PARENTHESISED)
def test_parenthesised_number_matches_the_length_pattern(text):
    duties = re.search(r"\((\d+)", text)
    expected = duties.group(1) if duties else None
    assert find_parenthesised_number(text) == expected


@pytest.mark.parametrize(
    "text,word,expected",
    [
        ("INTEGER UNSIGNED", "UNSIGNED", True),
        ("integer unsigned", "UNSIGNED", True),
        ("UNSIGNED", "UNSIGNED", True),
        ("INTEGERUNSIGNED", "UNSIGNED", False),
        ("UNSIGNED_INTEGER", "UNSIGNED", False),
        ("INT UNSIGNED_BYTE", "UNSIGNED", False),
        ("INTEGER", "UNSIGNED", False),
        ("", "UNSIGNED", False),
    ],
)
def test_contains_word_matches_the_word_boundary(text, word, expected):
    duties = re.search(r"\bUNSIGNED\b", text, re.IGNORECASE)
    assert contains_word(text, word) is (duties is not None)
    assert contains_word(text, word) is expected


@pytest.mark.parametrize(
    "text,word,expected",
    [
        ("INTEGER", "INT", False),
        ("INT128", "INT", False),
        ("INTEGER", "INTEGER", True),
        ("INT1", "INT", False),
        ("INT(3)", "INT", True),
        ("TIME WITH TIME ZONE", "TIME", True),
    ],
)
def test_starts_with_word_matches_the_leading_boundary(text, word, expected):
    duties = re.match(r"^" + word + r"\b", text)
    assert starts_with_word(text, word) is (duties is not None)
    assert starts_with_word(text, word) is expected


@pytest.mark.parametrize(
    "text,words,expected",
    [
        ("TINYINT", ("TINYINT", "INT1"), True),
        ("INT1", ("TINYINT", "INT1"), True),
        ("INT10", ("TINYINT", "INT1"), False),
        ("BIGINT", ("SMALLINT", "INT2", "INTEGER", "INT", "BIGINT", "INT8"), True),
        ("DOUBLE PRECISION", ("FLOAT", "DOUBLE", "REAL"), True),
    ],
)
def test_starts_with_any_word_matches_the_alternation(text, words, expected):
    pattern = "^(" + "|".join(words) + r")\b"
    duties = re.match(pattern, text)
    assert starts_with_any_word(text, *words) is (duties is not None)
    assert starts_with_any_word(text, *words) is expected


@pytest.mark.parametrize(
    "text,words,expected",
    [
        ("BLOB SUB_TYPE TEXT", ("BLOB", "SUB_TYPE", "TEXT"), True),
        ("BLOB SUB_TYPE BINARY", ("BLOB", "SUB_TYPE", "TEXT"), False),
        ("CHARACTER VARYING(5)", ("CHARACTER", "VARYING"), True),
        ("CHARACTERVARYING", ("CHARACTER", "VARYING"), False),
        ("TIMESTAMP WITH TIME ZONE", ("TIMESTAMP", "WITH", "TIME", "ZONE"), True),
        ("TIMESTAMP WITH TIME ZONEX", ("TIMESTAMP", "WITH", "TIME", "ZONE"), False),
    ],
)
def test_starts_with_phrase_matches_the_spaced_pattern(text, words, expected):
    pattern = "^" + r"\s+".join(words) + r"\b"
    duties = re.match(pattern, text)
    assert starts_with_phrase(text, words) is (duties is not None)
    assert starts_with_phrase(text, words) is expected
