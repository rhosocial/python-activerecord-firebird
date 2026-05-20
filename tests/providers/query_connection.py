from typing import List
from rhosocial.activerecord.testsuite.feature.query.connection.interfaces import IQueryConnectionProvider
from .scenarios import get_enabled_scenarios


class QueryConnectionProvider(IQueryConnectionProvider):
    def get_test_scenarios(self) -> List[str]:
        return list(get_enabled_scenarios().keys())

    def get_backend_class(self, scenario_name: str):
        from .scenarios import get_scenario
        cls, _ = get_scenario(scenario_name)
        return cls

    def get_connection_config(self, scenario_name: str):
        from .scenarios import get_scenario
        _, config = get_scenario(scenario_name)
        return config
