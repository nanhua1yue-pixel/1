"""钉钉签名验证和消息处理工具"""

import base64
import hashlib
import hmac
import time

from app.config import settings


def verify_signature(timestamp: str, sign: str) -> bool:
    """验证钉钉回调签名，防止伪造请求。

    钉钉机器人在发送消息时会附带 timestamp 和 sign，
    服务端需要用 app_secret 重新计算签名并比对。
    """
    if not settings.dingtalk_app_secret:
        return True  # 未配置密钥时跳过验证（开发模式）

    # 签名过期检查：超过 1 小时的请求视为无效
    current_time = int(time.time() * 1000)
    if abs(current_time - int(timestamp)) > 3600000:
        return False

    string_to_sign = f"{timestamp}\n{settings.dingtalk_app_secret}"
    hmac_code = hmac.new(
        settings.dingtalk_app_secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    calculated_sign = base64.b64encode(hmac_code).decode("utf-8")
    return hmac.compare_digest(calculated_sign, sign)


def build_text_response(content: str) -> dict:
    """构建钉钉文本消息回复"""
    return {"msgtype": "text", "text": {"content": content}}


def build_markdown_response(title: str, text: str) -> dict:
    """构建钉钉 Markdown 消息回复"""
    return {"msgtype": "markdown", "markdown": {"title": title, "text": text}}
