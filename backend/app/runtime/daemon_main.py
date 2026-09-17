"""Entry point for the launcher-managed `runtime` child (T79).

``python -m app.runtime.daemon_main`` loads the root ``.env`` settings,
requires valid live-local configuration, builds the runtime daemon graph
(no I/O at construction) and runs it until SIGTERM/SIGINT triggers the
graceful daemon stop path (bounded buffers flushed, final health
persisted). A stop signal that arrives before the run loop is entered is
remembered and honored as an immediate graceful stop — never discarded.
The child never writes any ``.env`` file and never touches a database
outside the dedicated live-local URL.
"""

import asyncio
import contextlib
import signal
import sys
from typing import Any

from app.config import Settings
from app.runtime.assembly import build_local_runtime_daemon
from app.runtime.config import require_live_local
from app.runtime.models import LiveLocalConfigurationError


async def run_daemon(graph: Any, *, stop_requested: list[bool] | None = None) -> None:
    """Run the daemon until a stop is requested, then close the graph.

    ``LocalRuntimeDaemon.run()`` resets its stopping flag on entry, so a
    SIGTERM/SIGINT that lands between handler registration and run-loop
    entry would be discarded by ``daemon.stop()`` alone. The handler
    therefore also records the request in ``stop_requested``; when the flag
    is already set at run-loop entry, the run loop is skipped entirely and
    the graceful stop (bounded flush, final health persist) runs instead.
    ``stop_requested`` is injectable for deterministic tests only.
    """
    loop = asyncio.get_running_loop()
    flag = stop_requested if stop_requested is not None else [False]

    def request_stop() -> None:
        flag[0] = True
        loop.create_task(graph.daemon.stop())

    for signum in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(RuntimeError, NotImplementedError):
            loop.add_signal_handler(signum, request_stop)
    try:
        # One loop iteration lets an already-delivered signal callback run
        # before the entry decision; a stop requested before this point is
        # honored as an immediate graceful stop, never discarded.
        await asyncio.sleep(0)
        if flag[0]:
            await graph.daemon.stop()
        else:
            await graph.daemon.run()
    finally:
        for signum in (signal.SIGTERM, signal.SIGINT):
            with contextlib.suppress(RuntimeError, NotImplementedError):
                loop.remove_signal_handler(signum)
        await graph.aclose()


async def run() -> int:
    settings = Settings()
    live = require_live_local(settings)
    if settings.local_runtime_role != "runtime":
        raise LiveLocalConfigurationError("LOCAL_RUNTIME_ROLE_INVALID")
    graph = build_local_runtime_daemon(settings, live)
    await run_daemon(graph)
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
