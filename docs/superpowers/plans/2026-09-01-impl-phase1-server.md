# 实施计划 Phase 1:契约冻结 + Server + Python 壳

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 冻结全部接口契约,实现服务器(aiohttp+SQLite+UDP+WS)、pywebview 壳、TTS 抽象——全部带测试,Linux 本机可跑通后端全链路。

**Architecture:** 中央服务器模式:单 exe 三角色(server/teacher/display),服务器托管前端、UDP 广播发现、WS 按班级推送。契约先行:Task 1 产出 `docs/CONTRACTS.md` + `docs/schemas.json` 并冻结,后续任务只对契约编码。

**Tech Stack:** Python 3.12、aiohttp、SQLite(WAL)、bcrypt、pypinyin、pywebview;pytest + pytest-aiohttp + jsonschema。

**Spec:** `docs/superpowers/specs/2026-09-01-call-system-design.md`
**后续:** Phase 2 前端(`2026-09-01-impl-phase2-frontend.md`)、Phase 3 打包发布(`2026-09-01-impl-phase3-delivery.md`)

## Global Constraints

- Python ≥3.12;`requirements.txt`(运行)/`requirements-dev.txt`(开发测试)
- 接口以 `docs/CONTRACTS.md` 为准;契约变更须主 agent 先改文档再广播
- UI 文案中文;注释少而准(中文);SQLite 原生 SQL,无 ORM
- 显示端 WS 匿名只读(仅 subscribe);叫号/管理必须 Bearer token
- TTS 走 `TTSService` 抽象,`TTS=none|espeak` 环境变量可强制;bridge 只暴露 `speak(text)`
- 每个 commit 测试绿;直接提交 master
- **契约增补(相对 spec §4,本计划锁定)**:①bootstrap 端点(首次建管理员);②WS `call` 载荷增加 `announce`(服务端合成好的完整播报文本);③`POST /api/calls` 请求体为 `{student_id, snippet_ids?, free_text?}`,message 由服务端合成;④`GET /api/classes` 为公开端点(显示端选班级用)

---

### Task 1: 冻结接口契约

**Files:**
- Create: `docs/CONTRACTS.md`
- Create: `docs/schemas.json`
- Create: `requirements.txt`、`requirements-dev.txt`
- Test: `tests/test_contracts.py`

**Interfaces:**
- Produces: 所有后续任务的接口依据(`docs/CONTRACTS.md`),机器可校验 schema(`docs/schemas.json`)

- [ ] **Step 1: 写 `docs/schemas.json`**

```json
{
  "discovery_packet": {
    "schema": {
      "type": "object", "required": ["app", "port", "version"],
      "properties": {
        "app": {"const": "call-center"},
        "port": {"type": "integer", "minimum": 1, "maximum": 65535},
        "version": {"type": "string"}
      }
    },
    "example": {"app": "call-center", "port": 8800, "version": "0.1.0"}
  },
  "call": {
    "schema": {
      "type": "object",
      "required": ["id", "student_id", "class_id", "teacher_id", "message", "announce", "created_at", "student_name", "class_name", "teacher_name", "office"],
      "properties": {
        "id": {"type": "integer"},
        "student_id": {"type": "integer"},
        "class_id": {"type": "integer"},
        "teacher_id": {"type": "integer"},
        "message": {"type": "string"},
        "announce": {"type": "string"},
        "created_at": {"type": "string"},
        "student_name": {"type": "string"},
        "class_name": {"type": "string"},
        "teacher_name": {"type": "string"},
        "office": {"type": "string"}
      }
    },
    "example": {"id": 1, "student_id": 3, "class_id": 2, "teacher_id": 1, "message": "订正数学作业,带上练习册", "announce": "请梁皓文同学到郑老师203办公室,订正数学作业,带上练习册", "created_at": "2026-09-01 10:30:00", "student_name": "梁皓文", "class_name": "高二(3)班", "teacher_name": "郑老师", "office": "203办公室"}
  },
  "latest_manifest": {
    "schema": {
      "type": "object", "required": ["version", "notes", "asset", "sha256", "size"],
      "properties": {
        "version": {"type": "string"},
        "notes": {"type": "string"},
        "asset": {"type": "string"},
        "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "size": {"type": "integer", "minimum": 0}
      }
    },
    "example": {"version": "0.2.0", "notes": "修复显示端重连", "asset": "call-center-0.2.0-x64.exe", "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "size": 12345678}
  },
  "ws_client_messages": {
    "schema": {
      "type": "object", "required": ["type"],
      "properties": {
        "type": {"const": "subscribe"},
        "class_id": {"type": "integer"}
      }
    },
    "example": {"type": "subscribe", "class_id": 3}
  },
  "ws_server_call": {
    "schema": {
      "type": "object", "required": ["type", "call"],
      "properties": {"type": {"const": "call"}, "call": {"$ref": "#/schemas/call/schema"}}
    },
    "example": {"type": "call", "call": {"id": 1, "student_id": 3, "class_id": 2, "teacher_id": 1, "message": "", "announce": "请梁皓文同学到郑老师203办公室", "created_at": "2026-09-01 10:30:00", "student_name": "梁皓文", "class_name": "高二(3)班", "teacher_name": "郑老师", "office": "203办公室"}}
  },
  "ws_server_retract": {
    "schema": {
      "type": "object", "required": ["type", "call_id"],
      "properties": {"type": {"const": "retract"}, "call_id": {"type": "integer"}}
    },
    "example": {"type": "retract", "call_id": 1}
  }
}
```

