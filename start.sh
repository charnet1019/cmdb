#!/bin/bash

# CMDB 开发环境启动脚本
# 在 WSL 中直接启动前后端服务（不使用 Docker）

set -e

echo "🚀 启动 CMDB 开发环境..."

# 启动后端（带热重载）
echo "📌 启动后端服务：http://localhost:8000"
echo "📌 API 文档：http://localhost:8000/docs"
cd /home/tim/workspace/cmdb/backend && source venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 启动前端（在后台，仅当需要时取消注释）
# echo "📌 启动前端服务：http://localhost:5173"
# cd /home/tim/workspace/cmdb/frontend && npm run dev &

wait
