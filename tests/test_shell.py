import inspect
import os

import pytest

import app.main as main_mod
from app.bridge import Bridge
from app.config import load_config, save_config
from app.tts import TTSService, NullBackend


def test_frameless_always_on():
    """C4:自绘标题栏全平台统一 —— FRAMELESS 恒 True,Linux 不再走系统窗框
    (Wayland 移动窗口改用 Super+拖拽)。frameless 传参一律跟随 FRAMELESS
    常量,不得再硬编码 True。"""
    assert main_mod.FRAMELESS is True
    src = inspect.getsource(main_mod)
    assert "frameless=True" not in src, "存在硬编码 frameless=True,应改用 FRAMELESS"
    # create_window 调用点都应显式传 frameless=FRAMELESS(共 5 处:错误/离线/显示/teacher/选角)
    assert src.count("frameless=FRAMELESS") == 5
    # 显示端 resizable 平台分叉独立保留:Linux 放开(GTK 非 resizable 的
    # min=max hint 会让部分 Wayland 合成器全屏仍截留 400×250),Windows 固定。
    assert "resizable=os.name != \"nt\"" in src or "resizable=os.name != 'nt'" in src


def test_set_display_mode_bring_up_before_expand(monkeypatch):
    """C3:expand 前先把窗口拉起 —— restore(取消最小化)→ show(显示+激活)
    → toggle_fullscreen,顺序固定;collapse 不拉起(纯切换);幂等记账不双切。"""
    import webview

    ops = []

    class FakeWin:
        def restore(self):
            ops.append("restore")

        def show(self):
            ops.append("show")

        def toggle_fullscreen(self):
            ops.append("fullscreen")

    monkeypatch.setattr(webview, "windows", [FakeWin()])
    b = Bridge("display", TTSService(backend=NullBackend(), repeat=1))
    b.set_display_mode("expand")
    assert ops == ["restore", "show", "fullscreen"]
    ops.clear()
    b.set_display_mode("collapse")
    assert ops == ["fullscreen"]  # 收回不拉起
    ops.clear()
    b.set_display_mode("expand")  # 状态翻转后再展开:完整拉起序列重来
    assert ops == ["restore", "show", "fullscreen"]


def test_set_display_mode_bring_up_failure_tolerant(monkeypatch):
    """C3 防御:restore 抛错(后端差异)不得挡住 show/fullscreen。"""
    import webview

    ops = []

    class HalfBrokenWin:
        def restore(self):
            raise RuntimeError("backend says no")

        def show(self):
            ops.append("show")

        def toggle_fullscreen(self):
            ops.append("fullscreen")

    monkeypatch.setattr(webview, "windows", [HalfBrokenWin()])
    b = Bridge("display", TTSService(backend=NullBackend(), repeat=1))
    assert b.set_display_mode("expand") is None
    assert ops == ["show", "fullscreen"]


def test_bridge_surface():
    svc = TTSService(backend=NullBackend(), repeat=1)
    b = Bridge("display", svc)
    assert b.get_role() == "display"
    from app import __version__
    assert b.app_version() == __version__  # 跟随 app/__init__,升版免改
    assert b.speak("测试") is None
    assert b.fullscreen(True) is None
    assert b.quit() is None
    assert b.minimize() is None  # v1.3:自绘标题栏最小化
    # v1.4:显示端小窗形态切换(无窗口环境下为无副作用 no-op)
    assert callable(b.set_display_mode)
    assert b.set_display_mode("expand") is None
    assert b.set_display_mode("collapse") is None
    assert b.set_display_mode("nonsense") is None  # 非法 mode 忽略不炸
    svc.stop()


def test_config_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.CONFIG_PATH", tmp_path / "config.json")
    save_config({"role": "teacher"})
    assert load_config()["role"] == "teacher"
    assert load_config().get("server_url") is None


def test_load_config_non_dict_json(tmp_path, monkeypatch):
    """终审 #15:JSON 合法但非对象(如 [])→ {} 兜底,不炸调用方 .get。"""
    monkeypatch.setattr("app.config.CONFIG_PATH", tmp_path / "config.json")
    (tmp_path / "config.json").write_text("[]", encoding="utf-8")
    assert load_config() == {}


def test_parse_args_defaults(monkeypatch):
    from app.main import parse_args
    args = parse_args([])
    assert args.role == "auto" and args.dev is False


def test_start_gui_writes_startup_error(tmp_path, monkeypatch):
    """终审 I9:webview.start() 抛异常(如缺 WebView2)→ 落盘排障后重抛。"""
    import webview

    def boom(*a, **k):
        raise RuntimeError("no WebView2 runtime")

    monkeypatch.setattr(webview, "start", boom)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(RuntimeError):
        main_mod._start_gui()
    err = tmp_path / "data" / "startup-error.txt"
    assert "no WebView2 runtime" in err.read_text(encoding="utf-8")


