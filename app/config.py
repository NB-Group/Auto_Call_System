"""壳配置:data/config.json(角色/服务器地址/更新镜像)。"""
import json
import sys
from pathlib import Path


def base_dir() -> Path:
    """数据目录锚点:frozen(exe)锚定 exe 所在目录,源码运行锚定 CWD。"""
    return (Path(sys.executable).parent if getattr(sys, "frozen", False)
            else Path("."))


CONFIG_PATH = base_dir() / "data" / "config.json"


def load_config() -> dict:
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    # JSON 合法但非对象(如 []/"x")时 {} 兜底:cfg.get(...) 调用方才不炸(#15)。
    return cfg if isinstance(cfg, dict) else {}


def save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2),
                           encoding="utf-8")
