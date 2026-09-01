"""E2E 显示端 WS 客户端:模拟 DisplayView 的匿名订阅(无 token)并打印收到的每条消息。

用法(服务器需已启动):
    .venv/bin/python scripts/e2e_display_client.py --class 1 --duration 15
输出:每条收到的 WS 消息一行 JSON(hello / call / retract),退出码 0。
"""
import argparse
import asyncio
import json
import sys

import aiohttp

OK = 0


async def run(url: str, class_id: int, duration: float) -> int:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + duration
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(url) as ws:
            await ws.send_json({"type": "subscribe", "class_id": class_id})
            print(f"[subscribed class {class_id}]", flush=True)
            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    break
                try:
                    msg = await asyncio.wait_for(ws.receive(), remaining)
                except asyncio.TimeoutError:
                    break
                if msg.type == aiohttp.WSMsgType.TEXT:
                    print(json.dumps(json.loads(msg.data), ensure_ascii=False),
                          flush=True)
                elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING,
                                  aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    print(f"[closed: {msg.type.name}]", flush=True)
                    break
    return OK


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="ws://127.0.0.1:8800/ws")
    p.add_argument("--class", dest="class_id", type=int, default=1)
    p.add_argument("--duration", type=float, default=15.0)
    a = p.parse_args()
    sys.exit(asyncio.run(run(a.url, a.class_id, a.duration)))


if __name__ == "__main__":
    main()
