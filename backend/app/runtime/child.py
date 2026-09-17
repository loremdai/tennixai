"""Tokenized child-process wrapper for the T79 local runtime launcher.

Every launcher-managed process is spawned as
``python -m app.runtime.child --token <tok> --role <role> -- <argv...>``
inside its own process group (the launcher spawns with
``start_new_session=True``). The wrapper:

* carries the launcher token in its command line so ``down`` can prove
  ownership before signalling (the token itself is never printed);
* forwards SIGTERM/SIGINT to the inner process so the runtime daemon can
  shut down gracefully (flush bounded buffers, persist health);
* exits with the inner process' exit code.

The wrapper performs no I/O of its own beyond spawning the inner command
and never writes to any ``.env`` file.
"""

import argparse
import signal
import subprocess
import sys


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.runtime.child",
        description="Tokenized child wrapper for the TennixAI local runtime launcher.",
    )
    parser.add_argument("--token", required=True, help="launcher ownership token")
    parser.add_argument("--role", required=True, help="managed role label")
    return parser


def parse_child_args(argv: list[str]) -> tuple[str, str, list[str]]:
    """Split wrapper arguments into ``(token, role, inner_argv)``.

    Raises ``SystemExit(2)`` when the token, the role, the ``--`` separator
    or the inner command is missing.
    """
    parser = _build_parser()
    if "--" not in argv:
        parser.error("missing '--' separator before the inner command")
    index = argv.index("--")
    args = parser.parse_args(argv[:index])
    inner = argv[index + 1 :]
    if not inner:
        parser.error("missing inner command after '--'")
    return args.token, args.role, inner


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    _token, _role, inner = parse_child_args(argv)
    process = subprocess.Popen(inner)  # noqa: S603 - launcher-controlled argv

    def forward(signum: int, _frame: object) -> None:
        if process.poll() is None:
            try:
                process.send_signal(signum)
            except ProcessLookupError:
                pass

    signal.signal(signal.SIGTERM, forward)
    signal.signal(signal.SIGINT, forward)
    return process.wait()


if __name__ == "__main__":
    sys.exit(main())
