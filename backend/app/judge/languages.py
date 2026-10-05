"""How each supported language is started, and which of them the platform offers.

The registry is the single answer to "can this language be run here", and both the
API and the catalog validator ask it that question rather than each keeping their
own list. That is deliberate: the four catalog definitions that shipped a Java
starter tab which the submission API then refused with a ``422`` were exactly the
kind of drift this module exists to make impossible.

Every interpreter is resolved from a fixed name at import time, never from
anything a request supplied, and a language whose interpreter is missing from
the machine is reported as unavailable rather than as an error the learner sees. The
editor should not offer a tab that cannot run.

Two shapes of language live here
--------------------------------
An *interpreted* language is one command line: the interpreter, its flags, and the
path the source was written to. Python and JavaScript are both of this shape, and
their command line is complete before the sandbox directory exists.

A *compiled* language is two command lines: a compiler that turns the source into
an artifact, and then a runtime that executes the artifact. Java is the only one of
this shape today. The split is recorded on the spec rather than inferred by the
runner, so "does this language need compiling" is one boolean answered in one
place, and a language is never half-supported because a caller forgot to compile.

Compilation is a separate step with its own budget for the reason the judge's own
docstring gives for having two clocks: a compiler that hangs is a different failure
from a program that hangs, and charging a learner for the compiler's start-up on
every test case would make the per-case time limit meaningless for a language whose
runtime alone takes hundreds of milliseconds to boot.
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
JAVA_EXTENSION = ".java"

#: The class a Java submission must declare. Fixed rather than derived from the
#: submitted filename because the judge writes every submission to one known name;
#: a learner whose class is called something else gets a compile error naming the
#: class the platform ran, which is the detail they need.
JAVA_MAIN_CLASS = "Main"


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
    #:
    #: Java is off for the same reason as Node, and for a stronger one: the JVM
    #: reserves its heap and metaspace as address space at start-up, so a cap
    #: below the reservation aborts the VM before the program's first line rather
    #: than when it allocates.
    enforce_address_space: bool

    #: Whether this language must be compiled before it can be run. ``False`` for
    #: an interpreted language, whose single command line is complete on its own.
    needs_compile: bool = False
    #: The compiler binary. Resolved at import time from a fixed name, exactly like
    #: :attr:`interpreter`, and required to be present as well as the interpreter
    #: before the language counts as available: a JVM with no ``javac`` cannot
    #: build a submission, so offering the tab would promise something the machine
    #: cannot deliver.
    compiler: str | None = None
    #: Flags passed to the compiler before the source path. ``-encoding UTF-8`` is
    #: not optional: ``javac`` otherwise assumes the platform's default charset, so
    #: a non-ASCII string in a reference solution would compile on a UTF-8 machine
    #: and fail on another. The source is always written as UTF-8, so the compiler
    #: is told to read it that way.
    compile_flags: tuple[str, ...] = ()
    #: Flags passed to the runtime before the classpath. These only shorten JVM
    #: start-up: a graded run gets a fixed wall clock per case, and the JVM's
    #: default tiered compilation and parallel collector cost more than they save
    #: on programs this size.
    runtime_flags: tuple[str, ...] = ()
    #: The class the runtime is asked to start. Only meaningful when
    #: :attr:`needs_compile` is set.
    main_class: str | None = None
    #: The stem of the file the source is written to, without its extension. Java
    #: cannot use the default ``main``: it requires a public class to live in a
    #: file named after it, so a submission declaring ``public class Main`` written
    #: to ``main.java`` is rejected by the compiler before it is read. Deriving the
    #: stem from the class name keeps the two from being able to disagree.
    entry_stem: str = "main"

    @property
    def available(self) -> bool:
        """Whether this machine can actually run the language.

        A compiled language needs two working binaries, not one, so asking for the
        compiler here is what keeps a JDK-less or JRE-only host from advertising a
        Java tab it cannot honour.
        """
        if self.interpreter is None:
            return False
        return not self.needs_compile or self.compiler is not None

    @property
    def appends_entry_path(self) -> bool:
        """Whether the command line ends with the path the source was written to.

        An interpreted language is started *by* its source file. A compiled one is
        started by a class name and finds its classes on a classpath instead, so
        appending the source path would hand the runtime an argument it cannot
        use. The worker reads this rather than guessing from the extension.
        """
        return not self.needs_compile

    def entry_name(self) -> str:
        """The file name the source is written to inside the sandbox directory."""
        return f"{self.entry_stem}{self.extension}"

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

    def compile_command(self, output_dir: str) -> list[str]:
        """The command line that compiles the source into ``output_dir``.

        ``output_dir`` is supplied by the caller rather than created here so that
        the compiled artifact outlives the single compile invocation and can be
        reused by every case of the submission. The path is absolute, so it means
        the same thing from the worker's sandbox directory.
        """
        if not self.needs_compile or self.compiler is None:
            raise LanguageUnavailableError(self.id)
        return [self.compiler, *self.compile_flags, "-d", output_dir]

    def run_command(self, classpath: str | None = None) -> list[str]:
        """The command line that runs an already-compiled program.

        For an interpreted language this is the interpreter and the source path,
        and ``classpath`` is ignored. For a compiled one it is the runtime, the
        directory the compiler wrote into, and the main class -- no source path,
        because the program is started from the artifact rather than the file.
        """
        if not self.needs_compile:
            return self.argv_prefix()
        if self.interpreter is None or not self.main_class or not classpath:
            raise LanguageUnavailableError(self.id)
        return [self.interpreter, *self.runtime_flags, "-cp", classpath, self.main_class]


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

#: Java is a compiled language, so it is the first entry in the registry that is
#: started by something other than the submitted file. ``javac`` builds the
#: submission into a class directory once per submission and ``java`` then runs it
#: once per test case; neither binary is resolved from anything a request supplied.
JAVA = LanguageSpec(
    id="java",
    label="Java",
    extension=JAVA_EXTENSION,
    interpreter=shutil.which("java") or shutil.which("java.exe"),
    enforce_address_space=False,
    needs_compile=True,
    compiler=shutil.which("javac") or shutil.which("javac.exe"),
    compile_flags=("-encoding", "UTF-8", "-nowarn"),
    runtime_flags=("-XX:+UseSerialGC", "-XX:TieredStopAtLevel=1"),
    main_class=JAVA_MAIN_CLASS,
    entry_stem=JAVA_MAIN_CLASS,
)

#: Every language the platform knows how to start. `database.problem_spec`
#: validates a catalog entry's `supported_languages` against this set, so a
#: problem cannot advertise a language with no runner behind it.
REGISTRY: tuple[LanguageSpec, ...] = (PYTHON, JAVASCRIPT, JAVA)

#: The canonical order, used wherever a list of languages is rendered so the
#: editor tabs and the API agree.
LANGUAGE_IDS: tuple[str, ...] = tuple(spec.id for spec in REGISTRY)

_BY_ID: dict[str, LanguageSpec] = {spec.id: spec for spec in REGISTRY}

#: Which languages a deployment has switched on, on top of which interpreters the
#: machine actually has. Resolved through the settings rather than baked in, so
#: setting `EXECUTION_JAVASCRIPT=false` genuinely removes the tab instead of
#: leaving a language the editor offers and the runner refuses.
_ENABLED_FLAGS = {
    "python": "execution_python",
    "javascript": "execution_javascript",
    "java": "execution_java",
}


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
    "JAVASCRIPT_EXTENSION",
    "JAVA",
    "JAVA_EXTENSION",
    "JAVA_MAIN_CLASS",
    "LANGUAGE_IDS",
    "PYTHON",
    "PYTHON_EXTENSION",
    "REGISTRY",
    "LanguageSpec",
    "LanguageUnavailableError",
    "available_languages",
    "get_language",
    "is_enabled",
    "supported_language_ids",
]
