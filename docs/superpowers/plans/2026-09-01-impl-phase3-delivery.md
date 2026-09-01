# 实施计划 Phase 3:自动更新 · CI/发布 · 交付

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 镜像源自动更新的完整链路(探测/双源校验/下载/pending 替换)、GitHub Actions CI 与 Nuitka Windows 发布、Linux 全链路联调脚本与 README。

**Architecture:** 更新器是纯 Python 模块(`app/updater.py`),镜像前缀列表可配置;清单从多镜像并发探测取回,sha256 双源一致才下载;exe 以 `pending.exe` 暂存,下次启动用"改名换新"完成自替换(规避运行中文件锁)。CI 在 Linux 验证(python+前端+Nuitka 冒烟),Release 在 windows-latest 编译 onefile。

**Tech Stack:** stdlib(urllib/hashlib/concurrent.futures)、GitHub Actions、Nuitka、pnpm。

**前置:** Phase 1、Phase 2 完成。

## Global Constraints(继承前两阶段全部)

- 更新只提示不强制;**服务器角色不自动更新**(spec §8)
- 镜像列表默认值与 spec §8 一致;全部源失败必须静默降级
- 下载产物进 `data/updates/`;`server/static`、`dist`、`data/` 全部 gitignore
- Release 资产名 ASCII:`call-center-<version>-x64.exe`

---

### Task 17: 自动更新器 + 壳接线 + 更新设置

**Files:**
- Create: `app/updater.py`
- Modify: `app/main.py`(启动时 install_pending → 非服务器角色 check_update → evaluate_js 发 `cc-update` 事件)
- Modify: `app/bridge.py`(契约 v1.2:`get_update_config/set_update_config`)
- Modify: `frontend/src/App.vue`(更新横幅)
- Modify: `frontend/src/views/ServerView.vue`(更新设置卡)
- Modify: `docs/CONTRACTS.md`(v1.2 增补)
- Test: `tests/test_updater.py`

**Interfaces:**
- Produces: `parse_version(v) -> tuple`;`fetch_manifests(repo, mirrors, timeout) -> [(mirror, manifest)]`;`check_update(current, repo, mirrors) -> manifest|None`;`download_asset(manifest, repo, mirrors) -> Path|None`(sha 校验失败返回 None);`stage_update(...) -> manifest|None`(下载到 `data/updates/pending.exe`);`install_pending() -> bool`(仅 frozen 生效);`__main__`:`python -m app.updater check`

- [ ] **Step 1: 契约 v1.2 增补(CONTRACTS.md 追加)**

```
## v1.2 增补(2026-09-01)
bridge 新增:
- get_update_config() -> {"repo": str, "mirrors": [str, ...]}
- set_update_config(repo: str, mirrors_json: str) -> null   # mirrors_json 为 JSON 数组文本
壳 → 前端事件(经 evaluate_js 派发到 window):
- CustomEvent 'cc-update',detail = {"version": "...", "notes": "..."}
  (新版已下载暂存、重启生效;前端据此显示横幅,按钮调 api.quit() 重启)
```

- [ ] **Step 2: 写失败测试 `tests/test_updater.py`**

