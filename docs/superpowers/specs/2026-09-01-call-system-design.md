# 校园叫号系统(Call Center)设计文档

日期:2026-09-01
状态:已与用户逐节确认(架构/交互/视觉/TTS/构建发布/多agent协作)

## 1. 背景与目标

老师常请学生到办公室(订正作业等),教室与办公室距离远,需要局域网叫号系统。
全校电脑同一网段。为推广全校做准备:多班级路由、多老师账号。

**目标**
- 老师端:登录 → 拼音首字母搜索学生(敲 `lhw` 回车选中 `梁皓文`)→ 可选拼装短语消息 → 叫号
- 显示端(教室大屏):按班级订阅,大字卡片 + TTS 语音播报
- 中央服务器:账号/名单/历史统一存放,SQLite 单文件
- GitHub Actions 自动构建(Nuitka/Windows),自动更新走镜像源列表自动尝试
- UI 移植 GulyGuly(BewlyBewly 系)设计语言:毛玻璃 + 渐变背景 + 明暗双主题 + View Transition 圆形揭示

**非目标(明确不做)**
- 排队/状态机("订正中/已完成"之类,老师以后要加再加)
- 统计报表、手机端、公网访问、学生自助取号
- 服务器自动更新(它挂了全班没信号,更新由管理员手动执行)

## 2. 总体架构

单代码库,一个 exe,启动时选角色:**服务器 / 老师端 / 显示端**(记住选择,可改)。

```
学校局域网(同一网段)
  服务器模式(办公室常驻机,开机自启,托盘)
    ├ aiohttp:HTTP API + WebSocket + 静态托管前端
    ├ UDP 广播(端口 50000,每 3s):{服务名, HTTP端口, 版本}
    └ SQLite data/call.db(WAL 模式)
  老师端 ×N:发现服务器 → pywebview 加载 http://<server>/#/teacher
  显示端 ×N:发现服务器 → 加载 /#/display,选班级订阅
```

- **发现**:客户端监听 UDP 广播 2s 即得地址,零配置;找不到显示引导页持续重试
- **前端由服务器统一托管**:客户端壳只做发现/加载/bridge(TTS·全屏),UI 更新随服务器走,客户端 exe 不必重发
- **断线**:客户端心跳 + 自动重连,UI 玻璃横幅提示;服务器重启后 SQLite 恢复
- 兜底:若无专用服务器机器,任意教室电脑跑服务器模式(作息同步,到校即开机)

## 3. 数据模型(SQLite,WAL)

```sql
settings(key TEXT PRIMARY KEY, value TEXT)            -- schema_version...
teachers(id, username UNIQUE, password_hash,          -- bcrypt
         role,                                        -- 'teacher' | 'admin'
         display_name, office,                        -- "郑老师","203办公室"
         default_template, created_at, disabled)
classes(id, name UNIQUE, ord)                         -- "高二(3)班"
students(id, class_id FK, name, student_no,
         pinyin_full, pinyin_initials)                -- 导入时 pypinyin 预计算,建索引
snippets(id, teacher_id FK, text,                     -- 短语库(每老师私有)
         use_count, created_at)
calls(id, student_id FK, class_id FK, teacher_id FK,
      message, created_at, retracted_at NULL)         -- 只追加,1 分钟内可撤销
sessions(token PRIMARY KEY, teacher_id FK, created_at) -- 重启不掉线
```

- 首次启动服务器:引导创建管理员账号(用户名+密码,写入 teachers 表 role='admin';无默认密码、无默认账号)
- 管理员登录任意客户端即得管理后台:建老师账号、导班级名单(粘贴文本/CSV,一行一姓名)、看叫号历史
- 播报文本 = `{学生}请到{老师}{办公室}` + 短语顿号连接;办公室来自老师资料

## 4. 接口契约(多 agent 冻结点,详见实现期 docs/CONTRACTS.md)

实现期第一节就是把这些抄进 `docs/CONTRACTS.md` 并冻结。**任何 agent 不得自行偏离契约;改契约 = 主 agent 先改文档再重新派发**。

