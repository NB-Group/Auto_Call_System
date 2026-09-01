import pytest

import app.main as main_mod
from app.bridge import Bridge
from app.config import load_config, save_config
from app.tts import TTSService, NullBackend


def test_bridge_surface():
    svc = TTSService(backend=NullBackend(), repeat=1)
    b = Bridge("display", svc)
    assert b.get_role() == "display"
    assert b.app_version() == "0.1.0"
    assert b.speak("测试") is None
    assert b.fullscreen(True) is None
    assert b.quit() is None
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
