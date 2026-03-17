"""钉钉 OpenClaw Webhook 处理器

接收钉钉机器人的回调消息，验证签名后转发给 OpenClaw 多 Agent 系统处理。
"""

from fastapi import FastAPI, Header, HTTPException, Request

from app.agents import router as agent_router
from app.config import settings
from app.dingtalk import verify_signature
from app.handlers import handle_message
from app.health import tracker

app = FastAPI(title="DingTalk-OpenClaw Webhook", version="0.2.0")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/models/health")
async def models_health():
    """查看所有模型的健康状态"""
    return {"models": tracker.all_status()}


@app.get("/api/agents")
async def list_agents():
    """列出所有 Agent 配置"""
    return {"agents": [a.to_dict() for a in agent_router.agents]}


@app.post("/api/reload")
async def reload_agents():
    """热重载 agents.json"""
    count = agent_router.reload()
    return {"status": "ok", "agent_count": count}


@app.post("/webhook/dingtalk")
async def dingtalk_webhook(
    request: Request,
    timestamp: str = Header(None, alias="timestamp"),
    sign: str = Header(None, alias="sign"),
):
    """钉钉机器人回调入口

    钉钉发送消息时会携带 timestamp 和 sign 用于安全校验。
    验证通过后将消息分发给 handler 处理。
    """
    # 签名验证
    if settings.dingtalk_app_secret and timestamp and sign:
        if not verify_signature(timestamp, sign):
            raise HTTPException(status_code=403, detail="签名验证失败")

    data = await request.json()
    response = await handle_message(data)
    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
