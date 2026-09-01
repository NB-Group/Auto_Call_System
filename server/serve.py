"""服务器模式:线程内运行 aiohttp(供 pywebview 壳调用)+ 控制台入口。"""
import asyncio
import threading

from aiohttp import web

from server.broadcast import Broadcaster

DEFAULT_PORT = 8800


def default_db_path():
    """data/call.db,锚定 base_dir:frozen 在 exe 旁,源码运行在 CWD(I7)。"""
    from app.config import base_dir  # 函数内导入,避免 server↔app 顶层环
    return base_dir() / "data" / "call.db"


def start_server(host="0.0.0.0", port=DEFAULT_PORT, db_path=None,
                 static_dir=None):
    """在后台线程跑 HTTP 服务,返回 (runner, thread, bcast, loop)。

    App(含 SQLite 连接)必须在线程内创建:sqlite3 默认
    check_same_thread=True,主线程建的连接被服务线程使用会
    ProgrammingError(所有请求 500)。Event 同步保证返回时端口已绑定,
    线程内启动失败(如端口占用)在主线程抛出。

    同时启动 UDP 广播(Broadcaster),供客户端 find_server() 零配置发现。
    """
    if db_path is None:
        db_path = default_db_path()
    loop = asyncio.new_event_loop()
    ready = threading.Event()
    box: dict = {}

    def run():
        asyncio.set_event_loop(loop)
        runner = None
        try:
            from server.app import create_app
            app = create_app(db_path, static_dir)
            runner = web.AppRunner(app)
            loop.run_until_complete(runner.setup())
            site = web.TCPSite(runner, host, port)
            loop.run_until_complete(site.start())
        except Exception as exc:  # 启动失败回传主线程
            if runner is not None:  # setup 已成功而 site.start 失败:回收 runner
                try:
                    loop.run_until_complete(runner.cleanup())
                except Exception:
                    pass
            box["error"] = exc
        else:
            box["runner"] = runner
        finally:
            ready.set()
        if "runner" in box:
            loop.run_forever()

    t = threading.Thread(target=run, daemon=True)
    t.start()
    ready.wait(timeout=10)
    if "error" in box:
        raise box["error"]
    if "runner" not in box:
        raise TimeoutError("start_server: server thread not ready in 10s")
    from app import __version__
    bcast = Broadcaster(port, __version__)
    bcast.start()
    return box["runner"], t, bcast, loop


def stop_server(runner, loop, bcast):
    """停服:先停 UDP 广播,再 runner.cleanup() 释放端口,最后停事件循环。

    仅 loop.stop() 不关监听 socket,端口保持占用,同进程内无法重绑
    (实证:第二次 start_server 同端口 EADDRINUSE)。

    幂等:重复调用安全。loop 已停(如双停)时仍尝试 cleanup 释放端口;
    loop 已关闭则 run_coroutine_threadsafe 抛 RuntimeError,忽略。
    """
    bcast.stop()
    async def _shutdown():
        await runner.cleanup()
        loop.stop()

    if loop.is_running():
        loop.call_soon_threadsafe(lambda: asyncio.ensure_future(_shutdown()))
    else:
        try:
            asyncio.run_coroutine_threadsafe(runner.cleanup(), loop)
        except RuntimeError:  # loop 已关闭,无可清理
            pass


if __name__ == "__main__":
    import signal
    from server.app import create_app
    web.run_app(create_app(default_db_path()), host="0.0.0.0",
                port=DEFAULT_PORT, handle_signals=True)
