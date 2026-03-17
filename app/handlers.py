"""消息路由与处理：根据消息内容路由到对应的 Bot/Agent

支持自动 fallback：当主模型不可用时，按优先级尝试备用模型，
结合健康检测实现"永不掉线"。
"""

import logging

import httpx

from app.agents import AgentConfig, router as agent_router
from app.config import settings
from app.dingtalk import build_markdown_response, build_text_response
from app.health import tracker
from app.providers import registry as provider_registry

logger = logging.getLogger(__name__)


async def handle_message(data: dict) -> dict:
    """处理收到的钉钉消息。

    命令：
      /help      - 显示帮助
      /status    - 查看服务状态
      /bots      - 列出所有已配置的 Bot 及其模型
      其他文本    - 根据关键词/前缀路由到对应 Bot
    """
    msg_type = data.get("msgtype", "")

    if msg_type == "text":
        text = data.get("text", {}).get("content", "").strip()
    else:
        return build_text_response(f"暂不支持 {msg_type} 类型的消息")

    sender = data.get("senderNick", "用户")

    # 系统命令
    if text.startswith("/help"):
        return _handle_help()
    if text.startswith("/status"):
        return _handle_status()
    if text.startswith("/bots") or text.startswith("/agents"):
        return _handle_bots()
    if text.startswith("/reload"):
        return _handle_reload()
    if text.startswith("/health"):
        return _handle_health()

    # 路由到对应 Bot
    agent, cleaned_text = agent_router.route(text)
    logger.info("消息路由到 Bot [%s] (model=%s): %s", agent.name, agent.model, cleaned_text[:50])
    return await _forward_to_agent(agent, cleaned_text, sender, data)


def _handle_help() -> dict:
    # 动态生成前缀命令列表
    prefix_lines = []
    for agent in agent_router.agents:
        if agent.prefix:
            prefix_lines.append(f"- `{agent.prefix} <消息>` - {agent.description}")

    help_text = (
        "## OpenClaw 钉钉助手\n\n"
        "**系统命令：**\n"
        "- `/help` - 显示此帮助\n"
        "- `/status` - 查看服务状态\n"
        "- `/bots` - 列出所有 Bot 及模型\n"
        "- `/health` - 查看模型健康状态\n"
        "- `/reload` - 热重载 agents.json 配置\n\n"
    )
    if prefix_lines:
        help_text += "**Bot 命令：**\n" + "\n".join(prefix_lines) + "\n\n"
    help_text += "直接发送文本会根据关键词自动路由到合适的 Bot。"

    return build_markdown_response("帮助", help_text)


def _handle_status() -> dict:
    bot_count = len(agent_router.agents)
    return build_text_response(
        f"服务运行中\n"
        f"已配置 {bot_count} 个 Bot\n"
        f"OpenClaw: {settings.openclaw_webhook_url}"
    )


def _handle_bots() -> dict:
    return build_markdown_response("Bot 列表", agent_router.list_agents_markdown())


def _handle_reload() -> dict:
    agent_count = agent_router.reload()
    provider_count = provider_registry.reload()
    return build_text_response(
        f"配置已重载: {agent_count} 个 Agent, {provider_count} 个供应商"
    )


def _handle_health() -> dict:
    statuses = tracker.all_status()
    if not statuses:
        return build_text_response("暂无模型调用记录")
    lines = ["## 模型健康状态\n"]
    for s in statuses:
        icon = "OK" if s["healthy"] else "DOWN"
        line = (
            f"- **{s['model']}** [{icon}] "
            f"成功:{s['total_successes']} 失败:{s['total_failures']}"
        )
        if s["cooldown_remaining"] > 0:
            line += f" (冷却剩余 {int(s['cooldown_remaining'])}s)"
        if s["last_error"]:
            line += f"\n  最后错误: {s['last_error']}"
        lines.append(line)
    return build_markdown_response("模型健康", "\n".join(lines))


async def _forward_to_agent(agent: AgentConfig, text: str, sender: str, raw_data: dict) -> dict:
    """将消息转发给指定 Bot，主模型失败时自动切换备用模型。

    流程：
    1. 获取该 Agent 所有可用模型（主 + fallback）
    2. 过滤掉健康检测标记为不可用的模型
    3. 按顺序尝试，成功即返回
    4. 全部失败则返回错误信息
    """
    models = agent.all_models()
    healthy_models = tracker.get_healthy_models(models)

    last_error = ""
    used_fallback = False

    async with httpx.AsyncClient(timeout=60.0) as client:
        for i, model in enumerate(healthy_models):
            payload = {
                "message": text,
                "sender": sender,
                "source": "dingtalk",
                "agent": agent.name,
                "model": model,
                "raw": raw_data,
            }

            # 附带供应商凭证，让 OpenClaw 知道用哪个 API
            provider_info = provider_registry.lookup(model)
            if provider_info:
                payload["api_base"] = provider_info[0]
                payload["api_key"] = provider_info[1]

            try:
                resp = await client.post(agent.endpoint, json=payload)
                resp.raise_for_status()
                result = resp.json()
                reply = result.get("reply", result.get("text", "处理完成"))

                tracker.record_success(model)

                prefix = f"[{agent.name}]"
                if used_fallback:
                    prefix = f"[{agent.name}|备用:{model}]"
                return build_text_response(f"{prefix} {reply}")

            except (httpx.ConnectError, httpx.HTTPStatusError, httpx.TimeoutException) as e:
                error_msg = _format_error(e)
                tracker.record_failure(model, error_msg)
                last_error = error_msg
                used_fallback = True
                logger.warning(
                    "Bot [%s] 模型 [%s] 失败 (%d/%d): %s",
                    agent.name, model, i + 1, len(healthy_models), error_msg,
                )
                continue
            except Exception as e:
                tracker.record_failure(model, str(e))
                last_error = str(e)
                used_fallback = True
                logger.warning(
                    "Bot [%s] 模型 [%s] 异常 (%d/%d): %s",
                    agent.name, model, i + 1, len(healthy_models), e,
                )
                continue

    # 所有模型都失败了
    return build_text_response(
        f"Bot [{agent.name}] 所有模型均不可用（共尝试 {len(healthy_models)} 个），"
        f"最后错误: {last_error}"
    )


def _format_error(e: Exception) -> str:
    if isinstance(e, httpx.ConnectError):
        return "连接失败"
    if isinstance(e, httpx.TimeoutException):
        return "请求超时"
    if isinstance(e, httpx.HTTPStatusError):
        return f"HTTP {e.response.status_code}"
    return str(e)
