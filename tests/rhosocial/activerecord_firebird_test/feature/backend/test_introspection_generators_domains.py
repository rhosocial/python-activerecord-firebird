# tests/rhosocial/activerecord_firebird_test/feature/backend/test_introspection_generators_domains.py
"""Generators, domains and the cache discipline that answers for them.

Two halves, split the way this directory already splits them:

**Offline.** The questions are built from expression nodes, so the rendered
statements are read back here: ``GEN_ID(<name>, 0)`` for a value, a LEFT JOIN
to the charset (an inner join would drop every numeric domain), and the filters
that keep Firebird's own nameless domain rows out of an answer about the
domains a caller created. The parsers are pure, so they are pinned against
catalogue-shaped rows too -- including the type codes Firebird uses for
``NUMERIC``/``DECIMAL`` and the blobs a domain's default and check arrive in.

**Live.** The rest needs a server: create a generator and a domain, then assert
that the typed results describe them, that reading a generator with
``GEN_ID(name, 0)`` did not advance it, that the CLI's two new introspection
types answer, and that the second call is answered from the cache with zero
catalogue statements. Without a reachable server the live half skips, as
``test_firebird_literal_defaults.py`` does -- a missing driver is a reason to
skip, never to pass.

These cases create and drop real objects, so the module is grouped onto one
worker with the other connected modules; see the reason, once, in this
directory's conftest.
"""

import io
import json
import uuid
from contextlib import redirect_stderr, redirect_stdout

import pytest

from rhosocial.activerecord.backend.impl.firebird.__main__ import main
from rhosocial.activerecord.backend.impl.firebird.backend import FirebirdBackend
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.introspection.async_introspector import (
    FirebirdAsyncIntrospectorMixin,
)
from rhosocial.activerecord.backend.impl.firebird.introspection.types import (
    FirebirdDomainInfo,
    FirebirdGeneratorInfo,
)

pytestmark = pytest.mark.xdist_group("live_db")


class _Probe(FirebirdAsyncIntrospectorMixin):
    """The shared builders and parsers, with only a dialect behind them."""

    def __init__(self, dialect):
        self._backend = type("_B", (), {"dialect": dialect})()


@pytest.fixture
def probe():
    return _Probe(FirebirdDialect(version=(4, 0, 0)))


# ---------------------------------------------------------------------------
# Offline: the questions
# ---------------------------------------------------------------------------


class TestGeneratorStatements:
    def test_list_asks_the_catalogue_by_name(self, probe):
        sql, params = probe.generator_list_statement().to_sql()
        assert sql == (
            'SELECT "RDB$GENERATOR_NAME" AS "GENERATOR_NAME", '
            '"RDB$SYSTEM_FLAG" AS "SYSTEM_FLAG" FROM "RDB$GENERATORS" '
            'WHERE "RDB$SYSTEM_FLAG" = 0 ORDER BY "RDB$GENERATOR_NAME"'
        )
        assert params == ()

    def test_include_system_drops_the_filter(self, probe):
        sql, params = probe.generator_list_statement(include_system=True).to_sql()
        assert "WHERE" not in sql
        assert params == ()

    def test_value_is_a_zero_increment_named_as_an_identifier(self, probe):
        """``GEN_ID(name, 0)``: a read, and the name is an identifier, not a value.

        The name walks in as an :class:`Identifier`, so the dialect spells it
        -- Firebird folds an unquoted name to upper case, and asserting a
        spelling here would pin the dialect's folding rule rather than this
        statement's contract. What must hold is that the name is quoted into
        the call text, not pushed into the parameter tuple. The next test pins
        what that means when the name cannot be spelled as one identifier.
        """
        sql, params = probe.generator_value_statement("my_gen").to_sql()
        assert "GEN_ID(" in sql
        assert '"' in sql.split("GEN_ID(", 1)[1].split(")", 1)[0]
        assert params == ()
        assert "?" not in sql
        assert sql.endswith('AS "GENERATOR_VALUE" FROM "RDB$DATABASE"')

    def test_value_name_is_quoted_not_bound(self, probe):
        """A bind marker in GEN_ID's first argument is a syntax error."""
        sql, _ = probe.generator_value_statement('odd "name').to_sql()
        assert '?' not in sql
        assert '"ODD ""NAME"' in sql or "odd" in sql.lower()


