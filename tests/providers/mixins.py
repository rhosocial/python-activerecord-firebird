# tests/providers/mixins.py
import os
import logging
from typing import Type, List, Set

from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.testsuite.utils import select_fixture
from rhosocial.activerecord.testsuite.feature.mixins.fixtures.models import (
    TimestampedPost as TimestampedPostBase,
    VersionedProduct as VersionedProductBase,
    Task as TaskBase,
    CombinedArticle as CombinedArticleBase,
)
from rhosocial.activerecord.testsuite.feature.mixins.interfaces import (
    MixinsProviderBase,
    IMixinsSyncProvider,
    IMixinsAsyncProvider,
)
from rhosocial.activerecord.backend.impl.firebird import AsyncFirebirdBackend
from .scenarios import get_enabled_scenarios, get_scenario

logger = logging.getLogger(__name__)


def _select_model_class(base_cls, py312_cls, py311_cls, py310_cls, name):
    candidates = [c for c in [py312_cls, py311_cls, py310_cls, base_cls] if c is not None]
    return select_fixture(*candidates)


TimestampedPost = _select_model_class(TimestampedPostBase, None, None, None, "TimestampedPost")
VersionedProduct = _select_model_class(VersionedProductBase, None, None, None, "VersionedProduct")
Task = _select_model_class(TaskBase, None, None, None, "Task")
CombinedArticle = _select_model_class(CombinedArticleBase, None, None, None, "CombinedArticle")


class MixinsProviderBaseImpl(MixinsProviderBase):
    def __init__(self):
        self._created_tables: Set[str] = set()

    def get_test_scenarios(self) -> List[str]:
        return list(get_enabled_scenarios().keys())

    def _load_firebird_schema(self, filename: str) -> str:
        schema_dir = os.path.join(
            os.path.dirname(__file__), "..", "rhosocial", "activerecord_firebird_test", "feature", "mixins", "schema"
        )
        schema_path = os.path.join(schema_dir, filename)
        if os.path.exists(schema_path):
            with open(schema_path, "r", encoding="utf-8") as f:
                return f.read()
        return ""


class MixinsSyncProvider(MixinsProviderBaseImpl, IMixinsSyncProvider):
    def __init__(self):
        super().__init__()
        self._active_backends: List = []

    def _setup_model(
        self, model_class: Type[ActiveRecord], scenario_name: str, table_name: str
    ) -> Type[ActiveRecord]:
        backend_class, config = get_scenario(scenario_name)
        model_class.configure(config, backend_class)
        backend = model_class.__backend__
        if backend not in self._active_backends:
            self._active_backends.append(backend)
        try:
            backend.execute(f"DROP TABLE {table_name}", fetch=False)
        except Exception:
            pass
        schema = self._load_firebird_schema(f"{table_name}.sql")
        if schema.strip():
            backend.executescript(schema)
        self._created_tables.add(table_name)
        return model_class

    def setup_timestamped_post_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(TimestampedPost, scenario_name, "timestamped_posts")

    def setup_versioned_product_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(VersionedProduct, scenario_name, "versioned_products")

    def setup_task_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(Task, scenario_name, "tasks")

    def setup_combined_article_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(CombinedArticle, scenario_name, "combined_articles")

    def cleanup_after_test(self, scenario_name: str):
        for backend in self._active_backends:
            try:
                for table_name in list(self._created_tables):
                    try:
                        backend.execute(f"DROP TABLE {table_name}", fetch=False)
                    except Exception:
                        pass
            finally:
                try:
                    backend.disconnect()
                except Exception:
                    pass
        self._active_backends.clear()
        self._created_tables.clear()


class MixinsAsyncProvider(MixinsProviderBaseImpl, IMixinsAsyncProvider):
    """Async provider for the 'mixins' feature tests."""

    def __init__(self):
        super().__init__()
        self._active_backends: List = []

    async def _setup_model(
        self, model_class: Type[ActiveRecord], scenario_name: str, table_name: str
    ) -> Type[ActiveRecord]:
        from rhosocial.activerecord.backend.options import ExecutionOptions
        from rhosocial.activerecord.backend.schema import StatementType

        _, config = get_scenario(scenario_name)
        await model_class.configure(config, AsyncFirebirdBackend)
        backend = model_class.__backend__
        if backend not in self._active_backends:
            self._active_backends.append(backend)
        ddl = ExecutionOptions(stmt_type=StatementType.DDL, process_result_set=False)
        try:
            await backend.execute(f"DROP TABLE {table_name}", options=ddl)
        except Exception:
            pass
        schema = self._load_firebird_schema(f"{table_name}.sql")
        if schema.strip():
            await backend.executescript(schema)
        self._created_tables.add(table_name)
        return model_class

    async def setup_timestamped_post_model(self, scenario_name: str) -> Type[ActiveRecord]:
        from rhosocial.activerecord.testsuite.feature.mixins.fixtures.models import AsyncTimestampedPost

        return await self._setup_model(AsyncTimestampedPost, scenario_name, "timestamped_posts")

    async def setup_versioned_product_model(self, scenario_name: str) -> Type[ActiveRecord]:
        from rhosocial.activerecord.testsuite.feature.mixins.fixtures.models import AsyncVersionedProduct

        return await self._setup_model(AsyncVersionedProduct, scenario_name, "versioned_products")

    async def setup_task_model(self, scenario_name: str) -> Type[ActiveRecord]:
        from rhosocial.activerecord.testsuite.feature.mixins.fixtures.models import AsyncTask

        return await self._setup_model(AsyncTask, scenario_name, "tasks")

    async def setup_combined_article_model(self, scenario_name: str) -> Type[ActiveRecord]:
        from rhosocial.activerecord.testsuite.feature.mixins.fixtures.models import AsyncCombinedArticle

        return await self._setup_model(AsyncCombinedArticle, scenario_name, "combined_articles")

    async def cleanup_after_test(self, scenario_name: str):
        from rhosocial.activerecord.backend.options import ExecutionOptions
        from rhosocial.activerecord.backend.schema import StatementType

        ddl = ExecutionOptions(stmt_type=StatementType.DDL, process_result_set=False)
        for backend in self._active_backends:
            try:
                for table_name in list(self._created_tables):
                    try:
                        await backend.execute(f"DROP TABLE {table_name}", options=ddl)
                    except Exception:
                        pass
            finally:
                try:
                    await backend.disconnect()
                except Exception:
                    pass
        self._active_backends.clear()
        self._created_tables.clear()
