import os
import sys
import logging
from typing import Type, List, Tuple

from rhosocial.activerecord.model import ActiveRecord

from rhosocial.activerecord.testsuite.utils import select_fixture

from rhosocial.activerecord.testsuite.feature.query.fixtures.models import (
    User as UserBase, JsonUser as JsonUserBase,
    Order as OrderBase, OrderItem as OrderItemBase,
    Post as PostBase, Comment as CommentBase,
    MappedUser as MappedUserBase, MappedPost as MappedPostBase, MappedComment as MappedCommentBase,
)
from rhosocial.activerecord.testsuite.feature.query.fixtures.cte_models import (
    Node as CteNodeBase,
)
from rhosocial.activerecord.testsuite.feature.query.fixtures.extended_models import (
    User as ExtUserBase, ExtendedOrder, ExtendedOrderItem,
)

from rhosocial.activerecord.testsuite.feature.query.interfaces import IQueryProvider
from rhosocial.activerecord.testsuite.core.protocols import WorkerTestProtocol
from .scenarios import get_enabled_scenarios, get_scenario

logger = logging.getLogger(__name__)


def _select_model_class(base_cls, py312_cls, py311_cls, py310_cls, name):
    candidates = [c for c in [py312_cls, py311_cls, py310_cls, base_cls] if c is not None]
    return select_fixture(*candidates)


User = _select_model_class(UserBase, None, None, None, "User")
JsonUser = _select_model_class(JsonUserBase, None, None, None, "JsonUser")
Order = _select_model_class(OrderBase, None, None, None, "Order")
OrderItem = _select_model_class(OrderItemBase, None, None, None, "OrderItem")
Post = _select_model_class(PostBase, None, None, None, "Post")
Comment = _select_model_class(CommentBase, None, None, None, "Comment")
MappedUser = _select_model_class(MappedUserBase, None, None, None, "MappedUser")
MappedPost = _select_model_class(MappedPostBase, None, None, None, "MappedPost")
MappedComment = _select_model_class(MappedCommentBase, None, None, None, "MappedComment")
CteNode = _select_model_class(CteNodeBase, None, None, None, "CteNode")
ExtUser = _select_model_class(ExtUserBase, None, None, None, "ExtUser")


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
        return self._setup_model(User, scenario_name, "users")

    def setup_post_model(self, scenario_name):
        return self._setup_model(Post, scenario_name, "posts")

    def setup_comment_model(self, scenario_name):
        return self._setup_model(Comment, scenario_name, "comments")

    def setup_tree_fixtures(self, scenario_name):
        return self._setup_model(CteNode, scenario_name, "nodes")

    def setup_user_comment_models(self, scenario_name):
        return self._setup_multiple_models([
            (User, "users"), (Comment, "comments")
        ], scenario_name)

    def setup_order_fixtures(self, scenario_name):
        return self._setup_multiple_models([
            (User, "users"),
            (Order, "orders"),
            (OrderItem, "order_items"),
        ], scenario_name)

    def setup_blog_fixtures(self, scenario_name):
        return self._setup_multiple_models([
            (User, "users"),
            (Post, "posts"),
            (Comment, "comments"),
        ], scenario_name)

    def setup_json_user_fixtures(self, scenario_name):
        json_user_model = self._setup_model(JsonUser, scenario_name, "json_users")
        return (json_user_model,)

    def setup_extended_order_fixtures(self, scenario_name):
        return self._setup_multiple_models([
            (ExtUser, "users"),
            (ExtendedOrder, "extended_orders"),
            (ExtendedOrderItem, "extended_order_items"),
        ], scenario_name)

    def setup_combined_fixtures(self, scenario_name):
        return self._setup_multiple_models([
            (User, "users"),
            (Order, "orders"),
            (OrderItem, "order_items"),
            (Post, "posts"),
            (Comment, "comments"),
        ], scenario_name)

    def setup_annotated_query_fixtures(self, scenario_name):
        from rhosocial.activerecord.testsuite.feature.query.fixtures.annotated_adapter_models import SearchableItem
        return self._setup_multiple_models([
            (SearchableItem, "searchable_items"),
        ], scenario_name)

    def setup_mapped_models(self, scenario_name):
        return self._setup_multiple_models([
            (MappedUser, "users"),
            (MappedPost, "posts"),
            (MappedComment, "comments"),
        ], scenario_name)

    async def setup_async_order_fixtures(self, scenario_name):
        raise NotImplementedError("Firebird backend does not support async")

    async def setup_async_blog_fixtures(self, scenario_name):
        raise NotImplementedError("Firebird backend does not support async")

    async def setup_async_json_user_fixtures(self, scenario_name):
        raise NotImplementedError("Firebird backend does not support async")

    async def setup_async_tree_fixtures(self, scenario_name):
        raise NotImplementedError("Firebird backend does not support async")

    async def setup_async_extended_order_fixtures(self, scenario_name):
        raise NotImplementedError("Firebird backend does not support async")

    async def setup_async_combined_fixtures(self, scenario_name):
        raise NotImplementedError("Firebird backend does not support async")

    async def setup_async_annotated_query_fixtures(self, scenario_name):
        raise NotImplementedError("Firebird backend does not support async")

    async def setup_async_mapped_models(self, scenario_name):
        raise NotImplementedError("Firebird backend does not support async")

    def cleanup_after_test(self, scenario_name):
        tables = ["users", "posts", "comments", "nodes",
                  "orders", "order_items", "json_users",
                  "extended_orders", "extended_order_items",
                  "searchable_items"]
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

    async def cleanup_after_test_async(self, scenario_name):
        raise NotImplementedError("Firebird backend does not support async")

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