class TestDomainStatements:
    def test_reads_the_one_catalogue_row(self, probe):
        """``RDB$FIELDS`` is the whole answer; there is no ``RDB$DOMAINS``.

        The earlier version of this query joined ``RDB$DOMAINS``, which does
        not exist -- the server refused it with "Table unknown". Firebird keeps
        domain and column definitions on ``RDB$FIELDS`` (language reference
        D.11), name and type descriptor together, so the read is one relation
        and the join that used to split it across two is gone.
        """
        sql, params = probe.domain_list_statement().to_sql()
        assert '"RDB$FIELDS"' in sql
        assert "RDB$DOMAINS" not in sql
        assert params == ()

    def test_the_named_domain_filter_is_on_the_name(self, probe):
        """``NOT LIKE 'RDB$%'`` -- the discriminator the docs state.

        ``RDB$FIELDS`` also holds the row Firebird generates for every
        inline-declared column, and those are not objects a caller created.
        The language reference notes that system-created domain names start
        with ``RDB$``, so the filter is on the name.
        """
        sql, _ = probe.domain_list_statement().to_sql()
        assert "NOT LIKE" in sql
        assert "RDB$%" in sql

    def test_system_rows_are_filtered_unless_asked_for(self, probe):
        filtered, _ = probe.domain_list_statement().to_sql()
        everything, _ = probe.domain_list_statement(include_system=True).to_sql()
        # Both filters say something different, so both are pinned: the flag
        # is what ``is_system`` on the result is read from, and the name is
        # what removes the engine's implicit column descriptors.
        assert '"RDB$SYSTEM_FLAG" = 0' in filtered
        assert "NOT LIKE" not in everything

    def test_the_flag_filter_matches_what_the_result_reports(self, probe):
        """The filter and ``is_system`` read the same column.

        A listing that returned system rows while reporting ``is_system``
        False on each of them would be lying in the field the caller reads.
        """
        sql, _ = probe.domain_list_statement().to_sql()
        assert 'AS "SYSTEM_FLAG"' in sql
        assert '"RDB$SYSTEM_FLAG" = 0' in sql

    def test_charset_is_a_left_join(self, probe):
        """An inner join would drop every non-character domain."""
        sql, _ = probe.domain_list_statement().to_sql()
        assert 'LEFT JOIN "RDB$CHARACTER_SETS" AS "CS"' in sql

    def test_the_projection_carries_what_the_parser_reads(self, probe):
        """Every alias ``parse_domains`` looks up is projected.

        A missing one is a silent ``None`` rather than a failure, which is the
        worse of the two ways for this to be wrong.
        """
        sql, _ = probe.domain_list_statement().to_sql()
        for alias in (
            "DOMAIN_NAME", "FIELD_TYPE", "FIELD_SUB_TYPE", "FIELD_LENGTH",
            "CHARACTER_LENGTH", "PRECISION", "SCALE", "CHARACTER_SET_NAME",
            "NULL_FLAG", "DEFAULT_SOURCE", "VALIDATION_SOURCE", "SYSTEM_FLAG",
            "DESCRIPTION",
        ):
            assert 'AS "%s"' % alias in sql, alias


# ---------------------------------------------------------------------------
# Offline: the parsers
# ---------------------------------------------------------------------------


def _domain_row(**overrides):
    row = {
        "DOMAIN_NAME": "POSITIVE_INT ",
        "FIELD_TYPE": 8,
        "FIELD_SUB_TYPE": 0,
        "FIELD_LENGTH": 4,
        "CHARACTER_LENGTH": None,
        "PRECISION": None,
        "SCALE": 0,
        "CHARACTER_SET_NAME": None,
        "NULL_FLAG": 1,
        "DEFAULT_SOURCE": None,
        "VALIDATION_SOURCE": None,
        "SYSTEM_FLAG": 0,
        "DESCRIPTION": None,
    }
    row.update(overrides)
    return row


