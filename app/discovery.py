"""客户端发现:监听 UDP 广播(CONTRACTS discovery_packet)。"""
import json
import socket
import time

from server.broadcast import DISCOVERY_PORT


def find_server(timeout: float = 2.0) -> dict | None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", DISCOVERY_PORT))
    sock.settimeout(timeout)
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            try:
                data, addr = sock.recvfrom(1024)
            except socket.timeout:
                break
            try:
                pkt = json.loads(data)
            except ValueError:
                continue
            if pkt.get("app") == "call-center":
                return {"host": addr[0], "port": pkt["port"],
                        "version": pkt["version"]}
        return None
    finally:
        sock.close()