- [ ] **Step 2: 写 `docs/CONTRACTS.md`**

````markdown
# 接口契约(冻结版 v1,2026-09-01)

变更规则:任何实现需要改本文件 → 停下,交主 agent 修改并广播后再继续。

## 通用
- 所有 JSON,UTF-8;时间戳格式 `YYYY-MM-DD HH:MM:SS`(本地时间)
- 鉴权头 `Authorization: Bearer <token>`;401 `{"error":"unauthorized"}`;403 `{"error":"forbidden"}`
- 公开端点(免鉴权):`POST /api/auth/login`、`GET /api/bootstrap/status`、`POST /api/bootstrap/admin`、`GET /api/classes`、`/ws`、静态资源
- 错误响应统一 `{"error": "<code>"}`;code ∈ unauthorized|forbidden|not_found|bad_request|conflict|gone

## HTTP API

### POST /api/auth/login
Req `{"username": "...", "password": "..."}`
Res 200 `{"token": "...", "role": "teacher"|"admin", "display_name": "...", "office": "..."}`
Res 401 unauthorized

### POST /api/auth/logout(需鉴权)
Res 200 `{"ok": true}`

### GET /api/me → 200 `{"id","username","role","display_name","office","default_template"}`
### PUT /api/me Req `{"display_name"?, "office"?, "default_template"?}` → 200 同 GET

### GET /api/bootstrap/status(公开)
→ `{"needs_admin": bool, "version": "0.1.0"}`

### POST /api/bootstrap/admin(公开;仅当 needs_admin=true 时有效)
Req `{"username","password","display_name"?}` → 201 `{"token","role":"admin","display_name","office":""}`
已有管理员时 → 409 conflict

### GET /api/classes(公开)→ `[{"id":1,"name":"高二(3)班","ord":0}]`(按 ord,name)

### GET /api/students/search?q=<拼音或姓名>&limit=8(教师)
匹配优先级:首字母前缀 > 全拼前缀 > 姓名子串;→ `[{"id","name","class_name","pinyin_initials"}]`

### POST /api/calls(教师) Req `{"student_id": 3, "snippet_ids": [1,2], "free_text": ""}`
message = 选中短语文本以 ``,` 连接 +(`,`+free_text,若有);announce = default_template 渲染
(`{student}`→学生姓名,`{teacher}`→display_name,`{office}`→office)+(`,`+message,若有)
→ 201 `{"call": {...call 对象,见 schemas.json}}`

### DELETE /api/calls/{id}(本人 60s 内或 admin)→ 200 `{"ok":true}`;超时 410 gone;他人 403

### GET /api/calls/today(教师)→ `{"calls": [call...]}`(本老师今日,新在前,retracted 含标记 `retracted_at`)

### GET /api/snippets(教师)→ `[{"id","text","use_count"}]`(use_count 降序)
### POST /api/snippets Req `{"text"}` → 201 `[对象同上]`(增后全表)
### DELETE /api/snippets/{id} → 200 `{"ok":true}`

### 管理员(role=admin)
- `GET /api/admin/teachers` → `[{"id","username","role","display_name","office","disabled","created_at"}]`
- `POST /api/admin/teachers` Req `{"username","password","display_name","office":"","role":"teacher"}` → 201
- `PUT /api/admin/teachers/{id}` Req `{"display_name"?,"office"?,"disabled"?,"password"?}` → 200
- `DELETE /api/admin/teachers/{id}` → 200 `{"ok":true}`
- `POST /api/admin/classes` Req `{"name","ord":0}` → 201 `{"id","name","ord"}`
- `DELETE /api/admin/classes/{id}`(级联删学生)→ 200 `{"ok":true}`
- `POST /api/admin/classes/{id}/students` Req `{"text": "梁皓文\\n王小雨,李涵文 0305"}`(行/逗号分隔,可选尾缀学号)→ 201 `{"imported": 2, "skipped": ["王小雨"]}`(班级内姓名+学号重复跳过)
- `GET /api/admin/calls?date=YYYY-MM-DD` → `{"calls":[call...]}`(全班,新在前)
- `GET /api/server/info` → `{"version", "displays": <当前WS显示端数>}`

## WebSocket /ws?token=<可空>(显示端可匿名)
- 鉴权失败(提供了 token 但无效)→ 连接后立即 close code=4401
- 客户端→服务器:`{"type":"subscribe","class_id":3}`(重新订阅即换班)
- 服务器→显示端:
  - `{"type":"hello"}`(订阅确认/重连成功)
  - `{"type":"call","call":{...}}`(schemas.json `call`)
  - `{"type":"retract","call_id":n}`
- 服务器心跳 20s(pywebview/aiohttp 自带 ping)

## UDP 发现(端口 50000,服务器每 3s 广播)
`schemas.json` `discovery_packet`:{"app":"call-center","port":8800,"version":"0.1.0"}

## pywebview bridge(window.pywebview.api,壳注入,前端防御式调用)
- `speak(text) -> null` TTS 入队(显示端用)
- `fullscreen(on: bool) -> null`
- `get_role() -> "server"|"teacher"|"display"`
- `app_version() -> "0.1.0"`
- `quit() -> null`

## 自动更新
- 每个 GitHub Release 附 `latest.json`(schemas.json `latest_manifest`)+ exe 资产
- 下载 URL 模板:`{mirror}https://github.com/<repo>/releases/download/v{version}/{asset}`
- 清单 URL 模板:`{mirror}https://github.com/<repo>/releases/latest/download/latest.json`
- 镜像前缀列表(可配置):`""`(直连)、`https://gh-proxy.org/`、`https://ghfast.top/`、`https://ghproxy.net/`、`https://ghproxy.homeboyc.cn/`、`https://gh.zwy.one/`
- 防投毒:清单须从 ≥2 个源取得且 sha256 一致才下载;下载后文件 sha256 再验一次
````

