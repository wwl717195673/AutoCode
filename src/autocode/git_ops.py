from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def run_git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def ensure_git_repo(repo: Path) -> None:
    try:
        run_git(repo, "rev-parse", "--is-inside-work-tree")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Repository is not a git worktree: {repo}") from exc


def current_head(repo: Path) -> str:
    return run_git(repo, "rev-parse", "HEAD")


def create_worktree(repo: Path, worktree_path: Path, branch_name: str, base_ref: str) -> None:
    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "worktree", "add", "-b", branch_name, str(worktree_path), base_ref],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=True,
    )


def remove_worktree(repo: Path, worktree_path: Path) -> None:
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(worktree_path)],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=True,
    )


def commit_all(worktree_path: Path, message: str) -> str | None:
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(worktree_path),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if not status:
        return None
    subprocess.run(["git", "add", "-A"], cwd=str(worktree_path), check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=str(worktree_path),
        check=True,
        capture_output=True,
        text=True,
    )
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(worktree_path),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def tool_exists(command: str) -> bool:
    return shutil.which(command) is not None
