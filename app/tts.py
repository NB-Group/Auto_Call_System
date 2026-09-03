"""TTS 抽象:后端按平台/环境变量插拔,队列顺序播报(spec §7)。"""
import os
import queue
import subprocess
import threading


class NullBackend:
    available = False

    def speak(self, text: str) -> None:  # pragma: no cover
        pass


class EspeakBackend:
    """Linux 开发调试用:espeak-ng,中文语音,音质机械。"""

    def __init__(self):
        self._proc_check()

    @staticmethod
    def _proc_check():
        subprocess.run(["espeak-ng", "--version"], capture_output=True,
                       check=True)

    @property
    def available(self) -> bool:
        try:
            self._proc_check()
            return True
        except Exception:
            return False

    def speak(self, text: str) -> None:
        subprocess.run(["espeak-ng", "-v", "zh", "-s", "150", text],
                       capture_output=True)


class SapiBackend:
    """Windows 生产路径:SAPI 离线中文语音。"""

    def __init__(self):
        import win32com.client  # 惰性导入(Nuitka:--include-package=win32com)
        self.voice = win32com.client.Dispatch("SAPI.SpVoice")
        for v in self.voice.GetVoices():
            try:  # 单个语音 token 缺 Name 属性/COM 异常:跳过,不中断选择
                name = v.GetAttribute("Name") if v.GetDescription() else ""
                if any(k in name for k in ("Huihui", "Kangkang", "Yaoyao",
                                           "Microsoft")):
                    self.voice.Voice = v
                    break
            except Exception:
                continue  # 无匹配或坏 token 则保留默认语音
        self.voice.Rate = -1  # 0.9× 语速

    @property
    def available(self) -> bool:
        return True

    def speak(self, text: str) -> None:
        self.voice.Speak(text, 0)  # 同步,天然排队


def pick_backend():
    forced = os.environ.get("TTS", "").lower()
    if forced == "none":
        return NullBackend()
    if forced == "espeak":
        return EspeakBackend()
    if os.name == "nt":
        try:
            return SapiBackend()
        except Exception:
            return NullBackend()
    try:
        return EspeakBackend()
    except Exception:
        return NullBackend()


class TTSService:
    """队列化播报:每条文本连播 repeat 遍,间隔 gap 秒(spec §5)。
    repeat 默认 1(一批一念一遍):显示端已按「组窗口关闭时合成一条」播报,
    双读已按用户反馈移除(逐人×2 遍太慢)。"""

    def __init__(self, backend=None, repeat: int = 1, gap: float = 0.8):
        self.backend = backend if backend is not None else pick_backend()
        self.repeat, self.gap = repeat, gap
        self._q: queue.Queue[str | None] = queue.Queue()
        self._stop = threading.Event()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    @property
    def available(self) -> bool:
        return self.backend.available

    def speak(self, text: str) -> None:
        if self.available:
            self._q.put(text)

    def _run(self):
        while not self._stop.is_set():
            text = self._q.get()
            if text is None or self._stop.is_set():
                return
            for i in range(self.repeat):
                if self._stop.is_set():
                    return
                try:
                    self.backend.speak(text)
                except Exception:
                    pass
                if i < self.repeat - 1:
                    self._stop.wait(self.gap)

    def stop(self):
        self._stop.set()
        self._q.put(None)
