# tests/providers/registry.py
from rhosocial.activerecord.testsuite.core.registry import ProviderRegistry
from .basic import BasicSyncProvider
from .events import EventsSyncProvider
from .mixins import MixinsSyncProvider
from .query import QuerySyncProvider
from .relation import RelationSyncProvider
from .basic_connection import BasicConnectionProvider
from .query_connection import QueryConnectionProvider

provider_registry = ProviderRegistry()

provider_registry.register("feature.basic.IBasicProvider", BasicSyncProvider)
provider_registry.register("feature.basic.IBasicSyncProvider", BasicSyncProvider)

provider_registry.register("feature.events.IEventsProvider", EventsSyncProvider)
provider_registry.register("feature.events.IEventsSyncProvider", EventsSyncProvider)

provider_registry.register("feature.mixins.IMixinsProvider", MixinsSyncProvider)
provider_registry.register("feature.mixins.IMixinsSyncProvider", MixinsSyncProvider)

provider_registry.register("feature.query.IQueryProvider", QuerySyncProvider)
provider_registry.register("feature.query.IQuerySyncProvider", QuerySyncProvider)

provider_registry.register("feature.relation.IRelationProvider", RelationSyncProvider)
provider_registry.register("feature.relation.IRelationSyncProvider", RelationSyncProvider)

provider_registry.register(
    "feature.basic.connection.IBasicConnectionProvider", BasicConnectionProvider
)
provider_registry.register(
    "feature.query.connection.IQueryConnectionProvider", QueryConnectionProvider
)
