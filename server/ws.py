"""WebSocket:显示端订阅与叫号广播(CONTRACTS)。"""
import asyncio
import json

from aiohttp import web

from server.auth import resolve_token


async def ws_handler(request):
    token = request.query.get("token") or ""
    teacher = resolve_token(request.app["db"], token) if token else None
    if token and teacher is None:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        await ws.close(code=4401, message=b"bad token")
        return ws

    ws = web.WebSocketResponse(heartbeat=20)
    await ws.prepare(request)
    clients: dict = request.app["ws_clients"]
    clients[ws] = None
    try:
        async for msg in ws:
            data = json.loads(msg.data)
            if data.get("type") == "subscribe":
                clients[ws] = data.get("class_id")
                await ws.send_json({"type": "hello"})
    finally:
        clients.pop(ws, None)
    return ws


async def broadcast_call(app, call: dict) -> None:
    payload = json.dumps({"type": "call", "call": call}, ensure_ascii=False)
    targets = [ws for ws, cid in app["ws_clients"].items() if cid == call["class_id"]]
    await asyncio.gather(*(ws.send_str(payload) for ws in targets),
                         return_exceptions=True)


async def broadcast_retract(app, call_id: int) -> None:
    payload = json.dumps({"type": "retract", "call_id": call_id},
                         ensure_ascii=False)
    await asyncio.gather(*(ws.send_str(payload)
                           for ws in app["ws_clients"]),
                         return_exceptions=True)


def displays_count(app) -> int:
    return sum(1 for cid in app["ws_clients"].values() if cid is not None)
