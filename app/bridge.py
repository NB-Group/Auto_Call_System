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

        expand 前先把窗口拉起:叫号时显示窗可能被最小化/被别的窗口盖住,
        只 toggle_fullscreen 会"无感"全屏。pywebview 6.x Window.restore()
        = 取消最小化(winforms WindowState.Normal / gtk deiconify+present),
        Window.show() = 显示并激活(winforms Show+Activate);gtk 的 present
        同样带前置聚焦,无独立 focus API。各后端实现有差异,逐个 try:
        单步失败只少拉起一招,不挡全屏切换。collapse 不拉起(收回去即可)。
        """
        if mode not in ("expand", "collapse"):
            return None
        import webview

        want = mode == "expand"
        if webview.windows and want != self._fullscreen:
            win = webview.windows[0]
            if want:
                for bring_up in (win.restore, win.show):
                    try:
                        bring_up()
                    except Exception:
                        pass
            win.toggle_fullscreen()
            self._fullscreen = want
        return None

    def get_role(self) -> str:
        return self.role

    def app_version(self) -> str:
        return __version__

    def quit(self) -> None:
        import webview

        # M1:服务器角色的 × 不是普通关窗 —— daemon 服务器线程随进程
        # 死,全校叫号静默中断。弹一次 JS confirm,同意才真关;main.py
        # 的 closing 兜底拦 Alt+F4 等旁路。evaluate_js 在 js_api 线程里
        # 调用,GUI 线程空闲,标准用法无死锁。
        if self.role == "server" and not getattr(self, "_allow_close", False):
            try:
                ok = webview.windows[0].evaluate_js(
                    "confirm('这是服务器:关闭后全校叫号会中断。\\n"
                    "确定要关闭吗?')")
            except Exception:
                ok = True  # 判定失败不锁死人
            if not ok:
                return None
            self._allow_close = True
        if webview.windows:
            webview.windows[0].destroy()

    def restart(self) -> None:
        """更新横幅「立即重启」(H1 修复):真重启,不是纯退出。

        先拉起新进程再退旧窗口:顺序不能反,否则 display 这类无自启的
        角色退出后没人拉起,黑屏到有人手动重开。新进程用部署位 exe
        (original_exe_path,onefile 下 sys.executable 是临时解包文件)
        带上本角色参数;拉起失败退回纯退出(横幅仍在,重开即新版)。
        """
        import subprocess

        from app.config import original_exe_path

        exe = original_exe_path()
        if exe is not None:
            try:
                subprocess.Popen(
                    [str(exe), "--role", self.role],
                    cwd=str(exe.parent),
                    close_fds=True,
                )
            except OSError:
                pass  # 拉不起:退回纯退出,保守不炸
        self.quit()

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
