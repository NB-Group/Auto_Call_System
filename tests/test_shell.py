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


def test_parse_args_defaults(monkeypatch):
    from app.main import parse_args
    args = parse_args([])
    assert args.role == "auto" and args.dev is False
