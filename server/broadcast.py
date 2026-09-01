"""UDP 广播:每 interval 秒宣告服务器存在(CONTRACTS discovery_packet)。"""
import json
import socket
import threading

DISCOVERY_PORT = 50000


class Broadcaster(threading.Thread):
    def __init__(self, http_port: int, version: str, interval: float = 3.0):
        super().__init__(daemon=True)
        self.http_port = http_port
        self.version = version
        self.interval = interval
        self._stop = threading.Event()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    def _packet(self) -> bytes:
        return json.dumps({"app": "call-center", "port": self.http_port,
                           "version": self.version}).encode()

    def _send_once(self, addr) -> None:
        self._sock.sendto(self._packet(), addr)

    def run(self):
        while not self._stop.wait(self.interval):
            try:
                self._send_once(("255.255.255.255", DISCOVERY_PORT))
            except OSError:
                pass

    def stop(self):
        self._stop.set()
        self._sock.close()
