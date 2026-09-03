"""应用组装:中间件、全部路由、静态托管。"""
from pathlib import Path

from aiohttp import web

from server import api, ws
from server.auth import auth_middleware, create_session, hash_password
from server.db import connect, init_db
from server.search import pinyin_of, search_students

STATIC_FALLBACK = Path(__file__).parent / "static"


def create_app(db_path, static_dir=None) -> web.Application:
    conn = connect(db_path)
    init_db(conn)
    app = web.Application(middlewares=[auth_middleware])
    app["db"] = conn
    app["ws_clients"] = {}
    app["ws_broadcast"] = lambda call: ws.broadcast_call(app, call)
    app["ws_retract"] = lambda cid: ws.broadcast_retract(app, cid)
    api.setup_business_routes(app.router)
    _setup_auth_routes(app.router)
    _setup_public_routes(app.router)
    _setup_admin_routes(app.router)
    app.router.add_get("/ws", ws.ws_handler)

    static = Path(static_dir) if static_dir else STATIC_FALLBACK
    if static.is_dir():
        app.router.add_get("/", _index(static))
        if (static / "assets").is_dir():
            app.router.add_static("/assets/", static / "assets")
    return app


def _index(static: Path):
    async def handler(request):
        # index.html 禁缓存:前端热更新后客户端立刻拿新版本;
        # /assets/ 文件名带哈希,可长缓存。
        return web.FileResponse(static / "index.html",
                                headers={"Cache-Control": "no-store"})
    return handler


def _setup_auth_routes(router):
    from server.auth import resolve_token, verify_password

    async def login(request):
        body = await request.json()
        row = request.app["db"].execute(
            "SELECT * FROM teachers WHERE username=? AND disabled=0",
            (body.get("username", ""),)).fetchone()
        if row is None or not verify_password(body.get("password", ""),
                                              row["password_hash"]):
            return web.json_response({"error": "unauthorized"}, status=401)
        token = create_session(request.app["db"], row["id"])
        return web.json_response({
            "token": token, "role": row["role"],
            "display_name": row["display_name"], "office": row["office"]})

    router.add_post("/api/auth/login", login)


def _setup_public_routes(router):
    from app import __version__
    from server.auth import create_session, hash_password

    async def bootstrap_status(request):
        n = request.app["db"].execute(
            "SELECT COUNT(*) FROM teachers WHERE role='admin'").fetchone()[0]
        return web.json_response({"needs_admin": n == 0,
                                  "version": __version__})

    async def bootstrap_admin(request):
        db = request.app["db"]
        n = db.execute(
            "SELECT COUNT(*) FROM teachers WHERE role='admin'").fetchone()[0]
        if n > 0:
            return web.json_response({"error": "conflict"}, status=409)
        body = await request.json()
        username, password = body.get("username", ""), body.get("password", "")
        if not username or len(password) < 6:
            return web.json_response({"error": "bad_request"}, status=400)
        cur = db.execute(
            "INSERT INTO teachers(username,password_hash,role,display_name) "
            "VALUES (?,?,'admin',?)",
            (username, hash_password(password),
             body.get("display_name") or "管理员"))
        db.commit()
        token = create_session(db, cur.lastrowid)
        return web.json_response({"token": token, "role": "admin",
                                  "display_name": "管理员", "office": ""},
                                 status=201)

    async def list_classes(request):
        rows = request.app["db"].execute(
            "SELECT id,name,ord FROM classes ORDER BY ord,name").fetchall()
        return web.json_response([dict(r) for r in rows])

    router.add_get("/api/bootstrap/status", bootstrap_status)
    router.add_post("/api/bootstrap/admin", bootstrap_admin)
    router.add_get("/api/classes", list_classes)


