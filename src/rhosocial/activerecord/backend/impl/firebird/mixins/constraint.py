# src/rhosocial/activerecord/backend/impl/firebird/mixins/constraint.py
"""Firebird constraint capability declarations and their render-time gates.

Every switch here is declared **in this backend's package**, even where core's
``ConstraintMixin`` / ``DDLColumnMixin`` already defaults it to the same
value.  That is deliberate: those mixins are shared with the dummy dialect and
are exactly the kind of default that can move, and a silent move of a core
default would move Firebird's measured contract with it.  A declaration here
is the pin.

The measurements behind every value were taken against the instance
``tests/config/firebird_scenarios.yaml`` names ``firebird_5``:

* **Firebird 5.0.4** at ``192.168.1.3:19582``, database
  ``/var/lib/firebird/data/test_db`` (UTF8), user ``SYSDBA``, driven by
  ``firebird-driver`` 2.0.3. ``rdb$get_context('SYSTEM','ENGINE_VERSION')``
  returns ``5.0.4``.

Every refusal below is the server's own SQLCODE and message text, so a claim
can be re-checked without re-measuring the family.

Four things about Firebird are worth reading before the individual docstrings,
because three of them are counter-intuitive and one of them is wrong in the
plan document:

**1. A CHECK predicate is NOT a restricted grammar.**  An earlier round of
this repository's documentation claimed that Firebird's ``<check_condition>``
is a narrow grammar, that subqueries are therefore unsafe inside ``CHECK ( )``,
and that the core's habit of inlining an arbitrary predicate would "not be
guaranteed legal".  Live measurement refutes all of it.  Firebird compiles
each CHECK predicate into a **system-generated trigger**, and a trigger body
can hold any subquery::

    CREATE TABLE t (c INT CONSTRAINT ck_e CHECK (EXISTS (SELECT 1 FROM r WHERE id = 99)))
    -- accepted; INSERT INTO t VALUES (1)
    -- -> -297 Operation violates CHECK constraint CK_E on view or table T
    --    -At trigger 'CHECK_303'
    CREATE TABLE t (c INT CONSTRAINT ck_n CHECK (NOT (c > 0 AND c < 10)))   -- accepted, enforced
    CREATE TABLE t (c INT CONSTRAINT ck_i CHECK (c IN (1,2,3)))            -- accepted, enforced
    CREATE TABLE t (c INT CONSTRAINT ck_d CHECK (c IS DISTINCT FROM 1))    -- accepted, enforced

So ``supports_check_constraint`` is ``True`` in the ordinary sense and no
"restricted grammar" restriction belongs anywhere in this backend.  The
``.claude/plan/2026-10-11/firebird-constraint-coverage.md`` top section
records the same refutation.

**2. CHECK is a per-row trigger, NOT DDL-time validation.**  Adding a CHECK to
a table that already violates it *succeeds*, and the violating row stays::

    CREATE TABLE d1 (id INT, c INT);  INSERT INTO d1 VALUES (1, -1);
    ALTER TABLE d1 ADD CONSTRAINT ck_dd CHECK (c > 0);   -- accepted
    SELECT c FROM d1;                                   -- still -1

``RDB$TRIGGERS`` confirms the mechanism: the constraint gets two system
triggers, ``CHECK_<id>`` with ``RDB$SYSTEM_FLAG = 3`` and
``RDB$TRIGGER_TYPE`` 1 (BEFORE INSERT) and 3 (BEFORE UPDATE).  Do not assume
``ADD CONSTRAINT ... CHECK`` back-fills a validation of the existing data --
it does not, and a caller that needs one has to run it.

**3. Constraint names are unique across the whole DATABASE, not per table.**
Reusing a name on another table -- even as a different constraint kind -- is
refused, and the message names a *catalog* constraint rather than the
kind that clashed::

    -607: violation of PRIMARY or UNIQUE KEY constraint "RDB$INDEX_12"
          on table "RDB$RELATION_CONSTRAINTS"
          -Problematic key value is ("RDB$CONSTRAINT_NAME" = 'X')

The identical ``-607`` comes back for a NOT NULL, a CHECK and a UNIQUE, so a
caller that classifies -607 by message text will mis-attribute it.  It says
"PRIMARY or UNIQUE KEY", not "your constraint kind was wrong".

**4. ``ON UPDATE`` exists.**  This is the one Firebird has that several of its
siblings do not: Oracle has no ``ON UPDATE`` referential action at all.  It is
pinned locally with a functional measurement (see
:meth:`supports_fk_on_update`) so a change made for a backend without the
clause cannot quietly remove it here.

The gates the rendering path consults live here too, so the whole constraint
contract of this backend reads in one module: :meth:`_require_no_constraint_
deferral` and :meth:`_require_constraint_enforcement` narrow the shared
whitelists to "nothing, for this server" while keeping the refusal named by
the exact SQL spelling that was requested.
"""

from typing import Any, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.expression.statements.ddl_table import (
        ColumnConstraint,
        ReferencesClause,
        TableConstraint,
    )

#: The engine every verdict in this module was measured on. Kept as a constant
#: so the docstrings and the tests cannot drift onto different releases.
MEASURED_ENGINE = "Firebird 5.0.4"


