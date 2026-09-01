"""构建前端并拷贝到 server/static(CI/打包/本地共用)。"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    if "--skip-build" not in sys.argv:
        subprocess.run(["corepack", "enable"], check=False)
        subprocess.run(["pnpm", "--dir", str(ROOT / "frontend"), "install"],
                       check=True)
        subprocess.run(["pnpm", "--dir", str(ROOT / "frontend"), "build"],
                       check=True)
    static = ROOT / "server" / "static"
    if static.exists():
        shutil.rmtree(static)
    shutil.copytree(ROOT / "frontend" / "dist", static)
    print(f"static ready: {static}")


if __name__ == "__main__":
    main()
