import pytest
from aiohttp import web
from pathlib import Path

from server.api import setup_business_routes
from server.auth import auth_middleware, create_session, hash_password
from server.db import connect, init_db
from server.search import pinyin_of


@pytest.fixture()
async def client(aiohttp_client, tmp_path):
    conn = connect(tmp_path / "call.db")
    init_db(conn)
    conn.execute(
        "INSERT INTO teachers(username,password_hash,display_name,office) "
        "VALUES ('zheng',?, '郑老师','203办公室')", (hash_password("pw"),))
    conn.execute("INSERT INTO classes(name) VALUES ('高二(3)班')")
    conn.execute(
        "INSERT INTO students(class_id,name,pinyin_full,pinyin_initials) "
        "VALUES (1,'梁皓文',?,?)", pinyin_of("梁皓文"))
    conn.execute(
        "INSERT INTO snippets(teacher_id,text,use_count) VALUES (1,'订正数学作业',3)")
    conn.commit()
    # auth_middleware 从 Bearer token 解析出 request["teacher"](与 app.py 生产组装一致)
    app = web.Application(middlewares=[auth_middleware])
    app["db"] = conn
    app["ws_broadcast"] = None
    setup_business_routes(app.router)
    c = await aiohttp_client(app)
    c.db = conn
    yield c
    conn.close()


async def auth(client):
    token = create_session(client.db, 1)
    return {"Authorization": f"Bearer {token}"}


async def test_call_composes_message_and_announce(client):
    r = await client.post("/api/calls", json={
        "student_id": 1, "snippet_ids": [1], "free_text": "带练习册"},
        headers=await auth(client))
    assert r.status == 201
    call = (await r.json())["call"]
    assert call["message"] == "订正数学作业,带练习册"
    assert call["announce"] == "请梁皓文同学到郑老师203办公室,订正数学作业,带练习册"
    assert call["student_name"] == "梁皓文"


async def test_call_minimal(client):
    r = await client.post("/api/calls", json={"student_id": 1},
                          headers=await auth(client))
    call = (await r.json())["call"]
    assert call["message"] == ""
    assert call["announce"] == "请梁皓文同学到郑老师203办公室"


async def test_call_bad_student(client):
    r = await client.post("/api/calls", json={"student_id": 999},
                          headers=await auth(client))
    assert r.status == 404


async def test_undo_window_and_ownership(client):
    headers = await auth(client)
    cid = (await (await client.post("/api/calls", json={"student_id": 1},
                                    headers=headers)).json())["call"]["id"]
    r = await client.delete(f"/api/calls/{cid}", headers=headers)
    assert r.status == 200

    conn2 = connect(client.db.execute(
        "PRAGMA database_list").fetchone()[2])
    conn2.execute("UPDATE calls SET created_at=datetime('now','localtime','-120 seconds') "
                  "WHERE id=?", (cid,))
    conn2.commit(); conn2.close()
    cid2 = (await (await client.post("/api/calls", json={"student_id": 1},
                                     headers=headers)).json())["call"]["id"]
    conn3 = connect(client.db.execute("PRAGMA database_list").fetchone()[2])
    conn3.execute("UPDATE calls SET created_at=datetime('now','localtime','-120 seconds') "
                  "WHERE id=?", (cid2,))
    conn3.commit(); conn3.close()
    r = await client.delete(f"/api/calls/{cid2}", headers=headers)
    assert r.status == 410


async def test_snippets_crud_and_usage_bump(client):
    headers = await auth(client)
    r = await client.get("/api/snippets", headers=headers)
    assert (await r.json())[0]["text"] == "订正数学作业"
    await client.post("/api/snippets", json={"text": "带上作图工具"},
                      headers=headers)
    await client.post("/api/calls", json={"student_id": 1, "snippet_ids": [1]},
                      headers=headers)
    rows = await (await client.get("/api/snippets", headers=headers)).json()
    assert rows[0]["use_count"] == 4
    r = await client.delete("/api/snippets/2", headers=headers)
    assert r.status == 200


