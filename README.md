# 校园叫号系统

老师办公室叫学生来订正作业,教室大屏实时显示 + 语音播报。局域网零配置。

## 角色
- **服务器**:办公室一台白天开机的电脑,开机自启。数据(SQLite)都在这台。
- **老师端**:登录 → 敲拼音首字母(`lhw` → 梁皓文)→ 回车选中 → 可选拼短语(`dz` → 订正数学作业,Tab 自由输入)→ 回车发送。
- **显示端**:教室电脑,选一次班级后全自动,大字 + TTS 播报两遍。

## 部署(学校)
1. 服务器电脑跑 `call-center-<版本>-x64.exe`(GitHub Release 下载),首次选「服务器」角色,窗口即引导页:建管理员 → 添加老师 → 导入班级名单。
2. 老师端 / 显示端电脑跑同一个 exe,首次运行选对应角色,自动发现服务器,零配置。

## 开发(Linux)
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
corepack enable && pnpm --dir frontend install
scripts/dev_all.sh          # 服务器前台 + vite;浏览器开三个角色页面(浏览器模式无语音)
```
后端测试:`pytest -v`;前端:`pnpm --dir frontend test`。

## 发布
push tag 即自动构建 Windows 单文件(仓库 `NB-Group/Auto_Call_System`,私有):
```bash
git tag v0.2.0 && git push --tags
```
v0.1.0 已发布;Release 附 `call-center-<版本>-x64.exe` 与 `latest.json`,客户端启动自动经镜像列表检查更新(设置里可改 repo/镜像)。

## 换服务器机器
拷走 `data/`(call.db + config.json)到新机,新机以服务器模式启动即可。

## 排障(Windows)
- **双击 exe 无反应 / 闪退**:看 exe 旁 `data/startup-error.txt`(启动异常的完整堆栈都落在这里;排障后删除该文件即可,不影响数据)。把堆栈发给我即可定位。
- **提示/日志指向 WebView2 缺失**:安装 [WebView2 运行时](https://developer.microsoft.com/microsoft-edge/webview2/)后重开程序(绝大多数 Win11 已自带;部分精简版 LTSC 需手装)。

## 设计文档
`docs/superpowers/specs/2026-09-01-call-system-design.md` · 接口契约 `docs/CONTRACTS.md`
