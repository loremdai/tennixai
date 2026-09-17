"""Command surface for the T79 safe local runtime launcher.

``./scripts/tennix-live {init,up,status,down,logs,verify}``

``verify`` is a placeholder in T79: end-to-end verification (including
browser checks) arrives in T80. It prints that fact and exits nonzero so
no caller can mistake it for a passing verification.
"""

import argparse
import sys

from app.runtime.launcher import EXIT_FAILURE, build_launcher


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
    subparsers.add_parser(
        "verify", help="PLACEHOLDER — end-to-end verification arrives in T80"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "verify":
        print(
            "verify is not implemented yet: end-to-end verification "
            "(stack health, browser checks, paper-only invariants) arrives in T80."
        )
        return EXIT_FAILURE
    launcher = build_launcher()
    if args.command == "status":
        return launcher.status(as_json=args.json)
    if args.command == "logs":
        return launcher.logs(args.role)
    handler = getattr(launcher, args.command)
    return handler()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