```python
import hashlib
import json
import socket
import threading

import pytest
from aiohttp import web

from app.updater import (DEFAULT_MIRRORS, check_update, download_asset,
                         fetch_manifests, install_pending, parse_version,
                         stage_update)

EXE = b"fake-exe-bytes-0.2.0"


def free_port() -> int:
    s = socket.socket()
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def serve(manifest: dict, exe: bytes = EXE, tamper: bool = False):
    """起一个本地 HTTP'镜像',返回 (url_prefix, runner, thread)。"""
    loop = __import__("asyncio").new_event_loop()
    app = web.Application()

    async def latest(request):
        m = dict(manifest)
        if tamper:
            m["sha256"] = "f" * 64
        return web.json_response(m)

    async def asset(request):
        return web.Response(body=exe)

    app.router.add_get("/releases/latest/download/latest.json", latest)
    app.router.add_get(
        f"/releases/download/v{manifest['version']}/{manifest['asset']}", asset)
    runner = web.AppRunner(app)

    def run():
        loop.run_until_complete(runner.setup())
        port = free_port()
        site = web.TCPSite(runner, "127.0.0.1", port)
        loop.run_until_complete(site.start())
        loop.run_forever()

    t = threading.Thread(target=run, daemon=True)
    t.start()
    import time
    time.sleep(0.2)
    return f"http://127.0.0.1:{port}/", runner, loop


@pytest.fixture()
def manifest():
    return {"version": "0.2.0", "notes": "测试版本", "asset": "call-center-0.2.0-x64.exe",
            "sha256": hashlib.sha256(EXE).hexdigest(), "size": len(EXE)}


def stop(runner, loop):
    loop.call_soon_threadsafe(lambda: loop.create_task(runner.cleanup()))


def test_parse_version():
    assert parse_version("v0.10.2") == (0, 10, 2)
    assert parse_version("0.2.0") < parse_version("0.10.0")


def test_fetch_manifests_multi_mirror(manifest):
    a, ra, la = serve(manifest)
    b, rb, lb = serve(manifest)
    mirrors = [a, b, "http://127.0.0.1:1/"]  # 第三个必然失败
    got = fetch_manifests("x/y", mirrors, timeout=1.0)
    stop(ra, la); stop(rb, lb)
    assert len(got) == 2
    assert {m["version"] for _, m in got} == {"0.2.0"}


def test_check_update_quorum_tamper_rejected(manifest):
    good, rg, lg = serve(manifest)
    bad, rb, lb = serve(manifest, tamper=True)
    assert check_update("0.1.0", "x/y", [good, bad], timeout=1.0) is None
    found = check_update("0.1.0", "x/y", [good], timeout=1.0)
    # 单源直连放行规则:good 非直连但列表里唯一可用 → 谨慎起见也放行?
    # 契约:仅当唯一源是直连("")才放行。这里断言 None。
    assert found is None
    stop(rg, lg); stop(rb, lb)


def test_check_update_direct_single_allowed(manifest):
    d, rd, ld = serve(manifest)
    # 直连前缀 "" 无法本地模拟;用 monkeypatch 把直连 URL 指到本地
    import app.updater as up
    orig = up._manifest_url
    up._manifest_url = lambda mirror, repo: f"{d}releases/latest/download/latest.json"
    try:
        assert check_update("0.1.0", "x/y", [""], timeout=1.0) == manifest
    finally:
        up._manifest_url = orig
    stop(rd, ld)


def test_check_update_not_newer(manifest):
    a, ra, la = serve(manifest)
    b, rb, lb = serve(manifest)
    assert check_update("0.2.0", "x/y", [a, b], timeout=1.0) is None
    stop(ra, la); stop(rb, lb)


def test_download_asset_verifies_sha(manifest, tmp_path, monkeypatch):
    a, ra, la = serve(manifest)
    monkeypatch.chdir(tmp_path)
    path = download_asset(manifest, "x/y", [a, "http://127.0.0.1:1/"], timeout=1.0)
    stop(ra, la)
    assert path is not None and path.read_bytes() == EXE

    bad_manifest = dict(manifest, sha256="0" * 64)
    a2, ra2, la2 = serve(bad_manifest)
    assert download_asset(bad_manifest, "x/y", [a2], timeout=1.0) is None
    stop(ra2, la2)


def test_stage_update_writes_pending(manifest, tmp_path, monkeypatch):
    a, ra, la = serve(manifest)
    b, rb, lb = serve(manifest)
    monkeypatch.chdir(tmp_path)
    got = stage_update("0.1.0", "x/y", [a, b], timeout=1.0)
    stop(ra, la); stop(rb, lb)
    assert got == manifest
    assert (tmp_path / "data" / "updates" / "pending.exe").read_bytes() == EXE


def test_install_pending_swaps_exe(tmp_path, monkeypatch):
    exe = tmp_path / "app.exe"
    exe.write_bytes(b"old")
    pending_dir = tmp_path / "data" / "updates"
    pending_dir.mkdir(parents=True)
    (pending_dir / "pending.exe").write_bytes(b"new")
    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setattr("sys.executable", str(exe))
    assert install_pending() is True
    assert exe.read_bytes() == b"new"
    assert (tmp_path / "app.old").read_bytes() == b"old"
```

- [ ] **Step 3: 跑测试确认失败**

Run: `pytest tests/test_updater.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'app.updater'`

- [ ] **Step 4: 实现 `app/updater.py`**

