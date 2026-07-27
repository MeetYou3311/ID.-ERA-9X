#!/usr/bin/env bash
# 在本机长期运行「文案分享站」并通过 Cloudflare 隧道暴露到公网（无需任何云平台账号）
# 前置：
#   1) 安装 Python 3.11+
#   2) 安装 cloudflared：https://developers.cloudflare.com/cloudflared/get-started/
#      （Mac: brew install cloudflared | Windows: winget install Cloudflare.cloudflared）
set -e
cd "$(dirname "$0")"

# 1) 安装依赖并后台启动应用
pip3 install -r requirements.txt
FLASK_DEBUG=0 python3 app.py &
APP_PID=$!
echo "应用已启动 (PID=$APP_PID)，监听 http://localhost:5000"

# 2) 建立公网隧道（每次重启 URL 会变；想要固定 URL 见 README）
echo "正在建立公网隧道，请勿关闭此窗口…"
cloudflared tunnel --url http://localhost:5000 || true

# 退出时顺手关掉应用
kill $APP_PID 2>/dev/null || true
