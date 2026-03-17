"""模型健康状态追踪

记录每个模型的成功/失败情况，自动标记不健康的模型，
并在冷却期后自动恢复探测，实现"永不掉线"。
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# 连续失败多少次后标记为不健康
FAILURE_THRESHOLD = 3
# 不健康模型的冷却时间（秒），冷却后自动尝试恢复
COOLDOWN_SECONDS = 120


@dataclass
class ModelStatus:
    """单个模型的健康状态"""

    model: str
    consecutive_failures: int = 0
    total_successes: int = 0
    total_failures: int = 0
    last_failure_time: float = 0.0
    last_success_time: float = 0.0
    last_error: str = ""

    @property
    def is_healthy(self) -> bool:
        if self.consecutive_failures < FAILURE_THRESHOLD:
            return True
        # 冷却期过了，允许重新探测
        if time.time() - self.last_failure_time > COOLDOWN_SECONDS:
            return True
        return False

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "healthy": self.is_healthy,
            "consecutive_failures": self.consecutive_failures,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "last_error": self.last_error,
            "cooldown_remaining": max(
                0,
                COOLDOWN_SECONDS - (time.time() - self.last_failure_time),
            )
            if not self.is_healthy
            else 0,
        }


class HealthTracker:
    """全局模型健康追踪器"""

    def __init__(self):
        self._models: dict[str, ModelStatus] = {}

    def _get(self, model: str) -> ModelStatus:
        if model not in self._models:
            self._models[model] = ModelStatus(model=model)
        return self._models[model]

    def record_success(self, model: str) -> None:
        status = self._get(model)
        status.consecutive_failures = 0
        status.total_successes += 1
        status.last_success_time = time.time()
        if status.last_error:
            logger.info("模型 [%s] 已恢复健康", model)
            status.last_error = ""

    def record_failure(self, model: str, error: str) -> None:
        status = self._get(model)
        status.consecutive_failures += 1
        status.total_failures += 1
        status.last_failure_time = time.time()
        status.last_error = error
        if status.consecutive_failures >= FAILURE_THRESHOLD:
            logger.warning(
                "模型 [%s] 连续失败 %d 次，标记为不健康，冷却 %ds",
                model,
                status.consecutive_failures,
                COOLDOWN_SECONDS,
            )

    def is_healthy(self, model: str) -> bool:
        return self._get(model).is_healthy

    def get_healthy_models(self, models: list[str]) -> list[str]:
        """从模型列表中筛选出健康的模型，保持原始顺序"""
        healthy = [m for m in models if self.is_healthy(m)]
        # 如果全挂了，返回原始列表（强制重试，避免完全不可用）
        return healthy if healthy else models

    def all_status(self) -> list[dict]:
        return [s.to_dict() for s in self._models.values()]


# 全局实例
tracker = HealthTracker()
