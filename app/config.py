"""壳配置:data/config.json(角色/服务器地址/更新镜像)。"""
import json
import os
import shutil
import sys
from pathlib import Path

# 一次性迁移哨兵:base_dir() 每次导入/调用只迁一回(见 _migrate_legacy)。
_migrated = False


def base_dir() -> Path:
    """数据目录锚点(Task-21):frozen(exe)→ %APPDATA%/call-center,
    源码运行锚定 CWD。

    旧版锚在 exe 旁,更新覆盖 exe 时整目录陪葬;迁出后 config/db/
    updates/startup-error 全部落在新址,升级不再丢数据。
    """
    if not getattr(sys, "frozen", False):
        return Path(".")
    root = Path(os.environ.get("APPDATA") or Path.home()) / "call-center"
    _migrate_legacy(root)
    return root


def _migrate_legacy(root: Path) -> None:
    """旧 exe 旁的 data/ 与 updates/ 一次性搬入新址(幂等,尽力而为)。

    - data/:config/db/startup-error;新址已有 data 则不搬(重复启动)。
    - updates/:捎带已暂存的 pending.exe —— 否则旧版暂存的新 exe 会永远
      躺在旧址,新版 UPDATE_DIR 指向新址装不到它(升级断链一拍)。
    - 任何失败(占用/权限)静默放弃:读旧写新,下次启动再试。
    """
    global _migrated
    if _migrated:
        return
    _migrated = True
    exe_dir = Path(sys.executable).parent
    try:
        if (exe_dir / "data").is_dir() and not (root / "data").exists():
            root.mkdir(parents=True, exist_ok=True)
            shutil.move(str(exe_dir / "data"), str(root / "data"))
        if (exe_dir / "updates").is_dir() and not (root / "updates").exists():
            root.mkdir(parents=True, exist_ok=True)
            shutil.move(str(exe_dir / "updates"), str(root / "updates"))
    except OSError:
        pass  # 迁移失败不阻断启动:角色重选一次的代价可接受


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
