
import os
from pathlib import Path
from typing import Dict, Any, Optional

import tomli
from loguru import logger


class ConfigManager:

    _instance: Optional['ConfigManager'] = None
    _config: Dict[str, Any] = {}

    def __new__(cls, config_path: Optional[str] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config(config_path)
        return cls._instance

    def _load_config(self, config_path: Optional[str] = None):
        if config_path is None:
            project_root = Path(__file__).parent.parent
            config_path = project_root / "config" / "config.toml"

        config_path = Path(config_path)

        if not config_path.exists():
            logger.warning(f"配置文件不存在: {config_path}，使用默认配置")
            self._config = self._get_default_config()
            return

        try:
            with open(config_path, 'rb') as f:
                self._config = tomli.load(f)
            logger.info(f"配置文件加载成功: {config_path}")
        except Exception as e:
            logger.error(f"配置文件加载失败: {e}，使用默认配置")
            self._config = self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        return {
            "nostr": {
                "relays": [
                    "wss://relay.damus.io",
                    "wss://relay.nostr.band",
                ],
                "connect_timeout": 10,
                "subscription_timeout": 30,
            },
            "nip304": {
                "version": "1.0.0",
                "protocol_name": "Cloak Risk Data Trading Protocol",
                "protocol_id": "cloak-risk-data",
            },
            "federated_learning": {
                "default_model_type": "logistic_regression",
                "default_rounds": 5,
                "default_local_epochs": 1,
                "default_learning_rate": 0.01,
                "default_batch_size": 32,
                "aggregation_algorithm": "fedavg",
            },
            "blockchain": {
                "chain_id": 11155111,
                "rpc_url": "",
                "contracts": {},
            },
            "logging": {
                "level": "INFO",
                "file_output": False,
            },
            "testing": {
                "mock_mode": True,
                "test_samples": 100,
                "test_clients": 3,
                "random_seed": 42,
            },
        }

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_section(self, section: str) -> Dict[str, Any]:
        return self._config.get(section, {})

    @property
    def config(self) -> Dict[str, Any]:
        return self._config.copy()

    def reload(self, config_path: Optional[str] = None):
        self._load_config(config_path)
        logger.info("配置已重新加载")


def get_config() -> ConfigManager:
    return ConfigManager()


__all__ = ["ConfigManager", "get_config"]
