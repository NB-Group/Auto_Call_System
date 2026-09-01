import time

from app.tts import NullBackend, TTSService


class FakeBackend:
    def __init__(self):
        self.played = []

    @property
    def available(self):
        return True

    def speak(self, text):
        self.played.append(text)


def test_queue_orders_and_repeats():
    fake = FakeBackend()
    svc = TTSService(backend=fake, repeat=2, gap=0.01)
    svc.speak("第一条")
    svc.speak("第二条")
    deadline = time.monotonic() + 5
    while len(fake.played) < 4 and time.monotonic() < deadline:
        time.sleep(0.01)
    svc.stop()
    assert fake.played == ["第一条", "第一条", "第二条", "第二条"]


def test_null_backend_available_false():
    assert NullBackend().available is False


class BadBackend:
    def __init__(self):
        self.calls = 0

    @property
    def available(self):
        return True

    def speak(self, text):
        self.calls += 1
        raise RuntimeError("boom")


def test_stop_unblocks_gap_wait():
    fake = FakeBackend()
    svc = TTSService(backend=fake, repeat=2, gap=5.0)
    svc.speak("仅一条")
    deadline = time.monotonic() + 5
    while len(fake.played) < 1 and time.monotonic() < deadline:
        time.sleep(0.01)
    svc.stop()
    time.sleep(0.5)
    assert len(fake.played) == 1  # stop() 后第二遍不播
    svc._worker.join(timeout=2)
    assert not svc._worker.is_alive()


def test_worker_survives_backend_exceptions():
    bad = BadBackend()
    svc = TTSService(backend=bad, repeat=1, gap=0.01)
    svc.speak("a")
    svc.speak("b")
    deadline = time.monotonic() + 5
    while bad.calls < 2 and time.monotonic() < deadline:
        time.sleep(0.01)
    assert svc._worker.is_alive()  # 异常未击穿 worker
    svc.stop()
    svc._worker.join(timeout=2)
    assert not svc._worker.is_alive()
    assert bad.calls == 2  # 两条都尝试过
