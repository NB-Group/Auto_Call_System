import pytest
from aiohttp import web

from server.app import create_app
from server.auth import create_session, hash_password


@pytest.fixture()
def admin_db(tmp_path):
    from server.db import connect, init_db
    conn = connect(tmp_path / "call.db")
    init_db(conn)
    conn.execute(
        "INSERT INTO teachers(username,password_hash,role,display_name) "
        "VALUES ('admin',?,'admin','管理员')", (hash_password("adminpw"),))
    conn.commit()
    return conn


@pytest.fixture()
async def client(aiohttp_client, admin_db, tmp_path):
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<html>app</html>", encoding="utf-8")
    app = create_app(tmp_path / "call.db", static)
    c = await aiohttp_client(app)
    c.db = admin_db
    yield c
    admin_db.close()


async def test_bootstrap_status(client):
    r = await client.get("/api/bootstrap/status")
    body = await r.json()
    assert body["needs_admin"] is False and body["version"]


async def test_bootstrap_admin_only_once(tmp_path, aiohttp_client):
    from server.db import connect, init_db
    conn = connect(tmp_path / "fresh.db")
    init_db(conn)
    app = create_app(tmp_path / "fresh.db")
    c = await aiohttp_client(app)
    r = await c.post("/api/bootstrap/admin", json={
        "username": "admin", "password": "pw123456",
        "display_name": "管理员"})
    assert r.status == 201
    r = await c.post("/api/bootstrap/admin", json={
        "username": "x", "password": "pw123456"})
    assert r.status == 409


async def test_admin_flow(client):
    token = create_session(client.db, 1)
    h = {"Authorization": f"Bearer {token}"}

    r = await client.post("/api/admin/teachers", json={
        "username": "zheng", "password": "pw123456",
        "display_name": "郑老师", "office": "203办公室"}, headers=h)
    assert r.status == 201
    tid = (await r.json())["id"]

    r = await client.put(f"/api/admin/teachers/{tid}", json={"disabled": 1},
                         headers=h)
    assert r.status == 200

    r = await client.post("/api/admin/classes", json={"name": "高二(3)班"},
                          headers=h)
    cid = (await r.json())["id"]
    r = await client.post(f"/api/admin/classes/{cid}/students", json={
        "text": "梁皓文\n王小雨,王小雨 李涵文"}, headers=h)
    body = await r.json()
    assert body["imported"] == 3 and body["skipped"] == ["王小雨"]

    r = await client.get("/api/admin/calls?date=2026-09-01", headers=h)
    assert (await r.json())["calls"] == []

    r = await client.get("/api/server/info", headers=h)
    assert (await r.json())["displays"] == 0


async def test_history_injection_is_parameterized(client):
    token = create_session(client.db, 1)
    h = {"Authorization": f"Bearer {token}"}
    db = client.db
    db.execute("INSERT INTO classes(name) VALUES ('高二(1)班')")
    db.execute("INSERT INTO students(class_id,name) VALUES (1,'测试学生')")
    for day in ("2026-08-30", "2026-08-31"):  # 两条不同回溯日期的呼叫
        db.execute(
            "INSERT INTO calls(student_id,class_id,teacher_id,created_at) "
            "VALUES (1,1,1,?)", (f"{day} 09:00:00",))
    db.commit()

    r = await client.get("/api/admin/calls", params={"date": "2026-08-31"},
                         headers=h)
    assert r.status == 200
    assert len((await r.json())["calls"]) == 1

    # 注入串按普通参数绑定 → 匹配不到任何日期 → 空表。
    # f-string 版会拼成 WHERE date(c.created_at)='' OR '1'='1' 返回全部行,
    # 此断言在未参数化版本上必失败。
    r = await client.get("/api/admin/calls", params={"date": "' OR '1'='1"},
                         headers=h)
    assert r.status == 200
    assert (await r.json())["calls"] == []


async def test_teacher_cannot_admin(client):
    token = create_session(client.db, 1)  # admin 自己
    client.db.execute(
        "INSERT INTO teachers(username,password_hash) VALUES ('t',?)",
        (hash_password("pw"),))
    client.db.commit()
    from server.auth import create_session as cs
    t_token = cs(client.db, 2)
    r = await client.get("/api/admin/teachers",
                         headers={"Authorization": f"Bearer {t_token}"})
    assert r.status == 403


async def test_static_index_served(client):
    r = await client.get("/")
    assert r.status == 200
    assert "app" in await r.text()
