from __future__ import annotations

from pathlib import Path
from typing import Any

from autocode.models import AgentName, AutoConfirmMode, BatchConfig
from autocode.simple_yaml import parse_simple_yaml


def _as_agent(value: str | None) -> AgentName:
    if value is None:
        return AgentName.AUTO
    return AgentName(value)


def _as_auto_confirm(value: str | None) -> AutoConfirmMode:
    if value is None:
        return AutoConfirmMode.SAFE
    return AutoConfirmMode(value)


def load_yaml_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = parse_simple_yaml(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Configuration file must contain a mapping: {path}")
    return data


def build_batch_config(args: Any, config_path: Path | None = None) -> BatchConfig:
    config_data = load_yaml_config(config_path or Path("autocode.yaml"))
    repo = Path(args.repo or config_data.get("repo") or ".").resolve()
    spec_dir = Path(args.spec_dir or config_data.get("spec_dir") or "specs")
    if not spec_dir.is_absolute():
        spec_dir = (repo / spec_dir).resolve()
    default_checks = list(args.default_check or config_data.get("default_checks") or [])
    prompt_template = args.prompt_template
    if prompt_template is None:
        prompt_template = config_data.get("prompt_template")
    return BatchConfig(
        repo=repo,
        spec_dir=spec_dir,
        agent=_as_agent(args.agent or config_data.get("agent")),
        default_checks=default_checks,
        max_rounds=int(args.max_rounds or config_data.get("max_rounds") or 3),
        continue_on_failure=bool(
            config_data.get("continue_on_failure", True)
            if args.continue_on_failure is None
            else args.continue_on_failure
        ),
        auto_confirm_mode=_as_auto_confirm(
            args.auto_confirm_mode or config_data.get("auto_confirm_mode")
        ),
        prompt_template=prompt_template,
        log_dir=str(config_data.get("log_dir") or ".autocode/runs"),
    )
