#!/usr/bin/env bash
# 启动 ID. ERA 9X软件升级分享文案站
set -e
cd "$(dirname "$0")"
pip3 install -r requirements.txt
exec python3 app.py
