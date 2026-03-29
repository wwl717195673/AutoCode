from __future__ import annotations

import argparse
import json
from pathlib import Path

from autocode.config import build_batch_config
from autocode.orchestrator import continue_batch, format_report, run_batch
from autocode.state import list_batches, load_batch_state


def _bool_flag(value: str | None) -> bool | None:
    if value is None:
        return None
    return value.lower() in {"1", "true", "yes", "on"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="autocode", description="Batch orchestrator for CLI coding agents.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run all specs in a batch.")
    _add_common_run_options(run_parser)

    resume_parser = subparsers.add_parser("resume", help="Resume an existing batch.")
    _add_common_run_options(resume_parser)
    resume_parser.add_argument("batch_id")

    status_parser = subparsers.add_parser("status", help="Show current batch status or list batches.")
    status_parser.add_argument("batch_id", nargs="?")
    status_parser.add_argument("--repo", default=".")
    status_parser.add_argument("--log-dir", default=".autocode/runs")

    report_parser = subparsers.add_parser("report", help="Show a batch report.")
    report_parser.add_argument("batch_id")
    report_parser.add_argument("--repo", default=".")
    report_parser.add_argument("--log-dir", default=".autocode/runs")
    report_parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def _add_common_run_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo")
    parser.add_argument("--spec-dir")
    parser.add_argument("--agent", choices=["auto", "codex", "claude"])
    parser.add_argument("--default-check", action="append")
    parser.add_argument("--max-rounds", type=int)
    parser.add_argument("--continue-on-failure", type=_bool_flag)
    parser.add_argument("--auto-confirm-mode", choices=["off", "safe", "aggressive"])
    parser.add_argument("--prompt-template")
    parser.add_argument("--config", default="autocode.yaml")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        config = build_batch_config(args, Path(args.config))
        state = run_batch(config)
        print(format_report(state))
        return 0 if state.status == "completed" else 1
    if args.command == "resume":
        config = build_batch_config(args, Path(args.config))
        state = continue_batch(config, args.batch_id)
        print(format_report(state))
        return 0 if state.status == "completed" else 1
    if args.command == "status":
        repo = Path(args.repo).resolve()
        if args.batch_id:
            state = load_batch_state(repo, args.log_dir, args.batch_id)
            print(format_report(state))
        else:
            batches = list_batches(repo, args.log_dir)
            print("\n".join(batches))
        return 0
    if args.command == "report":
        repo = Path(args.repo).resolve()
        state = load_batch_state(repo, args.log_dir, args.batch_id)
        if args.as_json:
            print(json.dumps(state.to_dict(), indent=2, ensure_ascii=False))
        else:
            print(format_report(state))
        return 0
    parser.error(f"Unknown command: {args.command}")
    return 2