- [ ] **Step 3: 写依赖文件**

`requirements.txt`:
```
aiohttp>=3.9
pywebview>=5.1
bcrypt>=4.1
pypinyin>=0.50
```

`requirements-dev.txt`:
```
-r requirements.txt
pytest>=8
pytest-aiohttp>=1.0
jsonschema>=4.20
```

- [ ] **Step 4: 写失败测试 `tests/test_contracts.py`**

```python
"""契约自检:schemas.json 可解析且 example 全部通过自身 schema 校验。"""
import json
from pathlib import Path

import jsonschema

DOCS = Path(__file__).parent.parent / "docs"


def load_schemas():
    return json.loads((DOCS / "schemas.json").read_text(encoding="utf-8"))


def test_every_example_validates():
    for name, spec in load_schemas().items():
        schema = dict(spec["schema"])
        # 展开 $ref 到同文件兄弟 schema
        if "properties" in schema:
            for prop in schema["properties"].values():
                if "$ref" in prop:
                    ref_name = prop["$ref"].split("/")[2]
                    prop.pop("$ref")
                    prop.update(load_schemas()[ref_name]["schema"])
        jsonschema.validate(spec["example"], schema)


def test_contracts_md_covers_all_schemas():
    text = (DOCS / "CONTRACTS.md").read_text(encoding="utf-8")
    for name in load_schemas():
        assert name in text, f"CONTRACTS.md 未提及 {name}"
```

- [ ] **Step 5: 跑测试确认通过**

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
pytest tests/test_contracts.py -v
```
Expected: 2 passed(本任务无实现代码,测试即文档校验,直接绿;若 example 校验失败修 example)

- [ ] **Step 6: Commit**

```bash
git add docs/ requirements.txt requirements-dev.txt tests/
git commit -m "feat: 冻结接口契约 CONTRACTS.md + schemas.json"
```

---

### Task 2: SQLite 层(db.py)

**Files:**
- Create: `server/__init__.py`(空)
- Create: `server/db.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Produces: `connect(db_path) -> sqlite3.Connection`(Row 工厂,WAL,外键开);`init_db(conn)`;`SCHEMA` 常量

- [ ] **Step 1: 写失败测试 `tests/test_db.py`**

```python
import sqlite3

import pytest

from server.db import connect, init_db


@pytest.fixture()
def db(tmp_path):
    conn = connect(tmp_path / "call.db")
    init_db(conn)
    yield conn
    conn.close()


def test_wal_and_fk(db):
    mode = db.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode == "wal"
    assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_all_tables_created(db):
    names = {r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"settings", "teachers", "classes", "students",
            "snippets", "calls", "sessions"} <= names


def test_init_idempotent(db):
    init_db(db)  # 不抛错即过


def test_cascade_delete_class_removes_students(db):
    db.execute("INSERT INTO classes(name) VALUES ('高二(3)班')")
    db.execute("INSERT INTO students(class_id,name) VALUES (1,'梁皓文')")
    db.commit()
    db.execute("DELETE FROM classes WHERE id=1")
    db.commit()
    assert db.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 0
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_db.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'server'`

- [ ] **Step 3: 实现 `server/db.py`**

```python
"""SQLite 连接与 schema。"""
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings(
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS teachers(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'teacher',
  display_name TEXT NOT NULL DEFAULT '',
  office TEXT NOT NULL DEFAULT '',
  default_template TEXT NOT NULL DEFAULT '请{student}同学到{teacher}{office}',
  created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  disabled INTEGER NOT NULL DEFAULT 0);

CREATE TABLE IF NOT EXISTS classes(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE NOT NULL,
  ord INTEGER NOT NULL DEFAULT 0);

CREATE TABLE IF NOT EXISTS students(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  student_no TEXT NOT NULL DEFAULT '',
  pinyin_full TEXT NOT NULL DEFAULT '',
  pinyin_initials TEXT NOT NULL DEFAULT '',
  UNIQUE(class_id, name, student_no));

CREATE INDEX IF NOT EXISTS idx_students_py
  ON students(pinyin_initials, pinyin_full);

CREATE TABLE IF NOT EXISTS snippets(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  teacher_id INTEGER NOT NULL REFERENCES teachers(id) ON DELETE CASCADE,
  text TEXT NOT NULL,
  use_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')));

CREATE TABLE IF NOT EXISTS calls(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id INTEGER NOT NULL,
  class_id INTEGER NOT NULL,
  teacher_id INTEGER NOT NULL,
  message TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  retracted_at TEXT);

CREATE TABLE IF NOT EXISTS sessions(
  token TEXT PRIMARY KEY,
  teacher_id INTEGER NOT NULL REFERENCES teachers(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')));
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_db.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add server/ tests/test_db.py
git commit -m "feat: SQLite schema 与连接层(WAL/外键/级联)"
```