```python
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
UPDATE_DIR = Path("data/updates")


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


def _fetch(url: str, timeout: float) -> bytes | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.read()
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
            if {"version", "asset", "sha256"}.issubset(m.keys()):
                out.append((mirror, m))
        except (ValueError, TypeError):
            continue
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
    UPDATE_DIR.mkdir(parents=True, exist_ok=True)
    target = UPDATE_DIR / manifest["asset"]
    for mirror in mirrors:
        data = _fetch(_asset_url(mirror, repo, manifest["version"],
                                 manifest["asset"]), timeout=timeout)
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
    pending = UPDATE_DIR / "pending.exe"
    if not pending.exists():
        return False
    exe = Path(sys.executable)
    old = exe.with_suffix(".old")
    try:
        if old.exists():
            old.unlink()
        os.rename(exe, old)
        shutil.move(str(pending), str(exe))
        return True
    except OSError:
        return False


if __name__ == "__main__":
    from app import __version__
    repo, mirrors = update_config()
    m = check_update(__version__, repo, mirrors)
    if m is None:
        print(f"v{__version__} 已是最新(或源不可达)")
    else:
        print(f"发现新版 v{m['version']}:{m['notes']}")
        print("下载…", stage_update(__version__, repo, mirrors) is not None)
```

- [ ] **Step 5: 跑测试确认通过**

Run: `pytest tests/test_updater.py -v` → 8 passed

- [ ] **Step 6: 壳与前端接线**

`app/bridge.py` 追加:
```python
    def get_update_config(self) -> str:
        from app.config import load_config
        cfg = load_config().get("update", {})
        return json.dumps({
            "repo": cfg.get("repo", "NB-Group/Auto_Call_System"),
            "mirrors": cfg.get("mirrors") or DEFAULT_MIRRORS,
        }, ensure_ascii=False)

    def set_update_config(self, repo: str, mirrors_json: str) -> None:
        from app.config import load_config, save_config
        cfg = load_config()
        cfg["update"] = {"repo": repo,
                         "mirrors": json.loads(mirrors_json)}
        save_config(cfg)
```
(bridge.py 顶部相应 `import json`;`from app.updater import DEFAULT_MIRRORS`。pywebview 序列化返回值,返回 JSON 字符串最稳。)

`app/main.py` 的 `main()` 开头(`webview.start()` 之前)插入:
```python
    from app.updater import install_pending, stage_update, update_config
    install_pending()
    update_manifest = None
    if role in ("teacher", "display"):
        repo, mirrors = update_config()
        update_manifest = stage_update(__version__, repo, mirrors)
```
`webview.start()` 之后(窗口关闭前不行——要在页面加载后注入):改为在 `main()` 里 `webview.start(func=after_start)` 风格不可用于 evaluate_js 时机;正确做法:窗口 `loaded` 事件:
```python
    if update_manifest:
        def notify():
            window.evaluate_js(
                f"window.dispatchEvent(new CustomEvent('cc-update',"
                f"{{detail:{json.dumps({'version': update_manifest['version'],"
                f"'notes': update_manifest['notes']}, ensure_ascii=False)}}}))")
        window.events.loaded += notify
```
(`import json` 加到 main.py 顶部;`stage_update` 全源失败返回 None → 静默,符合约束。)

`frontend/src/App.vue` 全量替换:
```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useDark } from './composables/useDark'

const { initTheme } = useDark()
const update = ref<{ version: string; notes: string } | null>(null)
const restart = () => (window as any).pywebview?.api?.quit?.()

onMounted(() => {
  initTheme()
  window.addEventListener('cc-update', (ev) => {
    update.value = (ev as CustomEvent).detail
  })
})
</script>

<template>
  <router-view />
  <div v-if="update" class="glass-pop" fixed top-4 left-1/2 translate-x--1/2
       px-5 py-3 flex="~ items-center gap-3" z-50 text-14px>
    <span>新版本 v{{ update.version }} 已就绪,重启后生效</span>
    <button class="cc-btn cc-btn-primary" py-1 @click="restart">立即重启</button>
  </div>
</template>
```

`ServerView.vue` 追加更新设置卡(模板末尾 `<Toasts />` 之前):
```html
    <div v-if="!needsAdmin" class="glass-card" p-8 mt-4 flex="~ col gap-3">
      <h2 text-16px font-600 m-0>更新设置</h2>
      <label flex="~ col gap-1" text-13px>
        GitHub 仓库(owner/name)
        <input v-model="repo" class="cc-input" placeholder="NB-Group/Auto_Call_System">
      </label>
      <label flex="~ col gap-1" text-13px>
        镜像源前缀(每行一个,留空行 = 直连)
        <textarea v-model="mirrorsText" class="cc-input" rows-4 />
      </label>
      <button class="cc-btn cc-btn-primary" @click="saveUpdateCfg">保存</button>
    </div>
```
script 增加:
```ts
const repo = ref('NB-Group/Auto_Call_System')
const mirrorsText = ref('')
onMounted(async () => {
  await refresh()
  const cfg = await (window as any).pywebview?.api?.get_update_config?.()
  if (cfg) {
    const c = JSON.parse(cfg)
    repo.value = c.repo
    mirrorsText.value = (c.mirrors as string[]).join('\n')
  }
})
async function saveUpdateCfg() {
  const mirrors = mirrorsText.value.split('\n').map(s => s.trim()).filter(Boolean)
  await (window as any).pywebview?.api?.set_update_config?.(
    repo.value.trim(), JSON.stringify(mirrors))
  push('更新设置已保存')
}
```
(注意:`onMounted` 已存在则合并逻辑,不要重复声明。)

