from __future__ import annotations

import os
import selectors
import shlex
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from autocode.models import AgentName, AutoConfirmMode, RoundResult, TaskSpec

SAFE_CONFIRM_PATTERNS = (
    "continue?",
    "proceed?",
    "continue anyway?",
    "apply changes?",
    "overwrite temporary file?",
    "enter next round?",
)

DANGEROUS_PATTERNS = (
    "delete",
    "remove",
    "rm -rf",
    "reset --hard",
    "install system",
    "sudo",
    "network access",
    "outside workspace",
)


@dataclass(slots=True)
class AgentInvocation:
    agent: AgentName
    prompt: str
    worktree: Path
    round_number: int
    auto_confirm_mode: AutoConfirmMode
    timeout_seconds: int = 1800
    extra_env: dict[str, str] = field(default_factory=dict)


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _contains_prompt(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in ("[y/n]", "(y/n)", "yes/no", "confirm", "continue?"))


def _is_dangerous_prompt(text: str) -> bool:
    lowered = text.lower()
    return any(pattern in lowered for pattern in DANGEROUS_PATTERNS)


def _is_safe_prompt(text: str) -> bool:
    lowered = text.lower()
    return any(pattern in lowered for pattern in SAFE_CONFIRM_PATTERNS)


class AgentAdapter(ABC):
    name: AgentName

    @abstractmethod
    def build_command(self, invocation: AgentInvocation) -> list[str]:
        raise NotImplementedError

    def invoke(self, invocation: AgentInvocation) -> RoundResult:
        command = self.build_command(invocation)
        started_at = _iso_now()
        started = time.monotonic()
        events: list[str] = []
        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []
        blocked_reason: str | None = None
        env = os.environ.copy()
        env.update(invocation.extra_env)
        process = subprocess.Popen(
            command,
            cwd=str(invocation.worktree),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
        )
        selector = selectors.DefaultSelector()
        assert process.stdout is not None
        assert process.stderr is not None
        assert process.stdin is not None
        selector.register(process.stdout, selectors.EVENT_READ, ("stdout", process.stdout))
        selector.register(process.stderr, selectors.EVENT_READ, ("stderr", process.stderr))
        try:
            while selector.get_map():
                if time.monotonic() - started > invocation.timeout_seconds:
                    blocked_reason = "Agent invocation timed out."
                    process.kill()
                    break
                events_ready = selector.select(timeout=0.2)
                if not events_ready and process.poll() is not None:
                    break
                for key, _ in events_ready:
                    stream_name, stream = key.data
                    chunk = stream.readline()
                    if chunk == "":
                        selector.unregister(stream)
                        continue
                    if stream_name == "stdout":
                        stdout_chunks.append(chunk)
                    else:
                        stderr_chunks.append(chunk)
                    if _contains_prompt(chunk):
                        if _is_dangerous_prompt(chunk):
                            blocked_reason = f"Dangerous interactive prompt blocked: {chunk.strip()}"
                            process.kill()
                            break
                        if invocation.auto_confirm_mode == AutoConfirmMode.OFF:
                            blocked_reason = f"Interactive prompt encountered: {chunk.strip()}"
                            process.kill()
                            break
                        if _is_safe_prompt(chunk) or invocation.auto_confirm_mode == AutoConfirmMode.AGGRESSIVE:
                            process.stdin.write("yes\n")
                            process.stdin.flush()
                            events.append(f"Auto-confirmed prompt: {chunk.strip()}")
                        else:
                            blocked_reason = f"Unapproved interactive prompt: {chunk.strip()}"
                            process.kill()
                            break
                if blocked_reason:
                    break
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            blocked_reason = blocked_reason or "Agent process did not exit cleanly after timeout."
        finally:
            selector.close()
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()
            if process.stdin is not None:
                process.stdin.close()
        finished_at = _iso_now()
        return RoundResult(
            round_number=invocation.round_number,
            agent=invocation.agent,
            prompt=invocation.prompt,
            command=command,
            exit_code=process.returncode if process.returncode is not None else -9,
            stdout="".join(stdout_chunks),
            stderr="".join(stderr_chunks),
            duration_seconds=time.monotonic() - started,
            started_at=started_at,
            finished_at=finished_at,
            auto_confirm_events=events,
            blocked_reason=blocked_reason,
        )


class CodexAdapter(AgentAdapter):
    name = AgentName.CODEX

    def build_command(self, invocation: AgentInvocation) -> list[str]:
        return [
            "codex",
            "exec",
            "--sandbox",
            "workspace-write",
            "--ask-for-approval",
            "never",
            invocation.prompt,
        ]


class ClaudeAdapter(AgentAdapter):
    name = AgentName.CLAUDE

    def build_command(self, invocation: AgentInvocation) -> list[str]:
        return [
            "claude",
            "-p",
            "--permission-mode",
            "dontAsk",
            invocation.prompt,
        ]


def resolve_agent(task: TaskSpec, default_agent: AgentName) -> AgentName:
    chosen = task.effective_agent(default_agent)
    if chosen == AgentName.AUTO:
        return AgentName.CODEX
    return chosen


def get_adapter(agent: AgentName) -> AgentAdapter:
    if agent == AgentName.CODEX:
        return CodexAdapter()
    if agent == AgentName.CLAUDE:
        return ClaudeAdapter()
    raise ValueError(f"Unsupported agent: {agent}")


def build_prompt(
    task: TaskSpec,
    round_number: int,
    max_rounds: int,
    checks: list[str],
    failure_summary: str | None,
    custom_template: str | None,
) -> str:
    template = custom_template or (
        "You are working inside the provided git worktree.\n"
        "Task title: {title}\n"
        "Task id: {task_id}\n"
        "Round: {round_number}/{max_rounds}\n"
        "Acceptance checks:\n{checks}\n"
        "Previous failure summary:\n{failure_summary}\n\n"
        "Specification:\n{body}\n\n"
        "Requirements:\n"
        "- Implement the spec in this worktree.\n"
        "- Run or account for the acceptance checks before finishing.\n"
        "- Make concrete code changes instead of only describing a plan.\n"
        "- Leave the repository in a working state for commit.\n"
    )
    check_lines = "\n".join(f"- {command}" for command in checks) if checks else "- No acceptance checks configured."
    return template.format(
        title=task.title,
        task_id=task.id,
        round_number=round_number,
        max_rounds=max_rounds,
        checks=check_lines,
        failure_summary=failure_summary or "None",
        body=task.body,
    )
