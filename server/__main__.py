"""python -m server = 纯控制台服务器(无窗口)。"""
from aiohttp import web

from server.app import create_app
from server.serve import DEFAULT_PORT

if __name__ == "__main__":
    web.run_app(create_app("data/call.db"), host="0.0.0.0",
                port=DEFAULT_PORT, handle_signals=True)