class TestDomainParsing:
    def test_character_domain_keeps_every_declared_attribute(self, probe):
        domain = probe.parse_domains(
            [
                _domain_row(
                    DOMAIN_NAME="CODE",
                    FIELD_TYPE=37,  # VARCHAR
                    FIELD_LENGTH=96,
                    CHARACTER_LENGTH=24,
                    CHARACTER_SET_NAME="UTF8",
                    NULL_FLAG=None,
                    DEFAULT_SOURCE="'n/a'",
                    VALIDATION_SOURCE="VALUE <> ''",
                    DESCRIPTION="a short code",
                )
            ]
        )[0]
        assert isinstance(domain, FirebirdDomainInfo)
        assert domain.name == "CODE"
        assert domain.base_type == "VARCHAR"
        assert domain.length == 96
        assert domain.character_length == 24
        assert domain.charset == "UTF8"
        assert domain.nullable is True
        assert domain.default_source == "'n/a'"
        assert domain.check_source == "VALUE <> ''"
        assert domain.description == "a short code"
        assert domain.is_system is False

    def test_not_null_is_the_catalogue_flag_not_the_absence_of_a_value(self, probe):
        domain = probe.parse_domains([_domain_row(NULL_FLAG=1)])[0]
        assert domain.nullable is False

    def test_names_are_stripped_of_char_padding(self, probe):
        assert probe.parse_domains([_domain_row()])[0].name == "POSITIVE_INT"

    @pytest.mark.parametrize(
        "field_type,sub_type,scale,expected",
        [
            (8, 1, -2, "NUMERIC"),
            (8, 2, -2, "DECIMAL"),
            (16, 2, -4, "DECIMAL"),
            (8, 0, 0, "INTEGER"),
            (7, 0, 0, "SMALLINT"),
            (261, 1, 0, "BLOB SUB_TYPE TEXT"),
            (261, 0, 0, "BLOB SUB_TYPE BINARY"),
        ],
    )
    def test_base_type_names_what_was_declared(self, probe, field_type, sub_type, scale, expected):
        """NUMERIC/DECIMAL are an integer code plus a negative scale, not INTEGER."""
        domain = probe.parse_domains(
            [_domain_row(FIELD_TYPE=field_type, FIELD_SUB_TYPE=sub_type, SCALE=scale)]
        )[0]
        assert domain.base_type == expected

    def test_empty_rows_mean_no_domains(self, probe):
        assert probe.parse_domains([]) == []

    def test_nameless_rows_are_skipped(self, probe):
        assert probe.parse_domains([_domain_row(DOMAIN_NAME=None)]) == []


class TestGeneratorParsing:
    def test_the_value_is_the_one_read_for_that_generator(self, probe):
        rows = [
            {"GENERATOR_NAME": "GEN_A ", "SYSTEM_FLAG": 0},
            {"GENERATOR_NAME": "GEN_B", "SYSTEM_FLAG": 1},
        ]
        generators = probe.parse_generators(rows, {"GEN_A": 7, "GEN_B": 0})
        assert generators == [
            FirebirdGeneratorInfo(name="GEN_A", value=7, is_system=False),
            FirebirdGeneratorInfo(name="GEN_B", value=0, is_system=True),
        ]

    def test_nameless_rows_are_skipped(self, probe):
        assert probe.parse_generators([{"GENERATOR_NAME": None}], {}) == []


class TestLookupByName:
    def test_case_insensitive_unquoted_names_match(self, probe):
        items = [FirebirdGeneratorInfo(name="MY_GEN", value=1)]
        assert probe._find_by_name(items, "my_gen").name == "MY_GEN"

    def test_exact_match_wins_over_folding(self, probe):
        items = [
            FirebirdGeneratorInfo(name="MixedCase", value=1),
            FirebirdGeneratorInfo(name="MIXEDCASE", value=2),
        ]
        assert probe._find_by_name(items, "MixedCase").value == 1
        assert probe._find_by_name(items, "MIXEDCASE").value == 2

    def test_missing_name_is_none(self, probe):
        assert probe._find_by_name([FirebirdGeneratorInfo(name="A", value=0)], "B") is None


# ---------------------------------------------------------------------------
# Live: the answers
# ---------------------------------------------------------------------------


@pytest.fixture
def live_backend(fb_config):
    backend = FirebirdBackend(connection_config=fb_config)
    try:
        backend.connect()
    except Exception as exc:
        pytest.skip(f"no reachable Firebird server: {exc}")
    yield backend
    try:
        backend.disconnect()
    except Exception:
        pass


