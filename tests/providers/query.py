# tests/providers/query.py
import os
import logging
from typing import Type, List, Tuple, Set

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
from rhosocial.activerecord.testsuite.feature.basic.fixtures.models import (
    OrderItem as CompositeOrderItem,
)

from rhosocial.activerecord.testsuite.feature.query.interfaces import (
    QueryProviderBase,
    IQuerySyncProvider,
    IQueryAsyncProvider,
)
from rhosocial.activerecord.backend.impl.firebird import AsyncFirebirdBackend
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


class QueryProviderBaseImpl(QueryProviderBase):
    def __init__(self):
        self._created_tables: Set[str] = set()

    def get_test_scenarios(self) -> List[str]:
        return list(get_enabled_scenarios().keys())

    def _load_firebird_schema(self, filename: str, schema_dir_name: str = "query") -> str:
        schema_dir = os.path.join(
            os.path.dirname(__file__), "..", "rhosocial", "activerecord_firebird_test",
            "feature", schema_dir_name, "schema",
        )
        schema_path = os.path.join(schema_dir, filename)
        if os.path.exists(schema_path):
            with open(schema_path, "r", encoding="utf-8") as f:
                return f.read()
        return ""


class QuerySyncProvider(QueryProviderBaseImpl, IQuerySyncProvider, WorkerTestProtocol):
    def __init__(self):
        super().__init__()
        self._active_backends: List = []

    def _track_backend(self, backend) -> None:
        if backend not in self._active_backends:
            self._active_backends.append(backend)

    def _setup_model(
        self, model_class: Type[ActiveRecord], scenario_name: str, table_name: str,
        schema_dir_name: str = "query",
    ) -> Type[ActiveRecord]:
        backend_class, config = get_scenario(scenario_name)
        model_class.configure(config, backend_class)
        backend = model_class.__backend__
        self._track_backend(backend)
        self._reset_table_sync(backend, table_name, schema_dir_name)
        self._created_tables.add(table_name)
        return model_class

    def _reset_table_sync(self, backend, table_name: str, schema_dir_name: str = "query") -> None:
        try:
            backend.execute(f"DROP TABLE {table_name}", fetch=False)
        except Exception:
            pass
        schema = self._load_firebird_schema(f"{table_name}.sql", schema_dir_name)
        if schema.strip():
            backend.executescript(schema)

    def _initialize_model_schema(
        self, model_class: Type[ActiveRecord], table_name: str,
        schema_dir_name: str = "query",
    ) -> None:
        self._reset_table_sync(model_class.__backend__, table_name, schema_dir_name)

    def _setup_multiple_models(
        self, model_classes: List[Tuple[Type[ActiveRecord], str]], scenario_name: str
    ) -> Tuple[Type[ActiveRecord], ...]:
        if not model_classes:
            return tuple()
        first_model_class, first_table_name = model_classes[0]
        first_model = self._setup_model(first_model_class, scenario_name, first_table_name)
        shared_backend = first_model.__backend__
        result = [first_model]
        for model_class, table_name in model_classes[1:]:
            model_class.__connection_config__ = first_model.__connection_config__
            model_class.__backend_class__ = first_model.__backend_class__
            model_class.__backend__ = shared_backend
            self._track_backend(shared_backend)
            self._initialize_model_schema(model_class, table_name)
            self._created_tables.add(table_name)
            result.append(model_class)
        return tuple(result)

    def setup_user_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(User, scenario_name, "users")

    def setup_post_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(Post, scenario_name, "posts")

    def setup_comment_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(Comment, scenario_name, "comments")

    def setup_tree_fixtures(self, scenario_name: str) -> Tuple[Type[ActiveRecord], ...]:
        return (self._setup_model(CteNode, scenario_name, "nodes"),)

    def setup_user_comment_models(self, scenario_name: str) -> Tuple[Type[ActiveRecord], ...]:
        return self._setup_multiple_models(
            [(User, "users"), (Comment, "comments")], scenario_name
        )

    def setup_order_fixtures(
        self, scenario_name: str
    ) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        return self._setup_multiple_models([
            (User, "users"),
            (Order, "orders"),
            (OrderItem, "order_items"),
        ], scenario_name)

    def setup_blog_fixtures(
        self, scenario_name: str
    ) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        return self._setup_multiple_models([
            (User, "users"),
            (Post, "posts"),
            (Comment, "comments"),
        ], scenario_name)

    def setup_json_user_fixtures(self, scenario_name: str) -> Tuple[Type[ActiveRecord], ...]:
        return (self._setup_model(JsonUser, scenario_name, "json_users"),)

    def setup_extended_order_fixtures(
        self, scenario_name: str
    ) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        return self._setup_multiple_models([
            (ExtUser, "users"),
            (ExtendedOrder, "extended_orders"),
            (ExtendedOrderItem, "extended_order_items"),
        ], scenario_name)

    def setup_combined_fixtures(
        self, scenario_name: str
    ) -> Tuple[
        Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord],
        Type[ActiveRecord], Type[ActiveRecord],
    ]:
        return self._setup_multiple_models([
            (User, "users"),
            (Order, "orders"),
            (OrderItem, "order_items"),
            (Post, "posts"),
            (Comment, "comments"),
        ], scenario_name)

    def setup_annotated_query_fixtures(self, scenario_name: str) -> Tuple[Type[ActiveRecord], ...]:
        from rhosocial.activerecord.testsuite.feature.query.fixtures.annotated_adapter_models import SearchableItem
        return self._setup_multiple_models([
            (SearchableItem, "searchable_items"),
        ], scenario_name)

    def setup_mapped_models(
        self, scenario_name: str
    ) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        return self._setup_multiple_models([
            (MappedUser, "users"),
            (MappedPost, "posts"),
            (MappedComment, "comments"),
        ], scenario_name)

    def setup_profile_fixtures(self, scenario_name: str) -> Tuple[Type[ActiveRecord], Type[ActiveRecord]]:
        Profile = User.get_relation("profile").get_related_model(User)
        return self._setup_multiple_models([
            (User, "users"),
            (Profile, "profiles"),
        ], scenario_name)

    def setup_order_item_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(CompositeOrderItem, scenario_name, "order_items", "basic")

    def get_worker_connection_params(self, scenario_name: str, fixture_type: str = None) -> dict:
        from .scenarios import SCENARIO_MAP
        if scenario_name not in SCENARIO_MAP:
            if SCENARIO_MAP:
                scenario_name = next(iter(SCENARIO_MAP))
            else:
                raise ValueError("No scenarios registered")
        config_dict = SCENARIO_MAP[scenario_name]
        from providers.pooling import resolve_database_name
        pooled_db = resolve_database_name(scenario_name)
        if pooled_db:
            config_dict = {**config_dict, "database": pooled_db}
        return {
            "backend_module": "rhosocial.activerecord.backend.impl.firebird",
            "backend_class_name": "FirebirdBackend",
            "config_class_module": "rhosocial.activerecord.backend.impl.firebird.config",
            "config_class_name": "FirebirdConnectionConfig",
            "config_kwargs": config_dict,
            "schema_sql": self.get_worker_schema_sql(scenario_name, "users"),
        }

    def get_worker_schema_sql(self, scenario_name: str, table_name: str) -> str:
        return self._load_firebird_schema(f"{table_name}.sql")

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


