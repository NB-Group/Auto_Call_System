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
    # 部署位而非临时解包目录(onefile 下 sys.executable 是后者,见
    # original_exe_path 注释):旧版 data/updates 放在真 exe 旁。
    exe_dir = (original_exe_path() or Path(sys.executable)).parent
    try:
        if (exe_dir / "data").is_dir() and not (root / "data").exists():
            root.mkdir(parents=True, exist_ok=True)
            shutil.move(str(exe_dir / "data"), str(root / "data"))
        if (exe_dir / "updates").is_dir() and not (root / "updates").exists():
            root.mkdir(parents=True, exist_ok=True)
            shutil.move(str(exe_dir / "updates"), str(root / "updates"))
    except OSError:
        pass  # 迁移失败不阻断启动:角色重选一次的代价可接受


def original_exe_path() -> Path | None:
    """onefile 部署位 exe:Nuitka onefile 子进程里 sys.executable 指向临时
    解包目录的 exe,sys.argv[0] 才是用户实际启动的那个(2026-09-04 .50
    实证:子进程 CommandLine 首段=部署路径,Application=临时解包 exe)。

    自更新换新 / 旧数据迁移都必须作用于部署位 —— 改到临时解包 exe 上
    等于白改(onefile 临时目录用后即焚,新版永远装不上 → 每次启动重
    下载的更新死循环)。拿不到可信路径时返回 None,调用方应放弃而非
    回退 sys.executable。
    """
    try:
        p = Path(sys.argv[0]).resolve()
    except OSError:
        return None
    return p if p.suffix.lower() == ".exe" and p.is_file() else None


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
