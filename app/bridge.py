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
        # 壳层全屏状态跟踪:toggle_fullscreen() 是纯切换(无目标态 API,
        # 后端各自维护 is_fullscreen,Window 未暴露),必须自己记账防双切。
        # 显示端(Task-23)初始即小窗,False 正确;teacher/server 永不全屏。
        self._fullscreen = False

    def speak(self, text: str) -> None:
        self.tts.speak(text)

    def fullscreen(self, on: bool) -> None:
        self.set_display_mode("expand" if on else "collapse")

    def set_display_mode(self, mode: str) -> None:
        """v1.4:显示端形态。'expand' → 全屏;'collapse' → 退回右下角小窗。

        幂等:目标态与当前一致时不碰窗口(toggle 两次会切回去)。非法 mode
        直接忽略,不炸调用方。
        """
        if mode not in ("expand", "collapse"):
            return None
        import webview

        want = mode == "expand"
        if webview.windows and want != self._fullscreen:
            webview.windows[0].toggle_fullscreen()
            self._fullscreen = want
        return None

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
