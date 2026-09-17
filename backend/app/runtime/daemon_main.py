"""Entry point for the launcher-managed `runtime` child (T79).

``python -m app.runtime.daemon_main`` loads the root ``.env`` settings,
requires valid live-local configuration, builds the runtime daemon graph
(no I/O at construction) and runs it until SIGTERM/SIGINT triggers the
graceful daemon stop path (bounded buffers flushed, final health
persisted). The child never writes any ``.env`` file and never touches a
database outside the dedicated live-local URL.
"""

import asyncio
import contextlib
import signal
import sys

from app.config import Settings
from app.runtime.assembly import build_local_runtime_daemon
from app.runtime.config import require_live_local
from app.runtime.models import LiveLocalConfigurationError


async def run() -> int:
    settings = Settings()
    live = require_live_local(settings)
    if settings.local_runtime_role != "runtime":
        raise LiveLocalConfigurationError("LOCAL_RUNTIME_ROLE_INVALID")
    graph = build_local_runtime_daemon(settings, live)
    loop = asyncio.get_running_loop()

    def request_stop() -> None:
        asyncio.get_running_loop().create_task(graph.daemon.stop())

    for signum in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(RuntimeError, NotImplementedError):
            loop.add_signal_handler(signum, request_stop)
    try:
        await graph.daemon.run()
    finally:
        await graph.aclose()
    return 0


def main() -> int:
    try:
        return asyncio.run(run())
    except LiveLocalConfigurationError as exc:
        # Stable code only — never echo URLs, hosts or credential material.
        print(f"runtime child refused to start: {exc.code}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
