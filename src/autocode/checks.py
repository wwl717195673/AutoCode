from __future__ import annotations

import subprocess
import time
from pathlib import Path

from autocode.models import CheckResult


def run_check(command: str, cwd: Path) -> CheckResult:
    started = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        shell=True,
        capture_output=True,
        text=True,
    )
    return CheckResult(
        command=command,
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        duration_seconds=time.monotonic() - started,
    )


def summarize_failures(checks: list[CheckResult]) -> str:
    failures = [check for check in checks if not check.ok]
    if not failures:
        return "All acceptance checks passed."
    lines: list[str] = []
    for failure in failures:
        excerpt = (failure.stdout or failure.stderr).strip().splitlines()[:12]
        lines.append(f"Command `{failure.command}` failed with exit code {failure.exit_code}.")
        if excerpt:
            lines.append("\n".join(excerpt))
    return "\n\n".join(lines)