---

### Task 3: 鉴权(auth.py)

**Files:**
- Create: `server/auth.py`
- Test: `tests/test_auth.py`

**Interfaces:**
- Consumes: `server.db.connect/init_db`
- Produces: `hash_password(p)`, `verify_password(p, h)`, `create_session(conn, teacher_id) -> token`, `resolve_token(conn, token) -> Row|None`, `auth_middleware`(aiohttp 中间件,公开路径见 CONTRACTS), `require_admin(request) -> web.Response|None`

- [ ] **Step 1: 写失败测试 `tests/test_auth.py`**

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_auth.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'server.auth'`

- [ ] **Step 3: 实现 `server/auth.py`**

```python
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_auth.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add server/auth.py tests/test_auth.py
git commit -m "feat: bcrypt 鉴权 + 会话 + 中间件"
```

---

### Task 4: 拼音搜索(search.py)

**Files:**
- Create: `server/search.py`
- Test: `tests/test_search.py`

**Interfaces:**
- Produces: `pinyin_of(name) -> (full, initials)`;`search_students(conn, q, limit=8) -> [dict]`(优先级:首字母前缀 > 全拼前缀 > 姓名子串,同级按姓名排序)

- [ ] **Step 1: 写失败测试 `tests/test_search.py`**

```python
import pytest

from server.db import connect, init_db
from server.search import pinyin_of, search_students


@pytest.fixture()
def db(tmp_path):
    conn = connect(tmp_path / "call.db")
    init_db(conn)
    conn.execute("INSERT INTO classes(name) VALUES ('高二(3)班')")
    students = [("梁皓文",), ("李涵文",), ("王小雨",), ("刘昊然",)]
    conn.executemany(
        "INSERT INTO students(class_id,name,pinyin_full,pinyin_initials) "
        "VALUES (1,?,?,?)",
        [(n, *pinyin_of(n)) for (n,) in students])
    conn.commit()
    yield conn
    conn.close()


def test_pinyin_of():
    assert pinyin_of("梁皓文") == ("lianghaowen", "lhw")


def test_initials_prefix_beats_full(db):
    rows = search_students(db, "lh")
    names = [r["name"] for r in rows]
    assert names[0] == "李涵文"          # lh 前缀(lhw 全命中也行,首字母优先)
    assert "梁皓文" in names              # lhw 命中首字母前缀


def test_full_pinyin_prefix(db):
    assert search_students(db, "liang")[0]["name"] == "梁皓文"


def test_name_substring(db):
    assert search_students(db, "皓文")[0]["name"] == "梁皓文"


def test_no_match(db):
    assert search_students(db, "zzz") == []


def test_limit_and_shape(db):
    rows = search_students(db, "l", 2)
    assert len(rows) == 2
    assert set(rows[0]) == {"id", "name", "class_name", "pinyin_initials"}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_search.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'server.search'`

- [ ] **Step 3: 实现 `server/search.py`**

```python
"""学生搜索:拼音首字母 > 全拼 > 姓名子串(CONTRACTS)。"""
from pypinyin import Style, lazy_pinyin


def pinyin_of(name: str) -> tuple[str, str]:
    full = "".join(lazy_pinyin(name))
    initials = "".join(lazy_pinyin(name, style=Style.FIRST_LETTER))
    return full, initials


def _score(q: str, row) -> int | None:
    ql = q.strip().lower()
    if not ql:
        return None
    if row["pinyin_initials"].startswith(ql):
        return 0
    if row["pinyin_full"].startswith(ql):
        return 1
    if ql in row["name"].lower():
        return 2
    return None


def search_students(conn, q: str, limit: int = 8) -> list[dict]:
    rows = conn.execute(
        "SELECT s.id, s.name, s.pinyin_full, s.pinyin_initials, "
        "       c.name AS class_name "
        "FROM students s JOIN classes c ON c.id = s.class_id").fetchall()
    scored = [(s, r) for r in rows if (s := _score(q, r)) is not None]
    scored.sort(key=lambda t: (t[0], t[1]["name"]))
    return [{k: r[k] for k in ("id", "name", "class_name", "pinyin_initials")}
            for _, r in scored[:limit]]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_search.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add server/search.py tests/test_search.py