def test_retry_find_server_loads_url(monkeypatch):
    """终审 I5:后台重试线程找到服务器后 load_url 正式页面。"""
    monkeypatch.setattr(main_mod, "find_server",
                        lambda timeout=3.0: {"host": "10.1.2.3", "port": 8800})
    calls = []

    class FakeWindow:
        def load_url(self, url):
            calls.append(url)

    main_mod._retry_find_server(FakeWindow(), "teacher")
    assert calls == ["http://10.1.2.3:8800/#/teacher"]


def test_retry_find_server_prefers_pinned(monkeypatch):
    """开机竞态(v0.1.7):钉死地址可达时优先于广播发现,且去尾部斜杠。"""
    monkeypatch.setattr(main_mod, "_url_reachable",
                        lambda url: url == "http://127.0.0.1:8800/")
    monkeypatch.setattr(main_mod, "find_server",
                        lambda timeout=3.0: {"host": "10.9.9.9", "port": 8800})
    calls = []

    class FakeWindow:
        def load_url(self, url):
            calls.append(url)

    main_mod._retry_find_server(FakeWindow(), "display",
                                pinned="http://127.0.0.1:8800/")
    assert calls == ["http://127.0.0.1:8800/#/display"]


def test_resolve_server_url_pinned_unreachable(monkeypatch):
    """钉死地址探不通 → None → 走离线页重试,不加载打不开的死页。"""
    monkeypatch.setattr(main_mod, "_url_reachable", lambda url: False)
    assert main_mod.resolve_server_url("http://127.0.0.1:8800", False) is None
    monkeypatch.setattr(main_mod, "_url_reachable", lambda url: True)
    assert main_mod.resolve_server_url("http://127.0.0.1:8800", False) \
        == "http://127.0.0.1:8800"


def test_restart_relanches_then_quits(monkeypatch, tmp_path):
    """H1:更新横幅「重启」先拉新进程再退旧窗(纯退出=显示端黑屏)。"""
    import subprocess
    import webview

    exe = tmp_path / "call-center.exe"
    exe.write_bytes(b"x")
    monkeypatch.setattr("sys.argv", [str(exe)])
    spawned, destroyed = [], []

    class FakeWin:
        def destroy(self):
            destroyed.append(1)

    monkeypatch.setattr(webview, "windows", [FakeWin()])
    monkeypatch.setattr(subprocess, "Popen",
                        lambda args, **k: spawned.append(args))

    b = Bridge("display", TTSService(backend=NullBackend(), repeat=1))
    b.restart()
    assert spawned == [[str(exe), "--role", "display"]]
    assert destroyed == [1]  # 拉起成功也要退旧窗


def test_restart_falls_back_to_quit_when_no_exe(monkeypatch):
    """拿不到部署位(如源码运行):退回纯退出,不得炸。"""
    import webview

    monkeypatch.setattr("sys.argv", ["not-an-exe.py"])
    destroyed = []

    class FakeWin:
        def destroy(self):
            destroyed.append(1)

    monkeypatch.setattr(webview, "windows", [FakeWin()])
    b = Bridge("teacher", TTSService(backend=NullBackend(), repeat=1))
    b.restart()
    assert destroyed == [1]


def test_server_quit_requires_confirmation(monkeypatch):
    """M1:服务器角色 × 弹 confirm,取消 → 不关;同意 → 关。"""
    import webview

    destroyed = []

    class FakeWin:
        def __init__(self, answer):
            self._answer = answer

        def evaluate_js(self, js):
            assert "confirm" in js
            return self._answer

        def destroy(self):
            destroyed.append(1)

    b = Bridge("server", TTSService(backend=NullBackend(), repeat=1))
    monkeypatch.setattr(webview, "windows", [FakeWin(False)])
    b.quit()
    assert destroyed == []          # 取消:拦下
    monkeypatch.setattr(webview, "windows", [FakeWin(True)])
    b.quit()
    assert destroyed == [1]         # 同意:真关
    b.quit()                        # 已确认过(旗标):二次直接关
    assert len(destroyed) == 2


def test_teacher_quit_no_confirmation(monkeypatch):
    """非服务器角色关窗不弹确认(体验不回退)。"""
    import webview

    destroyed, js = [], []

    class FakeWin:
        def evaluate_js(self, j):
            js.append(j)

        def destroy(self):
            destroyed.append(1)

    monkeypatch.setattr(webview, "windows", [FakeWin()])
    Bridge("teacher", TTSService(backend=NullBackend(), repeat=1)).quit()
    assert destroyed == [1] and js == []
