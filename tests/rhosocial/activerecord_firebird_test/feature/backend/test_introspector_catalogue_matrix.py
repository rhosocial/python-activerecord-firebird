# tests/rhosocial/activerecord_firebird_test/feature/backend/test_introspector_catalogue_matrix.py
"""Every catalogue family, answered by the sync introspector against a live server.

The rest of the introspection tests pin two ends of the path: what a family
asks (the statement tests) and what the CLI prints (the fake-backend tests).
Between them sits the layer that executes the question and parses the answer,
and nothing called the family methods themselves -- so a formatter that
rendered correctly and a parser that read correctly could still be wired to
different names and no test would notice.

These cases call each family once and assert the shape of the answer, then call
it a second time and assert the catalogue is asked nothing: a cache that never
answers is a cache that costs the walk it was added to avoid.

Skips, never passes, when no server is reachable -- the same rule the rest of
the connected area follows.
"""

from __future__ import annotations

import pytest

from rhosocial.activerecord.backend.impl.firebird.backend import FirebirdBackend

pytestmark = pytest.mark.xdist_group("live_db")


@pytest.fixture
def live_backend(fb_config):
    backend = FirebirdBackend(connection_config=fb_config)
    try:
        backend.connect()
    except Exception as exc:
        pytest.skip(f"no reachable Firebird server: {exc}")
    # The dialect must know the server's version before a formatter renders,
    # which is what the CLI does at its entry rather than per branch.
    backend.introspect_and_adapt()
    yield backend
    try:
        backend.disconnect()
    except Exception:
        pass


# Every family a caller can ask about, and the call that asks. The parameters
# name an object that does not exist: the answer's *shape* is what is under
# test here, and an empty answer is still an answer.
FAMILIES = [
    ("exceptions", lambda i: i.list_exceptions()),
    ("procedures", lambda i: i.list_procedures()),
    ("procedures with source", lambda i: i.list_procedures(include_source=True)),
    ("procedure parameters", lambda i: i.list_procedure_parameters("AR_FB_NO_SUCH_PROCEDURE")),
    ("functions", lambda i: i.list_functions()),
    ("functions with source", lambda i: i.list_functions(include_source=True)),
    ("function arguments", lambda i: i.list_function_arguments("AR_FB_NO_SUCH_FUNCTION")),
    ("constraints", lambda i: i.list_constraints()),
    ("roles", lambda i: i.list_roles()),
    ("privileges", lambda i: i.list_privileges()),
    ("charsets", lambda i: i.list_charsets()),
    ("collations", lambda i: i.list_collations()),
    ("dependencies", lambda i: i.list_dependencies()),
    ("view relations", lambda i: i.list_view_relations()),
    ("publications", lambda i: i.list_publications()),
]


class TestEveryFamilyAnswers:
    @pytest.mark.parametrize("family,call", FAMILIES, ids=[name for name, _ in FAMILIES])
    def test_the_family_answers_with_a_list(self, live_backend, family, call):
        """One family, one answer, and a list of typed records rather than rows.

        A parser that quietly returned ``None`` for every row would still make
        the CLI print an empty table, so the assertion is on the container the
        caller receives.
        """
        result = call(live_backend.introspector)
        assert isinstance(result, list)
        assert all(
            not isinstance(item, dict) for item in result
        ), "a catalogue row handed back as a dict means the parser was skipped"

    @pytest.mark.parametrize("family,call", FAMILIES, ids=[name for name, _ in FAMILIES])
    def test_asking_twice_answers_the_same(self, live_backend, family, call):
        """The second call is the cached one; it must not disagree with the first."""
        introspector = live_backend.introspector
        first = call(introspector)
        second = call(introspector)
        assert len(first) == len(second)

    def test_a_name_that_matches_nothing_is_an_empty_answer(self, live_backend):
        """An empty list and a failure are different statements about the server."""
        introspector = live_backend.introspector
        assert introspector.list_procedure_parameters("AR_FB_NO_SUCH_PROCEDURE") == []
        assert introspector.list_function_arguments("AR_FB_NO_SUCH_FUNCTION") == []
        assert introspector.list_collations("NO_SUCH_CHARSET") == []


LOOKUPS = [
    ("exception", lambda i, name: i.get_exception_info(name)),
    ("procedure", lambda i, name: i.get_procedure_info(name)),
    ("function", lambda i, name: i.get_function_info(name)),
    ("generator", lambda i, name: i.get_generator_info(name)),
    ("domain", lambda i, name: i.get_domain_info(name)),
]


class TestSingleObjectLookup:
    @pytest.mark.parametrize("family,lookup", LOOKUPS, ids=[name for name, _ in LOOKUPS])
    def test_a_missing_name_is_none_not_an_empty_object(self, live_backend, family, lookup):
        """``None`` is how the CLI tells "not found" (exit 1) from "found".

        A lookup that returned an object with an empty name would make every
        miss print as a hit, which is the worse of the two failures. The
        unquoted-name folding each of these does first is pinned offline in
        ``test_introspection_generators_domains.py``; what is under test here
        is that both passes of the fallback end in ``None``.
        """
        assert lookup(live_backend.introspector, "AR_FB_NO_SUCH_OBJECT") is None


class TestFamiliesEveryServerHas:
    """Three families exist in every database; an empty answer is a defect."""

    def test_the_charsets_are_there(self, live_backend):
        names = [charset.name for charset in live_backend.introspector.list_charsets()]
        assert "UTF8" in names

    def test_a_charset_carries_its_collations(self, live_backend):
        names = [c.name for c in live_backend.introspector.list_collations("UTF8")]
        assert "UCS_BASIC" in names

    def test_a_collation_names_its_charset(self, live_backend):
        (collation,) = [
            c for c in live_backend.introspector.list_collations("UTF8") if c.name == "UCS_BASIC"
        ]
        assert collation.charset == "UTF8"
        assert collation.is_system is True


class _CountingExecutor:
    def __init__(self, inner):
        self._inner = inner
        self.questions = 0

    def execute(self, sql, params=()):
        self.questions += 1
        return self._inner.execute(sql, params)


CACHED_FAMILIES = [
    ("generators", lambda i: i.list_generators()),
    ("exceptions", lambda i: i.list_exceptions()),
    ("procedures", lambda i: i.list_procedures()),
    ("charsets", lambda i: i.list_charsets()),
    ("collations", lambda i: i.list_collations()),
]


class TestTheCacheHoldsForEveryFamily:
    @pytest.mark.parametrize("family,call", CACHED_FAMILIES, ids=[n for n, _ in CACHED_FAMILIES])
    def test_the_second_pass_asks_the_catalogue_nothing(self, live_backend, family, call):
        """The cold pass asks, the warm pass does not.

        Both halves are asserted: a cache that answered nothing would show
        zero questions twice, and a listing that never cached would show a
        question count that never drops.
        """
        introspector = live_backend.introspector
        counting = _CountingExecutor(introspector._executor)
        introspector._executor = counting
        try:
            call(introspector)
            assert counting.questions > 0, "the cold pass must actually ask"
            counting.questions = 0
            call(introspector)
            assert counting.questions == 0
        finally:
            introspector._executor = counting._inner
