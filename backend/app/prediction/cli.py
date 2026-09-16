"""P3 prediction CLI: audit, benchmark, verify-artifact (T61).

Fails closed when `TENNIX_MODEL_DATA_PATH` (or --data), the source/license
metadata or the audit gate is missing. Selection happens on validation; the
test split is reported only after selection. Never prints raw rows.

Usage:
    uv run python -m app.prediction.cli audit --data PATH --output artifacts/p3/audit.json
    uv run python -m app.prediction.cli benchmark --data PATH --output artifacts/p3
    uv run python -m app.prediction.cli verify-artifact --artifact-dir artifacts/p3
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from app.prediction.audit import audit_source
from app.prediction.benchmark import (
    BenchmarkGateError,
    run_benchmark,
    verify_artifact,
)
from app.prediction.data import CsvHistoricalMatchSource, DataGateError

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_AUDIT_FAILED = 3
EXIT_VERIFY_FAILED = 4


def _code_version() -> str:
    try:
        return (
            subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            ).stdout.strip()
            or "unknown"
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _resolve_data_path(explicit: str | None) -> Path:
    raw = explicit or os.environ.get("TENNIX_MODEL_DATA_PATH")
    if not raw:
        raise SystemExit(
            "TENNIX_MODEL_DATA_PATH (or --data) is required; refusing to run "
            "without an identified local historical source"
        )
    return Path(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.prediction.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit_parser = subparsers.add_parser("audit")
    audit_parser.add_argument("--data")
    audit_parser.add_argument("--output", required=True)

    benchmark_parser = subparsers.add_parser("benchmark")
    benchmark_parser.add_argument("--data")
    benchmark_parser.add_argument("--output", required=True)
    benchmark_parser.add_argument("--seed", type=int, default=42)

    verify_parser = subparsers.add_parser("verify-artifact")
    verify_parser.add_argument("--artifact-dir", required=True)

    args = parser.parse_args(argv)

    if args.command == "verify-artifact":
        result = verify_artifact(Path(args.artifact_dir))
        if result.ok:
            print("artifact verification: OK")
            return EXIT_OK
        for reason in result.reasons:
            print(f"artifact verification failed: {reason}", file=sys.stderr)
        return EXIT_VERIFY_FAILED

    try:
        data_path = _resolve_data_path(getattr(args, "data", None))
        source = CsvHistoricalMatchSource(data_path)
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE

    if args.command == "audit":
        try:
            report = audit_source(source)
        except DataGateError as exc:
            print(f"audit gate failed: {exc}", file=sys.stderr)
            return EXIT_AUDIT_FAILED
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report.to_json(), encoding="utf-8")
        summary = {
            "passed": report.passed,
            "total_matches": report.total_matches,
            "reasons": list(report.reasons),
        }
        print(json.dumps(summary, sort_keys=True))
        return EXIT_OK if report.passed else EXIT_AUDIT_FAILED

    if args.command == "benchmark":
        output_dir = Path(args.output)
        try:
            report = run_benchmark(
                source,
                output_dir=output_dir,
                seed=args.seed,
                code_version=_code_version(),
            )
        except (BenchmarkGateError, DataGateError) as exc:
            print(f"benchmark gate failed: {exc}", file=sys.stderr)
            return EXIT_AUDIT_FAILED
        summary = {
            "champion": report["selection"]["champion"],
            "selection_dataset": report["selection"]["dataset"],
            "test_log_loss": round(report["test_metrics"]["log_loss"], 6),
            "test_ci95": [
                round(value, 6) for value in report["test_metrics"]["ci95_log_loss"]
            ],
            "promotion": report["promotion"]["result"],
            "windows": report["windows"],
        }
        print(json.dumps(summary, sort_keys=True))
        return EXIT_OK

    return EXIT_USAGE  # pragma: no cover


if __name__ == "__main__":
    raise SystemExit(main())
