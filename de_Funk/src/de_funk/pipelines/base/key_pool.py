import time
from collections import deque

class ApiKeyPool:
    def __init__(self, keys, cooldown_seconds=60.0):
        self.keys = deque(keys or [])
        self.cooldown = cooldown_seconds
        self.last_used = {}

    def size(self):
        return len(self.keys)

    def next_key(self):
        if not self.keys:
            return None
        now = time.time()
        k = self.keys[0]
        if k in self.last_used and (now - self.last_used[k]) < self.cooldown:
            self.keys.rotate(-1)
            k = self.keys[0]
        self.last_used[k] = now
        self.keys.rotate(-1)
        return k

    def mark_exhausted(self, key):
        """Mark a key as exhausted (rate-limited). Moves it to the back."""
        if key in self.keys:
            self.keys.remove(key)
            self.keys.append(key)
            self.last_used[key] = time.time()
