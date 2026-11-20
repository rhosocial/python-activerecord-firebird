# tests/rhosocial/activerecord_firebird_test/feature/backend/execute/introspection/test_introspection_data_profile.py
"""The data-profile family, measured against a real server.

Rendering these statements proves only that they are well-formed. What needs
checking is whether Firebird accepts them, and whether the conversions the
parser performs -- the pivot of one wide row back into a record per column, the
``null_count / row_count`` fraction, and the ``NULL`` slots a BLOB leaves behind
-- land on values a hand count agrees with. That is only answerable against a
server.

The table is a hundred rows, built so every figure is arithmetic rather than
guesswork:

    id      INTEGER NOT NULL PRIMARY KEY   i, unique      -> 100 distinct, no nulls
    code    VARCHAR(8) NOT NULL            "a"/"b"/"c"   -> 3 distinct, no nulls
    amount  NUMERIC(10,2) NOT NULL         i, unique     -> 100 distinct, no nulls
    note    VARCHAR(8)                     "x"/"y"/NULL  -> 2 distinct, 60% null
    doc     BLOB SUB_TYPE TEXT             as note       -> not comparable

``note`` and ``doc`` are declared plain, not ``NULL``: Firebird has no explicit
nullability constraint and rejects the token.

The size is modest on purpose: Firebird aggregates the rows rather than reading
a histogram, so the answer does not depend on a sample being large. It only has
to be big enough that a duplicate silently dropped by ``COUNT(DISTINCT ...)``,
or a NULL miscounted by the ``SUM(CASE ...)`` slot, would move a number off its
hand-counted value -- which a hundred rows does.

Two shapes are specific to this engine and are pinned here rather than left to
be discovered. First, the profile is answered as one wide row and pivoted by the
parser, because a ``UNION ALL`` would have to reconcile one type per column
position and ``amount``'s numeric bounds do not share a type with ``code``'s
text. Second, ``doc`` is a ``BLOB``: Firebird refuses ``MIN``, ``MAX`` and
``COUNT(DISTINCT ...)`` on a type it cannot compare, so that column's row
carries its null count and the table's row count and *no* distinct count or
bounds. The distinction matters -- ``None`` there means "the engine will not
measure this", not "the engine measured nothing".
"""

import pytest

TABLE = "intro_profile_orders"
CUSTOMERS = "intro_profile_customers"
LEFT_TABLE = "intro_coverage_left"
RIGHT_TABLE = "intro_coverage_right"
CODES = ("a", "b", "c")

ROWS = 100

#: ``note`` and ``doc`` are NULL on 60 of the 100 rows, "x" on 20 and "y" on 20.
NULL_SHARE = 0.6


@pytest.fixture
def fb_backend(fb_config):
    """A connected, version-adapted backend over the configured server.

    The shared ``fb_backend`` fixture in ``tests/conftest.py`` connects and
    nothing more, and this family cannot render without the version: the value
    sample's row bound is version-dependent -- ``FETCH NEXT ... ROWS ONLY``
    from Firebird 3, ``ROWS m TO n`` before it -- so a formatter asked for it
    raises ``DialectNotAdaptedException`` rather than guessing a floor. The
    CLI adapts at its entry, and this fixture does the same here.
    """
    from rhosocial.activerecord.backend.impl.firebird.backend.backend import (
        FirebirdBackend,
    )

    backend = FirebirdBackend(connection_config=fb_config)
    backend.connect()
    backend.introspect_and_adapt()
    yield backend
    try:
        backend.disconnect()
    except Exception:
        pass


def _rows():
    rows = []
    for i in range(1, ROWS + 1):
        if i % 5 == 0:
            note = "x"
        elif i % 5 == 1:
            note = "y"
        else:
            note = None
        rows.append((i, CODES[i % 3], i, note, note))
    return rows


def _drop(backend, table):
    try:
        backend.execute(f"DROP TABLE {table}")
    except Exception:
        pass


def _setup(backend):
    _drop(backend, TABLE)
    _drop(backend, CUSTOMERS)
    backend.execute(
        f"CREATE TABLE {TABLE} ("
        "id INTEGER NOT NULL PRIMARY KEY, "
        "code VARCHAR(8) NOT NULL, "
        "amount NUMERIC(10,2) NOT NULL, "
        # No ``NULL`` keyword: Firebird has no explicit nullability constraint,
        # and rejects the token. A column is nullable unless declared NOT NULL.
        "note VARCHAR(8), "
        "doc BLOB SUB_TYPE TEXT"
        ")"
    )
    backend.execute_many(
        f"INSERT INTO {TABLE} (id, code, amount, note, doc) "
        "VALUES (?, ?, ?, ?, ?)",
        _rows(),
    )
    # The right side of every coverage measurement: four codes and one NULL.
    # The NULL is the point -- it must not be counted as a value of the domain,
    # so right coverage is 3/4 and not 3/5.
    backend.execute(
        f"CREATE TABLE {CUSTOMERS} (id INTEGER NOT NULL PRIMARY KEY, code INTEGER)"
    )
    backend.execute_many(
        f"INSERT INTO {CUSTOMERS} (id, code) VALUES (?, ?)",
        [(1, 1), (2, 2), (3, 3), (4, 4), (5, None)],
    )


