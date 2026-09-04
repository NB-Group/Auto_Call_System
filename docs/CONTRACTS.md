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
- 客户端→服务器:`{"type":"subscribe","class_id":3}`(schemas.json `ws_client_messages`;重新订阅即换班)
- 服务器→显示端:
  - `{"type":"hello"}`(订阅确认/重连成功)
  - `{"type":"call","call":{...}}`(schemas.json `ws_server_call`,内嵌 schemas.json `call`)
  - `{"type":"retract","call_id":n}`(schemas.json `ws_server_retract`)
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

## v1.1 增补(2026-09-01)
GET /api/snippets/search?q=&limit=6(教师)
匹配:短语拼音首字母前缀 > 短语文本子串;→ [{"id","text","use_count"}](use_count 降序)

## v1.2 增补(2026-09-01)
bridge 新增:
- get_update_config() -> {"repo": str, "mirrors": [str, ...]}
- set_update_config(repo: str, mirrors_json: str) -> null   # mirrors_json 为 JSON 数组文本
壳 → 前端事件(经 evaluate_js 派发到 window):
- CustomEvent 'cc-update',detail = {"version": "...", "notes": "..."}
  (新版已下载暂存、重启生效;前端据此显示横幅,按钮调 api.quit() 重启)

## v1.3 增补(2026-09-02,Task-21)
bridge 新增(自绘标题栏):
- `minimize() -> null`   # 最小化窗口(webview.windows[0].minimize())

## v1.4 增补(2026-09-02,Task-23)
bridge 新增(显示端小窗形态):
- `set_display_mode(mode: "expand"|"collapse") -> null`   # expand=进全屏,collapse=退回右下角小窗;幂等(目标态=当前态时不碰窗口)
显示端窗口形态:右下角 400×250 无边框小窗常驻(on_top 置顶);页面内按钮一键展开全屏,来号自动展开,末组结束 12s 后自动收回小窗(手动全屏期间不自动收回)

## v1.5 增补(2026-09-03)
GET /api/students/search 匹配优先级调整为:首字母前缀 > 全拼前缀 > **全拼包含(新增)** > 姓名子串
(动机:同班多名学生共用名拼音,如 张嘉琪/王佳琪/李佳琪 均含 "jiaqi",前缀匹配漏人)。
同级排序规则不变(逐字拼音序);响应结构、limit 默认值不变;短语搜索(/api/snippets/search)不变。

## v1.6 增补(2026-09-04,v0.1.7 预备)
bridge 新增(更新横幅真重启,H1):
- `restart() -> null`   # 先以部署位 exe + 本角色参数拉起新进程,再关旧窗口;
  拉起失败退回纯退出。前端 fallback:旧壳(无 restart)调 api.quit()
行为修订:
- 服务器角色 quit():先弹 confirm 确认(关服=全校中断);Alt+F4 等
  旁路由 closing 兜底拦下(M1)
- `--server-url` 钉死地址在服务器不可达时改走离线页 + 3s 重试
  (同机开机竞态:显示端不再加载出打不开的死页)
- 畸形 JSON 请求体一律 400 bad_request,不再 500(M6;login/
  bootstrap_admin 等全部端点)
