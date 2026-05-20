import os
import sys
import logging
from typing import Type, List

from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.testsuite.utils import select_fixture

from rhosocial.activerecord.testsuite.feature.query.fixtures.models import (
    User as QueryUserBase, Post as QueryPostBase, Comment as QueryCommentBase,
)
from rhosocial.activerecord.testsuite.feature.query.fixtures.cte_models import (
    Node as CteNodeBase,
)

from rhosocial.activerecord.testsuite.feature.query.interfaces import IQueryProvider
from rhosocial.activerecord.testsuite.core.protocols import WorkerTestProtocol
from .scenarios import get_enabled_scenarios, get_scenario

logger = logging.getLogger(__name__)


def _select_model_class(base_cls, py312_cls, py311_cls, py310_cls, name):
    candidates = [c for c in [py312_cls, py311_cls, py310_cls, base_cls] if c is not None]
    return select_fixture(*candidates)


QueryUser = _select_model_class(QueryUserBase, None, None, None, "QueryUser")
QueryPost = _select_model_class(QueryPostBase, None, None, None, "QueryPost")
QueryComment = _select_model_class(QueryCommentBase, None, None, None, "QueryComment")
CteNode = _select_model_class(CteNodeBase, None, None, None, "CteNode")


class QueryProvider(IQueryProvider, WorkerTestProtocol):
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
                                  "activerecord_firebird_test", "feature", "query", "schema")
        path = os.path.join(schema_dir, filename)
        if os.path.exists(path):
            with open(path) as f:
                return f.read()
        return ""

    def _setup_multiple_models(self, models, scenario_name):
        if not models:
            return tuple()
        first_cls, first_tbl = models[0]
        first = self._setup_model(first_cls, scenario_name, first_tbl)
        shared = first.__backend__
        result = [first]
        for cls, tbl in models[1:]:
            cls.__connection_config__ = first.__connection_config__
            cls.__backend_class__ = first.__backend_class__
            cls.__backend__ = shared
            try:
                shared.execute(f"DROP TABLE {tbl}", fetch=False)
            except Exception:
                pass
            schema = self._load_schema(f"{tbl}.sql")
            if schema.strip():
                shared.executescript(schema)
            result.append(cls)
        return tuple(result)

    def setup_user_model(self, scenario_name):
        return self._setup_model(QueryUser, scenario_name, "users")

    def setup_post_model(self, scenario_name):
        return self._setup_model(QueryPost, scenario_name, "posts")

    def setup_comment_model(self, scenario_name):
        return self._setup_model(QueryComment, scenario_name, "comments")

    def setup_tree_fixtures(self, scenario_name):
        return self._setup_model(CteNode, scenario_name, "nodes")

    def setup_user_comment_models(self, scenario_name):
        return self._setup_multiple_models([
            (QueryUser, "users"), (QueryComment, "comments")
        ], scenario_name)

    def cleanup_after_test(self, scenario_name):
        tables = ["users", "posts", "comments", "nodes"]
        for b in self._active_backends:
            try:
                for t in tables:
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

    def get_worker_connection_params(self, scenario_name, fixture_type=None):
        from .scenarios import SCENARIO_MAP
        name = scenario_name if scenario_name in SCENARIO_MAP else next(iter(SCENARIO_MAP))
        return {
            'backend_module': 'rhosocial.activerecord.backend.impl.firebird',
            'backend_class_name': 'FirebirdBackend',
            'config_class_module': 'rhosocial.activerecord.backend.impl.firebird.config',
            'config_class_name': 'FirebirdConnectionConfig',
            'config_kwargs': SCENARIO_MAP[name],
            'schema_sql': "",
        }

    def get_worker_schema_sql(self, scenario_name, table_name):
        return self._load_schema(f"{table_name}.sql")
