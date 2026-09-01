import pytest
from aiohttp import web

from server.auth import (auth_middleware, create_session, hash_password,
                         resolve_token, verify_password)
from server.db import connect, init_db


@pytest.fixture()
def db(tmp_path):
    conn = connect(tmp_path / "call.db")
    init_db(conn)
    conn.execute(
        "INSERT INTO teachers(username,password_hash,role,display_name) "
        "VALUES (?,?, 'teacher', '郑老师')",
        ("zheng", hash_password("pw123456")))
    conn.commit()
    yield conn
    conn.close()


def test_password_roundtrip():
    h = hash_password("pw123456")
    assert verify_password("pw123456", h)
    assert not verify_password("wrong", h)


def test_session_roundtrip(db):
    token = create_session(db, 1)
    row = resolve_token(db, token)
    assert row["username"] == "zheng"
    assert resolve_token(db, "nope") is None


async def test_middleware_protects_api(aiohttp_client, db):
    app = web.Application(middlewares=[auth_middleware])
    app["db"] = db

    async def secret(request):
        return web.json_response({"role": request["teacher"]["role"]})

    app.router.add_get("/api/me", secret)
    client = await aiohttp_client(app)

    r = await client.get("/api/me")
    assert r.status == 401

    token = create_session(db, 1)
    r = await client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status == 200
    assert (await r.json())["role"] == "teacher"


async def test_middleware_allows_public(aiohttp_client, db):
    app = web.Application(middlewares=[auth_middleware])
    app["db"] = db

    async def pub(request):
        return web.json_response({})

    app.router.add_get("/api/classes", pub)
    client = await aiohttp_client(app)
    assert (await client.get("/api/classes")).status == 200
