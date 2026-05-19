# tests/providers/scenarios.py
"""Firebird backend test scenario configuration mapping table"""

import os
from typing import Dict, Any, Tuple, Type
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

SCENARIO_MAP: Dict[str, Dict[str, Any]] = {}


def register_scenario(name: str, config: Dict[str, Any]):
    """Register Firebird test scenario"""
    SCENARIO_MAP[name] = config


def get_scenario(name: str) -> Tuple[Type[FirebirdBackend], FirebirdConnectionConfig]:
    """
    Retrieves the backend class and a connection configuration object for a given
    scenario name.
    """
    if name not in SCENARIO_MAP:
        if SCENARIO_MAP:
            name = next(iter(SCENARIO_MAP))
        else:
            raise ValueError("No scenarios registered")

    config = FirebirdConnectionConfig(**SCENARIO_MAP[name])
    return FirebirdBackend, config


def get_enabled_scenarios() -> Dict[str, Any]:
    """
    Returns the map of all currently enabled scenarios.
    """
    return SCENARIO_MAP


def _load_scenarios_from_config():
    """
    Load scenarios from a configuration file with the following priority:
    1. Environment variable specified path (highest priority)
    2. Default path tests/config/firebird_scenarios.yaml (lowest priority)
    """
    import yaml

    env_config_path = os.getenv("FIREBIRD_SCENARIOS_CONFIG_PATH")
    if env_config_path and os.path.exists(env_config_path):
        print(f"Loading Firebird scenarios from environment-specified path: {env_config_path}")
        config_path = env_config_path
    else:
        config_path = os.path.join(os.path.dirname(__file__), "..", "config", "firebird_scenarios.yaml")
        if not os.path.exists(config_path):
            raise FileNotFoundError(
                "No Firebird scenarios configuration file found. "
                "Either set FIREBIRD_SCENARIOS_CONFIG_PATH environment variable to point to a valid YAML file "
                "or place firebird_scenarios.yaml in the tests/config directory."
            )
        print(f"Loading Firebird scenarios from default path: {config_path}")

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)

        if 'scenarios' not in config_data:
            raise ValueError(f"Configuration file {config_path} does not contain 'scenarios' key")

        for scenario_name, config in config_data['scenarios'].items():
            register_scenario(scenario_name, config)

    except ImportError:
        raise ImportError("PyYAML is required to load Firebird scenario configuration files")


def _register_default_scenarios():
    _load_scenarios_from_config()


_register_default_scenarios()