git commit -m "feat: 拼音首字母/全拼/姓名三级匹配搜索"
```

---

### Task 5: 业务端点(api.py 之 calls/snippets/me)

**Files:**
- Create: `server/api.py`
- Test: `tests/test_api_calls.py`

**Interfaces:**
- Consumes: `server.db`、`server.auth`、`server.search.search_students`、`server.ws.broadcast_call/broadcast_retract`(Task 6 产出;本任务以 `app['ws_broadcast']` 钩子解耦:`app['ws_broadcast'] = async fn(call) | None`)
- Produces: `setup_business_routes(router)`;`call_row(conn, call_id) -> dict|None`(完整 call 对象含 announce,Task 6 复用);`render_template(t, student, teacher, office) -> str`

- [ ] **Step 1: 写失败测试 `tests/test_api_calls.py`**

```python
import pytest
from aiohttp import web
from pathlib import Path

from server.api import setup_business_routes
from server.auth import create_session, hash_password
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
    app = web.Application()
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_api_calls.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'server.api'`

- [ ] **Step 3: 实现 `server/api.py`**

```python
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_api_calls.py -v`
Expected: 7 passed
(测试里对 created_at 直接改库模拟超时,若 sqlite 锁冲突,在改库连接上先执行 `PRAGMA busy_timeout=5000`)

- [ ] **Step 5: Commit**

```bash
git add server/api.py tests/test_api_calls.py
git commit -m "feat: calls/snippets/me 端点(消息合成+播报模板+60s撤销)"
```

---

### Task 6: WebSocket 推送(ws.py)

**Files:**
- Create: `server/ws.py`
- Test: `tests/test_ws.py`

**Interfaces:**
- Consumes: `server.auth.resolve_token`
- Produces: `ws_handler`(挂 `/ws`);`broadcast_call(app, call)`、`broadcast_retract(app, call_id)`;`app['ws_clients']: {ws: class_id|None}`;`displays_count(app) -> int`

- [ ] **Step 1: 写失败测试 `tests/test_ws.py`**

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_ws.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'server.ws'`

- [ ] **Step 3: 实现 `server/ws.py`**

```python
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_ws.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add server/ws.py tests/test_ws.py
git commit -m "feat: WS 按班级路由广播(匿名显示端+4401)"
```

---

### Task 7: bootstrap + 管理端点 + 应用组装(app.py / serve.py)

**Files:**
- Create: `server/app.py`
- Create: `server/serve.py`
- Create: `server/__main__.py`(空壳,见 Step 3)
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: 前面全部模块;`app/__init__.py` 的 `__version__`(本任务一并创建)
- Produces: `create_app(db_path, static_dir=None) -> web.Application`(含中间件/路由/静态托管/静态回退);`serve.py:start_server(host,port,db_path) -> (Runner, thread)`、`stop_server(runner)`、控制台入口 `python -m server`

- [ ] **Step 1: 写失败测试 `tests/test_app.py`**

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_app.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'server.app'`

- [ ] **Step 3: 实现 `server/app.py`、`server/serve.py`、`app/__init__.py`**

`app/__init__.py`:
```python
"""pywebview 壳与版本号(Nuitka 打包入口 app/main.py)。"""
__version__ = "0.1.0"
```

`server/app.py`:
```python
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
        return web.FileResponse(static / "index.html")
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
        for line in text.replace(",", "\n").replace(",", "\n").splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            name, no = parts[0], (parts[1] if len(parts) > 1 else "")
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
        where = f"date(c.created_at)='{date}'" if date else "1=1"
        rows = request.app["db"].execute(
            f"SELECT id FROM calls c WHERE {where} ORDER BY id DESC").fetchall()
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
```

`server/serve.py`:
```python
"""服务器模式:线程内运行 aiohttp(供 pywebview 壳调用)+ 控制台入口。"""
import asyncio
import threading

from aiohttp import web

DEFAULT_PORT = 8800


def start_server(host="0.0.0.0", port=DEFAULT_PORT, db_path="data/call.db",
                 static_dir=None):
    """在后台线程跑 HTTP 服务,返回 (runner, thread, loop)。

    UDP 广播(Broadcaster)由 Task 8 接入:文件顶部 import,本函数末尾
    创建并 start(),返回值追加 bcast。
    """
    from server.app import create_app
    app = create_app(db_path, static_dir)
    loop = asyncio.new_event_loop()
    runner = web.AppRunner(app)

    def run():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(runner.setup())
        site = web.TCPSite(runner, host, port)
        loop.run_until_complete(site.start())
        loop.run_forever()

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return runner, t, loop


def stop_server(runner, loop):
    loop.call_soon_threadsafe(loop.stop)


if __name__ == "__main__":
    import signal
    from server.app import create_app
    web.run_app(create_app("data/call.db"), host="0.0.0.0",
                port=DEFAULT_PORT, handle_signals=True)
```

`server/__main__.py`:
```python
"""python -m server = 纯控制台服务器(无窗口)。"""
from aiohttp import web

from server.app import create_app
from server.serve import DEFAULT_PORT