**HTTP(均 JSON,鉴权头 `Authorization: Bearer <token>`)**
```
POST /api/auth/login        {username,password} → {token, role, display_name, office}
POST /api/auth/logout
GET  /api/me                → 老师/管理员信息 + 默认模板
PUT  /api/me                {display_name?,office?,default_template?}
GET  /api/students/search?q=&limit=   → [{id,name,class_name,pinyin_initials}]
  匹配优先级:首字母前缀 > 全拼前缀 > 姓名子串
POST /api/calls             {student_id, message?} → {call}     # 老师
DELETE /api/calls/{id}      # 60s 内可撤销
GET  /api/calls/today       → 今日已叫(本老师视角)
GET  /api/snippets          → 短语库(按 use_count 降序)
POST /api/snippets          {text}
DELETE /api/snippets/{id}
# 以下管理员(role=admin)
GET/POST/PUT/DELETE /api/admin/teachers
GET/POST/DELETE     /api/admin/classes
POST /api/admin/classes/{id}/students  {text|csv}  → {imported,skipped}
GET                 /api/admin/calls?date=
```

**WebSocket `/ws?token=`(JSON 消息,双向)**
```
客户端→服务器:{"type":"subscribe","class_id":3}
服务器→显示端:{"type":"call","call":{"id","student_name","class_name",
                "teacher_name","office","message","created_at"}}
              {"type":"retract","call_id":...}
              {"type":"hello"}   # 连接/重连成功
```

**UDP 发现包(50000 端口,JSON,utf-8)**
```
{"app":"call-center","port":8800,"version":"0.1.0"}
```

**pywebview bridge(壳暴露给前端,`window.pywebview.api`)**
```
speak(text) -> null            # TTS 入队(显示端)
fullscreen(on: bool) -> null
get_role() -> "server"|"teacher"|"display"
app_version() -> "0.1.0"
quit() -> null
```

**自动更新清单 latest.json(每个 Release 附带)**
```
{"version":"0.2.0","notes":"...","asset":"叫号系统-0.2.0-x64.exe",
 "sha256":"...","size":12345678}
```

## 5. 三端交互

### 老师端
- 单窗口,顶部 64px 毛玻璃 Dock(头像/主题切换/设置),主区 = 常驻聚焦搜索拼装台 + 今日已叫列表
- 流:敲 `lhw` → 下拉 `梁皓文 高二(3)` → 回车选中 → 搜索框变拼装台:
  - 直接回车 = 无附加消息发送(最快路径)
  - 敲 `dz` 过滤短语(`✚订正数学作业`)→ 回车挂 chip,可多个
  - Tab = 自由文本任意输入
  - 回车发送 → toast 成功 + 播报已触发;今日已叫列表顶部插入(60s 内可撤销)
- 短语管理独立编辑页:添加/删除/使用频率排序

### 显示端
- 首次选班级(记住),之后全屏零操作,重启自动恢复
- 强制深色主题(投影近黑底最 readable):当前叫号 hero 卡(姓名 12vw 大字 + 消息 chips),新叫滑入(overshoot);底部走马灯今日已叫;待机 = 大时钟 + 班级名
- 新叫号:卡片滑入 + TTS(0.9× 语速,播两遍,间隔 800ms);多条连叫顺序播报不重叠
- 无中文语音 → 提示音 + 屏幕高亮降级

### 管理后台(管理员登录即见)
卡片式表格:老师账号、班级与名单导入、叫号历史、系统信息

## 6. 视觉系统(GulyGuly DNA)

技术栈:**Vue 3 + Vite + UnoCSS attributify**(与 GulyGuly 同栈)。

Token(精简自有版,命名同源便于移植):
- `--glass-1: blur(24px) saturate(180%) brightness(1.04)`;内容层透明度 0.62 + edge-glow 内阴影
- 背景:浅 `hsl(240 31% 96%)→白` / 深 `hsl(230 12% 8%)→4%` 纵向渐变
- 圆角 12px;四级阴影;文字 `--text-1/2/3/4`(hsl 215 19% 系)
- 动效:180/330/550ms 档;`cubic-bezier(0.22,1,0.36,1)` 平滑 + overshoot 进场;`prefers-reduced-motion` 全降 0
- 主题色 `hsl(195 100% 42%)`,`color-mix` 生成 -10~-90 十级
- 明暗跟随系统 + 手动切换,**View Transition 圆形揭示**(点击坐标扩散,处理 WebView2 非整数 dpr 偏移:GulyGuly 的 `transform:none!important` 修法一并移植)
- 显示端强制深色;字体系统栈(Segoe UI/MiSans/PingFang/Noto Sans CJK)

## 7. TTS 抽象

```python
class TTSProvider(Protocol):
    def speak(self, text: str) -> None: ...
    def is_available(self) -> bool: ...
Windows → SAPI(SpVoice,Huihui/Kangkang/Yaoyao,离线)
Linux   → espeak-ng(开发调试,音质机械但全链路可验)
CI      → Null(静默,验证时序)
```
bridge 只认 `api.speak(text)`,环境变量 `TTS=espeak|none` 可切;播报队列化。

