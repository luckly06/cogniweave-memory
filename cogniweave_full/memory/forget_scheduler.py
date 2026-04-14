import threading
import time
from typing import Optional


class ForgetScheduler:
    def __init__(self, forget_manager, interval_seconds: int = 1800):
        self.forget_manager = forget_manager
        self.interval_seconds = interval_seconds
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="ForgetScheduler", daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

    def _loop(self):
        while self._running:
            try:
                self.forget_manager.run_full_cycle(dry_run=False)
            except Exception as exc:
                print(f"[ForgetScheduler] cycle failed: {exc}")
            time.sleep(self.interval_seconds)
