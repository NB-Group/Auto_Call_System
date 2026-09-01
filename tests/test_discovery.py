import json
import socket
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
