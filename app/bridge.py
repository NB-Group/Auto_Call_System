"""pywebview js_api(CONTRACTS bridge)。

`import webview` 放在方法内而非模块顶:无显示/无 GTK 的环境(测试、CI)
可纯构造 Bridge,只有真正动窗口(fullscreen/quit)才触碰 webview。
"""
import json

from app import __version__
from app.updater import DEFAULT_MIRRORS


class Bridge:
    def __init__(self, role: str, tts: "TTSService"):
        self.role = role
        self.tts = tts

    def speak(self, text: str) -> None:
        self.tts.speak(text)

    def fullscreen(self, on: bool) -> None:
        import webview

        if webview.windows:
            webview.windows[0].toggle_fullscreen()

    def get_role(self) -> str:
        return self.role

    def app_version(self) -> str:
        return __version__

    def quit(self) -> None:
        import webview

        if webview.windows:
            webview.windows[0].destroy()

    def minimize(self) -> None:
        import webview

        if webview.windows:
            webview.windows[0].minimize()

    def get_update_config(self) -> str | None:
        # 角色门控:更新源配置只有服务器端可读写。老师/显示端页面走明文
        # HTTP,LAN 内注入的 JS 不得借此投毒 repo/mirrors 绕过 sha256 quorum。
        if self.role != "server":
            return None
        from app.config import load_config
        cfg = load_config().get("update", {})
        return json.dumps({
            "repo": cfg.get("repo", "NB-Group/Auto_Call_System"),
            "mirrors": cfg.get("mirrors") or DEFAULT_MIRRORS,
        }, ensure_ascii=False)

    def set_update_config(self, repo: str, mirrors_json: str) -> None:
        if self.role != "server":
            return None
        from app.config import load_config, save_config
        cfg = load_config()
        cfg["update"] = {"repo": repo,
                         "mirrors": json.loads(mirrors_json)}
        save_config(cfg)