def _constraint_kind_sql(branch: Any) -> str:
    """The SQL spelling of a constraint branch's kind.

    A refusal names the constraint the way a caller spelled it, so the message
    reads ``CHECK NOT ENFORCED`` rather than naming a Python class. The kind
    used to be a member of the removed ``*ConstraintType`` enums and is a
    branch class now, so the spelling is derived rather than carried on the
    node; a branch outside the table falls back to its own class name rather
    than being reported as some other kind.
    """
    from rhosocial.activerecord.backend.expression.statements import (
        ColumnCheckConstraint,
        ColumnForeignKeyConstraint,
        ColumnPrimaryKeyConstraint,
        ColumnUniqueConstraint,
        TableCheckConstraint,
        TableExcludeConstraint,
        TableForeignKeyConstraint,
        TablePrimaryKeyConstraint,
        TableUniqueConstraint,
    )

    return {
        ColumnPrimaryKeyConstraint: "PRIMARY KEY",
        TablePrimaryKeyConstraint: "PRIMARY KEY",
        ColumnUniqueConstraint: "UNIQUE",
        TableUniqueConstraint: "UNIQUE",
        ColumnForeignKeyConstraint: "FOREIGN KEY",
        TableForeignKeyConstraint: "FOREIGN KEY",
        ColumnCheckConstraint: "CHECK",
        TableCheckConstraint: "CHECK",
        TableExcludeConstraint: "EXCLUDE",
    }.get(type(branch), type(branch).__name__)