if __name__ == "__main__":
    web.run_app(create_app("data/call.db"), host="0.0.0.0",
                port=DEFAULT_PORT, handle_signals=True)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_app.py -v`
Expected: 5 passed(Broadcaster 尚未存在,serve.py 里只留了注释占位,Task 8 接入)

- [ ] **Step 5: Commit**

```bash
git add server/ app/__init__.py tests/test_app.py
git commit -m "feat: 应用组装+bootstrap+管理端点+静态托管"
```

---

### Task 8: UDP 广播与发现(broadcast.py / discovery.py)

**Files:**
- Create: `server/broadcast.py`
- Create: `app/discovery.py`
- Test: `tests/test_discovery.py`

**Interfaces:**
- Consumes: `docs/schemas.json` `discovery_packet`
- Produces: `Broadcaster(http_port, version, interval=3.0)`(daemon 线程,`.start()/.stop()`);`find_server(timeout=2.0) -> {"host","port","version"}|None`

- [ ] **Step 1: 写失败测试 `tests/test_discovery.py`**

```python
import json
import socket
import time

from app.discovery import find_server
from server.broadcast import DISCOVERY_PORT, Broadcaster


def test_broadcast_and_discover():
    b = Broadcaster(8800, "0.1.0", interval=0.2)
    b.start()
    try:
        found = find_server(timeout=2.0)
    finally:
        b.stop()
    assert found is not None
    assert found["port"] == 8800
    assert found["version"] == "0.1.0"
    assert found["host"]  # 本机 IP


def test_discover_returns_none_when_silent():
    # 广播端先占用再停止,确保静默
    b = Broadcaster(8800, "0.1.0", interval=0.1)
    b.start(); time.sleep(0.3); b.stop()
    assert find_server(timeout=0.5) is None


def test_packet_shape():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", DISCOVERY_PORT + 1))
    b = Broadcaster(8800, "0.1.0", interval=0.2)
    # 直接调用一次内部发送,发到 DISCOVERY_PORT+1 由我们接收
    b._send_once(("127.0.0.1", DISCOVERY_PORT + 1))
    data, _ = sock.recvfrom(1024)
    sock.close(); b.stop()
    pkt = json.loads(data)
    assert pkt["app"] == "call-center"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_discovery.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'server.broadcast'`

- [ ] **Step 3: 实现 `server/broadcast.py` 与 `app/discovery.py`**

`server/broadcast.py`:
```python
"""UDP 广播:每 interval 秒宣告服务器存在(CONTRACTS discovery_packet)。"""
import json
import socket
import threading

DISCOVERY_PORT = 50000


class Broadcaster(threading.Thread):
    def __init__(self, http_port: int, version: str, interval: float = 3.0):
        super().__init__(daemon=True)
        self.http_port = http_port
        self.version = version
        self.interval = interval
        self._stop = threading.Event()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    def _packet(self) -> bytes:
        return json.dumps({"app": "call-center", "port": self.http_port,
                           "version": self.version}).encode()

    def _send_once(self, addr) -> None:
        self._sock.sendto(self._packet(), addr)

    def run(self):
        while not self._stop.wait(self.interval):
            try:
                self._send_once(("255.255.255.255", DISCOVERY_PORT))
            except OSError:
                pass

    def stop(self):
        self._stop.set()
        self._sock.close()
```

`app/discovery.py`:
```python
"""客户端发现:监听 UDP 广播(CONTRACTS discovery_packet)。"""
import json
import socket
import time

from server.broadcast import DISCOVERY_PORT


def find_server(timeout: float = 2.0) -> dict | None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", DISCOVERY_PORT))
    sock.settimeout(timeout)
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            try:
                data, addr = sock.recvfrom(1024)
            except socket.timeout:
                break
            try:
                pkt = json.loads(data)
            except ValueError:
                continue
            if pkt.get("app") == "call-center":
                return {"host": addr[0], "port": pkt["port"],
                        "version": pkt["version"]}
        return None
    finally:
        sock.close()
```

补回 Task 7 中 serve.py 预留的广播接入:顶部 `from server.broadcast import Broadcaster`;`start_server` 末尾 `from app import __version__` + `bcast = Broadcaster(port, __version__); bcast.start()`,返回值改为 `(runner, t, bcast, loop)`;`stop_server` 增加 `bcast` 参数并先 `bcast.stop()`。

- [ ] **Step 4: 跑全量测试确认通过**

Run: `pytest -v`
Expected: 全部 passed(含前面所有任务)

- [ ] **Step 5: 手动冒烟:两个终端**

```bash
# 终端1
. .venv/bin/activate && python -m server
# 终端2
. .venv/bin/activate && python -c "from app.discovery import find_server; print(find_server())"
```
Expected: 终端2 打印 `{'host': '<本机IP>', 'port': 8800, 'version': '0.1.0'}`;Ctrl+C 停终端1

- [ ] **Step 6: Commit**

```bash
git add server/broadcast.py app/discovery.py tests/test_discovery.py server/serve.py
git commit -m "feat: UDP 广播发现(零配置)"
```

---

### Task 9: TTS 抽象(tts.py)

**Files:**
- Create: `app/tts.py`
- Test: `tests/test_tts.py`

**Interfaces:**
- Produces: `TTSService(backend=None, repeat=2, gap=0.8)`:`.speak(text)` 入队、`.available -> bool`、`.stop()`;后端 `SapiBackend/EspeakBackend/NullBackend`(`.speak(text)` 阻塞播放、`.available -> bool`);`pick_backend()` 按 `TTS` 环境变量与平台选择

- [ ] **Step 1: 写失败测试 `tests/test_tts.py`**

```python
import time