- [ ] **Step 7: 全量测试 + 手动验证**

```bash
pytest -v && pnpm --dir frontend build && pnpm --dir frontend test
python -m app.updater check   # 期望:静默输出"已是最新(或源不可达)"——真实 repo 尚无 Release
```

- [ ] **Step 8: Commit**

```bash
git add app/ frontend/ docs/CONTRACTS.md tests/test_updater.py
git commit -m "feat: 自动更新(镜像探测/双源校验/pending 自替换)+ 更新设置"
```

---

### Task 18: CI 与发布流水线

**Files:**
- Create: `.github/workflows/ci.yml`、`.github/workflows/release.yml`、`scripts/prepare_frontend.py`
- Create: `.gitignore`
- Modify: `frontend/.gitignore`(pnpm 产物,若无则新建)

**Interfaces:**
- Produces: push/pr 自动验证;`git tag v0.1.0 && git push --tags` 产出 Windows exe + latest.json 的 Release

- [ ] **Step 1: `.gitignore`**

```
.venv/
__pycache__/
*.pyc
data/
dist/
server/static/
frontend/node_modules/
frontend/dist/
*.old
*.exe
```

- [ ] **Step 2: `scripts/prepare_frontend.py`**

```python
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
```

- [ ] **Step 3: `.github/workflows/ci.yml`**

```yaml
name: ci
on:
  push: { branches: ["**"] }
  pull_request:

jobs:
  python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements-dev.txt
      - run: pytest -v

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: corepack enable
      - run: pnpm --dir frontend install
      - run: pnpm --dir frontend test
      - run: pnpm --dir frontend build

  nuitka-smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: corepack enable
      - run: pip install -r requirements.txt nuitka ordered-set
      - run: sudo apt-get update && sudo apt-get install -y ccache
      - run: python scripts/prepare_frontend.py
      - run: |
          python -m nuitka --onefile --assume-yes-for-downloads \
            --include-data-dir=server/static=server/static \
            --output-dir=dist app/main.py
      - uses: actions/upload-artifact@v4
        with: { name: linux-smoke, path: dist/main.bin }
        if: always()
```

- [ ] **Step 4: `.github/workflows/release.yml`**

```yaml
name: release
on:
  push: { tags: ["v*"] }

permissions: { contents: write }

jobs:
  windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: corepack enable
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements.txt nuitka ordered-set pywin32
      - run: python scripts/prepare_frontend.py

      - name: Build exe
        shell: pwsh
        run: |
          $v = "${{ github.ref_name }}" -replace '^v',''
          python -m nuitka --onefile --assume-yes-for-downloads `
            --windows-console-mode=disable `
            --include-package=win32com --include-package=win32 --include-package=pythoncom `
            --include-data-dir=server/static=server/static `
            --output-filename="call-center-$v-x64.exe" `
            --output-dir=dist app/main.py

      - name: Manifest and release
        shell: pwsh
        env: { GH_TOKEN: "${{ github.token }}" }
        run: |
          $v = "${{ github.ref_name }}" -replace '^v',''
          $exe = "dist/call-center-$v-x64.exe"
          $sha = (Get-FileHash $exe -Algorithm SHA256).Hash.ToLower()
          $size = (Get-Item $exe).Length
          @{ version = $v; notes = "见 Release 说明"; asset = "call-center-$v-x64.exe";
             sha256 = $sha; size = $size } |
            ConvertTo-Json | Out-File dist/latest.json -Encoding utf8
          gh release create "${{ github.ref_name }}" $exe dist/latest.json --generate-notes
