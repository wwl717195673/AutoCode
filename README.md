# AutoCode CLI

AutoCode CLI is a Python command line orchestrator that runs coding agents like
Codex and Claude against a queue of Markdown specs, verifies the results, and
keeps moving through the batch with persistent state.

## Features

- Sequential execution of `specs/*.md`
- Per-task git worktree isolation
- Non-interactive adapters for `codex` and `claude`
- Retry loop with automated validation checks
- Persistent run state in `.autocode/runs/<batch-id>/`
- Human-readable and JSON reports

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
autocode run --repo /path/to/repo --spec-dir specs --default-check "pytest -q"
```

## Spec Format

Each task is a Markdown file. Optional YAML frontmatter may define metadata:

```md
---
title: Add login endpoint
agent: codex
priority: 10
max_rounds: 4
acceptance_checks:
  - pytest -q
  - ruff check .
---

Implement login endpoint and tests.
```

## Configuration

An optional `autocode.yaml` file may define defaults:

```yaml
repo: /path/to/repo
spec_dir: specs
agent: auto
max_rounds: 3
continue_on_failure: true
default_checks:
  - pytest -q
auto_confirm_mode: aggressive
prompt_template: null
```
