# tests/benchmark/providers.py
"""Firebird benchmark implementations registered with the shared testsuite.

The testsuite's ``benchmark/*`` contracts obtain a backend implementation from
the global ``benchmarks`` registry.  Registering here (at conftest import time)
is what turns those contracts from "skip: no implementation" into real
measurements.  Direct ``StorageBackend.execute`` benchmarks stay backend-owned
under ``tests/benchmark/`` and do not use this registry.

Firebird has no async backend in this release, so every ``async_setup`` returns
``None`` and the shared async contracts skip themselves (the testsuite fixtures
turn a ``None`` context into a skip).  Sync contracts run against a fresh
Firebird database file per case.
"""
import uuid
from typing import ClassVar, Optional

from pydantic import EmailStr, Field

from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType
from rhosocial.activerecord.base.field_proxy import FieldProxy
from rhosocial.activerecord.field import DefaultTimestampMixin, IntegerPKMixin
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.testsuite.benchmark.crud.fixtures.data import (
    make_user_payloads,
    payload_count_for_size,
)
from rhosocial.activerecord.testsuite.benchmark.crud.interfaces import CrudBenchmarkContext
from rhosocial.activerecord.testsuite.benchmark.mixin.interfaces import MixinBenchmarkContext
from rhosocial.activerecord.testsuite.benchmark.query.interfaces import QueryBenchmarkContext
from rhosocial.activerecord.testsuite.benchmark.registry import (
    BenchmarkImplementation,
    benchmarks,
)
from rhosocial.activerecord.testsuite.benchmark.transaction.interfaces import (
    TransactionBenchmarkContext,
)

from support.firebird import SCENARIOS, scenario


# DDL options used by the derived statements.
DDL = ExecutionOptions(stmt_type=StatementType.DDL)

BACKEND_NAMESPACE = "rhosocial.activerecord.backend.impl.firebird"
BACKEND_NAME = "firebird"


# --------------------------------------------------------------------------- #
# Minimal benchmark-only models.  Each run uses a fresh dataset, so these are
# declared locally instead of reusing feature fixtures.  DDL is derived from
# the model via the expression system (no hand-built SQL).
# --------------------------------------------------------------------------- #
class _BenchUserBase:
    @classmethod
    def table_name(cls):
        return "benchmark_users"

    c: ClassVar[FieldProxy] = FieldProxy()
    id: Optional[int] = None
    username: str
    email: EmailStr
    age: Optional[int] = Field(..., ge=0, le=120)
    balance: float = 0.0
    notes: Optional[str] = None
    is_active: bool = True


class BenchUser(IntegerPKMixin, DefaultTimestampMixin, _BenchUserBase, ActiveRecord):
    pass


def _config_for_scenario(scenario_name: str, tag: str):
    """A fresh Firebird database file per feature run.

    Firebird connects to a physical file whose logical name is the scenario's
    base path plus a unique suffix.  The file must exist before any DDL runs,
    so create it here; the returned config points at that same file.
    """
    sc = scenario(scenario_name)
    unique = f"bench_{tag}_{scenario_name}_{uuid.uuid4().hex}"
    cfg = sc.make_config(unique)
    sc.ensure_database(unique)
    return sc, cfg


class CrudBenchmarkImpl(BenchmarkImplementation):
    def __init__(self, tag="crud"):
        self.tag = tag
        self._backends = []

    def scenarios(self):
        return list(SCENARIOS)

    def sync_setup(self, scenario_name, size):
        sc, cfg = _config_for_scenario(scenario_name, self.tag)
        BenchUser.configure(cfg, sc.backend_class)
        backend = BenchUser.backend()
        backend.execute(*BenchUser.create_table_statement(backend=backend).to_sql(), options=DDL)
        self._backends.append(backend)
        payloads = make_user_payloads(payload_count_for_size(size))
        ids = []
        for payload in payloads:
            obj = BenchUser(**payload)
            obj.save()
            ids.append(obj.id)
        return CrudBenchmarkContext(scenario_name, size, BenchUser, payloads, ids,
                                    BACKEND_NAMESPACE, BACKEND_NAME)

    def sync_teardown(self, scenario_name, context):
        for backend in self._backends:
            backend.disconnect()
        self._backends.clear()

    async def async_setup(self, scenario_name, size, strategy="context"):
        # Firebird has no async backend: the shared fixtures skip a None context.
        return None

    async def async_teardown(self, scenario_name, context):
        return None


class QueryBenchmarkImpl(CrudBenchmarkImpl):
    """Query benchmark shares the CRUD context shape."""
    def sync_setup(self, scenario_name, size):
        ctx = super().sync_setup(scenario_name, size)
        return QueryBenchmarkContext(ctx.scenario, ctx.size, ctx.model_class, ctx.payloads,
                                     ctx.record_ids, ctx.backend_namespace, ctx.backend_name)


class TransactionBenchmarkImpl(CrudBenchmarkImpl):
    def sync_setup(self, scenario_name, size):
        ctx = super().sync_setup(scenario_name, size)
        return TransactionBenchmarkContext(ctx.scenario, ctx.size, ctx.model_class, ctx.payloads,
                                            ctx.record_ids, ctx.backend_namespace, ctx.backend_name)


class MixinBenchmarkImpl(CrudBenchmarkImpl):
    def sync_setup(self, scenario_name, size):
        ctx = super().sync_setup(scenario_name, size)
        return MixinBenchmarkContext(ctx.scenario, ctx.size, ctx.model_class, ctx.payloads,
                                     ctx.record_ids, ctx.backend_namespace, ctx.backend_name)


# --------------------------------------------------------------------------- #
# Register.  Imported as a pytest plugin (``-p tests.benchmark.providers``) so
# registration happens before the shared contracts are collected.
# --------------------------------------------------------------------------- #
benchmarks.register("crud", CrudBenchmarkImpl("crud"))
benchmarks.register("query", QueryBenchmarkImpl("query"))
benchmarks.register("transaction", TransactionBenchmarkImpl("transaction"))
benchmarks.register("mixin", MixinBenchmarkImpl("mixin"))
