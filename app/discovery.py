"""客户端发现:监听 UDP 广播(CONTRACTS discovery_packet)。"""
import json
import socket
import time

from server.broadcast import DISCOVERY_PORT


def find_server(timeout: float = 2.0) -> dict | None:
    """等待合法发现包,返回 {"host","port","version"} 或 None;畸形 LAN 包一律跳过,网络错误不抛出。"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    except OSError:
        return None
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", DISCOVERY_PORT))
    except OSError:  # 端口被独占等:契约是 dict|None,调用方(Task 10)不包 try
        sock.close()
        return None
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            # 每轮按剩余期限收紧超时,避免期限边缘的散包导致 2× 等待
            sock.settimeout(max(0.05, deadline - time.monotonic()))
            try:
                data, addr = sock.recvfrom(1024)
            except socket.timeout:
                break
            try:
                pkt = json.loads(data)
            except ValueError:
                continue
            # 合法 JSON 但不是 dict(如 123 / [1])不能 .get;缺 port/version 的也跳过
            if not isinstance(pkt, dict) or pkt.get("app") != "call-center":
                continue
            port = pkt.get("port")
            version = pkt.get("version")
            if port is None or not isinstance(version, str):
                continue
            return {"host": addr[0], "port": port, "version": version}
        return None
    finally:
        sock.close()
