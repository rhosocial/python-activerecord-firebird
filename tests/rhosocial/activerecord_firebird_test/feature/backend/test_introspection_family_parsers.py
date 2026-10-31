# tests/rhosocial/activerecord_firebird_test/feature/backend/test_introspection_family_parsers.py
"""The schema-object families: the question each one asks and the row it reads.

The CLI can offer twenty-two types and the builders can render every statement,
but between them sits the pair this module pins -- a statement factory that
turns a family into a question, and a parser that turns the catalogue's rows
back into the typed record the CLI serialises.

The parsers earn their own tests because they fail quietly: every field is read
with ``row.get(...)``, so an alias the projection forgot arrives as ``None``
rather than as an error. Each case below is therefore a row shaped like that
family's own projection, which is the only way to tell "the catalogue had
nothing to say" from "the read never asked".

Generators, domains and their cache discipline live beside this file in
``test_introspection_generators_domains.py``; the families here are the ones the
core introspection contract has no shape for, so Firebird owns both directions.
"""

from __future__ import annotations

import pytest

from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.introspection.async_introspector import (
    FirebirdAsyncIntrospectorMixin,
)


class _Probe(FirebirdAsyncIntrospectorMixin):
    """The shared builders and parsers, with only a dialect behind them."""

    def __init__(self, dialect):
        self._backend = type("_B", (), {"dialect": dialect})()


@pytest.fixture
def probe():
    return _Probe(FirebirdDialect(version=(6, 0, 0)))


# ---------------------------------------------------------------------------
# The questions
# ---------------------------------------------------------------------------

# (family, builder, the relation it reads, whether a SYSTEM_FLAG filter is
#  expected on the default read)
LIST_QUESTIONS = [
    ("exceptions", lambda p: p.exception_list_statement(), "RDB$EXCEPTIONS", True),
    ("procedures", lambda p: p.procedure_list_statement(), "RDB$PROCEDURES", True),
    ("functions", lambda p: p.function_list_statement(), "RDB$FUNCTIONS", True),
    ("constraints", lambda p: p.constraint_list_statement(), "RDB$RELATION_CONSTRAINTS", False),
    ("roles", lambda p: p.role_list_statement(), "RDB$ROLES", True),
    ("privileges", lambda p: p.privilege_statement(), "RDB$USER_PRIVILEGES", False),
    ("charsets", lambda p: p.charset_list_statement(), "RDB$CHARACTER_SETS", False),
    ("collations", lambda p: p.collation_list_statement(), "RDB$COLLATIONS", False),
    ("dependencies", lambda p: p.dependency_statement(), "RDB$DEPENDENCIES", False),
    ("view relations", lambda p: p.view_relation_statement(), "RDB$VIEW_RELATIONS", False),
    ("publications", lambda p: p.publication_list_statement(), "RDB$PUBLICATIONS", True),
]


class TestListQuestions:
    @pytest.mark.parametrize("family,build,relation,system_filtered", LIST_QUESTIONS)
    def test_reads_the_relation_that_holds_the_family(
        self, probe, family, build, relation, system_filtered
    ):
        """One family, one relation: the read names it and binds nothing.

        A listing question takes no value -- its whole answer is the filter --
        so a parameter here would mean a name had been turned into a bind the
        caller cannot supply.
        """
        sql, params = build(probe).to_sql()
        assert f'"{relation}"' in sql
        assert params == ()

    @pytest.mark.parametrize("family,build,relation,system_filtered", LIST_QUESTIONS)
    def test_the_answer_has_an_order(self, probe, family, build, relation, system_filtered):
        """An unordered list is an answer whose rows move between runs."""
        sql, _ = build(probe).to_sql()
        assert "ORDER BY" in sql

    @pytest.mark.parametrize("family,build,relation,system_filtered", LIST_QUESTIONS)
    def test_the_default_read_says_which_families_filter_system_rows(
        self, probe, family, build, relation, system_filtered
    ):
        """Five families are flagged row by row; the rest are not.

        The flag is what ``is_system`` on every result is read from, so a
        listing that filtered while reporting the flag as a field of the same
        row would be self-contradictory. Naming the five here is also what
        keeps the switch meaningful: the other families have no system rows to
        hide, and their answer is narrowed by name instead.
        """
        sql, _ = build(probe).to_sql()
        assert ('"RDB$SYSTEM_FLAG" = 0' in sql) is system_filtered


