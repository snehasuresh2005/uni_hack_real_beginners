import threading


class LlmBudget:
    """Thread-safe request budget shared by a bulk enrichment run."""

    def __init__(self, limit):
        self.limit = max(0, int(limit))
        self.used = 0
        self._lock = threading.Lock()

    def reserve(self):
        with self._lock:
            if self.used >= self.limit:
                return False
            self.used += 1
            return True
