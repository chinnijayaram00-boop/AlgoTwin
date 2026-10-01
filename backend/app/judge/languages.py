"""How each supported language is started, and which of them the platform offers.

The registry is the single answer to "can this language be run here", and both the
API and the catalog validator ask it that question rather than each keeping their
own list. That is deliberate: the four catalog definitions that shipped a Java
starter tab which the submission API then refused with a ``422`` were exactly the
kind of drift this module exists to make impossible.

Every interpreter is resolved from a fixed name at import time, never from
anything a request supplied, and a language whose interpreter is missing from the
machine is reported as unavailable rather than as an error the learner sees. The
editor should not offer a tab that cannot run.
"""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass

#: The extension the source is written to inside the sandbox directory. It is not
#: cosmetic: a Python program started as `main.js` will not import cleanly, and
#: Node resolves a file without an extension as CommonJS.
PYTHON_EXTENSION = ".py"
JAVASCRIPT_EXTENSION = ".js"


@dataclass(frozen=True)
class LanguageSpec:
    """Everything needed to start one language's runtime on one case."""

    id: str
    label: str
    extension: str
    interpreter: str | None
    #: Whether a POSIX ``RLIMIT_AS`` can be applied to this runtime.
    #:
    #: It can for CPython, where exceeding it raises ``MemoryError``. It must not
    #: be applied to Node: V8 reserves a large virtual address range up front
    #: that it never backs with physical pages, so an address-space cap makes
    #: Node abort during start-up regardless of how little memory the program
    #: actually uses. For Node the wall clock is the real bound and the measured
    #: peak RSS is reported instead.
    enforce_address_space: bool

    @property
    def available(self) -> bool:
        """Whether this machine can actually run the language."""
        return self.interpreter is not None

    def entry_name(self) -> str:
        """The file name the source is written to inside the sandbox directory."""
        return f"main{self.extension}"

    def argv_prefix(self) -> list[str]:
        """The interpreter and its flags, with no program path yet.

        Split out from :meth:`argv` because the program path does not exist until
        the worker has created its sandbox directory, while the parent has to
        describe the command line when it hands over the job.
        """
        if self.interpreter is None:  # pragma: no cover - guarded by `available`
            raise LanguageUnavailableError(self.id)
        if self.id == "python":
            # `-I` is isolated mode, which ignores `PYTHONPATH`, `PYTHONHOME` and
            # the user site directory, so the submitted program is started from an
            # interpreter that cannot import anything AlgoTwin installed for
            # itself. `-B` stops the run writing `.pyc` files into the sandbox.
            return [self.interpreter, "-I", "-B"]
        return [self.interpreter]

    def argv(self, entry_path: str) -> list[str]:
        """The full command line that runs ``entry_path``."""
        return [*self.argv_prefix(), entry_path]


class LanguageUnavailableError(RuntimeError):
    """A language was asked for that this machine cannot run."""


PYTHON = LanguageSpec(
    id="python",
    label="Python",
    extension=PYTHON_EXTENSION,
    # The same interpreter the API runs on, so the sandbox needs no second
    # installation. `-I -B` is added in `argv`.
    interpreter=sys.executable or None,
    enforce_address_space=True,
)

JAVASCRIPT = LanguageSpec(
    id="javascript",
    label="JavaScript",
    extension=JAVASCRIPT_EXTENSION,
    interpreter=shutil.which("node") or shutil.which("node.exe"),
    enforce_address_space=False,
)

#: Every language the platform knows how to start. `database.problem_spec`
#: validates a catalog entry's `supported_languages` against this set, so a
#: problem cannot advertise a language with no runner behind it.
REGISTRY: tuple[LanguageSpec, ...] = (PYTHON, JAVASCRIPT)

#: The canonical order, used wherever a list of languages is rendered so the
#: editor tabs and the API agree.
LANGUAGE_IDS: tuple[str, ...] = tuple(spec.id for spec in REGISTRY)

_BY_ID: dict[str, LanguageSpec] = {spec.id: spec for spec in REGISTRY}

#: Which languages a deployment has switched on, on top of which interpreters the
#: machine actually has. Resolved through the settings rather than baked in, so
#: setting `EXECUTION_JAVASCRIPT=false` genuinely removes the tab instead of
#: leaving a language the editor offers and the runner refuses.
_ENABLED_FLAGS = {"python": "execution_python", "javascript": "execution_javascript"}


def _flag_enabled(language_id: str, settings=None) -> bool:
    flag = _ENABLED_FLAGS.get(language_id)
    if flag is None:
        return True
    if settings is None:
        from backend.app.core.config import get_settings

        try:
            settings = get_settings()
        except Exception:  # noqa: BLE001 - a broken config must not silence a language
            return True
    try:
        return bool(getattr(settings, flag))
    except Exception:  # noqa: BLE001 - a broken config must not silence a language
        return True


def get_language(language_id: str | None, settings=None) -> LanguageSpec | None:
    """The spec for ``language_id``, or ``None`` if it is not a runnable language.

    Matching is case-insensitive because a language name is a human-facing word
    ("Python") as often as it is an identifier ("python"), but the *stored* value
    is always the lowercase id, so a submission's `language` column stays a
    closed vocabulary.

    A language the deployment has switched off is reported the same way an unknown
    one is -- ``None`` -- so no caller can accidentally treat "off" and "typo" as
    two different situations to handle.

    ``settings`` is passed in by callers that already have request-scoped settings
    resolved, so that "can this run here" is answered from one set of settings
    rather than from a second, process-wide read of the configuration.
    """
    if not isinstance(language_id, str):
        return None
    spec = _BY_ID.get(language_id.strip().lower())
    if spec is None or not spec.available or not _flag_enabled(spec.id, settings):
        return None
    return spec


def is_enabled(language_id: str, settings=None) -> bool:
    """Whether the deployment has switched this language on."""
    return _flag_enabled(language_id, settings)


def available_languages(settings=None) -> tuple[LanguageSpec, ...]:
    """The languages this machine can run right now."""
    return tuple(spec for spec in REGISTRY if get_language(spec.id, settings) is not None)


def supported_language_ids() -> frozenset[str]:
    """The language ids the platform can run, whether or not they are installed.

    This is the set a *catalog* entry is validated against. Using the set of
    runnable languages rather than the set of installed ones keeps a catalog
    definition valid on a developer machine without Node installed, so the
    committed catalog does not depend on what happens to be on the box that
    seeds the database.
    """
    return frozenset(LANGUAGE_IDS)


__all__ = [
    "JAVASCRIPT",
    "LANGUAGE_IDS",
    "PYTHON",
    "REGISTRY",
    "LanguageSpec",
    "LanguageUnavailableError",
    "available_languages",
    "get_language",
    "is_enabled",
    "supported_language_ids",
]