SYSTEM_FLAG_QUESTIONS = [
    ("exceptions", lambda p, system: p.exception_list_statement(system)),
    ("procedures", lambda p, system: p.procedure_list_statement(system)),
    ("functions", lambda p, system: p.function_list_statement(system)),
    ("roles", lambda p, system: p.role_list_statement(system)),
    ("publications", lambda p, system: p.publication_list_statement(system)),
]


class TestSystemFlagSwitch:
    """``include_system`` on the five families Firebird flags individually."""

    @pytest.mark.parametrize("family,build", SYSTEM_FLAG_QUESTIONS)
    def test_asking_for_system_rows_drops_the_filter(self, probe, family, build):
        """A switch that is accepted and ignored is worse than none: the caller
        believes the answer changed when the same rows came back.
        """
        filtered, _ = build(probe, False).to_sql()
        everything, params = build(probe, True).to_sql()
        assert '"RDB$SYSTEM_FLAG" = 0' in filtered
        assert '"RDB$SYSTEM_FLAG" = 0' not in everything
        assert params == ()


NAMED_QUESTIONS = [
    (
        "exception",
        lambda p, name: p.exception_info_statement(name),
        '"RDB$EXCEPTION_NAME"',
    ),
    (
        "procedure parameters",
        lambda p, name: p.procedure_parameter_statement(name),
        '"P"."RDB$PROCEDURE_NAME"',
    ),
    (
        "function arguments",
        lambda p, name: p.function_argument_statement(name),
        '"RDB$FUNCTION_NAME"',
    ),
]


class TestNamedQuestions:
    @pytest.mark.parametrize("family,build,column", NAMED_QUESTIONS)
    def test_the_name_is_a_bind_not_text(self, probe, family, build, column):
        """A name the caller supplies arrives as a parameter, always.

        These questions name one object, so the name is the only thing that
        varies; spelling it into the statement is how a catalogue read becomes
        an injection point. The quote inside the sample is the reason the check
        is on ``params`` rather than on the rendered text.
        """
        statement = build(probe, 'MY"OBJECT')
        rendered, bound = statement.to_sql()
        assert bound == ('MY"OBJECT',)
        assert "?" in rendered
        assert "MY" not in rendered

    @pytest.mark.parametrize("family,build,column", NAMED_QUESTIONS)
    def test_the_narrowing_column_is_the_one_asked_about(self, probe, family, build, column):
        """A bind against the wrong column is a filter that silently matches no row."""
        sql, _ = build(probe, "ANY").to_sql()
        assert column in sql.split("WHERE", 1)[1]


