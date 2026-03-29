from __future__ import annotations


def _parse_scalar(value: str):
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none", "~"}:
        return None
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        return value


def parse_simple_yaml(text: str) -> dict:
    result: dict = {}
    lines = [line.rstrip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    index = 0
    while index < len(lines):
        line = lines[index]
        if ":" not in line:
            raise ValueError(f"Invalid YAML line: {line}")
        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        if value:
            result[key] = _parse_scalar(value)
            index += 1
            continue
        index += 1
        items: list = []
        while index < len(lines):
            child = lines[index]
            if not child.startswith("  - "):
                break
            items.append(_parse_scalar(child[4:].strip()))
            index += 1
        if items:
            result[key] = items
        else:
            result[key] = None
    return result
