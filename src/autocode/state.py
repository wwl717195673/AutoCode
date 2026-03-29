from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from autocode.models import AgentName, BatchRunState, CheckResult, RoundResult, TaskRunState, TaskStatus, utc_now


def run_root(repo: Path, log_dir: str) -> Path:
    return repo / log_dir


def batch_dir(repo: Path, log_dir: str, batch_id: str) -> Path:
    return run_root(repo, log_dir) / batch_id


def batch_state_path(repo: Path, log_dir: str, batch_id: str) -> Path:
    return batch_dir(repo, log_dir, batch_id) / "batch.json"


def save_batch_state(repo: Path, log_dir: str, state: BatchRunState) -> Path:
    path = batch_state_path(repo, log_dir, state.batch_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    state.updated_at = utc_now()
    path.write_text(json.dumps(state.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _load_round(raw: dict) -> RoundResult:
    checks = [CheckResult(**check) for check in raw.get("checks", [])]
    return RoundResult(
        round_number=raw["round_number"],
        agent=AgentName(raw["agent"]),
        prompt=raw["prompt"],
        command=raw["command"],
        exit_code=raw["exit_code"],
        stdout=raw["stdout"],
        stderr=raw["stderr"],
        duration_seconds=raw["duration_seconds"],
        started_at=raw["started_at"],
        finished_at=raw["finished_at"],
        auto_confirm_events=raw.get("auto_confirm_events", []),
        blocked_reason=raw.get("blocked_reason"),
        checks=checks,
    )


def _load_task(raw: dict) -> TaskRunState:
    task = TaskRunState(
        task_id=raw["task_id"],
        title=raw["title"],
        spec_path=raw["spec_path"],
        branch_name=raw["branch_name"],
        worktree_path=raw["worktree_path"],
        status=TaskStatus(raw["status"]),
        agent=AgentName(raw["agent"]),
        checks=raw.get("checks", []),
        max_rounds=raw.get("max_rounds", 3),
        current_round=raw.get("current_round", 0),
        commit_hash=raw.get("commit_hash"),
        failure_reason=raw.get("failure_reason"),
        started_at=raw.get("started_at"),
        finished_at=raw.get("finished_at"),
    )
    task.rounds = [_load_round(item) for item in raw.get("rounds", [])]
    return task


def load_batch_state(repo: Path, log_dir: str, batch_id: str) -> BatchRunState:
    raw = json.loads(batch_state_path(repo, log_dir, batch_id).read_text(encoding="utf-8"))
    tasks = [_load_task(task) for task in raw["tasks"]]
    return BatchRunState(
        batch_id=raw["batch_id"],
        created_at=raw["created_at"],
        updated_at=raw["updated_at"],
        repo=raw["repo"],
        spec_dir=raw["spec_dir"],
        config=raw["config"],
        tasks=tasks,
        status=raw["status"],
    )


def list_batches(repo: Path, log_dir: str) -> list[str]:
    root = run_root(repo, log_dir)
    if not root.exists():
        return []
    return sorted(item.name for item in root.iterdir() if item.is_dir())