class TestOptionalNameQuestions:
    """The list questions that can also narrow to one object."""

    def test_constraints_narrow_by_table_and_type(self, probe):
        by_table, table_params = probe.constraint_list_statement("USERS").to_sql()
        by_type, type_params = probe.constraint_list_statement(None, "PRIMARY KEY").to_sql()
        assert table_params == ("USERS",)
        assert type_params == ("PRIMARY KEY",)
        # The table filter and the type filter are different columns; reading
        # one into the other would answer about a table named "PRIMARY KEY".
        assert '"RC"."RDB$RELATION_NAME" = ?' in by_table
        assert '"RC"."RDB$CONSTRAINT_TYPE" = ?' in by_type

    def test_a_check_constraint_carries_its_text(self, probe):
        """``CHECK`` lives on a trigger, so the read has to join through it.

        Without the two left joins a CHECK constraint reports a name and no
        condition, which reads as a constraint that accepts everything.
        """
        sql, _ = probe.constraint_list_statement().to_sql()
        assert 'LEFT JOIN "RDB$CHECK_CONSTRAINTS"' in sql
        assert 'LEFT JOIN "RDB$TRIGGERS"' in sql
        assert 'AS "CHECK_SOURCE"' in sql

    def test_privileges_keep_system_privileges_visible(self, probe):
        """A system privilege (``GRANT CREATE TABLE TO``) names no relation.

        Filtering ``RDB$RELATION_NAME NOT LIKE 'RDB$%'`` alone would drop it,
        because the column is NULL and NULL is not "not like"; the compound
        predicate is what keeps the grant in the answer.
        """
        sql, _ = probe.privilege_statement().to_sql()
        assert '"RDB$RELATION_NAME" IS NULL' in sql
        assert "NOT LIKE 'RDB$%'" in sql

    def test_a_dependency_names_its_object_on_both_sides(self, probe):
        """An edge is listed whether the object is the reader or the read."""
        sql, params = probe.dependency_statement("USERS").to_sql()
        assert params == ("USERS", "USERS")
        assert '"RDB$DEPENDENT_NAME" = ?' in sql
        assert '"RDB$DEPENDED_ON_NAME" = ?' in sql

    def test_collations_narrow_by_character_set(self, probe):
        sql, params = probe.collation_list_statement("UTF8").to_sql()
        assert params == ("UTF8",)
        assert '"CS"."RDB$CHARACTER_SET_NAME" = ?' in sql

    def test_view_relations_narrow_by_view(self, probe):
        sql, params = probe.view_relation_statement("V_USERS").to_sql()
        assert params == ("V_USERS",)
        assert '"RDB$VIEW_NAME" = ?' in sql

    def test_the_source_is_asked_for_only_when_wanted(self, probe):
        """``PROCEDURE_SOURCE``/``FUNCTION_SOURCE`` are blobs; a listing that
        carried them unasked would pay for every body in the database."""
        plain, _ = probe.procedure_list_statement().to_sql()
        with_source, _ = probe.procedure_list_statement(False, True).to_sql()
        assert "PROCEDURE_SOURCE" not in plain
        assert 'AS "PROCEDURE_SOURCE"' in with_source

        plain_fn, _ = probe.function_list_statement().to_sql()
        with_fn_source, _ = probe.function_list_statement(False, True).to_sql()
        assert "FUNCTION_SOURCE" not in plain_fn
        assert 'AS "FUNCTION_SOURCE"' in with_fn_source

    def test_the_charset_default_collation_is_read_from_its_own_column(self, probe):
        """The catalogue column is ``RDB$DEFAULT_COLLATE_NAME``.

        Reading ``RDB$DEFAULT_COLLATION_NAME`` would raise, and reading neither
        would leave ``default_collation`` empty on every charset.
        """
        sql, _ = probe.charset_list_statement().to_sql()
        assert '"RDB$DEFAULT_COLLATE_NAME" AS "DEFAULT_COLLATION_NAME"' in sql

    def test_a_collation_is_read_with_its_character_set(self, probe):
        """The id alone is not a name, and the join is on the id."""
        sql, _ = probe.collation_list_statement().to_sql()
        assert 'JOIN "RDB$CHARACTER_SETS" AS "CS"' in sql
        assert '"C"."RDB$CHARACTER_SET_ID" = "CS"."RDB$CHARACTER_SET_ID"' in sql


# ---------------------------------------------------------------------------
# The parsers
# ---------------------------------------------------------------------------


class TestExceptionParsing:
    def test_a_row_is_read_into_its_record(self, probe):
        """Firebird pads ``CHAR`` columns, and padding is not part of a name."""
        (info,) = probe.parse_exceptions(
            [
                {
                    "EXCEPTION_NAME": "EXC_LIMIT  ",
                    "EXCEPTION_NUMBER": -901,
                    "MESSAGE": "  limit exceeded  ",
                    "OWNER_NAME": "SYSDBA",
                    "SYSTEM_FLAG": 0,
                    "DESCRIPTION": "   ",
                }
            ]
        )
        assert info.name == "EXC_LIMIT"
        assert info.number == -901
        assert info.message == "limit exceeded"
        assert info.owner == "SYSDBA"
        assert info.is_system is False
        # An all-space blob is the catalogue's way of saying "no description".
        assert info.description is None


