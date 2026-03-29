from __future__ import annotations

import json
import subprocess
import uuid
from dataclasses import asdict
from pathlib import Path

from autocode.agents import AgentInvocation, build_prompt, get_adapter, resolve_agent
from autocode.checks import run_check, summarize_failures
from autocode.git_ops import commit_all, create_worktree, current_head, ensure_git_repo, tool_exists
from autocode.models import (
    BatchConfig,
    BatchRunState,
    RoundResult,
    TaskRunState,
    TaskSpec,
    TaskStatus,
    _json_ready,
    utc_now,
)
from autocode.specs import discover_specs
from autocode.state import batch_dir, load_batch_state, save_batch_state


def _task_branch_name(batch_id: str, task: TaskSpec) -> str:
    return f"autocode/{batch_id}/{task.id}"


def _task_worktree_path(repo: Path, batch_id: str, task: TaskSpec) -> Path:
    return repo / ".autocode" / "worktrees" / batch_id / task.id


def initialize_batch(config: BatchConfig) -> BatchRunState:
    ensure_git_repo(config.repo)
    specs = discover_specs(config.spec_dir)
    batch_id = uuid.uuid4().hex[:12]
    tasks: list[TaskRunState] = []
    for spec in specs:
        task_agent = resolve_agent(spec, config.agent)
        tasks.append(
            TaskRunState(
                task_id=spec.id,
                title=spec.title,
                spec_path=str(spec.path),
                branch_name=_task_branch_name(batch_id, spec),
                worktree_path=str(_task_worktree_path(config.repo, batch_id, spec)),
                agent=task_agent,
                checks=spec.effective_checks(config.default_checks),
                max_rounds=spec.effective_max_rounds(config.max_rounds),
            )
        )
    state = BatchRunState(
        batch_id=batch_id,
        created_at=utc_now(),
        updated_at=utc_now(),
        repo=str(config.repo),
        spec_dir=str(config.spec_dir),
        config={
            "agent": config.agent.value,
            "default_checks": list(config.default_checks),
            "max_rounds": config.max_rounds,
            "continue_on_failure": config.continue_on_failure,
            "auto_confirm_mode": config.auto_confirm_mode.value,
            "prompt_template": config.prompt_template,
            "log_dir": config.log_dir,
        },
        tasks=tasks,
        status="running",
    )
    save_batch_state(config.repo, config.log_dir, state)
    return state


def _find_spec(state: BatchRunState, task_state: TaskRunState) -> TaskSpec:
    all_specs = {spec.id: spec for spec in discover_specs(Path(state.spec_dir))}
    return all_specs[task_state.task_id]


def _ensure_tooling(task_state: TaskRunState) -> None:
    if not tool_exists(task_state.agent.value):
        raise RuntimeError(f"Required agent binary not found in PATH: {task_state.agent.value}")


def _persist_round_logs(repo: Path, log_dir: str, batch_id: str, task_id: str, round_result: RoundResult) -> None:
    directory = batch_dir(repo, log_dir, batch_id) / "tasks" / task_id / f"round-{round_result.round_number:02d}"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "prompt.txt").write_text(round_result.prompt, encoding="utf-8")
    (directory / "stdout.txt").write_text(round_result.stdout, encoding="utf-8")
    (directory / "stderr.txt").write_text(round_result.stderr, encoding="utf-8")
    payload = _json_ready(asdict(round_result))
    (directory / "result.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _run_task(config: BatchConfig, state: BatchRunState, task_state: TaskRunState) -> None:
    _ensure_tooling(task_state)
    spec = _find_spec(state, task_state)
    repo = Path(state.repo)
    worktree = Path(task_state.worktree_path)
    if not worktree.exists():
        create_worktree(repo, worktree, task_state.branch_name, current_head(repo))
    task_state.started_at = task_state.started_at or utc_now()
    task_state.status = TaskStatus.RUNNING
    failure_summary: str | None = None
    adapter = get_adapter(task_state.agent)
    for round_number in range(task_state.current_round + 1, task_state.max_rounds + 1):
        task_state.current_round = round_number
        prompt = build_prompt(
            task=spec,
            round_number=round_number,
            max_rounds=task_state.max_rounds,
            checks=task_state.checks,
            failure_summary=failure_summary,
            custom_template=config.prompt_template,
        )
        result = adapter.invoke(
            AgentInvocation(
                agent=task_state.agent,
                prompt=prompt,
                worktree=worktree,
                round_number=round_number,
                auto_confirm_mode=config.auto_confirm_mode,
            )
        )
        result.checks = [run_check(command, worktree) for command in task_state.checks]
        task_state.rounds.append(result)
        _persist_round_logs(repo, config.log_dir, state.batch_id, task_state.task_id, result)
        if result.blocked_reason:
            failure_summary = result.blocked_reason
        elif result.exit_code != 0:
            failure_summary = f"Agent exited with code {result.exit_code}.\n{result.stderr.strip()}"
        elif not result.checks_passed:
            failure_summary = summarize_failures(result.checks)
        else:
            task_state.status = TaskStatus.SUCCEEDED
            task_state.commit_hash = commit_all(
                worktree,
                f"autocode: complete {task_state.task_id} {task_state.title}",
            )
            task_state.finished_at = utc_now()
            return
        task_state.failure_reason = failure_summary
        save_batch_state(config.repo, config.log_dir, state)
    task_state.status = TaskStatus.FAILED
    task_state.finished_at = utc_now()


def run_batch(config: BatchConfig) -> BatchRunState:
    state = initialize_batch(config)
    return continue_batch(config, state.batch_id)


def continue_batch(config: BatchConfig, batch_id: str) -> BatchRunState:
    state = load_batch_state(config.repo, config.log_dir, batch_id)
    for task in state.tasks:
        if task.status in {TaskStatus.SUCCEEDED, TaskStatus.SKIPPED}:
            continue
        try:
            _run_task(config, state, task)
        except subprocess.CalledProcessError as exc:
            task.status = TaskStatus.FAILED
            task.finished_at = utc_now()
            task.failure_reason = exc.stderr.strip() or str(exc)
        except Exception as exc:  # noqa: BLE001
            task.status = TaskStatus.FAILED
            task.finished_at = utc_now()
            task.failure_reason = str(exc)
        save_batch_state(config.repo, config.log_dir, state)
        if task.status == TaskStatus.FAILED and not config.continue_on_failure:
            state.status = "failed"
            save_batch_state(config.repo, config.log_dir, state)
            return state
    if any(task.status == TaskStatus.FAILED for task in state.tasks):
        state.status = "completed_with_failures"
    else:
        state.status = "completed"
    save_batch_state(config.repo, config.log_dir, state)
    return state


def format_report(state: BatchRunState) -> str:
    lines = [
        f"Batch: {state.batch_id}",
        f"Status: {state.status}",
        f"Repo: {state.repo}",
        f"Spec dir: {state.spec_dir}",
        "",
    ]
    for task in state.tasks:
        lines.append(f"- {task.task_id} [{task.status}] {task.title}")
        lines.append(f"  rounds={task.current_round}/{task.max_rounds} agent={task.agent}")
        if task.commit_hash:
            lines.append(f"  commit={task.commit_hash}")
        if task.failure_reason:
            lines.append(f"  failure={task.failure_reason}")
    return "\n".join(lines)
