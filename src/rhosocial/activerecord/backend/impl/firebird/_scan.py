# src/rhosocial/activerecord/backend/impl/firebird/_scan.py
"""Regex-free scanners for the short spellings this backend reads.

Two kinds of text are parsed without a pattern matcher: the version string a
Firebird connection reports and the type spelling a catalog row or a caller
supplies. Both are small, fixed vocabularies, so they are read with
per-character scans. Each helper here replaces one construct that used to be a
regular expression, and the declaration reader keeps the same split every
pattern relied on: leading words, one optional parenthesised argument list, and
trailing words.

Nothing here raises: a string that does not have the shape simply fails to
match, and the caller decides what that means.
"""

_ASCII_LETTERS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
_DECIMAL_DIGITS = frozenset("0123456789")
_DECLARATION_PUNCTUATION = frozenset("_$.,() \t")
_IDENTIFIER_TRAILING = frozenset("_$")


def is_word_char(ch: str) -> bool:
    """Whether *ch* continues a word, i.e. belongs to ``\\w``."""
    return ch.isalnum() or ch == "_"


def skip_whitespace(text: str, pos: int) -> int:
    """The first position at or after *pos* that is not whitespace."""
    while pos < len(text) and text[pos].isspace():
        pos += 1
    return pos


def read_word(text: str, pos: int) -> tuple[str, int] | None:
    """The word-char run starting at *pos*, and the position after it."""
    end = pos
    while end < len(text) and is_word_char(text[end]):
        end += 1
    if end == pos:
        return None
    return text[pos:end], end


def read_digits(text: str, pos: int) -> tuple[str, int] | None:
    """The decimal-digit run starting at *pos*, and the position after it."""
    end = pos
    while end < len(text) and text[end].isdecimal():
        end += 1
    if end == pos:
        return None
    return text[pos:end], end


def read_balanced_group(text: str, pos: int) -> tuple[str, int] | None:
    """Read the parenthesised group that starts at *pos*.

    Returns ``(inner, end)``, or ``None`` when *pos* is not an opening
    parenthesis or the group never closes. Balance is counted, so a nested pair
    is scanned as one group rather than cut at the first ``)``.
    """
    if pos >= len(text) or text[pos] != "(":
        return None
    depth = 0
    start = pos + 1
    while pos < len(text):
        ch = text[pos]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return text[start:pos], pos + 1
        pos += 1
    return None


def is_word_boundary(text: str, pos: int, *, excludes: str = "") -> bool:
    """The ``\\b`` assertion at *pos*.

    *excludes* names extra characters that also break the boundary when a
    pattern said so with a negative lookahead (``INT128(?![A-Za-z0-9_$])``).
    """
    if pos >= len(text):
        return True
    ch = text[pos]
    return not is_word_char(ch) and ch not in excludes


def match_word_sequence(
    text: str,
    pos: int,
    words: tuple[str, ...],
    *,
    leading_space: bool = True,
) -> int | None:
    """Match *words* at *pos*, whitespace-separated, ending on a boundary.

    ``leading_space`` mirrors the ``\\s+`` in front of a clause: when it is set,
    at least one whitespace character must precede the first word. The return
    value is the position after the last word, or ``None`` when it does not
    match.
    """
    for index, word in enumerate(words):
        if leading_space or index:
            start = pos
            pos = skip_whitespace(text, pos)
            if pos == start:
                return None
        if not text.startswith(word, pos):
            return None
        end = pos + len(word)
        if not is_word_boundary(text, end):
            return None
        pos = end
    return pos


def starts_with_word(text: str, word: str, *, lookahead_excludes: str = "") -> bool:
    """``^WORD\\b``, with *lookahead_excludes* widening the boundary check."""
    if not text.startswith(word):
        return False
    return is_word_boundary(text, len(word), excludes=lookahead_excludes)


def starts_with_any_word(text: str, *words: str) -> bool:
    """``^(?:WORD1|WORD2|...)\\b``."""
    return any(starts_with_word(text, word) for word in words)


def starts_with_phrase(text: str, words: tuple[str, ...]) -> bool:
    """``^WORD1\\s+WORD2...\\b``, with the words given in order."""
    return match_word_sequence(text, 0, words, leading_space=False) is not None


