"""消息路由与处理：根据消息内容路由到对应的 Bot/Agent"""

import logging

import httpx

from app.agents import router as agent_router
from app.config import settings
from app.dingtalk import build_markdown_response, build_text_response

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
        "- `/bots` - 列出所有 Bot 及模型\n\n"
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


async def _forward_to_agent(agent, text: str, sender: str, raw_data: dict) -> dict:
    """将消息转发给指定 Bot 的端点处理"""
    payload = {
        "message": text,
        "sender": sender,
        "source": "dingtalk",
        "agent": agent.name,
        "model": agent.model,
        "raw": raw_data,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(agent.endpoint, json=payload)
            resp.raise_for_status()
            result = resp.json()
            reply = result.get("reply", result.get("text", "处理完成"))
            return build_text_response(f"[{agent.name}] {reply}")
    except httpx.ConnectError:
        return build_text_response(
            f"无法连接到 Bot [{agent.name}] ({agent.endpoint})，请确认服务已启动。"
        )
    except httpx.HTTPStatusError as e:
        return build_text_response(
            f"Bot [{agent.name}] 返回错误: {e.response.status_code}"
        )
    except Exception as e:
        return build_text_response(f"Bot [{agent.name}] 处理出错: {e}")