from app.tts import NullBackend, TTSService


class FakeBackend:
    def __init__(self):
        self.played = []

    @property
    def available(self):
        return True

    def speak(self, text):
        self.played.append(text)


def test_queue_orders_and_repeats():
    fake = FakeBackend()
    svc = TTSService(backend=fake, repeat=2, gap=0.01)
    svc.speak("第一条")
    svc.speak("第二条")
    deadline = time.monotonic() + 5
    while len(fake.played) < 4 and time.monotonic() < deadline:
        time.sleep(0.01)
    svc.stop()
    assert fake.played == ["第一条", "第一条", "第二条", "第二条"]


def test_null_backend_available_false():
    assert NullBackend().available is False
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_tts.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'app.tts'`

- [ ] **Step 3: 实现 `app/tts.py`**

```python
"""TTS 抽象:后端按平台/环境变量插拔,队列顺序播报(spec §7)。"""
import os
import queue
import subprocess
import threading


class NullBackend:
    available = False

    def speak(self, text: str) -> None:  # pragma: no cover
        pass


class EspeakBackend:
    """Linux 开发调试用:espeak-ng,中文语音,音质机械。"""

    def __init__(self):
        self._proc_check()

    @staticmethod
    def _proc_check():
        subprocess.run(["espeak-ng", "--version"], capture_output=True,
                       check=True)

    @property
    def available(self) -> bool:
        try:
            self._proc_check()
            return True
        except Exception:
            return False

    def speak(self, text: str) -> None:
        subprocess.run(["espeak-ng", "-v", "zh", "-s", "150", text],
                       capture_output=True)


class SapiBackend:
    """Windows 生产路径:SAPI 离线中文语音。"""

    def __init__(self):
        import win32com.client  # 惰性导入(Nuitka:--include-package=win32com)
        self.voice = win32com.client.Dispatch("SAPI.SpVoice")
        for v in self.voice.GetVoices():
            name = v.GetAttribute("Name") if v.GetDescription() else ""
            if any(k in name for k in ("Huihui", "Kangkang", "Yaoyao",
                                       "Microsoft")):
                self.voice.Voice = v
                break
        self.voice.Rate = -1  # 0.9× 语速

    @property
    def available(self) -> bool:
        return True

    def speak(self, text: str) -> None:
        self.voice.Speak(text, 0)  # 同步,天然排队


def pick_backend():
    forced = os.environ.get("TTS", "").lower()
    if forced == "none":
        return NullBackend()
    if forced == "espeak":
        return EspeakBackend()
    if os.name == "nt":
        try:
            return SapiBackend()
        except Exception:
            return NullBackend()
    try:
        return EspeakBackend()
    except Exception:
        return NullBackend()


class TTSService:
    """队列化播报:每条文本连播 repeat 遍,间隔 gap 秒(spec §5)。"""

    def __init__(self, backend=None, repeat: int = 2, gap: float = 0.8):
        self.backend = backend if backend is not None else pick_backend()
        self.repeat, self.gap = repeat, gap
        self._q: queue.Queue[str | None] = queue.Queue()
        self._stop = threading.Event()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    @property
    def available(self) -> bool:
        return self.backend.available

    def speak(self, text: str) -> None:
        if self.available:
            self._q.put(text)

    def _run(self):
        while not self._stop.is_set():
            text = self._q.get()
            if text is None or self._stop.is_set():
                return
            for i in range(self.repeat):
                if self._stop.is_set():
                    return
                try:
                    self.backend.speak(text)
                except Exception:
                    pass
                if i < self.repeat - 1:
                    self._stop.wait(self.gap)

    def stop(self):
        self._stop.set()
        self._q.put(None)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_tts.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add app/tts.py tests/test_tts.py