def _teardown(backend):
    _drop(backend, TABLE)
    _drop(backend, CUSTOMERS)


class TestColumnDataProfile:
    """What the rows hold, counted by the server rather than read from a catalog."""

    def test_profile_matches_a_hand_count(self, fb_backend):
        _setup(fb_backend)
        try:
            profiles = {
                profile.column_name: profile
                for profile in fb_backend.introspector.list_column_data_profiles(
                    TABLE
                )
            }
            # Firebird folds identifiers to upper case, so the catalogue reports
            # them in the case the table was created with -- upper.
            assert set(profiles) == {"ID", "CODE", "AMOUNT", "NOTE", "DOC"}

            assert profiles["ID"].null_fraction == 0.0
            assert profiles["ID"].distinct_count == 100
            assert int(profiles["ID"].min_value) == 1
            assert int(profiles["ID"].max_value) == 100

            assert profiles["CODE"].null_fraction == 0.0
            assert profiles["CODE"].distinct_count == 3
            assert profiles["CODE"].min_value == "a"
            assert profiles["CODE"].max_value == "c"

            assert profiles["AMOUNT"].null_fraction == 0.0
            assert profiles["AMOUNT"].distinct_count == 100
            # A NUMERIC bound comes back as the driver's decimal, so the
            # comparison is numeric rather than string-shaped.
            assert profiles["AMOUNT"].min_value == 1
            assert profiles["AMOUNT"].max_value == 100

            # 60 of 100 rows are NULL, so a profile that dropped or clamped the
            # figure would still look plausible.
            assert profiles["NOTE"].null_fraction == pytest.approx(NULL_SHARE)
            assert profiles["NOTE"].distinct_count == 2
            assert profiles["NOTE"].min_value == "x"
            assert profiles["NOTE"].max_value == "y"

            # A BLOB has no ordering, so Firebird refuses MIN/MAX and
            # COUNT(DISTINCT ...) on it. The row still exists -- its null count
            # and the table's row count are answerable -- and the three
            # unreadable figures are absent rather than zero.
            assert profiles["DOC"].null_fraction == pytest.approx(NULL_SHARE)
            assert profiles["DOC"].distinct_count is None
            assert profiles["DOC"].min_value is None
            assert profiles["DOC"].max_value is None
        finally:
            _teardown(fb_backend)

    def test_every_profile_says_it_was_aggregated(self, fb_backend):
        """The provenance travels in the row, not in a docstring.

        Firebird keeps no statistics catalogue, so every figure is a count from
        the rows and every row says so. A consumer comparing this profile with a
        PostgreSQL estimate can tell the two apart without knowing which engine
        it asked.
        """
        _setup(fb_backend)
        try:
            profiles = fb_backend.introspector.list_column_data_profiles(TABLE)
            assert profiles
            for profile in profiles:
                assert profile.source == "aggregate"
                assert profile.row_count == ROWS
                assert profile.collected_at is None
        finally:
            _teardown(fb_backend)

    def test_empty_table_answers_no_fraction(self, fb_backend):
        """Zero rows is "not measured" for the fraction, not a fabricated zero.

        ``SUM(CASE ...)`` over no rows is NULL, so the parser has nothing to
        divide; the counts the engine can answer -- ``COUNT(*)`` and
        ``COUNT(DISTINCT ...)`` -- are real zeroes and are reported as such.
        """
        _drop(fb_backend, TABLE)
        fb_backend.execute(f"CREATE TABLE {TABLE} (id INTEGER)")
        try:
            profiles = {
                profile.column_name: profile
                for profile in fb_backend.introspector.list_column_data_profiles(
                    TABLE
                )
            }
            assert profiles["ID"].row_count == 0
            assert profiles["ID"].null_fraction is None
            assert profiles["ID"].distinct_count == 0
            assert profiles["ID"].min_value is None
        finally:
            _teardown(fb_backend)