@pytest.fixture
def demo_objects(live_backend):
    """One generator (set to 7) and one domain, both dropped afterwards."""
    suffix = uuid.uuid4().hex[:8].upper()
    generator = f"AR_FB_GEN_{suffix}"
    domain = f"AR_FB_DOM_{suffix}"

    live_backend.execute(f"CREATE GENERATOR {generator}", fetch=False)
    live_backend.execute(f"SET GENERATOR {generator} TO 7", fetch=False)
    # The clause order is Firebird's, not free: ``DEFAULT`` must precede
    # ``NOT NULL``. Writing them the other way round parses up to the word
    # DEFAULT and then fails with "Token unknown", which is what CI reported.
    # This is the order the project's own domain renderer emits
    # (firebird/types.py: type, CHARACTER SET, DEFAULT, NOT NULL, CHECK).
    live_backend.execute(
        f"CREATE DOMAIN {domain} AS VARCHAR(24) CHARACTER SET UTF8 "
        f"DEFAULT 'n/a' NOT NULL CHECK (VALUE <> '')",
        fetch=False,
    )
    try:
        yield generator, domain
    finally:
        for statement in (f"DROP DOMAIN {domain}", f"DROP GENERATOR {generator}"):
            try:
                live_backend.execute(statement, fetch=False)
            except Exception:
                pass


class TestLiveGenerators:
    def test_list_reports_the_value_the_generator_holds(self, live_backend, demo_objects):
        generator, _ = demo_objects
        generators = live_backend.introspector.list_generators()
        assert all(isinstance(g, FirebirdGeneratorInfo) for g in generators)
        found = next(g for g in generators if g.name == generator)
        assert found.value == 7
        assert found.is_system is False

    def test_reading_a_generator_does_not_advance_it(self, live_backend, demo_objects):
        """``GEN_ID(name, 0)`` is a read; the second listing sees the same number."""
        generator, _ = demo_objects
        introspector = live_backend.introspector
        first = next(g for g in introspector.list_generators() if g.name == generator)
        introspector.clear_cache()
        second = next(g for g in introspector.list_generators() if g.name == generator)
        assert first.value == second.value == 7

    def test_get_generator_info_folds_an_unquoted_name(self, live_backend, demo_objects):
        generator, _ = demo_objects
        found = live_backend.introspector.get_generator_info(generator.lower())
        assert found is not None
        assert found.name == generator
        assert found.value == 7

    def test_unknown_generator_is_none(self, live_backend):
        assert live_backend.introspector.get_generator_info("AR_FB_NO_SUCH_GENERATOR") is None

    def test_user_listing_holds_no_system_generators(self, live_backend):
        assert all(not g.is_system for g in live_backend.introspector.list_generators())


class TestLiveDomains:
    def test_list_reports_the_declared_attributes(self, live_backend, demo_objects):
        _, domain_name = demo_objects
        domains = live_backend.introspector.list_domains()
        assert all(isinstance(d, FirebirdDomainInfo) for d in domains)
        domain = next(d for d in domains if d.name == domain_name)
        assert domain.base_type == "VARCHAR"
        assert domain.character_length == 24
        assert domain.charset == "UTF8"
        assert domain.nullable is False
        assert domain.default_source is not None
        assert "n/a" in domain.default_source
        assert domain.check_source is not None
        assert "VALUE" in domain.check_source.upper()
        assert domain.is_system is False

    def test_get_domain_info_folds_an_unquoted_name(self, live_backend, demo_objects):
        _, domain_name = demo_objects
        found = live_backend.introspector.get_domain_info(domain_name.lower())
        assert found is not None
        assert found.name == domain_name

    def test_unknown_domain_is_none(self, live_backend):
        assert live_backend.introspector.get_domain_info("AR_FB_NO_SUCH_DOMAIN") is None

    def test_user_listing_holds_no_system_domains(self, live_backend):
        assert all(not d.is_system for d in live_backend.introspector.list_domains())


# ---------------------------------------------------------------------------
# Live: the cache
# ---------------------------------------------------------------------------


