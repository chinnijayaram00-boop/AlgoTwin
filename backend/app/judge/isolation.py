"""The isolation capability check behind every code-execution route.

One question, answered honestly: *may this deployment run a learner's code right
now?* The answer is the conjunction of three decisions an operator makes, and a
refusal names which one is missing:

* **Intent.** ``EXECUTION_ENABLED`` is not set (the kill switch).
* **A verified backend.** ``EXECUTION_ISOLATION`` names a backend that is
  actually configured and verified to contain untrusted code.
* **An explicit acknowledgment.** When the named backend is *not* a verified
  containment backend, ``EXECUTION_ALLOW_INSECURE_NATIVE`` must be set -- an
  operator's recorded, nameable decision to run student code without OS-level
  isolation (a trusted host, a closed test network, a preview box).

The registry below is deliberately small and deliberately boring. Phase 2 of the
hardening work registers real containment backends (containers, a verified
sandbox). Until one exists, ``none`` is the only registered name and it states
plainly in its own definition that it provides no OS-level isolation; no code in
this repository may claim otherwise.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class IsolationBackend:
    """One isolation backend a deployment can name in ``EXECUTION_ISOLATION``.

    ``verified`` means a startup check confirmed the machinery is present and
    working. ``isolates_untrusted_code`` means that even verified, it contains
    untrusted code against the host. The native supervisor never satisfies the
    second: it enforces a wall clock and an output ceiling but no OS isolation.
    """

    id: str
    label: str
    verified: bool
    isolates_untrusted_code: bool


#: Backends registered in this codebase. Phase 1 registers only ``none``; future
#: backends are added here together with the startup verification that earns
#: ``verified=True``. A name not in the registry is refused, not guessed at.
REGISTERED_BACKENDS: dict[str, IsolationBackend] = {
    "none": IsolationBackend(
        id="none",
        label="native process supervisor (no OS-level isolation)",
        verified=True,
        isolates_untrusted_code=False,
    ),
}


def resolve_backend(settings) -> IsolationBackend | None:
    """The backend ``EXECUTION_ISOLATION`` names, or ``None`` if not registered.

    ``None`` (an unknown name) is a refusal, exactly like naming a backend whose
    verification failed: the response must never run code under a backend the
    deployment did not actually configure.
    """
    name = str(getattr(settings, "execution_isolation", "none") or "none").strip().lower()
    return REGISTERED_BACKENDS.get(name)


def execution_available(settings) -> tuple[bool, str | None]:
    """Whether learner code may run on this deployment, and the reason if not.

    ``(True, None)`` means the gate is open. ``(False, reason)`` names the single
    missing decision. Route handlers turn a ``False`` into a 503; nothing falls
    through to a silent run.
    """
    if not bool(getattr(settings, "execution_enabled", False)):
        return False, "Code execution is disabled on this deployment."
    backend = resolve_backend(settings)
    if backend is None:
        return (
            False,
            f"EXECUTION_ISOLATION={settings.execution_isolation!r} is not a registered "
            "isolation backend, so learner code cannot run.",
        )
    if backend.isolates_untrusted_code and backend.verified:
        return True, None
    if bool(getattr(settings, "execution_allow_insecure_native", False)):
        return True, None
    return (
        False,
        "This deployment has not configured a verified isolation backend for learner "
        f"code: EXECUTION_ISOLATION names {backend.label!r}, which provides no "
        "OS-level containment of untrusted code. Refusing rather than running "
        "un-isolated. A trusted environment may set EXECUTION_ALLOW_INSECURE_NATIVE=true "
        "to acknowledge that decision explicitly.",
    )