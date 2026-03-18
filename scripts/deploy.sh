#!/bin/bash
# 采购补货决策系统 - 宝塔面板部署脚本
# 使用方式: bash scripts/deploy.sh

set -e

echo "===== 采购补货决策系统 部署脚本 ====="

# 1. 项目目录
PROJECT_DIR="/www/wwwroot/purchase-decision"
echo "[1/6] 创建项目目录..."
mkdir -p $PROJECT_DIR
cp -r ./* $PROJECT_DIR/
cd $PROJECT_DIR

# 2. Python虚拟环境
echo "[2/6] 创建Python虚拟环境..."
python3 -m venv venv
source venv/bin/activate

# 3. 安装依赖
echo "[3/6] 安装依赖..."
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 4. 环境变量
echo "[4/6] 配置环境变量..."
cat > .env << 'EOF'
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=purchase_system
DB_PASSWORD=PurchaseSystem@2026
DB_NAME=purchase_decision
WDT_SID=yhcs03
WDT_APPKEY=yhcs03-otb
WDT_APPSECRET=3f14833b7e0cab5e12093d8683a415eb:13919219130536059064aa5236ea922c
APP_PORT=5000
FLASK_DEBUG=False
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
EOF

# 5. 初始化数据库
echo "[5/6] 初始化数据库..."
mysql -uroot -p"Ppp123876/" < scripts/init_db.sql 2>/dev/null || echo "数据库可能已存在，跳过"

# 加载环境变量并初始化表结构
set -a && source .env && set +a
python3 -c "
from backend.app import create_app
app = create_app()
print('数据库表创建成功！')
"

# 6. Gunicorn配置
echo "[6/6] 配置Gunicorn..."
cat > gunicorn_config.py << 'EOF'
bind = '0.0.0.0:5000'
workers = 2
worker_class = 'sync'
timeout = 120
accesslog = '/www/wwwlogs/purchase-decision-access.log'
errorlog = '/www/wwwlogs/purchase-decision-error.log'
loglevel = 'info'
EOF

# Systemd服务
cat > /etc/systemd/system/purchase-decision.service << EOF
[Unit]
Description=Purchase Decision System
After=network.target mysql.service

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$PROJECT_DIR/venv/bin/gunicorn -c gunicorn_config.py backend.app:create_app()
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable purchase-decision
systemctl start purchase-decision

echo ""
echo "===== 部署完成！====="
echo "系统地址: http://118.89.58.101:5000"
echo ""
echo "宝塔面板Nginx反向代理配置（可选）:"
echo "  在宝塔面板-网站-添加站点后，设置反向代理:"
echo "  代理目标: http://127.0.0.1:5000"
echo ""
echo "管理命令:"
echo "  启动: systemctl start purchase-decision"
echo "  停止: systemctl stop purchase-decision"
echo "  重启: systemctl restart purchase-decision"
echo "  日志: journalctl -u purchase-decision -f"
