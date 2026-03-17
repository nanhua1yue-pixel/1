# DingTalk-OpenClaw Webhook

钉钉 + OpenClaw 多 Agent 协作的 Webhook 处理器。接收钉钉机器人消息，转发给 OpenClaw 多 Agent 系统处理。

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的钉钉 App Secret 和 OpenClaw 地址

# 3. 启动服务
python -m app.main
```

服务启动后监听 `http://0.0.0.0:8000`。

## 钉钉配置

在钉钉开放平台创建机器人后，将回调地址设为：

```
http://你的服务器地址:8000/webhook/dingtalk
```

## 支持的命令

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助信息 |
| `/status` | 查看服务状态 |
| `/agents` | 列出 OpenClaw Agent |
| `/health` | 查看模型健康状态 |
| `/reload` | 热重载 agents.json 配置 |
| 其他文本 | 转发给 OpenClaw 处理 |

## 架构

```
钉钉群消息 → 钉钉回调 → 本服务(签名验证+路由) → OpenClaw Gateway → 多Agent处理 → 回复
                                                       ↓ 主模型失败
                                                   自动切换备用模型重试
```

## 高可用机制

每个 Agent 支持配置 `fallback_models` 备用模型列表。当主模型不可用时：

1. 自动切换到下一个备用模型重试
2. 健康检测记录连续失败次数，标记不健康模型
3. 不健康模型进入冷却期（120s），冷却后自动恢复探测
4. 所有模型都不可用时强制重试，避免完全拒绝服务

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 服务健康检查 |
| `/api/models/health` | GET | 模型健康状态 |
| `/api/agents` | GET | Agent 列表 |
| `/api/reload` | POST | 热重载配置 |

## 项目结构

```
app/
├── main.py       # FastAPI 入口，Webhook 和 API 端点
├── config.py     # 环境变量配置
├── dingtalk.py   # 签名验证、消息构建
├── handlers.py   # 消息路由与处理逻辑（含 fallback 重试）
├── health.py     # 模型健康状态追踪
└── agents.py     # Agent 配置、路由、热重载
```
