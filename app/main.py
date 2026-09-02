"""入口:角色解析 → 发现/启动服务器 → 打开 pywebview 窗口。"""
import argparse
import json
import sys
import threading
import time
import traceback

import webview

from app import __version__
from app.bridge import Bridge
from app.config import load_config, save_config
from app.discovery import find_server
from app.tts import TTSService

DEV_URL = "http://127.0.0.1:5173"

# Task-23 显示端小窗:右下角常驻尺寸 + 距屏幕边缘留白
DISPLAY_W, DISPLAY_H = 400, 250
DISPLAY_MARGIN = 16


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

    # 更新:先换上已暂存的新版(frozen 才生效,本地操作,快)。
    # 新版探测+下载移入后台线程:镜像探测 3-4s 起步、下载更久,
    # 不能挡在窗口创建前(否则老师/显示端每次启动都白等数秒)。
    from app.updater import install_pending
    install_pending()

    if role == "server":
        from server.serve import start_server
        try:
            start_server(static_dir=None)
        except Exception as e:  # 端口占用等:弹窗报错,不静默退(I6)
            webview.create_window("服务器启动失败", html=_error_html(str(e)),
                                  js_api=bridge, frameless=True,
                                  easy_drag=False)
            _start_gui()
            return
        url = "http://127.0.0.1:8800/#/server"
    else:
        url = resolve_server_url(args.server_url, args.dev)
        if url is None:
            window = webview.create_window("叫号系统", _offline_html(),
                                           js_api=bridge, frameless=True,
                                           easy_drag=False)
            if role in ("teacher", "display"):
                threading.Thread(target=_stage_and_notify, args=(window,),
                                 daemon=True).start()
                threading.Thread(target=_retry_find_server,
                                 args=(window, role), daemon=True).start()
            _start_gui()
            return
        url = f"{url}/#/{role}"

    # frameless + easy_drag=False(Task-21 自绘标题栏):拖拽只认页面里
    # .pywebview-drag-region 元素(壳注入的 customize.js 机制);easy_drag
    # 默认开着会把「整页」变成拖拽区,列表/表单全没法正常按住,必须关。
    if role == "display":
        # Task-23:显示端不再常驻 fullscreen,改为右下角小窗(一键/来号自动
        # 全屏,由前端 set_display_mode 驱动)。on_top:winforms/gtk 均支持
        # (winforms TopMost / gtk set_keep_above)。位置走创建参数 x/y ——
        # 两个后端都消费 initial_x/initial_y;不使用 window.move()(其
        # _shown_call 装饰器会阻塞等待 shown 事件,主线程 start 前调用会卡)。
        kwargs = dict(width=DISPLAY_W, height=DISPLAY_H, resizable=False,
                      on_top=True)
        pos = _display_corner_pos()
        if pos is not None:
            kwargs["x"], kwargs["y"] = pos
        window = webview.create_window(f"叫号系统 v{__version__}", url,
                                       js_api=bridge, frameless=True,
                                       easy_drag=False, **kwargs)
    else:
        window = webview.create_window(f"叫号系统 v{__version__}", url,
                                       js_api=bridge, frameless=True,
                                       easy_drag=False)
    # 服务器角色不自动更新(它是其他端的源头,由管理员手动控制)。
    if role in ("teacher", "display"):
        threading.Thread(target=_stage_and_notify, args=(window,),
                         daemon=True).start()
    _start_gui()
    tts.stop()


def _display_corner_pos():
    """显示端小窗初始位置:主屏右下角(webview.screens[0],logical px)。

    webview.screens 是 module_property(免括号访问),内部 initialize()
    GUI 库后取显示器几何;任何失败(无头/异常后端)返回 None → 落回
    pywebview 默认居中,可接受。
    """
    try:
        screens = webview.screens
        if not screens:
            return None
        s = screens[0]
        return (s.x + s.width - DISPLAY_W - DISPLAY_MARGIN,
                s.y + s.height - DISPLAY_H - DISPLAY_MARGIN)
    except Exception:
        return None


def _stage_and_notify(window) -> None:
    """后台探测新版并下载暂存,成功后向前端派发 cc-update 事件。

    pywebview evaluate_js 线程安全;窗口未加载完成时调用无害(吞错)。
    """
    try:
        from app.updater import stage_update, update_config
        repo, mirrors = update_config()
        m = stage_update(__version__, repo, mirrors)
        if not m:
            return
        time.sleep(5)  # 等待 UI ready(前端 App.vue 已挂载并注册 cc-update 监听)
        detail = json.dumps({"version": m["version"], "notes": m["notes"]},
                            ensure_ascii=False)
        window.evaluate_js(
            "window.dispatchEvent(new CustomEvent('cc-update',"
            f"{{detail:{detail}}}))")
    except Exception:
        pass  # 更新是尽力而为:任何失败都不得影响主窗口


def _retry_find_server(window, role: str) -> None:
    """离线重试:每 3s 找一次服务器,找到即把窗口切到正式页面(I5)。

    load_url 线程安全(pywebview 内部派发到 GUI 线程);窗口已被用户
    关闭时抛错,吞掉即止。窗口关闭 → webview.start() 返回 → 进程正常退出。
    """
    while True:
        found = find_server(timeout=3.0)
        if found is not None:
            try:
                window.load_url(
                    f"http://{found['host']}:{found['port']}/#/{role}")
            except Exception:
                pass
            return
        time.sleep(3.0)