def _setup_admin_routes(router):
    from server.auth import hash_password, require_admin
    from server.ws import displays_count

    def admin_guard(request):
        return require_admin(request)

    async def list_teachers(request):
        if (r := admin_guard(request)):
            return r
        rows = request.app["db"].execute(
            "SELECT id,username,role,display_name,office,disabled,created_at "
            "FROM teachers ORDER BY id").fetchall()
        return web.json_response([dict(r) for r in rows])

    async def add_teacher(request):
        if (r := admin_guard(request)):
            return r
        body = await request.json()
        if not body.get("username") or len(body.get("password", "")) < 6:
            return web.json_response({"error": "bad_request"}, status=400)
        if body.get("role", "teacher") not in ("teacher", "admin"):
            return web.json_response({"error": "bad_request"}, status=400)
        try:
            cur = request.app["db"].execute(
                "INSERT INTO teachers(username,password_hash,role,"
                "display_name,office) VALUES (?,?,?,?,?)",
                (body["username"], hash_password(body["password"]),
                 body.get("role", "teacher"),
                 body.get("display_name", ""), body.get("office", "")))
            request.app["db"].commit()
        except Exception:
            return web.json_response({"error": "conflict"}, status=409)
        return web.json_response({"id": cur.lastrowid}, status=201)

    async def update_teacher(request):
        if (r := admin_guard(request)):
            return r
        body = await request.json()
        tid = int(request.match_info["id"])
        # 停用自己 → 唯一管理员锁死自己之外无人解锁,拒绝(I8)。
        if body.get("disabled") and tid == request["teacher"]["id"]:
            return web.json_response({"error": "bad_request"}, status=400)
        sets, vals = [], []
        for k in ("display_name", "office", "disabled"):
            if k in body:
                sets.append(f"{k}=?")
                vals.append(body[k])
        if body.get("password"):
            sets.append("password_hash=?")
            vals.append(hash_password(body["password"]))
        if not sets:
            return web.json_response({"error": "bad_request"}, status=400)
        vals.append(tid)
        request.app["db"].execute(
            f"UPDATE teachers SET {', '.join(sets)} WHERE id=?", vals)
        request.app["db"].commit()
        return web.json_response({"ok": True})

    async def delete_teacher(request):
        if (r := admin_guard(request)):
            return r
        tid = int(request.match_info["id"])
        if tid == request["teacher"]["id"]:
            return web.json_response({"error": "bad_request"}, status=400)
        request.app["db"].execute("DELETE FROM teachers WHERE id=?", (tid,))
        request.app["db"].commit()
        return web.json_response({"ok": True})

    async def add_class(request):
        if (r := admin_guard(request)):
            return r
        body = await request.json()
        name = (body.get("name") or "").strip()
        if not name:
            return web.json_response({"error": "bad_request"}, status=400)
        try:
            cur = request.app["db"].execute(
                "INSERT INTO classes(name,ord) VALUES (?,?)",
                (name, body.get("ord", 0)))
            request.app["db"].commit()
        except Exception:
            return web.json_response({"error": "conflict"}, status=409)
        return web.json_response({"id": cur.lastrowid, "name": name,
                                  "ord": body.get("ord", 0)}, status=201)

    async def delete_class(request):
        if (r := admin_guard(request)):
            return r
        request.app["db"].execute("DELETE FROM classes WHERE id=?",
                                  (int(request.match_info["id"]),))
        request.app["db"].commit()
        return web.json_response({"ok": True})

    async def import_students(request):
        if (r := admin_guard(request)):
            return r
        db = request.app["db"]
        cid = int(request.match_info["id"])
        if db.execute("SELECT 1 FROM classes WHERE id=?", (cid,)).fetchone() is None:
            return web.json_response({"error": "not_found"}, status=404)
        text = (await request.json()).get("text", "")
        imported, skipped = 0, []
        # 分隔符:换行 + ASCII/全角逗号 + 顿号(中文名单粘贴最常见三种)。
        for line in (text.replace(",", "\n").replace("，", "\n")
                   .replace("、", "\n").splitlines()):
            line = line.strip()
            if not line:
                continue
            # 契约(CONTRACTS):行/逗号分隔,可选尾缀学号(ASCII,如"李涵文 0305");
            # 其余空白分词均为姓名(如"王小雨 李涵文"=两名学生)。
            # 注:brief 原稿取 parts[1] 为学号,与自身测试(须拆为两条)冲突,按契约修正。
            entries: list[tuple[str, str]] = []
            for tok in line.split():
                if entries and tok.isascii():
                    entries[-1] = (entries[-1][0], tok)
                else:
                    entries.append((tok, ""))
            for name, no in entries:
                dup = db.execute(
                    "SELECT 1 FROM students WHERE class_id=? AND name=? "
                    "AND student_no=?", (cid, name, no)).fetchone()
                if dup:
                    skipped.append(name)
                    continue
                full, ini = pinyin_of(name)
                db.execute(
                    "INSERT INTO students(class_id,name,student_no,pinyin_full,"
                    "pinyin_initials) VALUES (?,?,?,?,?)", (cid, name, no, full, ini))
                imported += 1
        db.commit()
        return web.json_response({"imported": imported, "skipped": skipped},
                                 status=201)

    async def history(request):
        if (r := admin_guard(request)):
            return r
        date = request.query.get("date")
        rows = request.app["db"].execute(
            "SELECT id FROM calls c "
            "WHERE (? IS NULL OR date(c.created_at)=?) ORDER BY id DESC",
            (date, date)).fetchall()
        from server.api import call_row
        return web.json_response(
            {"calls": [call_row(request.app["db"], r["id"]) for r in rows]})

    async def server_info(request):
        if (r := admin_guard(request)):
            return r
        from app import __version__
        return web.json_response({"version": __version__,
                                  "displays": displays_count(request.app)})

    router.add_get("/api/admin/teachers", list_teachers)
    router.add_post("/api/admin/teachers", add_teacher)
    router.add_put("/api/admin/teachers/{id}", update_teacher)
    router.add_delete("/api/admin/teachers/{id}", delete_teacher)
    router.add_post("/api/admin/classes", add_class)
    router.add_delete("/api/admin/classes/{id}", delete_class)
    router.add_post("/api/admin/classes/{id}/students", import_students)
    router.add_get("/api/admin/calls", history)
    router.add_get("/api/server/info", server_info)