class QueryAsyncProvider(QueryProviderBaseImpl, IQueryAsyncProvider):
    """Async provider for the 'query' feature tests."""

    def __init__(self):
        super().__init__()
        self._active_backends: List = []

    async def _setup_model(
        self, model_class: Type[ActiveRecord], scenario_name: str, table_name: str,
        schema_dir_name: str = "query",
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
        schema = self._load_firebird_schema(f"{table_name}.sql", schema_dir_name)
        if schema.strip():
            await backend.executescript(schema)
        self._created_tables.add(table_name)
        return model_class

    async def _setup_multiple_models(
        self, model_classes: List[Tuple[Type[ActiveRecord], str]], scenario_name: str,
    ) -> Tuple[Type[ActiveRecord], ...]:
        if not model_classes:
            return tuple()
        first_model_class, first_table_name = model_classes[0]
        first_model = await self._setup_model(first_model_class, scenario_name, first_table_name)
        shared_backend = first_model.__backend__
        from rhosocial.activerecord.backend.options import ExecutionOptions
        from rhosocial.activerecord.backend.schema import StatementType

        ddl = ExecutionOptions(stmt_type=StatementType.DDL, process_result_set=False)
        result = [first_model]
        for model_class, table_name in model_classes[1:]:
            model_class.__connection_config__ = first_model.__connection_config__
            model_class.__backend_class__ = first_model.__backend_class__
            model_class.__backend__ = shared_backend
            if shared_backend not in self._active_backends:
                self._active_backends.append(shared_backend)
            try:
                await shared_backend.execute(f"DROP TABLE {table_name}", options=ddl)
            except Exception:
                pass
            schema = self._load_firebird_schema(f"{table_name}.sql")
            if schema.strip():
                await shared_backend.executescript(schema)
            self._created_tables.add(table_name)
            result.append(model_class)
        return tuple(result)

    async def setup_order_fixtures(
        self, scenario_name: str
    ) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        from rhosocial.activerecord.testsuite.feature.query.fixtures.async_models import (
            AsyncUser,
            AsyncOrder,
            AsyncOrderItem,
        )

        return await self._setup_multiple_models(
            [(AsyncUser, "users"), (AsyncOrder, "orders"), (AsyncOrderItem, "order_items")], scenario_name
        )

    async def setup_blog_fixtures(
        self, scenario_name: str
    ) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        from rhosocial.activerecord.testsuite.feature.query.fixtures.async_blog_models import AsyncPost, AsyncComment
        from rhosocial.activerecord.testsuite.feature.query.fixtures.async_models import AsyncUser

        return await self._setup_multiple_models(
            [(AsyncUser, "users"), (AsyncPost, "posts"), (AsyncComment, "comments")], scenario_name
        )

    async def setup_json_user_fixtures(self, scenario_name: str) -> Tuple[Type[ActiveRecord], ...]:
        import pytest
        from rhosocial.activerecord.testsuite.feature.query.fixtures.async_json_models import AsyncJsonUser

        _, config = get_scenario(scenario_name)
        await AsyncJsonUser.configure(config, AsyncFirebirdBackend)
        backend = AsyncJsonUser.__backend__
        if backend not in self._active_backends:
            self._active_backends.append(backend)
        if not backend.dialect.supports_json_type():
            pytest.skip(f"JSON type not supported by Firebird {backend.dialect.version}")
        return (await self._setup_model(AsyncJsonUser, scenario_name, "json_users"),)

    async def setup_tree_fixtures(self, scenario_name: str) -> Tuple[Type[ActiveRecord], ...]:
        from rhosocial.activerecord.testsuite.feature.query.fixtures.async_cte_models import AsyncNode

        return (await self._setup_model(AsyncNode, scenario_name, "nodes"),)

    async def setup_extended_order_fixtures(
        self, scenario_name: str
    ) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        from rhosocial.activerecord.testsuite.feature.query.fixtures.async_extended_models import (
            AsyncUser,
            AsyncExtendedOrder,
            AsyncExtendedOrderItem,
        )

        return await self._setup_multiple_models(
            [
                (AsyncUser, "users"),
                (AsyncExtendedOrder, "extended_orders"),
                (AsyncExtendedOrderItem, "extended_order_items"),
            ],
            scenario_name,
        )

    async def setup_combined_fixtures(
        self, scenario_name: str
    ) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        from rhosocial.activerecord.testsuite.feature.query.fixtures.async_models import (
            AsyncUser,
            AsyncOrder,
            AsyncOrderItem,
        )
        from rhosocial.activerecord.testsuite.feature.query.fixtures.async_blog_models import AsyncPost, AsyncComment

        return await self._setup_multiple_models(
            [
                (AsyncUser, "users"),
                (AsyncOrder, "orders"),
                (AsyncOrderItem, "order_items"),
                (AsyncPost, "posts"),
                (AsyncComment, "comments"),
            ],
            scenario_name,
        )

    async def setup_annotated_query_fixtures(self, scenario_name: str) -> Tuple[Type[ActiveRecord], ...]:
        from rhosocial.activerecord.testsuite.feature.query.fixtures.async_annotated_adapter_models import (
            AsyncSearchableItem,
        )

        return await self._setup_multiple_models([(AsyncSearchableItem, "searchable_items")], scenario_name)

    async def setup_mapped_models(
        self, scenario_name: str
    ) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        from rhosocial.activerecord.testsuite.feature.query.fixtures.models import (
            AsyncMappedUser,
            AsyncMappedPost,
            AsyncMappedComment,
        )

        return await self._setup_multiple_models(
            [(AsyncMappedUser, "users"), (AsyncMappedPost, "posts"), (AsyncMappedComment, "comments")], scenario_name
        )

    async def setup_profile_fixtures(
        self, scenario_name: str
    ) -> Tuple[Type[ActiveRecord], Type[ActiveRecord]]:
        from rhosocial.activerecord.testsuite.feature.query.fixtures.async_models import (
            AsyncUser,
            AsyncProfile,
        )

        return await self._setup_multiple_models([(AsyncUser, "users"), (AsyncProfile, "profiles")], scenario_name)

    async def setup_order_item_model(self, scenario_name: str) -> Type[ActiveRecord]:
        from rhosocial.activerecord.testsuite.feature.basic.fixtures.models import AsyncOrderItem

        return await self._setup_model(AsyncOrderItem, scenario_name, "order_items", "basic")

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