def contains_word(text: str, word: str) -> bool:
    """``\\bWORD\\b`` anywhere in *text*, case-insensitively."""
    haystack = text.lower()
    needle = word.lower()
    start = 0
    while True:
        index = haystack.find(needle, start)
        if index < 0:
            return False
        end = index + len(needle)
        before_ok = index == 0 or not is_word_char(text[index - 1])
        after_ok = end == len(text) or not is_word_char(text[end])
        if before_ok and after_ok:
            return True
        start = index + 1


def find_version_triplet(text: str) -> tuple[int, int, int] | None:
    """The first ``digits.digits.digits`` run in *text*, as three integers.

    The leftmost start wins and each run is read greedily, exactly as a search
    for the three-run pattern would read it.
    """
    for start in range(len(text)):
        pos = start
        parts: list[int] = []
        for index in range(3):
            digits = read_digits(text, pos)
            if digits is None:
                break
            parts.append(int(digits[0]))
            pos = digits[1]
            if index < 2:
                if pos >= len(text) or text[pos] != ".":
                    break
                pos += 1
        else:
            return (parts[0], parts[1], parts[2])
    return None


def find_digit_runs(text: str) -> list[str]:
    """Every decimal-digit run in *text*, left to right, greedily."""
    runs: list[str] = []
    pos = 0
    while pos < len(text):
        digits = read_digits(text, pos)
        if digits is None:
            pos += 1
            continue
        runs.append(digits[0])
        pos = digits[1]
    return runs


def find_parenthesised_number(text: str) -> str | None:
    """The first ``(digits`` run in *text*, reading the group greedily.

    No whitespace is permitted between the parenthesis and the digits, which
    keeps the reading identical to the pattern it replaces.
    """
    index = text.find("(")
    while index >= 0:
        digits = read_digits(text, index + 1)
        if digits is not None:
            return digits[0]
        index = text.find("(", index + 1)
    return None


def read_head_with_precision(text: str, word: str) -> tuple[str | None, int, int] | None:
    """Read ``^WORD(?:\\s*\\(\\s*(\\d+)\\s*\\))?`` at the start of *text*.

    Returns ``(precision, word_end, end)``, or ``None`` when the first word is
    not *word*. *precision* is the parenthesised digit run as text, or ``None``
    when the word stands bare -- including when a parenthesised tail exists but
    is not a single digit run, which is the position an optional group failing
    to match would leave the scan at.
    """
    leading = read_word(text, 0)
    if leading is None or leading[0].upper() != word:
        return None
    word_end = leading[1]
    group = match_optional_precision(text, word_end)
    if group is not None:
        digits, end = group
        if digits is not None:
            return digits, word_end, end
    return None, word_end, word_end


def match_optional_precision(text: str, pos: int) -> tuple[str | None, int] | None:
    """Match ``(?:\\s*\\(\\s*(\\d+)\\s*\\))?`` at *pos*.

    Returns ``(digits, end)``; *end* is *pos* itself when the group is absent,
    because the whole construct is optional including its leading whitespace.
    Returns ``None`` when a parenthesis opens but does not hold a single digit
    run -- the group as a whole then did not match.
    """
    group_start = skip_whitespace(text, pos)
    if group_start >= len(text) or text[group_start] != "(":
        return None, pos
    group = read_balanced_group(text, group_start)
    if group is None:
        return None
    inner = group[0].strip()
    if not inner or not all(ch.isdecimal() for ch in inner):
        return None
    return inner, group[1]


