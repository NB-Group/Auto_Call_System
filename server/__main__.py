"""python -m server = 纯控制台服务器(无窗口)。"""
from aiohttp import web

from app import __version__
from server.app import create_app
from server.broadcast import Broadcaster
from server.serve import DEFAULT_PORT, default_db_path

if __name__ == "__main__":
    bcast = Broadcaster(DEFAULT_PORT, __version__)
    bcast.start()
    try:
        web.run_app(create_app(default_db_path()), host="0.0.0.0",
                    port=DEFAULT_PORT, handle_signals=True)
    finally:
        bcast.stop()
