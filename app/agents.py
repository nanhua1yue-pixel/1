"""OpenClaw Agent 配置与路由

支持多个 Bot，每个 Bot 可配置不同的模型、触发关键词和处理端点。
通过 agents.json 文件管理配置，消息进来后按规则路由到对应的 Bot。
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

AGENTS_CONFIG_PATH = Path(__file__).parent.parent / "agents.json"


@dataclass
class AgentConfig:
    """单个 Bot/Agent 的配置"""

    name: str  # Bot 名称
    description: str  # 描述
    endpoint: str  # 处理端点 URL
    model: str = ""  # 使用的模型，如 "gpt-4o", "claude-sonnet-4-20250514", "deepseek-v3"
    keywords: list[str] = field(default_factory=list)  # 触发关键词
    prefix: str = ""  # 命令前缀，如 "@review"
    enabled: bool = True

    def matches(self, text: str) -> bool:
        if not self.enabled:
            return False
        text_lower = text.lower()

        if self.prefix and text_lower.startswith(self.prefix.lower()):
            return True

        for kw in self.keywords:
            if re.search(re.escape(kw), text_lower):
                return True

        return False

    def extract_message(self, text: str) -> str:
        """去掉前缀，返回实际消息内容"""
        if self.prefix and text.lower().startswith(self.prefix.lower()):
            return text[len(self.prefix) :].strip()
        return text

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "endpoint": self.endpoint,
            "model": self.model,
            "keywords": self.keywords,
            "prefix": self.prefix,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AgentConfig:
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            endpoint=data["endpoint"],
            model=data.get("model", ""),
            keywords=data.get("keywords", []),
            prefix=data.get("prefix", ""),
            enabled=data.get("enabled", True),
        )


class AgentRouter:
    """Agent 路由器：根据消息内容选择最合适的 Bot"""

    def __init__(self, agents: list[AgentConfig] | None = None):
        self._agents = agents or []

    @property
    def agents(self) -> list[AgentConfig]:
        return [a for a in self._agents if a.enabled]

    def get_agent(self, name: str) -> AgentConfig | None:
        for agent in self._agents:
            if agent.name == name:
                return agent
        return None

    # 内部 Agent，不参与用户消息路由，只由调度员内部调用
    INTERNAL_AGENTS = {"subagent-l1", "subagent-l2"}

    def route(self, text: str) -> tuple[AgentConfig, str]:
        """匹配消息到 Bot，返回 (agent, 清理后的消息)。

        优先级：前缀命令 > 关键词 > fallback(main 调度员)
        内部 Agent（subagent-l1/l2）不参与路由。
        """
        routable = [a for a in self._agents if a.enabled and a.name not in self.INTERNAL_AGENTS]

        # 1. 前缀匹配
        for agent in routable:
            if agent.prefix and text.lower().startswith(agent.prefix.lower()):
                return agent, agent.extract_message(text)

        # 2. 关键词匹配
        for agent in routable:
            if agent.keywords and agent.matches(text):
                return agent, text

        # 3. Fallback 到 main（主调度员）
        main = self.get_agent("main")
        if main and main.enabled:
            return main, text

        # 4. 兼容旧配置：尝试 general
        general = self.get_agent("general")
        if general and general.enabled:
            return general, text

        # 5. 用第一个可路由的
        for agent in routable:
            return agent, text

        raise ValueError("没有可用的 Bot/Agent")

    def list_agents_markdown(self) -> str:
        """生成 Bot 列表的 Markdown，按角色分组"""
        core = []  # 核心调度
        biz = []   # 业务 Bot
        internal = []  # 内部 Agent

        for agent in self.agents:
            if agent.name in self.INTERNAL_AGENTS:
                internal.append(agent)
            elif agent.name in ("main", "greet"):
                core.append(agent)
            else:
                biz.append(agent)

        def _fmt(agent: AgentConfig) -> str:
            model_info = f" `[{agent.model}]`" if agent.model else ""
            line = f"- **{agent.name}**{model_info} — {agent.description}"
            if agent.prefix:
                line += f"\n  命令: `{agent.prefix} <消息>`"
            return line

        lines = ["## Bot 列表\n"]
        if core:
            lines.append("### 核心调度")
            lines.extend(_fmt(a) for a in core)
            lines.append("")
        if biz:
            lines.append("### 业务 Bot")
            lines.extend(_fmt(a) for a in biz)
            lines.append("")
        if internal:
            lines.append("### 内部 Agent（仅调度员可调用）")
            lines.extend(_fmt(a) for a in internal)
            lines.append("")

        return "\n".join(lines)


def load_agents(config_path: Path = AGENTS_CONFIG_PATH) -> list[AgentConfig]:
    """从 agents.json 加载 Bot 配置"""
    if not config_path.exists():
        logger.warning("agents.json 不存在，使用示例配置，请创建 agents.json")
        return _default_agents()

    with open(config_path) as f:
        data = json.load(f)

    agents_data = data if isinstance(data, list) else data.get("agents", [])
    agents = [AgentConfig.from_dict(item) for item in agents_data]
    logger.info("从 %s 加载了 %d 个 Bot 配置", config_path, len(agents))
    return agents


def _default_agents() -> list[AgentConfig]:
    """默认示例配置"""
    return [
        AgentConfig(
            name="code-reviewer",
            description="代码审查 Bot",
            endpoint="http://localhost:3000/agents/code-reviewer",
            model="claude-sonnet-4-20250514",
            keywords=["review", "代码审查", "看看代码"],
            prefix="@review",
        ),
        AgentConfig(
            name="task-planner",
            description="任务规划 Bot",
            endpoint="http://localhost:3000/agents/task-planner",
            model="gpt-4o",
            keywords=["规划", "拆解", "计划", "plan"],
            prefix="@plan",
        ),
        AgentConfig(
            name="bug-fixer",
            description="Bug 修复 Bot",
            endpoint="http://localhost:3000/agents/bug-fixer",
            model="deepseek-v3",
            keywords=["bug", "修复", "报错", "出错", "fix"],
            prefix="@fix",
        ),
        AgentConfig(
            name="general",
            description="通用对话 Bot，处理未匹配的消息",
            endpoint="http://localhost:3000/agents/general",
            model="gpt-4o-mini",
            keywords=[],
            prefix="",
        ),
    ]


# 全局路由器实例
router = AgentRouter(load_agents())
