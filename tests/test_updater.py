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


def serve(manifest: dict, exe: bytes = EXE, tamper: bool = False,
          raw_latest=None):
    """起一个本地 HTTP'镜像',返回 (url_prefix, runner, thread)。

    契约 URL 模板把绝对 GitHub URL 拼在镜像前缀之后
    (`{mirror}https://github.com/<repo>/...`),真实镜像站按整段路径代理;
    本地桩须同时注册裸路径(供直连测试 monkeypatch _manifest_url)与
    完整契约路径(供走真实 _manifest_url/_asset_url 的用例)。
    raw_latest 非 None 时 /latest.json 直接返回该对象(如 JSON 数组,模拟代理异常页)。
    """
    loop = __import__("asyncio").new_event_loop()
    app = web.Application()

    async def latest(request):
        if raw_latest is not None:
            return web.json_response(raw_latest)
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
    monkeypatch.setattr("sys.argv", [str(exe)])
    assert install_pending() is True
    assert exe.read_bytes() == b"new"
    assert (tmp_path / "app.old").read_bytes() == b"old"


def test_install_pending_targets_deployed_exe_not_temp(tmp_path, monkeypatch):
    """onefile 场景(v0.1.6 修复):sys.executable 是临时解包 exe,部署位
    在 sys.argv[0]。换新必须换部署位 —— 改临时 exe 等于白改,新版永远
    装不上,客户端每次启动重下载,更新死循环。"""
    monkeypatch.chdir(tmp_path)
    deployed = tmp_path / "call-center.exe"
    deployed.write_bytes(b"old")
    temp_exe = tmp_path / "onefile_tmp" / "call-center.exe"
    temp_exe.parent.mkdir()
    temp_exe.write_bytes(b"temp-old")
    pending_dir = tmp_path / "data" / "updates"
    pending_dir.mkdir(parents=True)
    (pending_dir / "pending.exe").write_bytes(b"new")
    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setattr("sys.executable", str(temp_exe))
    monkeypatch.setattr("sys.argv", [str(deployed)])
    assert install_pending() is True
    assert deployed.read_bytes() == b"new"          # 换的是部署位
    assert temp_exe.read_bytes() == b"temp-old"      # 临时 exe 未被碰
    assert (tmp_path / "call-center.old").read_bytes() == b"old"


def test_install_pending_bails_without_deployed_exe(tmp_path, monkeypatch):
    """argv[0] 不是可信 exe 路径时放弃换新,不得回退去改临时 exe。"""
    monkeypatch.chdir(tmp_path)
    pending_dir = tmp_path / "data" / "updates"
    pending_dir.mkdir(parents=True)
    (pending_dir / "pending.exe").write_bytes(b"new")
    temp_exe = tmp_path / "onefile_tmp" / "call-center.exe"
    temp_exe.parent.mkdir()
    temp_exe.write_bytes(b"temp-old")
    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setattr("sys.executable", str(temp_exe))
    # onefile 下 argv[0] 恒为部署位(Nuitka 保证);argv[0] 非可信 exe 时
    # 必须直接放弃,绝不能回退 sys.executable 去改临时解包 exe。
    monkeypatch.setattr("sys.argv", ["not-an-exe.py"])
    assert install_pending() is False
    assert temp_exe.read_bytes() == b"temp-old"


def test_manifest_non_dict_ignored(manifest):
    """镜像返回 JSON 数组(代理异常页)不得让 fetch_manifests 抛 AttributeError。"""
    good, rg, lg = serve(manifest)
    bad, rb, lb = serve(manifest, raw_latest=[1, 2])  # 非字典清单
    got = fetch_manifests("x/y", [good, bad], timeout=1.0)
    stop(rg, lg); stop(rb, lb)
    assert len(got) == 1
    assert got[0][0] == good  # 只留下好的那个源


def test_download_asset_traversal_sanitized(manifest, tmp_path, monkeypatch):
    """manifest.asset 携带 ../ 逃逸时:只允许落在 UPDATE_DIR 内的净化文件名。"""
    evil = dict(manifest, asset="../../evil.exe")  # 声明的资产名带逃逸
    route = dict(manifest, asset="evil.exe")  # 镜像按净化后的名字供字节
    a, ra, la = serve(route)
    monkeypatch.chdir(tmp_path)
    path = download_asset(evil, "x/y", [a], timeout=1.0)
    stop(ra, la)
    inside = tmp_path / "data" / "updates" / "evil.exe"
    assert path is not None and path.read_bytes() == EXE
    assert inside.read_bytes() == EXE
    assert (tmp_path / "evil.exe").exists() is False  # ../../ 逃逸未得逞
    # 全 tmp_path 内除 UPDATE_DIR 里那份,别无他物
    assert sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*")) == \
        ["data", "data/updates", "data/updates/evil.exe"]


def test_install_pending_rollback(tmp_path, monkeypatch):
    """换新(pending → exe)失败时必须回滚:旧 exe 原样保住。"""
    import shutil
    monkeypatch.chdir(tmp_path)
    exe = tmp_path / "app.exe"
    exe.write_bytes(b"old")
    pending_dir = tmp_path / "data" / "updates"
    pending_dir.mkdir(parents=True)
    (pending_dir / "pending.exe").write_bytes(b"new")
    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setattr("sys.argv", [str(exe)])

    def boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(shutil, "move", boom)  # updater 内调用时查属性,同模块生效
    assert install_pending() is False
    assert exe.read_bytes() == b"old"  # 已回滚
    assert not (tmp_path / "app.old").exists()  # .old 被 rename 回去,不留半态


def test_fetch_falls_back_when_system_proxy_dead(manifest, monkeypatch):
    """死系统代理降级:.50 实证(注册表 ProxyEnable→127.0.0.1:7897 已关,
    urllib 读注册表全 ConnectionRefused)。代理指到死端口时,_fetch 必须
    仍能直连取回(空 ProxyHandler 兜底),不能让更新整链静默失败。"""
    from app.updater import _fetch

    a, ra, la = serve(manifest)
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:9")   # 9=discard,秒拒
    monkeypatch.setenv("https_proxy", "http://127.0.0.1:9")
    monkeypatch.delenv("no_proxy", raising=False)
    monkeypatch.delenv("NO_PROXY", raising=False)
    try:
        data = _fetch(a + "releases/latest/download/latest.json",
                      timeout=2.0)  # 桩的裸路由;a 带尾斜杠,勿双杠
    finally:
        stop(ra, la)
    assert data is not None and json.loads(data)["version"] == "0.2.0"
