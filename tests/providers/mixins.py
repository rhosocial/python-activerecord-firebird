import os
import sys
import logging
from typing import Type, List

from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.testsuite.utils import select_fixture
from rhosocial.activerecord.testsuite.feature.mixins.fixtures.models import (
    TimestampedPost as TimestampedPostBase,
    VersionedProduct as VersionedProductBase,
    Task as TaskBase,
    CombinedArticle as CombinedArticleBase,
)
from rhosocial.activerecord.testsuite.feature.mixins.interfaces import IMixinsProvider
from .scenarios import get_enabled_scenarios, get_scenario

logger = logging.getLogger(__name__)


def _select_model_class(base_cls, py312_cls, py311_cls, py310_cls, name):
    candidates = [c for c in [py312_cls, py311_cls, py310_cls, base_cls] if c is not None]
    return select_fixture(*candidates)


TimestampedPost = _select_model_class(TimestampedPostBase, None, None, None, "TimestampedPost")
VersionedProduct = _select_model_class(VersionedProductBase, None, None, None, "VersionedProduct")
Task = _select_model_class(TaskBase, None, None, None, "Task")
CombinedArticle = _select_model_class(CombinedArticleBase, None, None, None, "CombinedArticle")


class MixinsProvider(IMixinsProvider):
    def __init__(self):
        self._active_backends = []

    def get_test_scenarios(self) -> List[str]:
        return list(get_enabled_scenarios().keys())

    def _setup_model(self, model_class, scenario_name, table_name):
        backend_class, config = get_scenario(scenario_name)
        model_class.configure(config, backend_class)
        backend = model_class.__backend__
        if backend not in self._active_backends:
            self._active_backends.append(backend)
        try:
            backend.execute(f"DROP TABLE {table_name}", fetch=False)
        except Exception:
            pass
        schema = self._load_schema(f"{table_name}.sql")
        if schema.strip():
            backend.executescript(schema)
        return model_class

    def _load_schema(self, filename):
        schema_dir = os.path.join(os.path.dirname(__file__), "..", "rhosocial",
                                  "activerecord_firebird_test", "feature", "mixins", "schema")
        path = os.path.join(schema_dir, filename)
        if os.path.exists(path):
            with open(path) as f:
                return f.read()
        return ""

    def setup_timestamped_post_model(self, scenario_name):
        return self._setup_model(TimestampedPost, scenario_name, "timestamped_posts")

    def setup_versioned_product_model(self, scenario_name):
        return self._setup_model(VersionedProduct, scenario_name, "versioned_products")

    def setup_task_model(self, scenario_name):
        return self._setup_model(Task, scenario_name, "tasks")

    def setup_combined_article_model(self, scenario_name):
        return self._setup_model(CombinedArticle, scenario_name, "combined_articles")

    def cleanup_after_test(self, scenario_name):
        for b in self._active_backends:
            try:
                for t in ["timestamped_posts", "versioned_products", "tasks", "combined_articles"]:
                    try:
                        b.execute(f"DROP TABLE {t}", fetch=False)
                    except Exception:
                        pass
            finally:
                try:
                    b.disconnect()
                except Exception:
                    pass
        self._active_backends.clear()
