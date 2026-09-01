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
    """起一个本地 HTTP'镜像',返回 (url_prefix, runner, thread)。

    契约 URL 模板把绝对 GitHub URL 拼在镜像前缀之后
    (`{mirror}https://github.com/<repo>/...`),真实镜像站按整段路径代理;
    本地桩须同时注册裸路径(供直连测试 monkeypatch _manifest_url)与
    完整契约路径(供走真实 _manifest_url/_asset_url 的用例)。
    """
    loop = __import__("asyncio").new_event_loop()
    app = web.Application()

    async def latest(request):
        m = dict(manifest)
        if tamper:
            m["sha256"] = "f" * 64
        return web.json_response(m)

    async def asset(request):
        return web.Response(body=exe)

    gh = f"/https://github.com/x/y"
    app.router.add_get("/releases/latest/download/latest.json", latest)
    app.router.add_get(f"{gh}/releases/latest/download/latest.json", latest)
    app.router.add_get(
        f"/releases/download/v{manifest['version']}/{manifest['asset']}", asset)
    app.router.add_get(
        f"{gh}/releases/download/v{manifest['version']}/{manifest['asset']}", asset)
    runner = web.AppRunner(app)
    port = free_port()  # 主线程先定端口:嵌套 run() 内赋值无法回传(nonlocal 缺失必 NameError)

    def run():
        loop.run_until_complete(runner.setup())
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
    # UPDATE_DIR 是相对路径 data/updates,chdir 到 tmp_path 隔离
    monkeypatch.chdir(tmp_path)
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