def _start_gui() -> None:
    """webview.start() 统一包装:GUI 起不来(如缺 WebView2)时落盘排障(I9)。

    无控制台的打包 exe 里异常一闪而过;写 data/startup-error.txt 到
    base_dir 旁,再重抛(有控制台的场景 stderr 仍可见)。
    """
    try:
        # private_mode=False(Task-21 登录态留存):默认 ephemeral,关窗即丢
        # localStorage → 每次开应用都要重新登录。关掉后 WebView2 用户数据
        # 落 %APPDATA%\pywebview(pywebview init_storage 语义),更新覆盖
        # exe 也不受影响。http 端口:本应用窗口全是远程 URL/内联 HTML,
        # 不会启用 pywebview 内置 server,无固定端口冲突。
        webview.start(private_mode=False)
    except Exception:
        tb = traceback.format_exc()
        print(tb, file=sys.stderr)
        try:
            from app.config import base_dir
            err_dir = base_dir() / "data"
            err_dir.mkdir(parents=True, exist_ok=True)
            (err_dir / "startup-error.txt").write_text(tb, encoding="utf-8")
        except OSError:
            pass  # 落盘也失败:只剩重抛
        raise


def _pick_role_dialog():
    """首启角色选择:pywebview 按钮小窗(C1)。

    打包后无控制台,控制台 input() 必 EOFError 崩溃 → GUI 选择。
    直接关窗不选 → None → 进程安静退出(下次启动再问)。
    """
    holder: dict = {}
    webview.create_window("选择本机角色", html=_picker_html(),
                          js_api=_PickerApi(holder), width=560, height=470,
                          resizable=False, frameless=True, easy_drag=False)
    _start_gui()
    return holder.get("role")


class _PickerApi:
    """角色选择窗 js_api:记录所选角色并关窗。"""

    def __init__(self, holder: dict):
        self.holder = holder

    def choose(self, role: str) -> None:
        self.holder["role"] = role
        if webview.windows:
            webview.windows[0].destroy()

    def quit(self) -> None:
        # frameless 无系统关闭钮:× 走这里,行为同旧版直接关窗(不选即退)
        if webview.windows:
            webview.windows[0].destroy()


def _chrome_bar(title: str) -> str:
    """frameless 内联页共用的迷你标题栏:拖拽区 + 关闭钮。

    pywebview 注入的 customize.js 令 .pywebview-drag-region 元素可拖窗;
    关闭钮 stopPropagation 防误拖。两个 js_api(Bridge/_PickerApi)都有 quit。
    """
    return (f"<div class='bar pywebview-drag-region'><span>{title}</span>"
            f"<button onmousedown='event.stopPropagation()' "
            f"onclick='pywebview.api.quit()'>&times;</button></div>")


def _picker_html() -> str:
    return """<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;height:100vh;display:flex;flex-direction:column;
justify-content:center;align-items:center;font-family:'Microsoft YaHei',
system-ui,sans-serif;background:linear-gradient(135deg,#16283f,#0b1220);
color:#fff}
h2{margin:0 0 4px;font-size:22px;font-weight:600}
p{margin:0 0 22px;font-size:13px;opacity:.65}
.menu{display:flex;flex-direction:column;gap:14px;width:78%}
button{padding:16px 20px;font-size:19px;color:#fff;cursor:pointer;
border:1px solid rgba(255,255,255,.22);border-radius:14px;
background:rgba(255,255,255,.07);transition:background .15s;text-align:center}
button:hover{background:rgba(255,255,255,.16)}
small{display:block;font-size:12px;opacity:.6;margin-top:4px}
.bar{position:fixed;top:0;left:0;right:0;height:36px;display:flex;
align-items:center;justify-content:space-between;padding:0 14px;
font-size:13px;opacity:.8;cursor:default;user-select:none}
.bar button{padding:0 10px;font-size:17px;line-height:36px;border:none;
border-radius:8px;background:transparent}
.bar button:hover{background:rgba(255,255,255,.16)}
</style></head><body>
""" + _chrome_bar("叫号中心") + """
<h2>首次运行:选择本机角色</h2>
<p>选择会保存在本机,下次启动不再询问</p>
<div class="menu">
<button onclick="pywebview.api.choose('server')">服务器<small>办公室常驻机</small></button>
<button onclick="pywebview.api.choose('teacher')">老师端</button>
<button onclick="pywebview.api.choose('display')">显示端<small>教室大屏</small></button>
</div></body></html>"""


_MINI_BAR_CSS = (
    ".bar{position:fixed;top:0;left:0;right:0;height:36px;display:flex;"
    "align-items:center;justify-content:space-between;padding:0 14px;"
    "font-size:13px;color:#333;cursor:default;user-select:none}"
    ".bar button{padding:0 10px;font-size:17px;line-height:36px;"
    "border:none;border-radius:8px;background:transparent;cursor:pointer}"
    ".bar button:hover{background:rgba(0,0,0,.08)}"
)


def _offline_html() -> str:
    return ("<html><head><style>" + _MINI_BAR_CSS + "</style></head>"
            "<body style='font-family:sans-serif;padding:56px 40px 40px'>"
            + _chrome_bar("叫号中心")
            + "<h2>正在寻找叫号服务器…</h2>"
            "<p>找到后自动进入(也可关闭后重开)。</p>"
            "</body></html>")


def _error_html(err: str) -> str:
    import html as html_escape
    return ("<html><head><style>" + _MINI_BAR_CSS + "</style></head>"
            "<body style='font-family:sans-serif;padding:56px 40px 40px'>"
            + _chrome_bar("叫号中心")
            + "<h2>服务器启动失败</h2>"
            f"<p style='color:#b00'>{html_escape.escape(err)}</p>"
            "<p>端口被占用?是否已开了一个实例?</p>"
            "</body></html>")


if __name__ == "__main__":
    main()
