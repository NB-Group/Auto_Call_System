"""pywebview js_api(CONTRACTS bridge)。

`import webview` 放在方法内而非模块顶:无显示/无 GTK 的环境(测试、CI)
可纯构造 Bridge,只有真正动窗口(fullscreen/quit)才触碰 webview。
"""
from app import __version__


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
