"""Simple in-memory sliding window rate limiter"""
import time
from collections import defaultdict
from fastapi import HTTPException, status

_WINDOW_SECONDS = 60
_MAX_REQUESTS = 10  # max decrypt attempts per window per user

_timestamps: dict[int, list[float]] = defaultdict(list)


def check_rate_limit(user_id: int, detail: str = "操作过于频繁，请稍后再试"):
    """Raise 429 if user_id exceeded _MAX_REQUESTS in the last _WINDOW_SECONDS."""
    now = time.monotonic()
    cutoff = now - _WINDOW_SECONDS
    # Prune expired entries
    ts = _timestamps[user_id] = [t for t in _timestamps[user_id] if t > cutoff]
    if len(ts) >= _MAX_REQUESTS:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)
    ts.append(now)
