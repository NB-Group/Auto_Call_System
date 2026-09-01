"""入口:角色解析 → 发现/启动服务器 → 打开 pywebview 窗口。"""
import argparse
import json

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

    # 更新:先换上已暂存的新版(frozen 才生效),再为非服务器角色探新版。
    # 服务器角色不自动更新(它是其他端的源头,由管理员手动控制)。
    from app.updater import install_pending, stage_update, update_config
    install_pending()
    update_manifest = None
    if role in ("teacher", "display"):
        repo, mirrors = update_config()
        update_manifest = stage_update(__version__, repo, mirrors)

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
    if update_manifest:
        def notify():
            detail = json.dumps(
                {"version": update_manifest["version"],
                 "notes": update_manifest["notes"]}, ensure_ascii=False)
            window.evaluate_js(
                "window.dispatchEvent(new CustomEvent('cc-update',"
                f"{{detail:{detail}}}))")
        window.events.loaded += notify
    webview.start()
    tts.stop()


def _pick_role_dialog():
    """无 GUI 组建可用前的极简角色选择:控制台。"""
    print("首次运行,选择本机角色:")
    print("  1. 服务器(办公室常驻机)")
    print("  2. 老师端")
    print("  3. 显示端(教室大屏)")
    choice = input("输入 1/2/3 对应数字: ").strip()
    return {"1": "server", "2": "teacher", "3": "display"}.get(choice)


def _offline_html() -> str:
    return ("<html><body style='font-family:sans-serif;padding:40px'>"
            "<h2>未找到叫号服务器</h2>"
            "<p>请确认办公室服务器电脑已开启;本窗口关闭后将自动重试。</p>"
            "</body></html>")


if __name__ == "__main__":
    main()
