from __future__ import annotations

import re
from pathlib import Path

from autocode.models import AgentName, TaskSpec
from autocode.simple_yaml import parse_simple_yaml

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    raw = parse_simple_yaml(match.group(1)) or {}
    if not isinstance(raw, dict):
        raise ValueError("Spec frontmatter must be a mapping")
    body = text[match.end() :].strip()
    return raw, body


def discover_specs(spec_dir: Path) -> list[TaskSpec]:
    if not spec_dir.exists():
        raise FileNotFoundError(f"Spec directory does not exist: {spec_dir}")
    specs: list[TaskSpec] = []
    for index, path in enumerate(sorted(spec_dir.glob("*.md"))):
        text = path.read_text(encoding="utf-8")
        metadata, body = _parse_frontmatter(text)
        title = str(metadata.get("title") or path.stem.replace("_", " ").strip())
        checks = metadata.get("acceptance_checks") or []
        if isinstance(checks, str):
            checks = [checks]
        agent = metadata.get("agent")
        specs.append(
            TaskSpec(
                id=f"task-{index + 1:03d}",
                path=path.resolve(),
                title=title,
                body=body.strip(),
                priority=int(metadata.get("priority") or 0),
                acceptance_checks=list(checks),
                agent=AgentName(agent) if agent else None,
                max_rounds=int(metadata["max_rounds"]) if metadata.get("max_rounds") else None,
                raw_metadata=metadata,
            )
        )
    specs.sort(key=lambda item: (-item.priority, item.path.name))
    return specs