class TestColumnValueSample:
    """The grouped listing, with NULL treated as a member of the domain."""

    def test_listing_is_ordered_by_frequency(self, fb_backend):
        _setup(fb_backend)
        try:
            samples = fb_backend.introspector.sample_column_values(
                TABLE, "code", limit=10
            )
            assert {item.value for item in samples} == set(CODES)
            # 34/33/33 by ``i % 3``, so the counts are arithmetic and the order
            # is by count first.
            assert sum(item.count for item in samples) == ROWS
            assert samples[0].count >= samples[-1].count
        finally:
            _teardown(fb_backend)

    def test_limit_bounds_the_listing(self, fb_backend):
        _setup(fb_backend)
        try:
            assert (
                len(
                    fb_backend.introspector.sample_column_values(
                        TABLE, "code", limit=2
                    )
                )
                == 2
            )
        finally:
            _teardown(fb_backend)

    def test_null_is_a_listed_value(self, fb_backend):
        """Firebird groups NULLs, so a column holding them lists one NULL entry.

        That is the opposite of PostgreSQL, whose most-common list never holds
        NULL because the null share is a separate figure. Same question, two
        engines, two shapes -- which is exactly why a caller reads
        ``null_fraction`` rather than scanning the listing for a NULL.
        """
        _setup(fb_backend)
        try:
            samples = fb_backend.introspector.sample_column_values(
                TABLE, "note", limit=10
            )
            values = {item.value: item.count for item in samples}
            assert values[None] == 60
            assert values["x"] == 20
            assert values["y"] == 20
        finally:
            _teardown(fb_backend)


def _coverage_setup(backend, left_values, right_values):
    """Two one-column tables, filled with the values the case was written for."""
    for table in (LEFT_TABLE, RIGHT_TABLE):
        _drop(backend, table)
        backend.execute(f"CREATE TABLE {table} (code INTEGER)")
    backend.execute_many(
        f"INSERT INTO {LEFT_TABLE} (code) VALUES (?)",
        [(value,) for value in left_values],
    )
    backend.execute_many(
        f"INSERT INTO {RIGHT_TABLE} (code) VALUES (?)",
        [(value,) for value in right_values],
    )


def _coverage_teardown(backend):
    for table in (LEFT_TABLE, RIGHT_TABLE):
        _drop(backend, table)


def _coverage(backend):
    return backend.introspector.estimate_join_coverage(
        LEFT_TABLE, "code", RIGHT_TABLE, "code"
    )


class TestJoinCoverage:
    """How far two columns' distinct value domains overlap.

    Every expectation is arithmetic rather than a recorded run: ``left`` has
    ``{1,2,3,4}`` and ``right`` has ``{2,3,4,5,6}``, so three of the four left
    values are matched and three of the five right ones are. The two figures are
    different on purpose -- an implementation that answered the same number
    twice, or averaged them, would still look plausible.

    The ``* 1.0`` in the statement is load-bearing on this engine: Firebird's
    ``/`` over two integer counts is integer arithmetic, so three quarters would
    answer zero without it.
    """

    def test_both_fractions_match_a_hand_count(self, fb_backend):
        _coverage_setup(fb_backend, range(1, 5), range(2, 7))
        try:
            coverage = _coverage(fb_backend)
            assert coverage is not None
            assert coverage.left_coverage == pytest.approx(3 / 4)
            assert coverage.right_coverage == pytest.approx(3 / 5)
        finally:
            _coverage_teardown(fb_backend)

    def test_values_are_counted_not_rows(self, fb_backend):
        """A repeated key that matches once is one covered value, not three.

        The left table holds four rows but only two distinct values, and the
        repeated value is the matched one: counting rows would answer 3/4 where
        the share of values is 1/2.
        """
        _coverage_setup(fb_backend, (2, 2, 2, 1), (2, 3))
        try:
            coverage = _coverage(fb_backend)
            assert coverage is not None
            assert coverage.left_coverage == pytest.approx(1 / 2)
            assert coverage.right_coverage == pytest.approx(1 / 2)
        finally:
            _coverage_teardown(fb_backend)

    def test_no_overlap_is_zero_not_none(self, fb_backend):
        """Disjoint domains are a measurement: both sides really are uncovered.

        ``None`` means "the engine could not measure", which is a different
        answer from "nothing matched", and a caller deciding whether a join is
        worth writing has to be able to tell them apart.
        """
        _coverage_setup(fb_backend, (1, 2, 3), (10, 11))
        try:
            coverage = _coverage(fb_backend)
            assert coverage is not None
            assert coverage.left_coverage == 0.0
            assert coverage.right_coverage == 0.0
        finally:
            _coverage_teardown(fb_backend)

    def test_a_side_with_no_value_answers_no_fraction(self, fb_backend):
        """A column of nothing but NULLs has no share to report.

        NULLs are excluded from the divisors as well as the numerators, and
        ``NULLIF`` turns the empty denominator into NULL. So the left side --
        which has no value at all -- answers ``None``, while the right side,
        which has values that simply did not match, answers a real zero.
        """
        _coverage_setup(fb_backend, (None, None), (1, 2))
        try:
            coverage = _coverage(fb_backend)
            assert coverage is not None
            assert coverage.left_coverage is None
            assert coverage.right_coverage == 0.0
        finally:
            _coverage_teardown(fb_backend)

    def test_neither_side_having_a_value_is_no_measurement(self, fb_backend):
        """When both fractions are NULL the parser reports nothing measured."""
        _coverage_setup(fb_backend, (None,), (None,))
        try:
            assert _coverage(fb_backend) is None
        finally:
            _coverage_teardown(fb_backend)
