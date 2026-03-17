"""钉钉 OpenClaw Webhook 处理器

接收钉钉机器人的回调消息，验证签名后转发给 OpenClaw 多 Agent 系统处理。
"""

from fastapi import FastAPI, Header, HTTPException, Request

from app.config import settings
from app.dingtalk import verify_signature
from app.handlers import handle_message

app = FastAPI(title="DingTalk-OpenClaw Webhook", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok"}


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