git commit -m "feat: TTS 抽象(SAPI/espeak/Null + 队列连播两遍)"
```

---

### Task 10: pywebview 壳(bridge.py / main.py)

**Files:**
- Create: `app/bridge.py`
- Create: `app/main.py`
- Create: `app/config.py`
- Test: `tests/test_shell.py`

**Interfaces:**
- Consumes: `find_server`、`TTSService`、`start_server`
- Produces: `python -m app.main [--role server|teacher|display] [--dev] [--server-url http://host:port]`;`app/bridge.py:Bridge(role, tts_service)`(CONTRACTS bridge 五方法);`app/config.py:load_config()/save_config()`(`data/config.json`:`role`、`server_url`、`update.mirrors`、`update.repo`)

- [ ] **Step 1: 写失败测试 `tests/test_shell.py`**

```python
from app.bridge import Bridge
from app.config import load_config, save_config
from app.tts import TTSService, NullBackend


def test_bridge_surface():
    svc = TTSService(backend=NullBackend(), repeat=1)
    b = Bridge("display", svc)
    assert b.get_role() == "display"
    assert b.app_version() == "0.1.0"
    assert b.speak("测试") is None
    assert b.fullscreen(True) is None
    assert b.quit() is None
    svc.stop()


def test_config_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.CONFIG_PATH", tmp_path / "config.json")
    save_config({"role": "teacher"})
    assert load_config()["role"] == "teacher"
    assert load_config().get("server_url") is None


def test_parse_args_defaults(monkeypatch):
    from app.main import parse_args
    args = parse_args([])
    assert args.role == "auto" and args.dev is False
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_shell.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'app.bridge'`

- [ ] **Step 3: 实现 `app/config.py`、`app/bridge.py`、`app/main.py`**

`app/config.py`:
```python
"""壳配置:data/config.json(角色/服务器地址/更新镜像)。"""
import json
from pathlib import Path

CONFIG_PATH = Path("data/config.json")


def load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2),
                           encoding="utf-8")
```

`app/bridge.py`:
```python
"""pywebview js_api(CONTRACTS bridge)。"""
import webview

from app import __version__


class Bridge:
    def __init__(self, role: str, tts: "TTSService"):
        self.role = role
        self.tts = tts

    def speak(self, text: str) -> None:
        self.tts.speak(text)

    def fullscreen(self, on: bool) -> None:
        if webview.windows:
            webview.windows[0].toggle_fullscreen()

    def get_role(self) -> str:
        return self.role

    def app_version(self) -> str:
        return __version__

    def quit(self) -> None:
        if webview.windows:
            webview.windows[0].destroy()
```

`app/main.py`:
```python
"""入口:角色解析 → 发现/启动服务器 → 打开 pywebview 窗口。"""
import argparse

import webview

from app import __version__
from app.bridge import Bridge
from app.config import load_config, save_config
from app.discovery import find_server
from app.tts import TTSService

DEV_URL = "http://127.0.0.1:5173"


def parse_args(argv=None):
    p = argparse.ArgumentParser("叫号系统")
    p.add_argument("--role", choices=["auto", "server", "teacher", "display"],
                   default="auto")
    p.add_argument("--dev", action="store_true", help="加载 vite dev server")
    p.add_argument("--server-url", default=None,
                   help="跳过发现,直连服务器(如 http://10.1.2.3:8800)")
    return p.parse_args(argv)


def resolve_server_url(arg_url, dev):
    if dev:
        return DEV_URL
    if arg_url:
        return arg_url
    found = find_server(timeout=2.0)
    return f"http://{found['host']}:{found['port']}" if found else None


def main():
    args = parse_args()
    cfg = load_config()
    role = args.role if args.role != "auto" else cfg.get("role")
    if role not in ("server", "teacher", "display"):
        role = _pick_role_dialog()
        if role is None:
            return
        cfg["role"] = role
        save_config(cfg)

    tts = TTSService()
    bridge = Bridge(role, tts)

    if role == "server":
        from server.serve import start_server
        start_server(static_dir=None)
        url = "http://127.0.0.1:8800/#/server"
    else:
        url = resolve_server_url(args.server_url, args.dev)
        if url is None:
            webview.create_window("叫号系统", _offline_html(), js_api=bridge)
            webview.start()
            return
        url = f"{url}/#/{role}"

    window = webview.create_window(
        f"叫号系统 v{__version__}", url, js_api=bridge,
        fullscreen=(role == "display"))
    webview.start()
    tts.stop()


def _pick_role_dialog():
    """无 GUI 组建可用前的极简角色选择:控制台。"""
    print("首次运行,选择本机角色:")
    print("  1. 服务器(办公室常驻机)")
    print("  2. 老师端")
    print("  3. 显示端(教室大屏)")
    choice = input("输入 1/3/3 对应数字: ").strip()
    return {"1": "server", "2": "teacher", "3": "display"}.get(choice)


def _offline_html() -> str:
    return ("<html><body style='font-family:sans-serif;padding:40px'>"
            "<h2>未找到叫号服务器</h2>"
            "<p>请确认办公室服务器电脑已开启;本窗口关闭后将自动重试。</p>"
            "</body></html>")
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_shell.py -v`
Expected: 3 passed(`webview` 导入在无显示环境不崩——bridge 的 `import webview` 顶部导入若无 GTK 会在测试环境报错的话,改为 `fullscreen/quit` 内部局部导入,保证 `Bridge` 可纯构造)

- [ ] **Step 5: 手动冒烟(Linux,三终端)**

```bash
# 终端1:服务器
TTS=none . .venv/bin/activate && python -m app.main --role server --dev
# 终端2:前端未就绪前用控制台验证
curl -s http://127.0.0.1:8800/api/bootstrap/status
# 期望:{"needs_admin": true, "version": "0.1.0"}
```
Expected: 窗口打开(暂时 404/空白属正常,前端在 Phase 2);status 接口返回正确

- [ ] **Step 6: Commit**

```bash
git add app/ tests/test_shell.py
git commit -m "feat: pywebview 壳(角色/发现/bridge)+ 控制台入口"
```

---

## Phase 1 验收清单(全部勾完才算完)

- [ ] `pytest -v` 全绿(contracts/db/auth/search/api/ws/app/discovery/tts/shell)
- [ ] `python -m server` 起服务,`find_server()` 能发现,curl bootstrap/status 正常
- [ ] `TTS=espeak` 时 `TTSService().speak("测试")` 真出声(装 espeak-ng 后)
- [ ] CONTRACTS.md 未被任何实现悄悄修改(`git diff docs/CONTRACTS.md` 为空)