class TestProcedureParsing:
    def test_the_signature_is_reported_as_declared(self, probe):
        (info,) = probe.parse_procedures(
            [
                {
                    "PROCEDURE_NAME": "PING",
                    "PROCEDURE_ID": 5,
                    "INPUTS": 2,
                    "OUTPUTS": 1,
                    "PROCEDURE_TYPE": 1,
                    "OWNER_NAME": "SYSDBA",
                    "VALID_BLR": 1,
                    "PRIVATE_FLAG": 0,
                    "SQL_SECURITY": 1,
                    "DESCRIPTION": None,
                    "SYSTEM_FLAG": 0,
                    "PROCEDURE_SOURCE": "BEGIN END",
                }
            ]
        )
        assert info.name == "PING"
        assert (info.inputs, info.outputs) == (2, 1)
        assert info.procedure_type == 1
        assert info.source == "BEGIN END"

    def test_the_source_is_absent_unless_the_read_asked(self, probe):
        """The parser must not invent a body from the row it did not get."""
        (info,) = probe.parse_procedures([{"PROCEDURE_NAME": "PING"}])
        assert info.source is None


class TestProcedureParameterParsing:
    def test_the_kind_separates_inputs_from_outputs(self, probe):
        """Both arrive in one read; the numeric code is the only thing telling them apart."""
        rows = [
            {"PARAMETER_NAME": "P_IN", "PARAMETER_TYPE": 0, "PARAMETER_NUMBER": 0},
            {"PARAMETER_NAME": "P_OUT", "PARAMETER_TYPE": 1, "PARAMETER_NUMBER": 0},
            {"PARAMETER_NAME": None, "PARAMETER_TYPE": 9, "PARAMETER_NUMBER": 3},
        ]
        first, second, unknown = probe.parse_procedure_parameters(rows)
        assert first.kind == "input"
        assert second.kind == "output"
        assert unknown.kind == "9"
        assert unknown.name is None

    def test_numeric_is_named_from_the_pair_not_the_storage(self, probe):
        """``NUMERIC(9,2)`` is an exact integer with sub type 1 and a negative scale.

        Naming it ``BIGINT`` would report the storage and lose the declaration,
        which is the whole of what a domain or a parameter says.
        """
        (info,) = probe.parse_procedure_parameters(
            [
                {
                    "PARAMETER_NAME": "P_AMOUNT",
                    "PARAMETER_TYPE": 0,
                    "FIELD_TYPE": 16,
                    "FIELD_SUB_TYPE": 1,
                    "SCALE": -2,
                    "PRECISION": 9,
                }
            ]
        )
        assert info.data_type == "NUMERIC"
        assert (info.numeric_precision, info.numeric_scale) == (9, -2)

    def test_null_flag_is_the_only_thing_that_makes_a_parameter_not_nullable(self, probe):
        """An absent flag means nullable; a present one means not."""
        nullable, not_nullable = probe.parse_procedure_parameters(
            [
                {"PARAMETER_TYPE": 0, "NULL_FLAG": None},
                {"PARAMETER_TYPE": 0, "NULL_FLAG": 1},
            ]
        )
        assert nullable.nullable is True
        assert not_nullable.nullable is False


class TestFunctionParsing:
    def test_a_legacy_udf_is_distinguishable_from_a_psql_function(self, probe):
        """``LEGACY_FLAG`` is what separates an external UDF from a PSQL body."""
        psql, legacy = probe.parse_functions(
            [
                {
                    "FUNCTION_NAME": "DOUBLE_IT",
                    "FUNCTION_TYPE": 0,
                    "LEGACY_FLAG": 0,
                    "DETERMINISTIC_FLAG": 1,
                    "RETURN_ARGUMENT": 1,
                    "SYSTEM_FLAG": 0,
                },
                {
                    "FUNCTION_NAME": "UDF_ADD",
                    "FUNCTION_TYPE": 1,
                    "LEGACY_FLAG": 1,
                    "ENGINE_NAME": "fbudf",
                    "ENTRYPOINT": "add",
                    "SYSTEM_FLAG": 1,
                },
            ]
        )
        assert psql.is_legacy is False
        assert psql.is_deterministic is True
        assert psql.return_argument == 1
        assert legacy.is_legacy is True
        assert (legacy.engine_name, legacy.entrypoint) == ("fbudf", "add")
        assert legacy.is_system is True


class TestFunctionArgumentParsing:
    def test_the_return_slot_is_an_argument(self, probe):
        """Firebird keeps the return value in the argument list; dropping it
        would report a one-argument function as taking no arguments."""
        rows = [
            {"ARGUMENT_POSITION": 0, "ARGUMENT_NAME": "X", "FIELD_TYPE": 8, "SCALE": 0},
            {"ARGUMENT_POSITION": 1, "ARGUMENT_NAME": None, "FIELD_TYPE": 8, "SCALE": 0},
        ]
        first, ret = probe.parse_function_arguments(rows)
        assert first.data_type == "INTEGER"
        assert first.name == "X"
        assert ret.position == 1
        assert ret.name is None


