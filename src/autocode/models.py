from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class AgentName(str, Enum):
    AUTO = "auto"
    CODEX = "codex"
    CLAUDE = "claude"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class AutoConfirmMode(str, Enum):
    OFF = "off"
    SAFE = "safe"
    AGGRESSIVE = "aggressive"


@dataclass(slots=True)
class BatchConfig:
    repo: Path
    spec_dir: Path
    agent: AgentName = AgentName.AUTO
    default_checks: list[str] = field(default_factory=list)
    max_rounds: int = 3
    continue_on_failure: bool = True
    auto_confirm_mode: AutoConfirmMode = AutoConfirmMode.SAFE
    prompt_template: str | None = None
    log_dir: str = ".autocode/runs"


@dataclass(slots=True)
class TaskSpec:
    id: str
    path: Path
    title: str
    body: str
    priority: int = 0
    acceptance_checks: list[str] = field(default_factory=list)
    agent: AgentName | None = None
    max_rounds: int | None = None
    raw_metadata: dict[str, Any] = field(default_factory=dict)

    def effective_checks(self, default_checks: list[str]) -> list[str]:
        return self.acceptance_checks or list(default_checks)

    def effective_agent(self, batch_agent: AgentName) -> AgentName:
        if self.agent and self.agent != AgentName.AUTO:
            return self.agent
        return batch_agent

    def effective_max_rounds(self, batch_max_rounds: int) -> int:
        return self.max_rounds or batch_max_rounds


@dataclass(slots=True)
class CheckResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


@dataclass(slots=True)
class RoundResult:
    round_number: int
    agent: AgentName
    prompt: str
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    started_at: str
    finished_at: str
    auto_confirm_events: list[str] = field(default_factory=list)
    blocked_reason: str | None = None
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def checks_passed(self) -> bool:
        return all(check.ok for check in self.checks)


@dataclass(slots=True)
class TaskRunState:
    task_id: str
    title: str
    spec_path: str
    branch_name: str
    worktree_path: str
    status: TaskStatus = TaskStatus.PENDING
    agent: AgentName = AgentName.AUTO
    checks: list[str] = field(default_factory=list)
    max_rounds: int = 3
    current_round: int = 0
    rounds: list[RoundResult] = field(default_factory=list)
    commit_hash: str | None = None
    failure_reason: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


@dataclass(slots=True)
class BatchRunState:
    batch_id: str
    created_at: str
    updated_at: str
    repo: str
    spec_dir: str
    config: dict[str, Any]
    tasks: list[TaskRunState]
    status: str = "running"

    def to_dict(self) -> dict[str, Any]:
        return _json_ready(asdict(self))


def _json_ready(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value
