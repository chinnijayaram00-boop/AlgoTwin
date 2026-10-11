"""Failed-attempt throttling for the unauthenticated auth endpoints.

There is no shared quota mechanism in this repository (no Redis, no memcached,
no token bucket library), so this is a deliberately small fixed-window limiter
instead of an integration -- the same shape the AI provider calls use in
:mod:`backend.app.ai.rate_limit`.

**What it protects.** ``/auth/login`` and ``/auth/register`` were the two
unauthenticated endpoints that spend CPU on an Argon2id hash for every well
formed request: a login run verifies (or equalizer-hashes) a password, and a
registration hashes a new password. Without a ceiling that is a scriptable
brute-force surface for any known account and an unauthenticated compute-DoS
vector. This module adds two ceilings, both fail-closed:

* **Login -- failed attempts per (email, client IP)**. Only failed logins count;
  each one still runs the Argon2id verify (or the timing-equalizer hash), so the
  brute-force surface is a window with a hard ceiling rather than an open
  guessing loop. A successful login does not clear the window -- the count is
  what the window is for -- and the (email, IP) scope means a legitimate user
  locked out by a streak can sign in from another device or network, or wait
  out the window.
* **Register -- attempts per client IP.** Registration has no credential to
  verify, so the count is per IP rather than per address, and it counts a
  request even when the address already exists (that retry still runs a hash).

**What it is not.** Like the AI limiter it is per process: N workers permit
roughly N times the limit. That is a documented limitation, not a subtlety, and
moving the counters to shared storage is a different implementation of the same
``check``/``record`` surface. Keying on the client IP also assumes the app is
not behind a shared egress proxy; X-Forwarded-For is deliberately ignored so an
unauthenticated caller cannot spoof a clean-IP key.

The guard is **on by default** (``AUTH_THROTTLE_ENABLED=true``); a deployment
that wants no ceiling disables it explicitly. Either way the threshold never
appears in the ``/health`` response, so a caller cannot read the active budget.
"""

from __future__ import annotations

import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock

from fastapi import HTTPException, Request, status

from backend.app.schemas.auth import normalize_email

__all__ = ["AuthThrottle", "build_auth_throttle", "reset_throttle"]

logger = logging.getLogger(__name__)

_MAX_FAILURES = 10
_FAIL_WINDOW = 15 * 60
_MAX_REGISTRATIONS = 15
_REGISTRATION_WINDOW = 60 * 60

#: A valid 429 body must name a real error; a browser never deserialises the
#: body, but a scripted attacker reads it and there is nothing private in it.
BLOCKED_DETAIL = (
    "Too many failed attempts. Wait for the window to expire and try again."
)
REGISTER_BLOCKED_DETAIL = "Too many registration attempts from this address. Try again later."


@dataclass(frozen=True)
class AuthThrottleConfig:
    enabled: bool
    max_login_failures: int
    login_window_seconds: float
    max_registrations: int
    registration_window_seconds: float


class _FixedWindowCounter:
    """A bounded map of fixed-window counters, keyed by an integer token.

    Thread-safe, and with O(1) sweep of expired windows on every access, so the
    map holds at most one entry per distinct key active within the last window.
    """

    def __init__(self) -> None:
        self._windows: OrderedDict[int, tuple[float, int]] = OrderedDict()
        self._lock = Lock()

    def record(self, key: int, window: float, *, now: float | None = None) -> int:
        """Increment the key's counter in its current window and return the new count.

        When the existing window has passed, a fresh window starts from one.
        """
        moment = time.monotonic() if now is None else now
        with self._lock:
            window_end, count = self._windows.get(key, (0.0, 0))
            if window_end <= moment:
                self._windows[key] = (moment + window, 1)
                self._sweep(moment)
                return 1
            self._windows[key] = (window_end, count + 1)
            self._sweep(moment)
            return count + 1

    def blocked_for(self, key: int, max_count: int, window: float, *, now: float | None = None) -> float:
        """Seconds until ``key`` may act again, or 0.0 when it may act now.

        The window start is re-derived from only things this class stores, so the
        caller cannot disagree with the limiter about the remaining wait.
        """
        moment = time.monotonic() if now is None else now
        with self._lock:
            window_end, count = self._windows.get(key, (0.0, 0))
            self._sweep(moment)
            if window_end <= moment or count < max_count:
                return 0.0
            return window_end - moment

    def reset(self) -> None:
        with self._lock:
            self._windows.clear()

    def _sweep(self, moment: float) -> None:
        """Drop every elapsed window. Call with the lock held."""
        while self._windows:
            first_key = next(iter(self._windows))
            window_end, _ = self._windows[first_key]
            if window_end > moment:
                return
            self._windows.popitem(last=False)


