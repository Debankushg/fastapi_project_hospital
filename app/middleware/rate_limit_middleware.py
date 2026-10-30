import time
from collections import defaultdict, deque

from fastapi import Depends, Request

from app.config.constants import AUTH_RATE_LIMIT
from app.utils.http_error_util import HttpError

# In-memory, per client IP (like express-rate-limit's default store).
_hits: dict[str, deque[float]] = defaultdict(deque)


async def _auth_rate_limit(request: Request) -> None:
    now = time.monotonic()
    window = AUTH_RATE_LIMIT["window_seconds"]
    q = _hits[request.client.host if request.client else "unknown"]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= AUTH_RATE_LIMIT["limit"]:
        raise HttpError(429, "Too many requests, please try again later.")
    q.append(now)


# Route dependency:  dependencies=[auth_rate_limiter]
auth_rate_limiter = Depends(_auth_rate_limit)
