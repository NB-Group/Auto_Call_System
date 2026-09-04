import sys
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


async def test_import_separators_fullwidth_and_dunhao(client):
    """终审 I3:半角/全角逗号 + 顿号都是分隔符;重复导入走 skipped。"""
    token = create_session(client.db, 1)
    h = {"Authorization": f"Bearer {token}"}
    r = await client.post("/api/admin/classes", json={"name": "高一(2)班"},
                          headers=h)
    cid = (await r.json())["id"]

    r = await client.post(f"/api/admin/classes/{cid}/students", json={
        "text": "王小雨，李涵文 0305,梁皓文、刘昊然"}, headers=h)
    body = await r.json()
    assert body["imported"] == 4 and body["skipped"] == []

    # 同一批再导 → 全部 skip(去重逻辑不受新分隔符影响)
    r = await client.post(f"/api/admin/classes/{cid}/students", json={
        "text": "王小雨，李涵文 0305,梁皓文、刘昊然"}, headers=h)
    body = await r.json()
    assert body["imported"] == 0 and sorted(body["skipped"]) == \
        sorted(["王小雨", "李涵文", "梁皓文", "刘昊然"])


async def test_admin_cannot_disable_self(client):
    """终审 I8:停用自己 → 400(单管理员锁死);停用他人 → 200。"""
    token = create_session(client.db, 1)  # admin 本人 id=1
    h = {"Authorization": f"Bearer {token}"}
    client.db.execute(
        "INSERT INTO teachers(username,password_hash) VALUES ('t2',?)",
        (hash_password("pw"),))
    client.db.commit()

    r = await client.put("/api/admin/teachers/1", json={"disabled": 1},
                         headers=h)
    assert r.status == 400
    r = await client.put("/api/admin/teachers/2", json={"disabled": 1},
                         headers=h)
    assert r.status == 200


async def test_add_teacher_rejects_bad_role(client):
    """终审 #13:role 只允许 teacher/admin。"""
    token = create_session(client.db, 1)
    h = {"Authorization": f"Bearer {token}"}
    r = await client.post("/api/admin/teachers", json={
        "username": "bad", "password": "pw123456", "role": "superroot"},
        headers=h)
    assert r.status == 400
    r = await client.post("/api/admin/teachers", json={
        "username": "ok", "password": "pw123456", "role": "admin"},
        headers=h)
    assert r.status == 201


async def test_static_index_served(client):
    r = await client.get("/")
    assert r.status == 200
    assert "app" in await r.text()


def test_is_frozen_source_vs_patched(monkeypatch):
    """frozen 判定:源码运行 False;sys.frozen 补 True 后 True。
    (真实 exe 命中 __compiled__ 分支,源码/测试侧只能走 sys.frozen 模拟。)
    """
    from app.config import is_frozen

    monkeypatch.delattr(sys, "frozen", raising=False)
    assert is_frozen() is False
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert is_frozen() is True


def test_base_dir_frozen_anchors_appdata(tmp_path, monkeypatch):
    """frozen 下锚 %APPDATA%/call-center(2026-09-04 实证:Nuitka 构建里
    sys.frozen 不存在,APPDATA 锚定从未生效,库落进 CWD\\data/System32)。"""
    from app import config as cfg

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(cfg, "_migrated", False)  # 迁移哨兵按例重置
    assert cfg.base_dir() == tmp_path / "call-center"


def test_migrate_legacy_moves_cwd_data_into_appdata(tmp_path, monkeypatch):
    """旧布局(exe 旁 data/)一次性迁入 %APPDATA%;新址已有 data 则不动。"""
    import shutil

    from app import config as cfg

    exe_dir = tmp_path / "deploy"
    exe_dir.mkdir()
    (exe_dir / "data").mkdir()
    (exe_dir / "data" / "call.db").write_bytes(b"olddb")
    root = tmp_path / "appdata" / "call-center"

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr(cfg, "_migrated", False)
    monkeypatch.setattr(cfg, "original_exe_path",
                        lambda: exe_dir / "call-center.exe")
    got = cfg.base_dir()
    assert got == root
    assert (root / "data" / "call.db").read_bytes() == b"olddb"   # 已迁入
    assert not (exe_dir / "data").exists()                         # 旧址清走

    # 新址已有 data:再迁(模拟另一部署位)不覆盖
    other = tmp_path / "deploy2"
    (other / "data").mkdir(parents=True)
    (other / "data" / "call.db").write_bytes(b"other")
    monkeypatch.setattr(cfg, "_migrated", False)
    monkeypatch.setattr(cfg, "original_exe_path",
                        lambda: other / "call-center.exe")
    cfg.base_dir()
    assert (root / "data" / "call.db").read_bytes() == b"olddb"    # 未被覆盖
