"""Real execution: drive the limiter with the real wall clock."""

import time

from ratelimiter import RateLimiter

limiter = RateLimiter(limit=3, window_seconds=1.0, clock=time.monotonic)

print("burst of 5 requests from 'alice' (limit 3/sec):")
print([limiter.allow("alice") for _ in range(5)])

print("'bob' is unaffected:", limiter.allow("bob"))

time.sleep(1.05)
print("after the window passes, 'alice' again:", limiter.allow("alice"))
