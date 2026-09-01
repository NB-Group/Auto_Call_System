import json

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient

from server.auth import create_session, hash_password
from server.db import connect, init_db
from server.ws import ws_handler


@pytest.fixture()
async def app(aiohttp_client, tmp_path):
    conn = connect(tmp_path / "call.db")
    init_db(conn)
    conn.execute(
        "INSERT INTO teachers(username,password_hash,role,display_name) "
        "VALUES ('zheng',?,'teacher','郑老师')", (hash_password("pw"),))
    conn.commit()
    app = web.Application()
    app["db"] = conn
    app["ws_clients"] = {}
    app.router.add_get("/ws", ws_handler)
    client = await aiohttp_client(app)
    client.db = conn
    yield client
    conn.close()


CALL = {"id": 1, "student_id": 1, "class_id": 2, "teacher_id": 1,
        "message": "", "announce": "请梁皓文同学到郑老师203办公室",
        "created_at": "2026-09-01 10:00:00", "student_name": "梁皓文",
        "class_name": "高二(3)班", "teacher_name": "郑老师",
        "office": "203办公室"}


async def _recv(ws, timeout=2.0):
    return json.loads((await ws.receive(timeout=timeout)).data)


async def test_anonymous_display_subscribes(app: TestClient):
    ws = await app.ws_connect("/ws")
    await ws.send_json({"type": "subscribe", "class_id": 2})
    assert (await _recv(ws))["type"] == "hello"


async def test_bad_token_closed(app: TestClient):
    ws = await app.ws_connect("/ws?token=nope")
    msg = await ws.receive(timeout=2.0)
    assert msg.type.name == "CLOSE"
    assert ws.close_code == 4401


async def test_broadcast_routes_by_class(app: TestClient):
    from server.ws import broadcast_call
    a = await app.ws_connect("/ws")
    await a.send_json({"type": "subscribe", "class_id": 2})
    await _recv(a)
    b = await app.ws_connect("/ws")
    await b.send_json({"type": "subscribe", "class_id": 3})
    await _recv(b)

    await broadcast_call(app.app, dict(CALL))
    got = await _recv(a)
    assert got["type"] == "call" and got["call"]["student_name"] == "梁皓文"
    with pytest.raises(Exception):
        await _recv(b, timeout=0.5)   # b 订阅 3 班,收不到


async def test_retract(app: TestClient):
    from server.ws import broadcast_call, broadcast_retract
    ws = await app.ws_connect("/ws")
    await ws.send_json({"type": "subscribe", "class_id": 2})
    await _recv(ws)
    await broadcast_call(app.app, dict(CALL))
    await _recv(ws)
    await broadcast_retract(app.app, 1)
    assert (await _recv(ws)) == {"type": "retract", "call_id": 1}
