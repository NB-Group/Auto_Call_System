"""自动更新:镜像列表自动尝试 + 双源 sha256 一致 + pending 自替换(spec §8)。

- 清单:每个 Release 附 latest.json(文件下载全镜像通用,不赌 API 反代)
- 防投毒:≥2 源取回且 sha256 一致;唯一源时仅直连放行
- 替换:下载为 data/updates/pending.exe,下次启动 rename 换新(规避运行锁)
"""
import hashlib
import json
import os
import shutil
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.config import load_config

DEFAULT_MIRRORS = [
    "",  # 直连
    "https://gh-proxy.org/",
    "https://ghfast.top/",
    "https://ghproxy.net/",
    "https://ghproxy.homeboyc.cn/",
    "https://gh.zwy.one/",
]
# 锚定下载目录:frozen 包跟 exe 同盘同级,源码运行用工作区 data/。
# 在模块导入时求值(frozen 属性由 PyInstaller 在用户代码前设置)。
UPDATE_DIR = (Path(sys.executable).parent / "updates"
              if getattr(sys, "frozen", False) else Path("data/updates"))


def parse_version(v: str) -> tuple:
    return tuple(int(x) for x in v.lstrip("v").split("."))


def update_config() -> tuple[str, list[str]]:
    cfg = load_config().get("update", {})
    repo = cfg.get("repo", "NB-Group/Auto_Call_System")
    mirrors = cfg.get("mirrors") or DEFAULT_MIRRORS
    return repo, mirrors


def _manifest_url(mirror: str, repo: str) -> str:
    return (f"{mirror}https://github.com/{repo}"
            "/releases/latest/download/latest.json")


def _asset_url(mirror: str, repo: str, version: str, asset: str) -> str:
    return (f"{mirror}https://github.com/{repo}"
            f"/releases/download/v{version}/{asset}")


def _fetch(url: str, timeout: float, limit: int | None = None) -> bytes | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            # limit=None 全量读(清单);资产按 manifest size 截断,防被代理灌超量字节
            return r.read() if limit is None else r.read(limit)
    except Exception:
        return None


def fetch_manifests(repo: str, mirrors: list[str] | None = None,
                    timeout: float = 3.0) -> list[tuple[str, dict]]:
    mirrors = mirrors if mirrors is not None else DEFAULT_MIRRORS
    with ThreadPoolExecutor(max_workers=len(mirrors)) as pool:
        results = list(pool.map(
            lambda m: (m, _fetch(_manifest_url(m, repo), timeout)), mirrors))
    out = []
    for mirror, data in results:
        if not data:
            continue
        try:
            m = json.loads(data)
        except (ValueError, TypeError):
            continue
        if not isinstance(m, dict):  # 代理异常页可能解析成数组/标量
            continue
        if {"version", "asset", "sha256"}.issubset(m.keys()):
            out.append((mirror, m))
    return out


def check_update(current: str, repo: str, mirrors: list[str] | None = None,
                 timeout: float = 3.0) -> dict | None:
    """有新版且通过防投烟校验 → 返回 manifest,否则 None。"""
    successes = fetch_manifests(repo, mirrors, timeout)
    if not successes:
        return None
    if len(successes) == 1:
        if successes[0][0] != "":  # 唯一源且非直连:拒绝
            return None
        manifest = successes[0][1]
    else:
        shas = {m["sha256"] for _, m in successes}
        if len(shas) != 1:  # 源之间不一致:疑似投毒,拒绝
            return None
        manifest = successes[0][1]
    try:
        newer = parse_version(manifest["version"]) > parse_version(current)
    except (ValueError, TypeError):
        return None
    return manifest if newer else None


def download_asset(manifest: dict, repo: str, mirrors: list[str] | None = None,
                   timeout: float = 3.0) -> Path | None:
    """按镜像顺序下载资产并校验 sha256;失败返回 None。"""
    mirrors = mirrors if mirrors is not None else DEFAULT_MIRRORS
    # 资产名净化:只取文件名,阻断清单里的 ../ 路径逃逸
    asset = Path(manifest["asset"]).name
    if not asset:
        return None
    try:
        UPDATE_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:  # 目录建不起来(权限/只读盘):无从落盘
        return None
    target = UPDATE_DIR / asset
    # 只读 manifest 声明的字节数:size 缺失/为 0 → 读回空 → sha 必不匹配 → 拒绝。
    # 代价:无 size 字段的清单不可下载(保守方向,误伤不会写入坏文件)。
    size = manifest.get("size") or 0
    for mirror in mirrors:
        data = _fetch(_asset_url(mirror, repo, manifest["version"], asset),
                      timeout=timeout, limit=size)
        if data is None:
            continue
        if hashlib.sha256(data).hexdigest() != manifest["sha256"]:
            continue
        target.write_bytes(data)
        return target
    return None


def stage_update(current: str, repo: str, mirrors: list[str] | None = None,
                 timeout: float = 3.0) -> dict | None:
    """检查+下载到 pending.exe;成功返回 manifest。"""
    manifest = check_update(current, repo, mirrors, timeout)
    if manifest is None:
        return None
    path = download_asset(manifest, repo, mirrors, timeout)
    if path is None:
        return None
    pending = UPDATE_DIR / "pending.exe"
    shutil.move(str(path), pending)
    return manifest


def install_pending() -> bool:
    """启动时调用:pending.exe 存在则改名换新(Windows 运行中 exe 可改名)。"""
    if not getattr(sys, "frozen", False):
        return False
    if not UPDATE_DIR.exists():  # 目录不在则 pending 必不在,早退
        return False
    pending = UPDATE_DIR / "pending.exe"
    if not pending.exists():
        return False
    exe = Path(sys.executable)
    old = exe.with_suffix(".old")
    try:
        if old.exists():
            old.unlink()
        os.rename(exe, old)
    except OSError:
        return False
    try:
        shutil.move(str(pending), str(exe))
    except OSError:
        try:
            os.rename(old, exe)  # 回滚:换新失败必须保住旧 exe,不能裸奔
        except OSError:
            pass
        return False
    return True


if __name__ == "__main__":
    from app import __version__
    repo, mirrors = update_config()
    m = check_update(__version__, repo, mirrors)
    if m is None:
        print(f"v{__version__} 已是最新(或源不可达)")
    else:
        print(f"发现新版 v{m['version']}:{m['notes']}")
        print("下载…", stage_update(__version__, repo, mirrors) is not None)