```

- [ ] **Step 5: 本地验证可验证部分**

```bash
python scripts/prepare_frontend.py --skip-build   # 若 dist 已存在,验证拷贝逻辑
git status   # 确认 server/static 未被跟踪(gitignore 生效)
```
Expected: static 拷贝成功;`git status` 干净

- [ ] **Step 6: Commit**

```bash
git add .github/ scripts/ .gitignore
git commit -m "ci: GitHub Actions 验证 + Nuitka Windows 发布流水线"
```

- [ ] **Step 7: 推送验证(需要用户仓库)**

```bash
git remote add origin git@github.com:<owner>/Auto_Call_System.git
git push -u origin master
# CI 三 job 全绿后:
git tag v0.1.0 && git push --tags
# 期望:release job 产出 call-center-0.1.0-x64.exe + latest.json
```
Expected: Actions 页 python/frontend/nuitka-smoke 绿;tag 后 release 资产齐全(约 10-20 分钟)

---

### Task 19: 全链路联调脚本 · README · 收尾

**Files:**
- Create: `scripts/dev_all.sh`(可执行)、`README.md`
- Modify: 项目记忆(由主 agent 完成,不派发)

**Interfaces:**
- Produces: 一键联调命令;交付文档

- [ ] **Step 1: `scripts/dev_all.sh`**

```bash
#!/usr/bin/env bash
# 一键 Linux 全链路联调:服务器 + 前端 dev + 两个壳窗口(teacher/display)
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  python -m venv .venv
  . .venv/bin/activate && pip install -r requirements-dev.txt
fi
. .venv/bin/activate

TTS="${TTS:-espeak}" python -m app.main --role server --dev &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT

sleep 1
TTS="${TTS:-espeak}" python -m app.main --role display --dev &
DISPLAY_PID=$!
TTS="${TTS:-espeak}" python -m app.main --role teacher --dev &
TEACHER_PID=$!
trap 'kill $SERVER_PID $DISPLAY_PID $TEACHER_PID 2>/dev/null || true' EXIT

echo "联调已启动:服务器 8800 / vite 5173 / 壳×2(TTS=$TTS)"
echo "浏览器建管理员+老师+名单: http://127.0.0.1:5173/#/server"
wait
```

```bash
chmod +x scripts/dev_all.sh
```

- [ ] **Step 2: `README.md`**

````markdown
# 校园叫号系统

老师办公室叫学生来订正作业,教室大屏实时显示 + 语音播报。局域网零配置。

## 角色
- **服务器**:办公室一台白天开机的电脑,开机自启。数据(SQLite)都在这台。
- **老师端**:登录 → 敲拼音首字母(`lhw` → 梁皓文)→ 回车选中 → 可选拼短语(`dz` → 订正数学作业,Tab 自由输入)→ 回车发送。
- **显示端**:教室电脑,选一次班级后全自动,大字 + TTS 播报两遍。

## 开发(Linux)
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
corepack enable && pnpm --dir frontend install
scripts/dev_all.sh          # 服务器+vite+两壳,espeak 播报
```
后端测试:`pytest -v`;前端:`pnpm --dir frontend test`。

## 发布
push tag 即自动构建 Windows 单文件:
```bash
git tag v0.2.0 && git push --tags
```
Release 附 `call-center-<版本>-x64.exe` 与 `latest.json`;客户端启动自动经镜像列表检查更新(设置里可改 repo/镜像)。

## 换服务器机器
拷走 `data/`(call.db + config.json)到新机,新机以服务器模式启动即可。

## 设计文档
`docs/superpowers/specs/2026-09-01-call-system-design.md` · 接口契约 `docs/CONTRACTS.md`
````

- [ ] **Step 3: 收尾验收**

```bash
pytest -v && pnpm --dir frontend test && pnpm --dir frontend build
scripts/dev_all.sh   # 手动走一遍:建管理员→老师→班级名单→叫号→大屏→撤销→历史
git add scripts/dev_all.sh README.md && git commit -m "docs: 联调脚本与 README"
```

- [ ] **Step 4: 代码评审(主 agent 执行,不派发)**

用 `superpowers:requesting-code-review` 对整个实现做一轮评审;重点核对 CONTRACTS.md 与实现逐条一致(端点/字段/错误码/WS 消息/bridge)。

- [ ] **Step 5: 更新记忆(主 agent)**

更新 `call-system-project` 记忆:阶段=实现完成待学校实测;记录验收数字(测试数、exe 大小、Actions 链接)。

---

## Phase 3 验收清单

- [ ] `pytest -v` 全绿(含 updater 8 项);前端 build+test 绿
- [ ] `python -m app.updater check` 静默安全(无 Release 时不崩)
- [ ] CI 三 job 绿;nuitka-smoke 产出 linux 二进制(证明打包配置成立)
- [ ] tag 推送后 Release 含 exe + latest.json,sha256 与 latest.json 一致
- [ ] 换机流程验证:拷 data/ → 新机服务器模式 → 客户端自动发现
