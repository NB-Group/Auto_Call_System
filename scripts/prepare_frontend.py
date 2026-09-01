"""构建前端并拷贝到 server/static(CI/打包/本地共用)。"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _run(cmd_name: str, *args: str, **kw) -> None:
    """Windows 下 corepack/pnpm 是 .cmd shim,CreateProcess 无法直接解析,
    统一用 shutil.which 解析出完整可执行路径再调用。"""
    exe = shutil.which(cmd_name)
    if exe is None:
        if kw.pop("optional", False):
            return
        raise SystemExit(f"未找到 {cmd_name},请先安装/启用")
    subprocess.run([exe, *args], **kw)


def main() -> None:
    if "--skip-build" not in sys.argv:
        _run("corepack", "enable", optional=True, check=False)
        _run("pnpm", "--dir", str(ROOT / "frontend"), "install", check=True)
        _run("pnpm", "--dir", str(ROOT / "frontend"), "build", check=True)
    static = ROOT / "server" / "static"
    if static.exists():
        shutil.rmtree(static)
    shutil.copytree(ROOT / "frontend" / "dist", static)
    print(f"static ready: {static}")


if __name__ == "__main__":
    main()
