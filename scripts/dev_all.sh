#!/usr/bin/env bash
# 一键 Linux 全链路联调:服务器(前台)+ vite dev + 各角色页面地址。
#
# 原设计(GUI 机器,见下)是服务器 + 前端 dev + 两个 pywebview 壳窗口:
#   TTS="${TTS:-espeak}" python -m app.main --role server  --dev &
#   TTS="${TTS:-espeak}" python -m app.main --role display --dev &
#   TTS="${TTS:-espeak}" python -m app.main --role teacher --dev &
# 本机无 GUI 工具链,pywebview 起窗即崩,故最小调整:服务器改用
# `python -m server` 纯控制台前台运行;teacher/display 不再开壳,
# 打印浏览器地址代替。有 GUI 的机器可按上面原设计自行开壳。
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  python -m venv .venv
  . .venv/bin/activate && pip install -r requirements-dev.txt
fi
. .venv/bin/activate

pnpm --dir frontend dev &
VITE_PID=$!
trap 'kill $VITE_PID 2>/dev/null || true' EXIT

sleep 1
# 用 localhost 而非 127.0.0.1:vite 在 Linux 上可能只绑 [::1](实测),
# 浏览器解析 localhost 会同时尝试 v4/v6,两种绑定都能打开。
echo "联调已启动:服务器 8800(前台)/ vite 5173"
echo "浏览器打开:"
echo "  建管理员+老师+名单: http://localhost:5173/#/server"
echo "  老师端(叫号):      http://localhost:5173/#/teacher"
echo "  显示端(教室大屏):  http://localhost:5173/#/display"
echo "Ctrl+C 全部退出"

# 服务器进程不说话,TTS 环境变量仅沿用原设计默认(espeak),无害。
# 不用 exec:保留 EXIT trap,服务器退出时一并收掉 vite。
TTS="${TTS:-espeak}" python -m server