class AuthThrottle:
    """The two failed-attempt guards wired into the auth routes.

    An instance holds no state of its own: it reads the configured limits and
    keeps its counters in :class:`_FixedWindowCounter` stores. Building a new
    instance is therefore cheap and RFC-docstring-safe.
    """

    def __init__(self, config: AuthThrottleConfig) -> None:
        self._config = config
        self._login = _FixedWindowCounter()
        self._register = _FixedWindowCounter()

    @property
    def config(self) -> AuthThrottleConfig:
        return self._config

    def check_login(self, request: Request, email: str) -> None:
        """Refuse a login attempt that has exhausted its (email, IP) budget.

        Raises 429 when the key is blocked. Every other attempt is passed
        through; the route records the outcome afterwards with
        :meth:`record_login_failure`.
        """
        if not self._config.enabled:
            return
        key = _account_key(email, request)
        retry_after = self._login.blocked_for(
            key, self._config.max_login_failures, self._config.login_window_seconds
        )
        if retry_after > 0:
            logger.warning("Login throttled after repeated failures (email=%s)", _mask(email))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=BLOCKED_DETAIL,
                headers={"Retry-After": str(max(1, int(retry_after)))},
            )

    def record_login_failure(self, request: Request, email: str) -> None:
        if not self._config.enabled:
            return
        self._login.record(
            _account_key(email, request), self._config.login_window_seconds
        )

    def check_register(self, request: Request) -> None:
        """Refuse a registration attempt from a (client IP) that is over budget."""
        if not self._config.enabled:
            return
        if self._register.blocked_for(
            _ip_key(request), self._config.max_registrations, self._config.registration_window_seconds
        ) > 0:
            logger.warning("Registration throttled (ip=%s)", request.client.host if request.client else "?")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=REGISTER_BLOCKED_DETAIL,
            )

    def record_register(self, request: Request) -> None:
        """Count a registration attempt (legitimate or refused)."""
        if not self._config.enabled:
            return
        self._register.record(
            _ip_key(request), self._config.registration_window_seconds
        )


#: The one throttle used when throttling is switched off: never blocks, never
#: counts. A single shared instance, so the "does anything throttle?" branch is a
#: lookup, not a per-request construction.
_DISABLED = AuthThrottle(
    AuthThrottleConfig(
        False, _MAX_FAILURES, _FAIL_WINDOW, _MAX_REGISTRATIONS, _REGISTRATION_WINDOW
    )
)

#: One throttle per process, keyed by the effective limits (see
#: :func:`build_auth_throttle`). The configuration in force when the application
#: was built decides which instance a request sees, mirroring how the AI limiter
#: keeps exactly one counter set per configured limit.
_AUTH_THROTTLES: dict[tuple, AuthThrottle] = {}


def build_auth_throttle(settings) -> AuthThrottle:
    """The process-wide throttle for this deployment (same shape as the AI
    limiter, :func:`backend.app.services.ai_service.build_limiter`).

    Reads the settings a route already resolved -- via ``Depends(get_settings)``
    -- rather than re-deriving configuration from the environment, so a process
    that overrides settings (tests, a multi-config app) throttles with the
    overrides, not the module's import-time defaults. Returns the shared
    disabled instance when throttling is switched off, and otherwise constructs
    one throttle per distinct effective limits and reuses it: every request in
    this process shares a single set of counters for the configured limits.
    """
    if not getattr(settings, "auth_throttle_enabled", False):
        return _DISABLED
    limits = _limits_from_settings(settings)
    key = (
        limits.max_login_failures,
        limits.login_window_seconds,
        limits.max_registrations,
        limits.registration_window_seconds,
    )
    cache = _AUTH_THROTTLES.setdefault(key, None)
    if cache is None:
        cache = AuthThrottle(limits)
        _AUTH_THROTTLES[key] = cache
    return cache


def reset_throttle() -> None:
    """Forget every cached throttle. For tests only."""
    for throttle in _AUTH_THROTTLES.values():
        throttle._login.reset()
        throttle._register.reset()
    _AUTH_THROTTLES.clear()


def _limits_from_settings(settings) -> AuthThrottleConfig:
    """Map a :class:`Settings` (or settings-like) onto a config with defaults."""
    return AuthThrottleConfig(
        enabled=bool(getattr(settings, "auth_throttle_enabled", False)),
        max_login_failures=int(getattr(settings, "auth_max_login_failures", _MAX_FAILURES)),
        login_window_seconds=float(getattr(settings, "auth_login_window_seconds", _FAIL_WINDOW)),
        max_registrations=int(getattr(settings, "auth_max_registrations", _MAX_REGISTRATIONS)),
        registration_window_seconds=float(
            getattr(settings, "auth_register_window_seconds", _REGISTRATION_WINDOW)
        ),
    )


def _account_key(email: str, request: Request) -> int:
    return hash((normalize_email(email), _ip_key(request)))


def _ip_key(request: Request) -> int:
    client = request.client
    host = client.host if client is not None else "unknown"
    return hash(host)


def _mask(email: str) -> str:
    """A display-safe rendering for logs: the local part is elided."""
    local, _, domain = email.partition("@")
    if not domain:
        return "***"
    return f"{local[:2]}***@{domain}"