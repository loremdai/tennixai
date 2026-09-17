"""daemon_main signal-safety tests (T79 hardening, pre-T80).

Deterministic only: a fake daemon/graph plus the injectable stop-request
flag holder prove that a stop requested BEFORE the run loop is entered is
honored as a graceful stop instead of being discarded by the run loop's
fresh stopping-flag reset. No real signal is ever delivered and nothing
is spawned.
"""

import asyncio
import signal
from collections.abc import Callable
from typing import Any

import pytest

from app.runtime import daemon_main


class FakeDaemon:
    def __init__(self) -> None:
        self.stop_calls = 0
        self.run_entered = False
        self._stopped = asyncio.Event()

    async def run(self) -> None:
        # Mirrors LocalRuntimeDaemon.run(): a fresh stopping state on entry.
        self.run_entered = True
        self._stopped.clear()
        await self._stopped.wait()

    async def stop(self) -> None:
        self.stop_calls += 1
        self._stopped.set()


class FakeGraph:
    def __init__(self, daemon: FakeDaemon) -> None:
        self.daemon = daemon
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


def _neutralize_loop_signal_registration(
    monkeypatch: pytest.MonkeyPatch,
    captured: dict[int, Callable[[], None]] | None = None,
) -> None:
    """Replace loop signal registration with a no-op (or a capture dict).

    Tests never deliver real signals and never touch the pytest process's
    own signal dispositions.
    """

    def fake_add(self: Any, signum: int, callback: Callable[[], None], *args: Any):
        if captured is not None:
            captured[signum] = callback

    def fake_remove(self: Any, signum: int, *args: Any):
        if captured is not None:
            captured.pop(signum, None)

    # add_signal_handler lives on the concrete loop class (e.g.
    # _UnixSelectorEventLoop), so patch exactly the running loop's type.
    loop_type = type(asyncio.get_running_loop())
    monkeypatch.setattr(loop_type, "add_signal_handler", fake_add)
    monkeypatch.setattr(loop_type, "remove_signal_handler", fake_remove)


async def test_stop_requested_before_run_entry_is_honored_gracefully(
    monkeypatch: pytest.MonkeyPatch,
):
    _neutralize_loop_signal_registration(monkeypatch)
    daemon = FakeDaemon()
    graph = FakeGraph(daemon)
    # The flag holder is exactly what the signal handler writes to; a True
    # entry means SIGTERM/SIGINT landed before the run-loop entry decision.
    await asyncio.wait_for(
        daemon_main.run_daemon(graph, stop_requested=[True]), timeout=5.0
    )
    assert daemon.run_entered is False
    assert daemon.stop_calls == 1
    assert graph.closed is True


async def test_stop_during_run_stops_gracefully_without_hanging(
    monkeypatch: pytest.MonkeyPatch,
):
    daemon = FakeDaemon()
    graph = FakeGraph(daemon)
    captured: dict[int, Callable[[], None]] = {}
    _neutralize_loop_signal_registration(monkeypatch, captured)

    task = asyncio.create_task(daemon_main.run_daemon(graph))
    for _ in range(100):
        if daemon.run_entered:
            break
        await asyncio.sleep(0)
    assert daemon.run_entered is True

    captured[signal.SIGTERM]()
    await asyncio.wait_for(task, timeout=5.0)
    assert daemon.stop_calls == 1
    assert graph.closed is True


async def test_run_without_signal_enters_run_loop_and_closes_graph(
    monkeypatch: pytest.MonkeyPatch,
):
    daemon = FakeDaemon()
    graph = FakeGraph(daemon)
    _neutralize_loop_signal_registration(monkeypatch)

    async def finish_run_soon() -> None:
        for _ in range(100):
            if daemon.run_entered:
                break
            await asyncio.sleep(0)
        await daemon.stop()

    waiter = asyncio.create_task(finish_run_soon())
    await asyncio.wait_for(daemon_main.run_daemon(graph), timeout=5.0)
    await waiter
    assert daemon.run_entered is True
    assert daemon.stop_calls == 1
    assert graph.closed is True