class Spelling:
    """A type spelling split into words, an argument list and trailing words.

    ``words`` are the words before the argument list -- all of them when the
    spelling has none. ``arguments`` holds the raw comma-separated parts of the
    list, or ``None`` when there is no list. ``tail`` holds the words after the
    list. Words are upper-cased because every caller compares them
    case-insensitively.
    """

    __slots__ = ("arguments", "tail", "words")

    def __init__(
        self,
        words: tuple[str, ...],
        arguments: tuple[str, ...] | None,
        tail: tuple[str, ...],
    ) -> None:
        self.words = words
        self.arguments = arguments
        self.tail = tail

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Spelling(words={self.words!r}, arguments={self.arguments!r}, tail={self.tail!r})"

    def digits(self, count: int | None = None) -> tuple[int, ...] | None:
        """The argument list as integers, or ``None`` when it is not that.

        *count* pins the number of arguments when the pattern did. A bare
        spelling (no list) always answers ``None``, so callers test for the
        argument list separately.
        """
        if self.arguments is None:
            return None
        if count is not None and len(self.arguments) != count:
            return None
        values: list[int] = []
        for argument in self.arguments:
            if not argument or not all(ch.isdecimal() for ch in argument):
                return None
            values.append(int(argument))
        return tuple(values)


def read_spelling(text: str, pos: int = 0) -> tuple[Spelling, int] | None:
    """Read a type spelling from *pos*, returning it and the position after it.

    The spelling is read as leading words, at most one parenthesised argument
    list, then trailing words. A clause after the argument list must be
    separated by whitespace, as every spelling this backend reads is. ``None``
    means the text does not have that shape (an unbalanced group, a dotted
    name, or a character that is neither a word nor punctuation).
    """
    words: list[str] = []
    arguments: tuple[str, ...] | None = None
    tail: list[str] = []
    end = pos
    while True:
        end = skip_whitespace(text, end)
        word = read_word(text, end)
        if word is None:
            break
        words.append(word[0].upper())
        end = word[1]
    group_start = skip_whitespace(text, end)
    if group_start < len(text) and text[group_start] == "(":
        group = read_balanced_group(text, group_start)
        if group is None:
            return None
        arguments = tuple(part.strip() for part in group[0].split(","))
        end = group[1]
        if end < len(text) and not text[end].isspace():
            return None
        while True:
            end = skip_whitespace(text, end)
            word = read_word(text, end)
            if word is None:
                break
            tail.append(word[0].upper())
            end = word[1]
    return Spelling(tuple(words), arguments, tuple(tail)), end


def parse_spelling(text: str) -> Spelling | None:
    """Read *text* as one whole type spelling, or ``None`` when it is not."""
    parsed = read_spelling(text)
    if parsed is None:
        return None
    spelling, end = parsed
    if skip_whitespace(text, end) != len(text):
        return None
    return spelling


def is_identifier_part(text: str) -> bool:
    """``[A-Za-z_][A-Za-z0-9_$]*`` matched against the whole string."""
    if not text:
        return False
    first = text[0]
    if first not in _ASCII_LETTERS and first != "_":
        return False
    for ch in text[1:]:
        if ch in _ASCII_LETTERS or ch in _DECIMAL_DIGITS or ch in _IDENTIFIER_TRAILING:
            continue
        return False
    return True


def is_qualified_identifier(text: str) -> bool:
    """``[A-Za-z_][A-Za-z0-9_$]*(?:\\.[A-Za-z_][A-Za-z0-9_$]*)?``, whole string."""
    parts = text.split(".")
    if len(parts) > 2:
        return False
    return all(is_identifier_part(part) for part in parts)


def is_declaration_text(text: str) -> bool:
    """``[A-Za-z_][A-Za-z0-9_$.,() \\t]*`` matched against the whole string."""
    if not text:
        return False
    first = text[0]
    if first not in _ASCII_LETTERS and first != "_":
        return False
    for ch in text[1:]:
        if ch in _ASCII_LETTERS or ch in _DECIMAL_DIGITS:
            continue
        if ch in _DECLARATION_PUNCTUATION:
            continue
        return False
    return True


__all__ = [
    "Spelling",
    "contains_word",
    "find_digit_runs",
    "find_parenthesised_number",
    "find_version_triplet",
    "is_declaration_text",
    "is_identifier_part",
    "is_qualified_identifier",
    "is_word_boundary",
    "is_word_char",
    "match_optional_precision",
    "match_word_sequence",
    "parse_spelling",
    "read_balanced_group",
    "read_digits",
    "read_head_with_precision",
    "read_spelling",
    "read_word",
    "skip_whitespace",
    "starts_with_any_word",
    "starts_with_phrase",
    "starts_with_word",
]