class TestConstraintParsing:
    def test_check_text_comes_from_the_trigger_it_lives_on(self, probe):
        """``CHECK_SOURCE`` is the trigger body; the constraint row has no condition."""
        (info,) = probe.parse_constraints(
            [
                {
                    "CONSTRAINT_NAME": "CHK_AGE",
                    "CONSTRAINT_TYPE": "CHECK",
                    "RELATION_NAME": "USERS",
                    "DEFERRABLE": "NO",
                    "INITIALLY_DEFERRED": "NO",
                    "INDEX_NAME": None,
                    "CHECK_TRIGGER": "CHK_AGE",
                    "CHECK_SOURCE": "CHECK (AGE >= 0)",
                }
            ]
        )
        assert info.constraint_type == "CHECK"
        assert info.table_name == "USERS"
        assert info.check_trigger == "CHK_AGE"
        assert info.check_source == "CHECK (AGE >= 0)"

    def test_a_primary_key_names_the_index_it_uses(self, probe):
        (info,) = probe.parse_constraints(
            [
                {
                    "CONSTRAINT_NAME": "PK_USERS",
                    "CONSTRAINT_TYPE": "PRIMARY KEY",
                    "RELATION_NAME": "USERS",
                    "INDEX_NAME": "IDX_PK_USERS",
                }
            ]
        )
        assert info.index_name == "IDX_PK_USERS"
        assert info.check_source is None


class TestRoleParsing:
    def test_a_system_privilege_bitmap_is_read_bit_by_bit(self, probe):
        """``RDB$SYSTEM_PRIVILEGES`` is one flag per bit, not a truthy blob.

        A role with the bitmap present but every bit clear has no system
        privileges, so "the blob came back non-empty" would answer yes.
        """
        granted, empty, blank = probe.parse_roles(
            [
                {"ROLE_NAME": "R1", "SYSTEM_PRIVILEGES": b"\x00\x01"},
                {"ROLE_NAME": "R2", "SYSTEM_PRIVILEGES": b"\x00\x00"},
                {"ROLE_NAME": "R3", "SYSTEM_PRIVILEGES": "   "},
            ]
        )
        assert granted.has_system_privileges is True
        assert empty.has_system_privileges is False
        assert blank.has_system_privileges is False


class TestPrivilegeParsing:
    def test_the_type_codes_are_named(self, probe):
        """``GRANTEE_TYPE``/``OBJECT_TYPE`` are integers; a caller reads words."""
        (info,) = probe.parse_privileges(
            [
                {
                    "GRANTEE": "PUBLIC",
                    "GRANTEE_TYPE": 8,
                    "GRANTOR": "SYSDBA",
                    "PRIVILEGE": "S",
                    "GRANT_OPTION": 2,
                    "OBJECT_NAME": "USERS",
                    "OBJECT_TYPE": 0,
                    "FIELD_NAME": None,
                }
            ]
        )
        assert info.grantee == "PUBLIC"
        assert info.grantee_type == "USER"
        assert info.object_type == "RELATION"
        # The letter is passed through: Firebird 4's system privileges use
        # letters no release documents as SQL privileges.
        assert info.privilege == "S"


class TestCharsetParsing:
    def test_the_default_collation_survives_the_alias(self, probe):
        """The result field is ``default_collation``; the column is ``COLLATE``."""
        (info,) = probe.parse_charsets(
            [
                {
                    "CHARACTER_SET_NAME": "UTF8",
                    "CHARACTER_SET_ID": 4,
                    "FORM_OF_USE": "UTF8",
                    "NUMBER_OF_CHARACTERS": None,
                    "BYTES_PER_CHARACTER": 4,
                    "DEFAULT_COLLATION_NAME": "UTF8",
                    "FUNCTION_NAME": None,
                    "SYSTEM_FLAG": 1,
                }
            ]
        )
        assert info.default_collation == "UTF8"
        assert info.bytes_per_character == 4
        assert info.is_system is True


