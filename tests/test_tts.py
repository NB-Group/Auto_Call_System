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
