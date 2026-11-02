"""Thread-safe sliding window rate limiter."""
import time
from collections import defaultdict
from threading import Lock
from functools import wraps
from flask import request, render_template

class SlidingWindowRateLimiter:
    def __init__(self):
        self._requests = defaultdict(list)
        self._lock = Lock()
    def is_allowed(self, key: str, max_requests: int, window_seconds: int = 60) -> tuple[bool, int]:
        now = time.time()
        cutoff = now - window_seconds
        with self._lock:
            ts = [t for t in self._requests[key] if t > cutoff]
            self._requests[key] = ts
            if len(ts) >= max_requests: return False, 0
            self._requests[key].append(now)
            return True, max_requests - len(self._requests[key])
    def reset(self, key: str):
        with self._lock:
            if key in self._requests: del self._requests[key]

limiter = SlidingWindowRateLimiter()

def rate_limit(max_requests: int = 15, window_seconds: int = 60, key_func=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            key = key_func() if key_func else f"{request.remote_addr or '127.0.0.1'}:{request.endpoint}"
            allowed, _ = limiter.is_allowed(key, max_requests=max_requests, window_seconds=window_seconds)
            if not allowed:
                return render_template('errors/429.html', retry_after=window_seconds), 429
            return f(*args, **kwargs)
        return decorated_function
    return decorator
