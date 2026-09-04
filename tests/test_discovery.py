import json
import socket
import threading
import time

from app.discovery import find_server
from server.broadcast import DISCOVERY_PORT, Broadcaster


def test_broadcast_and_discover():
    b = Broadcaster(8800, "0.1.0", interval=0.2)
    b.start()
    try:
        found = find_server(timeout=2.0)
    finally:
        b.stop()
    assert found is not None
    assert found["port"] == 8800
    assert found["version"] == "0.1.0"
    assert found["host"]  # 本机 IP


def test_discover_returns_none_when_silent():
    # 环境护栏:本测试的语义是「LAN 上无广播者 → None」。开发机上常有
    # 昨天调试残留的真服务器在广播(曾致全量跑随机红),先探到就跳过,
    # 不把环境污染误报成代码回归。
    if find_server(timeout=0.3) is not None:
        import pytest
        pytest.skip("LAN 上有真实广播者(开发机残留服务器)")
    # 广播端先占用再停止,确保静默
    b = Broadcaster(8800, "0.1.0", interval=0.1)
    b.start(); time.sleep(0.3); b.stop()
    assert find_server(timeout=0.5) is None


def test_packet_shape():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", DISCOVERY_PORT + 1))
    b = Broadcaster(8800, "0.1.0", interval=0.2)
    # 直接调用一次内部发送,发到 DISCOVERY_PORT+1 由我们接收
    b._send_once(("127.0.0.1", DISCOVERY_PORT + 1))
    data, _ = sock.recvfrom(1024)
    sock.close(); b.stop()
    pkt = json.loads(data)
    assert pkt["app"] == "call-center"


def test_find_server_ignores_malformed_packets():
    # 畸形包(合法 JSON 非 dict / 缺 port+version / 非 JSON)不得让 find_server 抛错或卡死
    result = []
    t = threading.Thread(target=lambda: result.append(find_server(timeout=2.0)))
    t.start()
    time.sleep(0.3)  # 等 find_server 绑定并阻塞在 recvfrom
    bad = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # 未 bind,单播直发即可
    for payload in (b"123", b'{"app":"call-center"}', b"not-json"):
        bad.sendto(payload, ("127.0.0.1", DISCOVERY_PORT))
    bad.close()
    b = Broadcaster(8800, "0.1.0", interval=0.2)
    b._send_once(("127.0.0.1", DISCOVERY_PORT))  # 单播回环 → host 应为 127.0.0.1
    b.stop()
    t.join(timeout=3.0)
    assert result and result[0] == {"host": "127.0.0.1", "port": 8800,
                                    "version": "0.1.0"}


def test_find_server_none_on_all_bad():
    # 只有畸形包:不抛错,超时后返回 None
    result = []
    t = threading.Thread(target=lambda: result.append(find_server(timeout=0.6)))
    t.start()
    time.sleep(0.3)
    bad = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for payload in (b"123", b'{"app":"call-center"}', b"not-json"):
        bad.sendto(payload, ("127.0.0.1", DISCOVERY_PORT))
    bad.close()
    t.join(timeout=2.0)
    assert result and result[0] is None
