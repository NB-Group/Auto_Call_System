"""鉴权:bcrypt 密码、会话 token、aiohttp 中间件。"""
import secrets

import bcrypt
from aiohttp import web

# CONTRACTS:公开端点
PUBLIC_PATHS = {
    "/api/auth/login",
    "/api/bootstrap/status",
    "/api/bootstrap/admin",
    "/api/classes",
}


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), h.encode())
    except ValueError:
        return False


def create_session(conn, teacher_id: int) -> str:
    token = secrets.token_urlsafe(32)
    conn.execute("INSERT INTO sessions(token,teacher_id) VALUES (?,?)",
                 (token, teacher_id))
    conn.commit()
    return token


def resolve_token(conn, token: str):
    row = conn.execute(
        "SELECT t.* FROM sessions s JOIN teachers t ON t.id=s.teacher_id "
        "WHERE s.token=? AND t.disabled=0", (token,)).fetchone()
    return row


@web.middleware
async def auth_middleware(request, handler):
    if request.path.startswith("/api") and request.path not in PUBLIC_PATHS:
        header = request.headers.get("Authorization", "")
        token = header[7:] if header.startswith("Bearer ") else None
        teacher = resolve_token(request.app["db"], token) if token else None
        if teacher is None:
            return web.json_response({"error": "unauthorized"}, status=401)
        request["teacher"] = teacher
    return await handler(request)


def require_admin(request) -> web.Response | None:
    """非管理员返回 403 响应,管理员返回 None 放行。"""
    if request["teacher"]["role"] != "admin":
        return web.json_response({"error": "forbidden"}, status=403)
    return None
