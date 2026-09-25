from dataclasses import dataclass


class ExecutionNotConfiguredError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExecutionRequest:
    language: str
    source_code: str
    stdin: str = ""
    test_cases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExecutionResult:
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int


class CodeExecutionService:
    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        raise ExecutionNotConfiguredError("Sandboxed code execution is not enabled in the foundation release.")
