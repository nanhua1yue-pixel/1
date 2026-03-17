"""多 API 供应商管理

根据模型名自动查找对应的 API 供应商（api_base + api_key），
支持热重载，供 handler 在转发时附带正确的凭证。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

PROVIDERS_CONFIG_PATH = Path(__file__).parent.parent / "providers.json"


@dataclass
class ProviderInfo:
    """单个供应商"""

    name: str
    api_base: str
    api_key: str
    models: list[str]


class ProviderRegistry:
    """供应商注册表：根据模型名查找 api_base 和 api_key"""

    def __init__(self):
        self._providers: list[ProviderInfo] = []
        # model -> ProviderInfo 快速查找
        self._model_map: dict[str, ProviderInfo] = {}
        self._load()

    def _load(self):
        if not PROVIDERS_CONFIG_PATH.exists():
            logger.info("providers.json 不存在，跳过供应商配置")
            return

        try:
            with open(PROVIDERS_CONFIG_PATH) as f:
                data = json.load(f)
        except Exception as e:
            logger.error("providers.json 解析失败: %s", e)
            return

        providers_data = data.get("providers", {})
        self._providers = []
        self._model_map = {}

        for key, cfg in providers_data.items():
            p = ProviderInfo(
                name=cfg.get("name", key),
                api_base=cfg["api_base"],
                api_key=cfg["api_key"],
                models=cfg.get("models", []),
            )
            self._providers.append(p)
            for model in p.models:
                self._model_map[model] = p

        logger.info(
            "加载了 %d 个供应商，共 %d 个模型",
            len(self._providers),
            len(self._model_map),
        )

    def reload(self) -> int:
        self._load()
        return len(self._providers)

    def lookup(self, model: str) -> tuple[str, str] | None:
        """根据模型名查找供应商，返回 (api_base, api_key) 或 None"""
        p = self._model_map.get(model)
        if p:
            return p.api_base, p.api_key
        return None

    def all_providers(self) -> list[dict]:
        return [
            {
                "name": p.name,
                "api_base": p.api_base,
                "model_count": len(p.models),
                "models": p.models,
            }
            for p in self._providers
        ]


# 全局实例
registry = ProviderRegistry()