class FirebirdConstraintMixin:
    """Firebird constraint capability declarations.

    Every value below is a live measurement against Firebird 5.0.4; see the
    module docstring for the instance and for the four engine facts that the
    individual docstrings assume.
    """

    # ------------------------------------------------------------------
    # Constraint kinds (SQL-86 / SQL-92)
    # ------------------------------------------------------------------

    def supports_primary_key_constraint(self) -> bool:
        """True: ``PRIMARY KEY`` is supported at column and table level.

        Firebird 5.0.4, both levels accepted, names stored in
        ``RDB$RELATION_CONSTRAINTS``::

            CREATE TABLE t (id INT CONSTRAINT pk_id PRIMARY KEY)
            CREATE TABLE t (id INT, PRIMARY KEY (id))

        Two engine conditions ride on top of the grammar and are properties of
        primary keys rather than of this statement, so they do not belong on a
        capability switch:

        * the columns must already be ``NOT NULL`` -- ``ALTER TABLE t ADD
          CONSTRAINT pk PRIMARY KEY (id)`` on a nullable column answers
          ``Column: ID not defined as NOT NULL - cannot be used in PRIMARY KEY
          constraint definition``; and
        * there is no ``ASC`` / ``DESC`` on the constraint.  Direction is only
          spellable through ``USING [ASC|DESC] INDEX``, and ``CREATE INDEX ix
          ON t (c DESC)`` is itself ``-104 Token unknown - DESC``.  That is why
          Firebird needs no ``supports_*_primary_key_direction`` switch at all.

        Core already defaults this to ``True``; the declaration pins it to the
        measurement.
        """
        return True

    def supports_unique_constraint(self) -> bool:
        """True: ``UNIQUE`` is supported at column and table level.

        Firebird 5.0.4::

            CREATE TABLE t (c INT CONSTRAINT uq_c UNIQUE)
            ALTER TABLE t ADD CONSTRAINT uq_c2 UNIQUE (c)      -- accepted

        Read back, ``RDB$RELATION_CONSTRAINTS`` carries the name and
        ``RDB$RELATION_CONSTRAINTS.RDB$CONSTRAINT_TYPE`` = ``UNIQUE``.

        Like PRIMARY KEY there is no column-level direction; ``UNIQUE (c) USING
        DESCENDING INDEX ix`` is the only spelling, and it is accepted.
        """
        return True

    def supports_not_null_constraint(self) -> bool:
        """True: ``NOT NULL`` is supported -- and it is a *column*-level kind.

        Firebird 5.0.4, at column level::

            CREATE TABLE t (id INT, c INT CONSTRAINT nn_c NOT NULL)   -- accepted
            INSERT INTO t (id, c) VALUES (1, NULL)
            -> -407: validation error for column "T"."C", value "*** null ***"

        The name is not decorative: ``RDB$RELATION_CONSTRAINTS`` holds the row
        ``(NN_C, NOT NULL)``, which is why the name also occupies the
        database-wide namespace described in the module docstring.  Measured
        directly: reusing ``NN_C`` on a second table answers ``-607``.

        There is **no table-level** form at all::

            ALTER TABLE t ADD CONSTRAINT nn NOT NULL
            -> -104: Token unknown - line 1, column 45 -NOT

        ``NOT NULL`` simply is not one of the four ``<tconstraint>`` branches;
        core's table-level branch family has no NOT NULL member, so the
        grammar's absence needs no switch here.
        """
        return True

    def supports_check_constraint(self) -> bool:
        """True: ``CHECK`` is supported at column and table level, with an
        unrestricted predicate and real enforcement.

        Firebird 5.0.4.  Three separate things are true and only the third was
        documented before:

        1. **Accepted**, at both levels::

               CREATE TABLE t (c INT CONSTRAINT ck_c CHECK (c > 0))
               ALTER TABLE t ADD CONSTRAINT ck_c2 CHECK (c > 0)

        2. **Enforced** at DML time, with the server naming the generated
           trigger it is enforcing through::

               INSERT INTO t VALUES (-1)
               -> -297: Operation violates CHECK constraint CK_C on view or
                        table T -At trigger 'CHECK_333'

        3. **The predicate is not a restricted grammar.**  Subqueries and
           boolean composition are all accepted and all enforced::

               CREATE TABLE t (c INT CONSTRAINT ck_e CHECK (EXISTS (SELECT 1 FROM r WHERE id = 99)))
               CREATE TABLE t (c INT CONSTRAINT ck_n CHECK (NOT (c > 0 AND c < 10)))
               CREATE TABLE t (c INT CONSTRAINT ck_i CHECK (c IN (1,2,3)))
               CREATE TABLE t (c INT CONSTRAINT ck_d CHECK (c IS DISTINCT FROM 1))

           each answered ``-297 ... At trigger 'CHECK_<id>'`` on a violating
           row.  The reason the acceptance surface is this wide is that a CHECK
           is compiled into a system-generated trigger whose body may contain
           arbitrary subqueries.  Any documentation in this repository saying
           the predicate grammar is restricted is superseded -- see the module
           docstring, point 1.

        What is *not* true is that adding a CHECK validates what is already
        there -- see the module docstring, point 2.  A caller that assumes
        ``ADD CONSTRAINT ... CHECK`` repairs a dirty table is wrong.
        """
        return True

    def supports_foreign_key_constraint(self) -> bool:
        """True: ``FOREIGN KEY`` is supported at column and table level.

        Firebird 5.0.4.  The two levels spell it differently, which is the one
        place a naive renderer trips::

            -- column level: REFERENCES, no FOREIGN KEY keyword
            CREATE TABLE t (c INT CONSTRAINT fk_c REFERENCES r(id))
            CREATE TABLE t (c INT CONSTRAINT fk_c FOREIGN KEY (c) REFERENCES r(id))
            -> -104: Token unknown - line 1, column 49 -FOREIGN

            -- table level: the column list is mandatory
            ALTER TABLE t ADD CONSTRAINT fk_c FOREIGN KEY (c) REFERENCES r(id)
            -- accepted; RDB$RELATION_CONSTRAINTS holds (FK_C, FOREIGN KEY)

        ``<tconstraint>`` has only these four branches -- PRIMARY KEY, UNIQUE,
        FOREIGN KEY, CHECK -- so a table-level constraint never carries a bare
        ``REFERENCES``.
        """
        return True

    # ------------------------------------------------------------------
    # Referential actions (SQL-92) and match modes (SQL:1999)
    # ------------------------------------------------------------------

    def supports_foreign_key_on_delete(self) -> bool:
        """True: ``ON DELETE`` referential actions are supported.

        Firebird 5.0.4, all four actions accepted on one foreign key::

            ON DELETE CASCADE | SET NULL | SET DEFAULT | NO ACTION

        ``RESTRICT`` is **not** one of them, even though it is in the SQL
        standard vocabulary and in Oracle's and MySQL's::

            ON DELETE RESTRICT
            -> -104: Token unknown - line 1, column 97 -RESTRICT

        Firebird spells the default action ``NO ACTION``, and ``NO ACTION`` is
        the omission as well as an explicit spelling -- both accepted.  This is
        the switch ``format_references_clause`` consults before emitting the
        clause.
        """
        return True

    def supports_foreign_key_on_update(self) -> bool:
        """True: ``ON UPDATE`` referential actions are supported.

        Firebird 5.0.4, all four actions accepted::

            ON UPDATE CASCADE | SET NULL | SET DEFAULT | NO ACTION
            ON UPDATE RESTRICT
            -> -104: Token unknown - line 1, column 97 -RESTRICT

        Worth pinning locally, and verified *functionally* rather than by
        parse-acceptance alone, because ``ON UPDATE`` is unusual for this
        family: the cross-backend table in
        ``python-activerecord/.claude/plan/2026-10-11/alter-table-live-findings.md``
        records Oracle as having no ``ON UPDATE`` action at all.  Measured on
        5.0.4:

        * ``ON UPDATE CASCADE`` -- updating the parent's key rewrote the child
          row, ``(id=10, pid=1)`` becoming ``(id=10, pid=7)``;
        * ``ON UPDATE SET NULL`` -- the same update nulled the child's ``pid``;
        * ``ON UPDATE NO ACTION`` -- the parent update was refused with
          ``-530: violation of FOREIGN KEY constraint "..." on table "..." -
          Foreign key references are present for the record -Problematic key
          value is ("ID" = 1)``.

        So the clause is honoured, not merely parsed.  Left riding on a shared
        core default, a change made for a backend without the clause would
        start dropping it from Firebird's rendering without anything failing
        here.  Declared here rather than inherited from ``DDLColumnMixin`` for
        the same reason.
        """
        return True

    def supports_fk_on_delete(self) -> bool:
        """True: ``ON DELETE`` referential actions are supported.

        The same question as :meth:`supports_foreign_key_on_delete`, under the
        spelling core's shared ``ConstraintMixin`` declares; the two are
        consulted by different parts of the reference path, so both are pinned
        here to the Firebird 5.0.4 measurement rather than left to inherit a core
        default. Measured on 5.0.4, all four actions accepted on one foreign
        key::

            ON DELETE CASCADE | SET NULL | SET DEFAULT | NO ACTION
            ON DELETE RESTRICT
            -> -104: Token unknown - line 1, column 97 -RESTRICT
        """
        return True

    def supports_fk_on_update(self) -> bool:
        """True: ``ON UPDATE`` referential actions are supported.

        The same question as :meth:`supports_foreign_key_on_update`, under the
        spelling core's shared ``ConstraintMixin`` declares. Measured on 5.0.4,
        all four actions accepted, and the clause is honoured:
        :meth:`supports_foreign_key_on_update` carries the functional evidence
        (``ON UPDATE CASCADE`` rewrote a live child row, ``ON UPDATE SET NULL``
        nulled one, ``ON UPDATE NO ACTION`` was refused with ``-530``), which is
        why the ``True`` is not a parse-acceptance guess::

            ON UPDATE CASCADE | SET NULL | SET DEFAULT | NO ACTION
            ON UPDATE RESTRICT
            -> -104: Token unknown - line 1, column 97 -RESTRICT
        """
        return True

    def supports_fk_match(self) -> bool:
        """False: Firebird has no ``MATCH {SIMPLE|PARTIAL|FULL}`` clause.

        Firebird 5.0.4, at both levels::

            ALTER TABLE t ADD CONSTRAINT f FOREIGN KEY (c) REFERENCES r(id) MATCH FULL
            -> -104: Token unknown - line 1, column 83 -MATCH

        Not a single ``MATCH`` spelling is accepted, and the refusal is at the
        parser -- unlike MySQL, which parses ``MATCH FULL`` and then silently
        discards it.  That difference is what makes the ``False`` the right
        answer rather than a pessimistic one: a renderer that emitted ``MATCH``
        would fail loudly instead of misleading the caller.

        A requested match type is refused by name in
        :meth:`~rhosocial.activerecord.backend.dialect.mixins.ddl_column.
        DDLColumnMixin.format_references_clause`, which every column- and
        table-level foreign key renders through, rather than dropped.
        """
        return False

    # ------------------------------------------------------------------
    # Constraint naming (SQL-92)
    # ------------------------------------------------------------------

    def supports_constraint_naming(self) -> bool:
        """True: a constraint may carry a ``CONSTRAINT <name>`` prefix.

        Firebird 5.0.4.  ``<col_constraint>`` opens with an optional
        ``[CONSTRAINT constr_name]`` ahead of **all five** of its branches, and
        ``<tconstraint>`` opens with the same option ahead of its four::

            CREATE TABLE t (id INT CONSTRAINT pk_id PRIMARY KEY)
            -- RDB$RELATION_CONSTRAINTS: (PK_ID, PRIMARY KEY)
            CREATE TABLE t (c INT CONSTRAINT uq_c UNIQUE)      -- (UQ_C, UNIQUE)
            CREATE TABLE t (c INT CONSTRAINT ck_c CHECK (c > 0))  -- (CK_C, CHECK)
            CREATE TABLE t (c INT CONSTRAINT fk_c REFERENCES r(id))  -- (FK_C, FOREIGN KEY)
            CREATE TABLE t (id INT, c INT CONSTRAINT nn_c NOT NULL)  -- (NN_C, NOT NULL)
            ALTER TABLE t ADD CONSTRAINT uq_c2 UNIQUE (c)       -- accepted

        So the single core switch is ``True``; note the *kind-specific* switch
        table in ``.claude/plan/2026-10-11/firebird-constraint-coverage.md``
        gave the table-level NOT NULL row a ``True`` that measurement refuses --
        there is no table-level NOT NULL, named or otherwise (see
        :meth:`supports_not_null_constraint`).

        Two consequences a name cannot warn about, carried in the module
        docstring instead: the name is unique **across the whole database**
        (measured: reusing one answers ``-607``), and a named column NOT NULL
        is stored as a real catalog constraint, not a comment.
        """
        return True

    # ------------------------------------------------------------------
    # Deferral (SQL:1999) -- every spelling refused
    # ------------------------------------------------------------------

    def supports_deferrable_constraint(self) -> bool:
        """False: Firebird has no ``DEFERRABLE`` / ``INITIALLY ...`` at all.

        Firebird 5.0.4, all four spellings refused at ``ADD CONSTRAINT`` time,
        each at the parser::

            ADD CONSTRAINT c CHECK (c > 0) DEFERRABLE
            -> -104: Token unknown - line 1, column 58 -DEFERRABLE
            ADD CONSTRAINT c CHECK (c > 0) NOT DEFERRABLE
            -> -104: Token unknown - line 1, column 58 -NOT
            ADD CONSTRAINT c CHECK (c > 0) INITIALLY DEFERRED
            -> -104: Token unknown - line 1, column 58 -INITIALLY
            ADD CONSTRAINT c CHECK (c > 0) INITIALLY IMMEDIATE   -- same

        and at column level::

            CREATE TABLE t (c INT CONSTRAINT nn NOT NULL DEFERRABLE)
            -> -104: Token unknown - line 1, column 44 -DEFERRABLE

        ``<col_constraint>`` and ``<tconstraint>`` have no tail clause after the
        constraint body, so there is nothing to hang deferral timing on.  A
        requested spelling is refused by name in
        :meth:`_require_no_constraint_deferral` rather than silently dropped.
        """
        return False

    # ------------------------------------------------------------------
    # Enforcement control (SQL:2016) and validation state -- all refused
    # ------------------------------------------------------------------

    def supports_constraint_enforced(self) -> bool:
        """False: Firebird has no ``ENFORCED`` / ``NOT ENFORCED``.

        Firebird 5.0.4, at ``ADD CONSTRAINT`` time and on column constraints
        alike::

            ADD CONSTRAINT c CHECK (c > 0) ENFORCED
            -> -104: Token unknown - line 1, column 58 -ENFORCED
            ADD CONSTRAINT c CHECK (c > 0) NOT ENFORCED
            -> -104: Token unknown - line 1, column 58 -NOT

        There is no gate on the version and none on the kind: the clause is not
        in the grammar for **any** of the kinds, so unlike PostgreSQL -- where
        ``ENFORCED`` exists for CHECK and FOREIGN KEY only -- there is no
        per-kind split to record.  A CHECK is enforced
        (:meth:`supports_check_constraint`); there is simply no way to ask for
        it not to be.

        A requested spelling is refused by name in
        :meth:`_require_constraint_enforcement` rather than dropped.
        """
        return False

    def supports_alter_constraint_enforced(self) -> bool:
        """False: ``ALTER CONSTRAINT`` is not Firebird syntax, enforced or not.

        Firebird 5.0.4::

            ALTER TABLE t ALTER CONSTRAINT c NOT ENFORCED
            -> -104: Token unknown - line 1, column 26 -CONSTRAINT

        The refusal is at the ``CONSTRAINT`` keyword, so it says nothing about
        enforcement specifically -- the whole verb is absent.  This is the same
        answer core's ``ConstraintMixin`` gives, and like every other switch in
        this module it is declared here so a move of that core default cannot
        change what Firebird renders.
        """
        return False

    def supports_constraint_novalidate(self) -> bool:
        """False: neither ``NOT VALID`` nor Oracle's ``NOVALIDATE`` is accepted.

        Firebird 5.0.4, at table level and at column level, and both
        spellings::

            ALTER TABLE t ADD CONSTRAINT c CHECK (c > 0) NOT VALID
            -> -104: Token unknown - line 1, column 58 -NOT
            CREATE TABLE t (c INT CONSTRAINT c2 CHECK (c > 0) NOT VALID)
            -> -104: Token unknown - line 1, column 65 -VALID
            ALTER TABLE t ADD CONSTRAINT u UNIQUE (c) NOVALIDATE
            -> -104: Token unknown - line 1, column 54 -NOVALIDATE

        Firebird answers this question with a mechanism rather than a keyword,
        which is the point of fact 2 in the module docstring: a CHECK does not
        validate existing rows *in the first place*, so there is no "skip the
        validation" option to express.  Adding a CHECK to a table with a
        violating row simply succeeds, whether or not the caller wanted a
        validation pass.

        This switch has **no** definition on any real backend outside the dummy
        -- core reaches it through ``getattr(self, "supports_constraint_novalidate",
        None)`` -- so before this module there was nothing to answer.
        """
        return False

    def supports_validate_constraint(self) -> bool:
        """False: ``VALIDATE CONSTRAINT`` is not Firebird syntax.

        Firebird 5.0.4::

            ALTER TABLE t VALIDATE CONSTRAINT c
            -> -104: Token unknown - line 1, column 20 -VALIDATE

        The clause is absent for the same reason ``NOT VALID`` is: there is no
        unvalidated-constraint state to move out of.
        """
        return False

    def supports_exclude_constraint(self) -> bool:
        """False: Firebird has no ``EXCLUDE`` constraint.

        Firebird 5.0.4::

            ALTER TABLE t ADD CONSTRAINT e EXCLUDE USING gist (c WITH =)
            -> -104: Token unknown - line 1, column 43 -EXCLUDE

        ``<tconstraint>`` has four branches and EXCLUDE is not one of them.
        Same value core's ``ConstraintMixin`` gives; declared here for the same
        reason as every other switch in this module.
        """
        return False

    # ------------------------------------------------------------------
    # ALTER TABLE constraint lifecycle (SQL-92)
    # ------------------------------------------------------------------

    def supports_add_constraint(self) -> bool:
        """True: ``ALTER TABLE ... ADD CONSTRAINT`` covers all four kinds.

        Firebird 5.0.4, all four accepted::

            ALTER TABLE t ADD CONSTRAINT p PRIMARY KEY (id)   -- after SET NOT NULL
            ALTER TABLE t ADD CONSTRAINT u UNIQUE (c)
            ALTER TABLE t ADD CONSTRAINT c CHECK (c > 0)
            ALTER TABLE t ADD CONSTRAINT f FOREIGN KEY (c) REFERENCES r(id)

        One engine condition that is *not* a capability answer: a PRIMARY KEY
        requires its columns to be ``NOT NULL`` already, and on a nullable
        column the statement answers ``Column: ID not defined as NOT NULL -
        cannot be used in PRIMARY KEY constraint definition``.  ``ALTER TABLE t
        ALTER COLUMN id SET NOT NULL`` first and it goes through.

        Two more facts a caller has to plan around, neither of which is
        captured by a ``supports_*`` switch:

        * **no back-fill validation.**  ``ADD CONSTRAINT ... CHECK (c > 0)``
          succeeds on a table that already contains ``c = -1``, and the row
          survives.  Firebird compiles the predicate into a system-generated
          per-row trigger; nothing runs it against the rows that are already
          there.  Do not read a successful ``ADD CONSTRAINT`` as "the data is
          now clean".
        * **the name is database-wide.**  ``ADD CONSTRAINT`` with a name already
          used anywhere in the database answers ``-607: violation of PRIMARY or
          UNIQUE KEY constraint "RDB$INDEX_12" on table
          "RDB$RELATION_CONSTRAINTS" -Problematic key value is
          ("RDB$CONSTRAINT_NAME" = '<name>')``.  The message names a catalog
          constraint and does not mention the constraint kind, so error
          classification keyed on that text will mis-attribute the clash.

        Core already defaults this to ``True``; the declaration pins it to the
        measurement.
        """
        return True

    def supports_drop_constraint(self) -> bool:
        """True: ``ALTER TABLE ... DROP CONSTRAINT name`` is accepted.

        Firebird 5.0.4::

            ALTER TABLE t DROP CONSTRAINT c    -- accepted

        A missing name is an error, not a no-op::

            ALTER TABLE t DROP CONSTRAINT nothere
            -> -607: unsuccessful metadata update -ALTER TABLE T failed
                     -CONSTRAINT NOTHERE does not exist.

        So there is no idempotent spelling: ``IF EXISTS`` does not exist either
        (:meth:`supports_drop_constraint_if_exists`), and ``-607`` is a
        metadata-update failure rather than a "no such object" code that a
        caller could reasonably swallow -- ``-607`` is also what a name clash
        returns, so catching it would swallow the wrong thing.

        Unlike MySQL, Firebird's ``DROP CONSTRAINT`` namespace **does** contain
        the primary key, and there is no separate ``DROP PRIMARY KEY``::

            ALTER TABLE t DROP PRIMARY KEY
            -> -104: Token unknown - line 1, column 25 -PRIMARY

        Neither is there a ``DROP CHECK``::

            ALTER TABLE t DROP CHECK c
            -> -104: Token unknown - line 1, column 25 -CHECK
        """
        return True

    def supports_drop_constraint_if_exists(self) -> bool:
        """False: Firebird has no ``DROP CONSTRAINT IF EXISTS``.

        Firebird 5.0.4::

            ALTER TABLE t DROP CONSTRAINT IF EXISTS c
            -> -104: Token unknown - line 1, column 39 -EXISTS

        The render-time guard lives on
        :class:`~.FirebirdAlterTableModifierMixin.supports_drop_constraint_if_exists`
        because that is the formatter's own mixin; the value is repeated here
        so the whole constraint contract reads in one place, and the two are
        asserted to agree in ``test_firebird_constraint_switches.py``.

        Worth noting against the siblings in the 2026-10-11 cross-backend
        table: MariaDB, PostgreSQL, SQL Server and ClickHouse all have this
        form and all make the missing-constraint case a *silent success*, while
        MySQL has neither the form nor a catchable code.  Firebird is in the
        MySQL position -- the statement never parses -- so a caller cannot get
        an idempotent drop on Firebird at all and has to pre-check
        ``RDB$RELATION_CONSTRAINTS``.  The guard raises
        ``UnsupportedFeatureError`` by name for exactly this reason.
        """
        return False

    # ------------------------------------------------------------------
    # Column-level clause position -- the CHARACTER SET / COLLATE pair
    # ------------------------------------------------------------------

    def supports_column_character_set(self) -> bool:
        """False: Firebird's ``CHARACTER SET`` is a **datatype qualifier**, not
        a column clause.

        Measured on Firebird 5.0.4 (see the module docstring for the
        instance).  This is the one that needs the measurement spelled out,
        because Firebird
        certainly *does* have character sets -- it has a database-level
        ``DEFAULT CHARACTER SET``, per-column sets, and ``OCTETS`` -- and the
        backend already renders ``CHARACTER SET`` in
        :class:`~....expression.column.FirebirdColumnDefinition`.  What it does
        not have is a standalone ``<col_clause>`` slot for it.  In
        ``<regular_col_def>`` the only clause after the constraints is
        ``[COLLATE collation_name]``; the charset belongs inside ``<datatype>``::

            CREATE TABLE t (x VARCHAR(20) CHARACTER SET UTF8)          -- accepted
            CREATE TABLE t (x CHARACTER SET UTF8 VARCHAR(20))
            -> -104: Token unknown - line 1, column 34 -SET
            CREATE TABLE t (x INTEGER CHARACTER SET UTF8)
            -> -104: Token unknown - line 1, column 32 -CHARACTER

        The decisive one, because it is the shape a generic
        ``CharacterSetClause`` would produce -- the fragment is emitted *after*
        the constraints, in the position core's ``format_column_attributes``
        puts it::

            CREATE TABLE t (x VARCHAR(20) NOT NULL CHARACTER SET UTF8)
            -> -104: Token unknown - line 1, column 45 -CHARACTER

        That is why this switch is ``False`` even though Firebird can and does
        carry a per-column character set: the supported route on this backend
        is the Firebird-only ``FirebirdColumnDefinition.character_set`` slot,
        which renders in the type position.  Routing the generic channel here
        would produce a statement the parser refuses.

        Core already defaults this to ``False`` (character sets being a
        MySQL/MariaDB concept in the generic dialect); the declaration pins it
        to the measurement, which is what stops a future core change from
        turning it on here.
        """
        return False

    def supports_column_collation(self) -> bool:
        """True: a column-level ``COLLATE`` attribute is supported.

        Firebird 5.0.4.  ``COLLATE`` is the one column clause Firebird has, and
        the grammar places it **last** -- after every ``<col_constraint>``::

            CREATE TABLE t (x VARCHAR(20) CHARACTER SET UTF8 NOT NULL COLLATE UNICODE)
            -- accepted

        Two details the switch cannot carry:

        * the collation must exist **for the column's character set** --
          ``COLLATE UNICODE`` on a column with no charset answers ``-204
          COLLATION UNICODE for CHARACTER SET NONE is not defined``, so the
          charset has to be given too;
        * it may not be moved earlier.  ``<col_clause>`` comes after
          ``<col_constraint>``, so a renderer that emits it right after the
          datatype, as the generic MySQL-shaped clause does, is wrong.

        Core already defaults this to ``True``; the declaration pins it to the
        measurement.
        """
        return True

    # ------------------------------------------------------------------
    # Render-time gates: the refusals, named by the spelling requested
    # ------------------------------------------------------------------

    def _require_no_constraint_deferral(self, constraint: Any) -> None:
        """Refuse a deferral trait by the exact spelling that was asked for.

        The probe (:meth:`supports_deferrable_constraint`) is a whole-family
        ``False``, and core's shared renderer refuses the family with one
        message.  The clause-pair guard, and a caller reading a traceback,
        need ``DEFERRABLE`` told apart from ``NOT DEFERRABLE`` and
        ``INITIALLY DEFERRED`` from ``INITIALLY IMMEDIATE``, so the refusal is
        re-spelled here with the branch's SQL kind and every requested
        spelling.  Both levels consult it: the column clause from
        :meth:`format_constraint_traits` and the table clause from
        :meth:`format_table_constraint`.

        Raises:
            UnsupportedFeatureError: Any deferral trait was requested.
        """
        wants = []
        if constraint.deferrable:
            wants.append("DEFERRABLE")
        if constraint.not_deferrable:
            wants.append("NOT DEFERRABLE")
        if constraint.initially_deferred:
            wants.append("INITIALLY DEFERRED")
        if constraint.initially_immediate:
            wants.append("INITIALLY IMMEDIATE")
        if wants and not self.supports_deferrable_constraint():
            from rhosocial.activerecord.backend.dialect.exceptions import (
                UnsupportedFeatureError,
            )

            feature = f"{_constraint_kind_sql(constraint.branch)} " + " ".join(wants)
            raise UnsupportedFeatureError(
                self.name,
                feature,
                f"{self.name} does not support {feature}. No spelling of "
                "constraint deferral exists in Firebird (measured on 5.0.4: "
                "-104 Token unknown).",
            )

    def _require_constraint_enforcement(self, constraint: Any) -> None:
        """Refuse an enforcement trait by the spelling that was asked for.

        The probe (:meth:`supports_constraint_enforced`) is ``False`` for every
        kind, so the gate has no kind to narrow -- what it adds is the
        spelling: ``CHECK ENFORCED`` and ``CHECK NOT ENFORCED`` are two
        distinct requests, and reporting them with one message would leave the
        pair indistinguishable to the guard that exists to tell them apart.
        Both levels consult it, for the same reason as
        :meth:`_require_no_constraint_deferral`.

        Raises:
            UnsupportedFeatureError: An enforcement trait was requested.
        """
        if not (constraint.enforced or constraint.not_enforced):
            return
        from rhosocial.activerecord.backend.dialect.exceptions import (
            UnsupportedFeatureError,
        )

        spelling = "ENFORCED" if constraint.enforced else "NOT ENFORCED"
        feature = f"{_constraint_kind_sql(constraint.branch)} {spelling}"
        raise UnsupportedFeatureError(
            self.name,
            feature,
            f"{self.name} does not support {feature}. Firebird's "
            "constraint grammar has no [NOT] ENFORCED clause at all "
            "(measured on 5.0.4: -104 Token unknown).",
        )

    # ------------------------------------------------------------------
    # Render-time gates over core's formatters
    # ------------------------------------------------------------------

    def format_constraint_traits(self, constraint: "ColumnConstraint") -> Tuple[str, str]:
        """Render the column clause's traits after this backend's gates.

        Core's renderer would refuse the deferral family with one generic
        message; the narrowing runs first here so the refusal names the
        spelling, and everything else (including core's own check of the
        enforcement probe) is delegated.
        """
        self._require_no_constraint_deferral(constraint)
        self._require_constraint_enforcement(constraint)
        return super().format_constraint_traits(constraint)

    def format_table_constraint(self, expr: "TableConstraint") -> Tuple[str, Tuple]:
        """Render a table-level constraint through this backend's gates.

        Firebird's grammar has no tail clause after a constraint body, so both
        trait families the production level can carry are refusals here rather
        than renderings:

        * ``DEFERRABLE`` / ``INITIALLY ...`` -- measured on 5.0.4 and 6.0.0:
          ``-104 Token unknown - DEFERRABLE`` / ``- NOT`` / ``- INITIALLY``;
        * ``ENFORCED`` / ``NOT ENFORCED`` -- measured on 5.0.4: ``-104 Token
          unknown - ENFORCED`` / ``- NOT``.

        Both are refused **by name, with the exact spelling requested**, before
        the branch body renders, so a caller is told which half of a pair they
        asked for rather than getting one generic family message. The kind
        comes from the branch class (``_constraint_kind_sql``), since the
        ``TableConstraintType`` tag is gone.

        What is *not* refused, and must not be: CHECK. The predicate is inlined
        verbatim because Firebird accepts any expression here -- there is no
        restricted CHECK grammar. Measured on 5.0.4: EXISTS (SELECT ...), NOT
        (a AND b), IN (...) and IS DISTINCT FROM are all accepted and all
        enforced, because Firebird compiles the predicate into a
        system-generated trigger (RDB$TRIGGERS: CHECK_<id>, SYSTEM_FLAG 3,
        TRIGGER_TYPE 1 and 3) whose body may hold arbitrary subqueries.

        What that mechanism means for the caller, and what no switch can
        express: CHECK IS NOT a DDL-time validation. Adding one to a table that
        already violates it succeeds and the row survives -- measured with
        ``ALTER TABLE d1 ADD CONSTRAINT ck CHECK (c > 0)`` against a row with
        c = -1. Do not render an ADD CONSTRAINT and assume the data was checked.

        This declaration must precede ``DDLColumnMixin`` in the dialect's MRO,
        which is what keeps this override on the dispatch path; the rest of the
        clause -- the ``CONSTRAINT <name>`` prefix and the branch body,
        including the referential actions -- is core's, reached by delegation.
        """
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
        from rhosocial.activerecord.backend.expression.statements import (
            TableForeignKeyConstraint,
        )

        self._require_no_constraint_deferral(expr)
        self._require_constraint_enforcement(expr)
        # ``match_type`` belongs to the foreign-key branch alone -- the other
        # branches the production level can carry declare no such field -- so
        # the kind decides whether the question exists, then the field is read.
        if (
            isinstance(expr.branch, TableForeignKeyConstraint)
            and expr.branch.match_type is not None
        ):
            # Measured on Firebird 5.0.4, ``MATCH FULL`` (and every other MATCH
            # spelling) answers ``-104: Token unknown - line 1, column 83
            # -MATCH``. Refused here, by name, ahead of the body so the message
            # names MATCH directly -- core would refuse it from inside
            # format_references_clause, reaching the same answer with a less
            # direct attribution.
            raise UnsupportedFeatureError(
                self.name, "FOREIGN KEY MATCH",
                "Firebird does not support FOREIGN KEY MATCH.",
            )

        return super().format_table_constraint(expr)

    def format_references_clause(self, expr: "ReferencesClause") -> Tuple[str, tuple]:
        """Render a ``REFERENCES`` clause with Firebird's separating space.

        Byte-for-byte the shared renderer except for the space between the
        referenced table and its column list: Firebird's grammar is written
        ``REFERENCES <table> ( <col list> )`` and this backend has always
        emitted ``REFERENCES "R" ("C")``. The shared default emits
        ``REFERENCES "R"("C")``, so the space is restored here rather than in
        core, where it would change seven other backends' SQL.

        This is the one place both foreign-key levels spell their reference --
        :meth:`DDLColumnMixin.format_column_fk_constraint` and
        :meth:`DDLColumnMixin.format_table_foreign_key_constraint` both build a
        ``ReferencesClause`` and render it through here -- so the space cannot
        diverge between the two, and the definition must precede
        ``DDLColumnMixin`` in the dialect's MRO for this override to win.

        Everything else is core's: the referential actions, the ``MATCH``
        refusal through :meth:`supports_fk_match`, and the object-kind check on
        ``referenced_table``.
        """
        sql, params = super().format_references_clause(expr)
        table_sql = expr.referenced_table.to_sql()[0]
        return sql.replace(f"{table_sql}(", f"{table_sql} (", 1), params