async def test_me_update(client):
    headers = await auth(client)
    r = await client.put("/api/me", json={"office": "205办公室"},
                         headers=headers)
    assert (await r.json())["office"] == "205办公室"


async def test_call_response_matches_contract_schema(client):
    """契约一致性(spec §10):真实响应必须通过 schemas.json 的 call schema。"""
    import json as _json

    import jsonschema

    schemas = _json.loads(
        (Path(__file__).parent.parent / "docs" / "schemas.json")
        .read_text(encoding="utf-8"))
    r = await client.post("/api/calls", json={"student_id": 1},
                          headers=await auth(client))
    jsonschema.validate((await r.json())["call"], schemas["call"]["schema"])


async def test_add_snippet_returns_full_list(client):
    """契约:POST /api/snippets → 201 增后全表(形状同 GET /api/snippets)。"""
    r = await client.post("/api/snippets", json={"text": "带上圆规"},
                          headers=await auth(client))
    assert r.status == 201
    rows = await r.json()
    assert isinstance(rows, list)
    assert {row["text"] for row in rows} == {"订正数学作业", "带上圆规"}
    assert all({"id", "text", "use_count"} <= row.keys() for row in rows)


async def test_undo_non_integer_id_400(client):
    r = await client.delete("/api/calls/abc", headers=await auth(client))
    assert r.status == 400
    assert await r.json() == {"error": "bad_request"}


async def test_snippet_search_limit_hardening(client):
    """limit 非数字 → 400 bad_request(原 int() 直接 500);负数钳 1 不崩溃。"""
    headers = await auth(client)
    r = await client.get("/api/snippets/search?q=&limit=abc", headers=headers)
    assert r.status == 400
    assert await r.json() == {"error": "bad_request"}
    r = await client.get("/api/snippets/search?q=&limit=-5", headers=headers)
    assert r.status == 200
    assert len(await r.json()) <= 6


async def test_negative_limit_clamped_to_one(client):
    """负数 limit 下界钳 1(snippets/students 两路由对称),补行到 2 条使命中
    可区分:snippets 不钳时 SQLite 负 LIMIT = 无上限(返回 2 行);students
    不钳时 scored[:负数] 从尾部截断(2 行命中被切空返回 0 行)。"""
    headers = await auth(client)
    client.db.execute(
        "INSERT INTO snippets(teacher_id,text) VALUES (1,'带上练习册')")
    client.db.execute(
        "INSERT INTO students(class_id,name,pinyin_full,pinyin_initials) "
        "VALUES (1,'梁小明',?,?)", pinyin_of("梁小明"))
    client.db.commit()
    r = await client.get("/api/snippets/search?q=&limit=-5", headers=headers)
    assert r.status == 200
    assert len(await r.json()) == 1
    r = await client.get("/api/students/search?q=l&limit=-5", headers=headers)
    assert r.status == 200
    assert len(await r.json()) == 1


async def test_admin_undo_bypasses_window(client):
    """admin 撤销绕过 60s 窗口与归属检查(controllers 裁定)。"""
    headers = await auth(client)
    cid = (await (await client.post("/api/calls", json={"student_id": 1},
                                    headers=headers)).json())["call"]["id"]
    conn2 = connect(client.db.execute(
        "PRAGMA database_list").fetchone()[2])
    conn2.execute("UPDATE calls SET created_at=datetime('now','localtime','-120 seconds') "
                  "WHERE id=?", (cid,))
    conn2.commit(); conn2.close()
    client.db.execute(
        "INSERT INTO teachers(username,password_hash,display_name,office,role) "
        "VALUES ('boss',?, '王校长','101办公室','admin')", (hash_password("pw"),))
    client.db.commit()
    admin_headers = {"Authorization": f"Bearer {create_session(client.db, 2)}"}
    r = await client.delete(f"/api/calls/{cid}", headers=admin_headers)
    assert r.status == 200
    assert await r.json() == {"ok": True}
