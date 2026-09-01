"""业务端点:me / search / calls / snippets(CONTRACTS)。"""
from datetime import datetime, timedelta

from aiohttp import web

from server.search import search_students

RETRACT_WINDOW = timedelta(seconds=60)


def _json_error(code: str, status: int) -> web.Response:
    return web.json_response({"error": code}, status=status)


def render_template(template: str, student: str, teacher: str, office: str) -> str:
    return (template.replace("{student}", student)
            .replace("{teacher}", teacher)
            .replace("{office}", office))


def call_row(conn, call_id: int) -> dict | None:
    r = conn.execute(
        "SELECT c.*, s.name AS student_name, k.name AS class_name, "
        "       t.display_name AS teacher_name, t.office, t.default_template "
        "FROM calls c "
        "JOIN students s ON s.id=c.student_id "
        "JOIN classes  k ON k.id=c.class_id "
        "JOIN teachers t ON t.id=c.teacher_id "
        "WHERE c.id=?", (call_id,)).fetchone()
    if r is None:
        return None
    d = {k: r[k] for k in ("id", "student_id", "class_id", "teacher_id",
                           "message", "created_at", "retracted_at",
                           "student_name", "class_name", "teacher_name",
                           "office")}
    announce = render_template(r["default_template"], r["student_name"],
                               r["teacher_name"], r["office"])
    d["announce"] = announce + f",{d['message']}" if d["message"] else announce
    return d


def _today_where() -> str:
    return "date(c.created_at)=date('now','localtime')"


def setup_business_routes(router: web.UrlDispatcher) -> None:
    async def me(request):
        t = request["teacher"]
        return web.json_response({k: t[k] for k in (
            "id", "username", "role", "display_name", "office",
            "default_template")})

    async def update_me(request):
        t, db = request["teacher"], request.app["db"]
        body = await request.json()
        fields = {k: body[k] for k in ("display_name", "office",
                                       "default_template") if k in body}
        if not fields:
            return _json_error("bad_request", 400)
        sets = ", ".join(f"{k}=?" for k in fields)
        db.execute(f"UPDATE teachers SET {sets} WHERE id={t['id']}",
                   tuple(fields.values()))
        db.commit()
        fresh = db.execute("SELECT * FROM teachers WHERE id=?",
                           (t["id"],)).fetchone()
        return web.json_response({k: fresh[k] for k in (
            "id", "username", "role", "display_name", "office",
            "default_template")})

    async def logout(request):
        token = request.headers.get("Authorization", "")[7:]
        request.app["db"].execute("DELETE FROM sessions WHERE token=?",
                                  (token,))
        request.app["db"].commit()
        return web.json_response({"ok": True})

    async def search(request):
        q = request.query.get("q", "")
        limit = min(int(request.query.get("limit", 8)), 20)
        return web.json_response(
            search_students(request.app["db"], q, limit))

    async def create_call(request):
        t, db = request["teacher"], request.app["db"]
        body = await request.json()
        sid = body.get("student_id")
        if not isinstance(sid, int):
            return _json_error("bad_request", 400)
        student = db.execute("SELECT * FROM students WHERE id=?",
                             (sid,)).fetchone()
        if student is None:
            return _json_error("not_found", 404)

        parts: list[str] = []
        for snip_id in body.get("snippet_ids") or []:
            row = db.execute(
                "SELECT * FROM snippets WHERE id=? AND teacher_id=?",
                (snip_id, t["id"])).fetchone()
            if row:
                parts.append(row["text"])
                db.execute("UPDATE snippets SET use_count=use_count+1 "
                           "WHERE id=?", (snip_id,))
        free = (body.get("free_text") or "").strip()
        if free:
            parts.append(free)
        message = ",".join(parts)

        cur = db.execute(
            "INSERT INTO calls(student_id,class_id,teacher_id,message) "
            "VALUES (?,?,?,?)",
            (sid, student["class_id"], t["id"], message))
        db.commit()
        call = call_row(db, cur.lastrowid)

        hook = request.app.get("ws_broadcast")
        if hook:
            await hook(call)
        return web.json_response({"call": call}, status=201)

    async def undo_call(request):
        t, db = request["teacher"], request.app["db"]
        row = db.execute("SELECT * FROM calls WHERE id=?",
                         (int(request.match_info["id"]),)).fetchone()
        if row is None:
            return _json_error("not_found", 404)
        if t["role"] != "admin" and row["teacher_id"] != t["id"]:
            return _json_error("forbidden", 403)
        created = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")
        if datetime.now() - created > RETRACT_WINDOW:
            return _json_error("gone", 410)
        db.execute("UPDATE calls SET retracted_at=datetime('now','localtime') "
                   "WHERE id=?", (row["id"],))
        db.commit()
        hook = request.app.get("ws_retract")
        if hook:
            await hook(row["id"])
        return web.json_response({"ok": True})

    async def today(request):
        db, t = request.app["db"], request["teacher"]
        rows = db.execute(
            f"SELECT id FROM calls WHERE teacher_id={t['id']} "
            f"AND {_today_where()} ORDER BY id DESC").fetchall()
        return web.json_response(
            {"calls": [call_row(db, r["id"]) for r in rows]})

    async def list_snippets(request):
        rows = request.app["db"].execute(
            "SELECT id,text,use_count FROM snippets WHERE teacher_id=? "
            "ORDER BY use_count DESC, id DESC",
            (request["teacher"]["id"],)).fetchall()
        return web.json_response([dict(r) for r in rows])

    async def add_snippet(request):
        text = (await request.json()).get("text", "").strip()
        if not text:
            return _json_error("bad_request", 400)
        db = request.app["db"]
        db.execute("INSERT INTO snippets(teacher_id,text) VALUES (?,?)",
                   (request["teacher"]["id"], text))
        db.commit()
        return web.json_response({"ok": True}, status=201)

    async def del_snippet(request):
        request.app["db"].execute(
            "DELETE FROM snippets WHERE id=? AND teacher_id=?",
            (int(request.match_info["id"]), request["teacher"]["id"]))
        request.app["db"].commit()
        return web.json_response({"ok": True})

    router.add_get("/api/me", me)
    router.add_put("/api/me", update_me)
    router.add_post("/api/auth/logout", logout)
    router.add_get("/api/students/search", search)
    router.add_post("/api/calls", create_call)
    router.add_delete("/api/calls/{id}", undo_call)
    router.add_get("/api/calls/today", today)
    router.add_get("/api/snippets", list_snippets)
    router.add_post("/api/snippets", add_snippet)
    router.add_delete("/api/snippets/{id}", del_snippet)