## 8. 构建 · 发布 · 自动更新

```
Auto_Call_System/
├─ server/        # aiohttp + SQLite + UDP 广播
├─ app/           # pywebview 壳(角色选择/发现/bridge)
├─ frontend/      # Vue3+Vite+UnoCSS → dist/ 由服务器托管
├─ scripts/       # 打包辅助
└─ .github/workflows/
   ├─ ci.yml      # push: pytest + vitest + build + Nuitka 试编译
   └─ release.yml # tag v*: windows-latest 编译 → Release 附 exe+latest.json+SHA256
```

- **Nuitka `--onefile`** 在 windows runner 编译(本地 Linux 零 Windows 环境);WebView2 运行时 Win10/11 自带,缺失时给下载引导
- 版本号 `app/__init__.py` 的 `__version__`,与 tag 一致

**自动更新(镜像源列表自动尝试)**
- 每个 Release 附 `latest.json`(版本/下载名/sha256/notes)——**文件下载所有前缀镜像通用**,不依赖任何镜像反代 api.github.com
- 客户端启动时按序探测(并发,3s 超时,取首个 200):
  1. 直连 `https://github.com/<repo>/releases/latest/download/latest.json`
  2. `https://gh-proxy.org/` + 同路径(gh-proxy 2025-11 新域名)
  3. `https://ghfast.top/`
  4. `https://ghproxy.net/`
  5. `https://ghproxy.homeboyc.cn/`
  6. `https://gh.zwy.one/`
- 下载 exe 同样按存活镜像列表逐个试;**SHA256 校验**(另从 raw.githubusercontent 经镜像取 checksums 交叉核对,防单镜像投毒)
- 下载到临时文件,退出时替换自身重启;更新是提示而非强制
- 镜像列表界面可编辑;全部超时 → 静默跳过下次再试
- 镜像可用性随时间变化,已知死亡:ghproxy.com(原域名)、ghgo.xyz、ghp.ci;发布站 https://ghproxy.link/ 可查最新

## 9. 错误处理

- 客户端:UDP 发现失败 → 引导页持续重试;WS 断开 → 横幅 + 指数退避重连;登录失败/无权限 → 明确文案
- 服务器:SQLite WAL 抗断电;端口被占 → 明确报错;单写者足够(叫号 QPS 极低)
- 更新:所有源失败静默降级;校验失败拒绝安装并回滚

## 10. 测试

- pytest:发现协议、登录鉴权、search 匹配优先级、叫号/撤销窗口、WS 班级路由、导入去重
- vitest:拼音匹配(共享同一份匹配 spec 用例)、命令面板状态机(选生→拼装→发送)、latest.json 解析与镜像选择
- 契约一致性:CI 用同一份 JSON Schema 校验 server 响应与 frontend 解析(防 API 对不上)
- GitHub Actions 全跑;Linux 本机可全链路三进程联调(server+teacher+display,TTS=espeak)

## 11. 多 agent 协作机制(契约先行)

1. **第一步只做一件事**:主 agent 抄第 4 节 → `docs/CONTRACTS.md` + JSON Schema 文件 → 冻结
2. 分工(每 agent 拿到 CONTRACTS.md 全文 + 自己的边界):
   - A:server(aiohttp 全部端点 + WS + UDP + SQLite)
   - B:frontend 骨架 + token 系统 + 登录/管理后台
   - C:老师端命令面板 + 短语(对 mock 契约开发)
   - D:显示端大屏 + 动效
   - E:pywebview 壳 + TTS 抽象 + 自动更新/镜像
   - F:CI/release workflow + Nuitka 打包脚本
3. **规则**:任何 agent 需要契约变化 → 停下报主 agent,主 agent 改 CONTRACTS.md 后广播受影响 agent;禁止两边私改接口
4. 集成阶段:server 起真服务,替换 mock,B/C/D 跑契约一致性测试过关才算完

## 12. 里程碑

1. M1 契约冻结 + server 全绿(pytest)
2. M2 三端 UI 完成(对 mock)+ Linux 三进程联调含 espeak TTS
3. M3 真集成 + 契约一致性测试全过
4. M4 CI/release 打通,产出首个 Windows exe,自动更新镜像链路验证
5. M5 视觉打磨(动效/双主题/圆形揭示)+ 学校实测
