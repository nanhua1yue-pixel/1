"""消息路由与处理：根据消息内容分发到对应的处理函数"""

import httpx

from app.config import settings
from app.dingtalk import build_markdown_response, build_text_response


async def handle_message(data: dict) -> dict:
    """处理收到的钉钉消息，根据内容分发到不同处理器。

    支持的命令：
      /help      - 显示帮助信息
      /status    - 查看当前服务状态
      /agents    - 列出已配置的 OpenClaw Agent
      其他文本    - 转发给 OpenClaw 处理
    """
    msg_type = data.get("msgtype", "")
    text = ""

    if msg_type == "text":
        text = data.get("text", {}).get("content", "").strip()
    else:
        return build_text_response(f"暂不支持 {msg_type} 类型的消息")

    sender = data.get("senderNick", "用户")

    # 命令路由
    if text.startswith("/help"):
        return _handle_help()
    if text.startswith("/status"):
        return _handle_status()
    if text.startswith("/agents"):
        return _handle_agents()

    # 默认：转发给 OpenClaw
    return await _forward_to_openclaw(text, sender, data)


def _handle_help() -> dict:
    help_text = (
        "## OpenClaw 钉钉助手\n\n"
        "**可用命令：**\n"
        "- `/help` - 显示此帮助\n"
        "- `/status` - 查看服务状态\n"
        "- `/agents` - 列出 OpenClaw Agent\n"
        "- 直接发送文本 - 交给 OpenClaw 处理\n"
    )
    return build_markdown_response("帮助", help_text)


def _handle_status() -> dict:
    return build_text_response(
        "服务运行中 ✓\n"
        f"OpenClaw 地址: {settings.openclaw_webhook_url}"
    )


def _handle_agents() -> dict:
    return build_markdown_response(
        "Agent 列表",
        "## 已配置的 Agent\n\n"
        "通过 OpenClaw 管理你的多 Agent，"
        "详见 OpenClaw 控制台。",
    )


async def _forward_to_openclaw(text: str, sender: str, raw_data: dict) -> dict:
    """将消息转发给 OpenClaw Gateway 处理"""
    payload = {
        "message": text,
        "sender": sender,
        "source": "dingtalk",
        "raw": raw_data,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(settings.openclaw_webhook_url, json=payload)
            resp.raise_for_status()
            result = resp.json()
            reply = result.get("reply", result.get("text", "处理完成"))
            return build_text_response(reply)
    except httpx.ConnectError:
        return build_text_response(
            "⚠ 无法连接到 OpenClaw，请确认 OpenClaw 服务已启动。"
        )
    except httpx.HTTPStatusError as e:
        return build_text_response(f"⚠ OpenClaw 返回错误: {e.response.status_code}")
    except Exception as e:
        return build_text_response(f"⚠ 处理消息时出错: {e}")
