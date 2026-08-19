import queue
import threading

class LogsBroker:
    """Thread-safe broker to dispatch log updates from pipeline threads to SSE streams."""
    def __init__(self):
        self.listeners = []
        self._lock = threading.Lock()

    def subscribe(self):
        # Create a thread-safe FIFO Queue
        q = queue.Queue(maxsize=500)
        with self._lock:
            self.listeners.append(q)
        return q

    def unsubscribe(self, q):
        with self._lock:
            if q in self.listeners:
                self.listeners.remove(q)

    def publish(self, log_entry):
        with self._lock:
            for q in self.listeners:
                try:
                    q.put_nowait(log_entry)
                except queue.Full:
                    # Drop old logs if the queue overflows (slow client)
                    pass

logs_broker = LogsBroker()
