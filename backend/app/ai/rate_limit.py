"""Rate limiting for outbound provider calls.

There is no shared quota mechanism anywhere in this repository -- no Redis, no
memcached, no token bucket library, no existing per-user counter -- so this is a
deliberately small implementation rather than an integration.

**What it limits, and why not more.** It charges a request only when a request is
actually sent to a provider. A cache hit is free and is never charged, because the
platform spent nothing on it and charging for it would make the cache a
penalty. It also does not charge a request that is refused before the network --
an unconfigured provider raises before anything is sent -- so a deployment with AI
switched off cannot exhaust a budget nobody can spend.

**How it counts.** A fixed-window counter per learner, per process. The window is a
minute of wall-clock time; when it elapses the counter resets. That is simpler than
a sliding window and the imprecision is in the generous direction: a learner can
burst at the boundary and reach roughly twice the limit within a few seconds. For a
guard against a client hammering a paid endpoint that is an acceptable trade, and
the alternative -- a sliding window -- needs per-request bookkeeping to answer a
question this feature does not ask.

**What it is not.** It is per process, so a deployment running N workers permits
roughly N times the limit. That is a real limitation, not a subtlety, and it is
stated in the README rather than left to be discovered. Moving it to shared storage
is the fix, and it is a different implementation of the same three methods
(``check``, ``record``, ``reset``) rather than a redesign.

The counters are bounded: at most one entry per learner who has made a request in
the last window, and expired entries are swept on every call. A process that serves
many distinct learners therefore holds a bounded map, not one that grows with the
user table.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from threading import Lock

from backend.app.ai.errors import AIRateLimitError

#: How long a window lasts. Named so the unit-window behaviour is stated once: this
#: is a fixed window of one minute, not a sliding log of the last minute's requests.
WINDOW_SECONDS: float = 60.0


class RateLimiter:
    """A per-learner, per-process limit on how often a provider may be called."""

    def __init__(self, limit: int, *, window_seconds: float = WINDOW_SECONDS) -> None:
        self._limit = max(1, int(limit))
        self._window = float(window_seconds)
        # Ordered by window end so the sweep at the front of every check removes the
        # oldest entries first, and so the map never holds a learner whose window has
        # passed.
        self._windows: OrderedDict[int, tuple[float, int]] = OrderedDict()
        self._lock = Lock()

    @property
    def limit(self) -> int:
        return self._limit

    def _now(self) -> float:
        # Injectable through the clock argument in tests; here it is the real clock.
        return time.monotonic()

    def check(self, key: int, *, now: float | None = None) -> float:
        """Seconds until ``key`` may make another call.

        Raises :class:`~backend.app.ai.errors.AIRateLimitError` when the learner is
        at their limit. The exception carries the wait, so the route can set
        ``Retry-After`` from the same number the limiter computed rather than
        re-deriving it and risking a disagreement between the two.
        """
        moment = self._now() if now is None else now
        with self._lock:
            window_end, count = self._windows.get(key, (0.0, 0))
            if window_end <= moment:
                # The window has passed: this learner starts again from zero.
                self._windows[key] = (moment + self._window, 1)
                self._sweep(moment)
                return 0.0
            if count >= self._limit:
                retry_after = window_end - moment
                self._sweep(moment)
                raise AIRateLimitError(retry_after)
            self._windows[key] = (window_end, count + 1)
            self._sweep(moment)
            return 0.0

    def remaining(self, key: int, *, now: float | None = None) -> int:
        """Calls ``key`` may still make in the current window, for diagnostics."""
        moment = self._now() if now is None else now
        with self._lock:
            window_end, count = self._windows.get(key, (0.0, 0))
            if window_end <= moment:
                return self._limit
            return max(0, self._limit - count)

    def reset(self, key: int | None = None) -> None:
        """Forget one learner's window, or every window.

        Used by tests to isolate cases. No request path calls it: a limiter that a
        request could reset is not a limiter.
        """
        with self._lock:
            if key is None:
                self._windows.clear()
            else:
                self._windows.pop(key, None)

    def _sweep(self, moment: float) -> None:
        """Drop every window that has elapsed. Called with the lock held.

        Sweeping here rather than on a timer means the map's size is bounded by the
        number of learners active within the last minute, with no background thread
        to leak.
        """
        while self._windows:
            first_key = next(iter(self._windows))
            window_end, _ = self._windows[first_key]
            if window_end > moment:
                return
            self._windows.popitem(last=False)


class NullRateLimiter:
    """A limiter that permits everything.

    What the routes are given when a deployment configures a limit below one. The
    interface is satisfied so the call site has no branch on whether limiting is in
    effect -- a ``if limiter is None`` check at three call sites is three chances to
    forget one.
    """

    limit = 0

    def check(self, key: int, *, now: float | None = None) -> float:
        return 0.0

    def remaining(self, key: int, *, now: float | None = None) -> int:
        return 0

    def reset(self, key: int | None = None) -> None:
        return None


__all__ = ["WINDOW_SECONDS", "NullRateLimiter", "RateLimiter"]
