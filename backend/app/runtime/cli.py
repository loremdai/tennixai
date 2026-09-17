"""Command surface for the safe local runtime launcher (T79/T80).

``./scripts/tennix-live {init,up,status,down,logs,verify}``

``verify`` (T80) runs the bounded, read-only real-source verification from
`app.runtime.verify` against adapters built from the root ``.env``. It never
writes fixtures or orders and only exercises the real Chat contract when
``--with-llm`` is given explicitly. Exit codes: any failed source exits
nonzero (`EXIT_FAILURE`); all-passed and passed+skipped mixes exit zero with
skips printed clearly — a quiet window is an honest skip, never a silent
pass. Configuration problems exit `EXIT_PRECONDITION` with a stable code.
"""

import argparse
import asyncio
import sys
from collections.abc import Callable, Iterable
from typing import Any, TextIO

from pydantic import ValidationError

from app.runtime.launcher import (
    EXIT_FAILURE,
    EXIT_OK,
    EXIT_PRECONDITION,
    build_launcher,
)
from app.runtime.models import LiveLocalConfigurationError
from app.runtime.verify import VerifyOutcome, build_verify_dependencies, verify_runtime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tennix-live",
        description="Safe one-command lifecycle for the TennixAI local real runtime.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "init",
        help="validate .env, ensure compose, create the live-local database, migrate and bootstrap",
    )
    subparsers.add_parser(
        "up", help="start runtime, api and frontend as owned children"
    )
    status = subparsers.add_parser(
        "status", help="show stack, processes and persisted runtime health"
    )
    status.add_argument(
        "--json", action="store_true", help="emit machine-readable JSON"
    )
    subparsers.add_parser(
        "down",
        help="gracefully stop owned children and exactly-owned compose containers",
    )
    logs = subparsers.add_parser("logs", help="tail a managed role's log file")
    logs.add_argument("role", choices=["runtime", "api", "frontend"])
    verify = subparsers.add_parser(
        "verify",
        help="bounded read-only verification of the real local runtime sources",
    )
    verify.add_argument(
        "--with-llm",
        action="store_true",
        help="also exercise the real Chat contract once (spends LLM quota)",
    )
    return parser


def verify_exit_code(outcomes: Iterable[VerifyOutcome]) -> int:
    """Any failed source exits nonzero; passed+skipped mixes exit zero."""
    return (
        EXIT_FAILURE
        if any(outcome.status == "failed" for outcome in outcomes)
        else EXIT_OK
    )


def format_verify_results(outcomes: Iterable[VerifyOutcome]) -> str:
    """Render the aggregate outcome table: names, statuses, reason codes."""
    results = tuple(outcomes)
    lines = ["local runtime verification (bounded, read-only):"]
    for outcome in results:
        reason = f"  reason={outcome.reason_code}" if outcome.reason_code else ""
        lines.append(f"  {outcome.name:<20} {outcome.status}{reason}")
    passed = sum(1 for outcome in results if outcome.status == "passed")
    skipped = sum(1 for outcome in results if outcome.status == "skipped")
    failed = sum(1 for outcome in results if outcome.status == "failed")
    lines.append(
        f"{len(results)} sources: {passed} passed, {skipped} skipped, {failed} failed"
    )
    if skipped:
        lines.append(
            "note: each skipped source is an honest quiet-window/no-target "
            "result, never counted as a pass."
        )
    return "\n".join(lines)


async def _verify_and_close(
    dependencies: Any,
    verifier: Callable[..., Any],
    with_llm: bool,
) -> tuple[VerifyOutcome, ...]:
    try:
        return await verifier(with_llm=with_llm, **dependencies.verify_kwargs())
    finally:
        await dependencies.aclose()


def run_verify(
    *,
    with_llm: bool,
    settings_factory: Callable[[], Any] | None = None,
    dependencies_factory: Callable[[Any], Any] | None = None,
    verifier: Callable[..., Any] | None = None,
    out: TextIO | None = None,
) -> int:
    """Run the real verification; injectable seams keep tests deterministic."""
    stream = out if out is not None else sys.stdout
    if settings_factory is None:
        from app.config import Settings

        settings_factory = Settings
    if dependencies_factory is None:
        dependencies_factory = build_verify_dependencies
    if verifier is None:
        verifier = verify_runtime
    try:
        settings = settings_factory()
        dependencies = dependencies_factory(settings)
    except LiveLocalConfigurationError as exc:
        print(f"verify precondition failed: {exc.code}", file=stream)
        return EXIT_PRECONDITION
    except ValidationError:
        print("verify precondition failed: SETTINGS_INVALID", file=stream)
        return EXIT_PRECONDITION
    outcomes = asyncio.run(_verify_and_close(dependencies, verifier, with_llm))
    print(format_verify_results(outcomes), file=stream)
    return verify_exit_code(outcomes)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "verify":
        return run_verify(with_llm=args.with_llm)
    launcher = build_launcher()
    if args.command == "status":
        return launcher.status(as_json=args.json)
    if args.command == "logs":
        return launcher.logs(args.role)
    handler = getattr(launcher, args.command)
    return handler()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