class TestCollationParsing:
    def test_an_attribute_bearing_collation_reports_them(self, probe):
        (info,) = probe.parse_collations(
            [
                {
                    "COLLATION_NAME": "UNICODE_CI_AI",
                    "CHARACTER_SET_NAME": "UTF8",
                    "COLLATION_ID": 51,
                    "BASE_COLLATION_NAME": "UNICODE",
                    "SPECIFIC_ATTRIBUTES": "DISABLE-COMPRESSIONS=1",
                    "FUNCTION_NAME": None,
                    "SYSTEM_FLAG": 1,
                }
            ]
        )
        assert info.charset == "UTF8"
        assert info.base_collation == "UNICODE"
        assert info.specific_attributes == "DISABLE-COMPRESSIONS=1"


class TestDependencyParsing:
    def test_both_ends_of_an_edge_are_named(self, probe):
        (info,) = probe.parse_dependencies(
            [
                {
                    "DEPENDENT_NAME": "V_USERS",
                    "DEPENDENT_TYPE": 1,
                    "DEPENDED_ON_NAME": "USERS",
                    "DEPENDED_ON_TYPE": 0,
                    "FIELD_NAME": "ID",
                }
            ]
        )
        assert (info.dependent_name, info.dependent_type) == ("V_USERS", "VIEW")
        assert (info.depended_on_name, info.depended_on_type) == ("USERS", "RELATION")
        assert info.field_name == "ID"


class TestViewRelationParsing:
    def test_a_context_is_kept_with_the_relation_it_names(self, probe):
        (info,) = probe.parse_view_relations(
            [
                {
                    "VIEW_NAME": "V_USERS",
                    "RELATION_NAME": "USERS",
                    "VIEW_CONTEXT": 1,
                    "CONTEXT_NAME": "USERS",
                    "CONTEXT_TYPE": 0,
                }
            ]
        )
        assert info.view_name == "V_USERS"
        assert info.relation_name == "USERS"
        assert info.view_context == 1
        assert info.context_type == "RELATION"


class TestPublicationParsing:
    def test_the_flags_are_read_as_booleans(self, probe):
        """``ACTIVE_FLAG``/``AUTO_ENABLE`` are small integers, not words."""
        active, inactive = probe.parse_publications(
            [
                {
                    "PUBLICATION_NAME": "PUB_ALL",
                    "OWNER_NAME": "SYSDBA",
                    "ACTIVE_FLAG": 1,
                    "AUTO_ENABLE": 1,
                    "SYSTEM_FLAG": 0,
                },
                {
                    "PUBLICATION_NAME": "PUB_PAUSED",
                    "ACTIVE_FLAG": 0,
                    "AUTO_ENABLE": 0,
                    "SYSTEM_FLAG": 0,
                },
            ]
        )
        assert (active.active, active.auto_enable) == (True, True)
        assert (inactive.active, inactive.auto_enable) == (False, False)


NAMED_PARSERS = [
    ("exceptions", lambda p, rows: p.parse_exceptions(rows), "EXCEPTION_NAME"),
    ("procedures", lambda p, rows: p.parse_procedures(rows), "PROCEDURE_NAME"),
    ("functions", lambda p, rows: p.parse_functions(rows), "FUNCTION_NAME"),
    ("constraints", lambda p, rows: p.parse_constraints(rows), "CONSTRAINT_NAME"),
    ("roles", lambda p, rows: p.parse_roles(rows), "ROLE_NAME"),
    ("charsets", lambda p, rows: p.parse_charsets(rows), "CHARACTER_SET_NAME"),
    ("collations", lambda p, rows: p.parse_collations(rows), "COLLATION_NAME"),
    ("publications", lambda p, rows: p.parse_publications(rows), "PUBLICATION_NAME"),
]


class TestUnnamedRows:
    @pytest.mark.parametrize("family,parse,column", NAMED_PARSERS)
    def test_a_row_without_a_name_is_not_an_object(self, probe, family, parse, column):
        """A padded-out name is the catalogue's "no name"; returning it as an
        item would put an object with an empty name in front of every caller.
        """
        assert parse(probe, [{column: "   "}]) == []

    @pytest.mark.parametrize("family,parse,column", NAMED_PARSERS)
    def test_an_empty_answer_is_an_empty_list(self, probe, family, parse, column):
        assert parse(probe, []) == []