class _CountingExecutor:
    def __init__(self, inner):
        self._inner = inner
        self.questions = 0

    def execute(self, sql, params=()):
        self.questions += 1
        return self._inner.execute(sql, params)


class TestLiveCache:
    def test_the_second_pass_asks_the_catalogue_nothing(self, live_backend, demo_objects):
        introspector = live_backend.introspector
        counting = _CountingExecutor(introspector._executor)
        introspector._executor = counting
        try:
            assert introspector.list_generators()
            assert introspector.list_domains()
            cold = counting.questions
            assert cold > 0, "the cold pass must actually ask the catalogue"

            counting.questions = 0
            introspector.list_generators()
            introspector.list_domains()
            assert counting.questions == 0
        finally:
            introspector._executor = counting._inner

    def test_invalidation_makes_the_next_pass_cold_again(self, live_backend, demo_objects):
        from rhosocial.activerecord.backend.introspection.types import IntrospectionScope

        introspector = live_backend.introspector
        assert introspector.list_generators()
        counting = _CountingExecutor(introspector._executor)
        introspector._executor = counting
        try:
            counting.questions = 0
            introspector.list_generators()
            assert counting.questions == 0

            introspector.invalidate_cache(IntrospectionScope.SEQUENCE)
            introspector.list_generators()
            assert counting.questions > 0
        finally:
            introspector._executor = counting._inner


# ---------------------------------------------------------------------------
# Live: the CLI
# ---------------------------------------------------------------------------


def _run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    code = None
    with redirect_stdout(out), redirect_stderr(err):
        try:
            main(argv)
        except SystemExit as exc:
            code = exc.code
    return out.getvalue(), err.getvalue(), code


@pytest.fixture
def conn_args(fb_config):
    return [
        "--host", fb_config.host,
        "--port", str(fb_config.port),
        "--database", fb_config.database,
        "--user", fb_config.username,
        "--password", fb_config.password or "",
        "--charset", fb_config.charset,
    ]


class TestCliGenerators:
    def test_lists_generators_as_json(self, demo_objects, conn_args):
        generator, _ = demo_objects
        out, err, code = _run_cli(["introspect", "generators"] + conn_args + ["-o", "json"])
        assert code is None, f"stderr: {err}\nstdout: {out}"
        rows = json.loads(out)
        found = next(row for row in rows if row["name"] == generator)
        assert found["value"] == 7
        assert found["is_system"] is False

    def test_one_generator_by_name(self, demo_objects, conn_args):
        generator, _ = demo_objects
        out, err, code = _run_cli(
            ["introspect", "generators", generator] + conn_args + ["-o", "json"]
        )
        assert code is None, f"stderr: {err}\nstdout: {out}"
        rows = json.loads(out)
        assert len(rows) == 1
        assert rows[0]["name"] == generator

    def test_unknown_generator_exits_nonzero(self, live_backend, conn_args):
        out, err, code = _run_cli(
            ["introspect", "generators", "AR_FB_NO_SUCH_GENERATOR"] + conn_args + ["-o", "json"]
        )
        assert code == 1
        assert "not found" in err


class TestCliDomains:
    def test_lists_domains_as_json(self, demo_objects, conn_args):
        _, domain = demo_objects
        out, err, code = _run_cli(["introspect", "domains"] + conn_args + ["-o", "json"])
        assert code is None, f"stderr: {err}\nstdout: {out}"
        rows = json.loads(out)
        found = next(row for row in rows if row["name"] == domain)
        assert found["base_type"] == "VARCHAR"
        assert found["charset"] == "UTF8"
        assert found["nullable"] is False

    def test_one_domain_by_name(self, demo_objects, conn_args):
        _, domain = demo_objects
        out, err, code = _run_cli(
            ["introspect", "domains", domain] + conn_args + ["-o", "json"]
        )
        assert code is None, f"stderr: {err}\nstdout: {out}"
        rows = json.loads(out)
        assert len(rows) == 1
        assert rows[0]["name"] == domain

    def test_unknown_domain_exits_nonzero(self, live_backend, conn_args):
        out, err, code = _run_cli(
            ["introspect", "domains", "AR_FB_NO_SUCH_DOMAIN"] + conn_args + ["-o", "json"]
        )
        assert code == 1
        assert "not found" in err
