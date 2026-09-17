"""T79 safe repository-root launcher tests.

Deterministic only: every test uses a fake command runner, a fake process
inspector, a fake port prober and a fake clock. No test invokes real Docker,
binds a port, reads actual ``.env`` values, kills a process, or touches the
network.
"""

import json
import os
import signal
import stat
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from app.config import Settings
from app.runtime.child import parse_child_args
from app.runtime.config import require_live_local
from app.runtime.daemon import LocalRuntimeDaemon
from app.runtime.launcher import (
    CommandResult,
    DatabaseStatus,
    LauncherState,
    ManagedProcess,
    PsProcessInspector,
    RuntimeLauncher,
    SubprocessCommandRunner,
    default_state_dir,
)
from app.runtime.models import (
    RuntimeHealth,
    RuntimeInitRecord,
    RuntimeSourceHealth,
    RuntimeSourceStatus,
)

NOW = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)

REPO_ROOT = Path(__file__).resolve().parents[2]

BRIEF_WRAPPER = """#!/usr/bin/env sh
set -eu
root_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec uv run --directory "$root_dir/backend" python -m app.runtime.cli "$@"
"""

SECRET_MATERIAL = (
    "test-api-tennis-key",
    "test-llm-key",
    "https://llm.invalid/v1",
    "postgresql+asyncpg://tennix:tennix@127.0.0.1:5432/tennix_live_local",
)


def local_settings(**overrides: Any) -> Settings:
    """Valid live-local settings with dummy credentials; never reads .env."""
    values: dict[str, Any] = {
        "provider_mode": "api_tennis",
        "api_tennis_api_key": "test-api-tennis-key",
        "llm_api_key": "test-llm-key",
        "llm_base_url": "https://llm.invalid/v1",
        "p3_mode": "paper",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def source_health(
    status: RuntimeSourceStatus, reason_code: str | None = None
) -> RuntimeSourceHealth:
    return RuntimeSourceHealth(
        status=status, reason_code=reason_code, last_tracked=1, success_count=1
    )


def healthy_health() -> RuntimeHealth:
    return RuntimeHealth(
        generated_at=NOW,
        sources={
            "tennis_live": source_health(RuntimeSourceStatus.OK),
            "polymarket": source_health(RuntimeSourceStatus.OK),
            "live_catalog": source_health(RuntimeSourceStatus.OK),
            "upcoming_catalog": source_health(RuntimeSourceStatus.OK),
            "rankings": source_health(RuntimeSourceStatus.OK),
        },
        paper_status="paper_only",
        model_status="not_promoted",
    )


# ---------------------------------------------------------------------------
# Deterministic fakes
# ---------------------------------------------------------------------------


@dataclass
class SpawnCall:
    argv: list[str]
    cwd: str | None
    env: dict[str, str]
    log_path: str


class FakeProcessInspector:
    def __init__(self) -> None:
        self.command_for_pid: dict[int, str] = {}
        self.alive: set[int] = set()
        self.stubborn: set[int] = set()

    def register(self, pid: int, command: str) -> None:
        self.command_for_pid[pid] = command
        self.alive.add(pid)

    def command_line(self, pid: int) -> str | None:
        return self.command_for_pid.get(pid)

    def is_alive(self, pid: int) -> bool:
        return pid in self.alive or pid in self.command_for_pid

    def kill(self, pid: int, signum: int) -> None:
        if signum == signal.SIGTERM and pid in self.stubborn:
            return
        self.alive.discard(pid)
        self.command_for_pid.pop(pid, None)


class FakeCommandRunner:
    def __init__(self, inspector: FakeProcessInspector | None = None) -> None:
        self.commands: list[list[str]] = []
        self.spawned: list[SpawnCall] = []
        self.signalled_pids: list[int] = []
        self.signals: list[tuple[int, int]] = []
        self.results: dict[tuple[str, ...], CommandResult] = {}
        self.sequences: dict[tuple[str, ...], list[CommandResult]] = {}
        self.default_result = CommandResult(0, "", "")
        self._inspector = inspector
        self._next_pid = 4000

    def run(
        self,
        argv: list[str],
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> CommandResult:
        self.commands.append(list(argv))
        key = tuple(argv)
        if key in self.sequences and self.sequences[key]:
            return self.sequences[key].pop(0)
        return self.results.get(key, self.default_result)

    def spawn(
        self,
        argv: list[str],
        *,
        cwd: str | None,
        env: dict[str, str],
        log_path: str,
    ) -> int:
        pid = self._next_pid
        self._next_pid += 1
        self.spawned.append(
            SpawnCall(argv=list(argv), cwd=cwd, env=dict(env), log_path=log_path)
        )
        if self._inspector is not None:
            self._inspector.register(pid, " ".join(argv))
        return pid

    def signal_group(self, pid: int, signum: int) -> bool:
        self.signalled_pids.append(pid)
        self.signals.append((pid, signum))
        if self._inspector is not None:
            self._inspector.kill(pid, signum)
        return True


class FakePortProber:
    def __init__(self) -> None:
        self.in_use: dict[int, str] = {}

    def listener(self, port: int) -> str | None:
        return self.in_use.get(port)


class FakeTime:
    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds

    def sleep_sync(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


class FakeDatabaseEnsure:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[Any] = []
        self.error = error

    async def __call__(self, live: Any) -> None:
        self.calls.append(live)
        if self.error is not None:
            raise self.error


class FakeMigrations:
    def __init__(self, revision: str = "rev_test") -> None:
        self.revision = revision
        self.calls = 0

    async def upgrade_head(self) -> str:
        self.calls += 1
        return self.revision


class FakeBootstrap:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls = 0
        self.error = error
        self.migrations: Any = None

    async def __call__(self, settings: Any, live: Any, migrations: Any):
        self.calls += 1
        if self.error is not None:
            raise self.error
        self.migrations = migrations
        revision = await migrations.upgrade_head()
        return RuntimeInitRecord(
            completed_at=NOW,
            migration_revision=revision,
            player_count=3,
            match_count=7,
        )


class FakeDatabaseProbe:
    def __init__(
        self, initialized: bool = True, schema_head: str | None = "rev_test"
    ) -> None:
        self.initialized = initialized
        self.schema_head = schema_head
        self.calls = 0

    async def __call__(self) -> DatabaseStatus:
        self.calls += 1
        return DatabaseStatus(
            initialized=self.initialized, schema_head=self.schema_head
        )


_HEALTH_UNSET = object()


class FakeHealthProbe:
    def __init__(
        self,
        results: list[RuntimeHealth | None] | None = None,
        final: Any = _HEALTH_UNSET,
    ) -> None:
        self.results: list[RuntimeHealth | None] = list(results or [])
        self.final: RuntimeHealth | None = (
            healthy_health() if final is _HEALTH_UNSET else final
        )
        self.calls = 0

    async def __call__(self) -> RuntimeHealth | None:
        self.calls += 1
        if self.results:
            return self.results.pop(0)
        return self.final


class FakeHttpProbe:
    def __init__(self, final: bool = True) -> None:
        self.final = final
        self.urls: list[str] = []

    async def __call__(self, url: str) -> bool:
        self.urls.append(url)
        return self.final


@pytest.fixture()
def launcher(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> RuntimeLauncher:
    root = tmp_path / "repo"
    (root / "backend").mkdir(parents=True)
    (root / "frontend").mkdir(parents=True)
    state_dir = tmp_path / "state"

    inspector = FakeProcessInspector()
    runner = FakeCommandRunner(inspector=inspector)
    ports = FakePortProber()
    fake_time = FakeTime()
    output: list[str] = []
    tokens = iter(f"tok-{i}" for i in range(1, 200))

    # Pre-existing compose containers: same ID before and after `compose up`
    # means the launcher must NOT claim ownership of them.
    runner.results[("docker", "compose", "ps", "-q", "postgres")] = CommandResult(
        0, "cpg-existing\n", ""
    )
    runner.results[("docker", "compose", "ps", "-q", "redis")] = CommandResult(
        0, "crd-existing\n", ""
    )

    database_ensure = FakeDatabaseEnsure()
    bootstrap = FakeBootstrap()
    migrations = FakeMigrations()
    database_probe = FakeDatabaseProbe()
    health_probe = FakeHealthProbe()
    http_probe = FakeHttpProbe()

    instance = RuntimeLauncher(
        root_dir=root,
        state_dir=state_dir,
        settings_factory=lambda: local_settings(),
        runner=runner,
        inspector=inspector,
        ports=ports,
        clock=fake_time.monotonic,
        sleep=fake_time.sleep,
        sleep_sync=fake_time.sleep_sync,
        output=output.append,
        token_factory=lambda: next(tokens),
        database_ensure=database_ensure,
        migrations_factory=lambda live: migrations,
        bootstrap=bootstrap,
        database_probe=database_probe,
        health_probe=health_probe,
        http_probe=http_probe,
        health_timeout=5.0,
        api_timeout=5.0,
        poll_interval=1.0,
        stop_grace_seconds=2.0,
    )
    instance.state.initialized = True
    instance.state.schema_head = "rev_test"

    # Expose the fakes for assertions (the brief's tests reach through the
    # launcher itself).
    instance.time = fake_time  # type: ignore[attr-defined]
    instance.output = output  # type: ignore[attr-defined]
    instance.database_ensure = database_ensure  # type: ignore[attr-defined]
    instance.bootstrap = bootstrap  # type: ignore[attr-defined]
    instance.migrations = migrations  # type: ignore[attr-defined]
    instance.database_probe = database_probe  # type: ignore[attr-defined]
    instance.health_probe = health_probe  # type: ignore[attr-defined]
    instance.http_probe = http_probe  # type: ignore[attr-defined]
    return instance


def spawned_roles(runner: FakeCommandRunner) -> list[str]:
    roles: list[str] = []
    for call in runner.spawned:
        argv = call.argv
        assert argv[1:3] == ["-m", "app.runtime.child"]
        roles.append(argv[argv.index("--role") + 1])
    return roles


def joined_output(launcher: RuntimeLauncher) -> str:
    return "\n".join(launcher.output)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Brief Step 1: the three mandatory safety tests (verbatim behavior)
# ---------------------------------------------------------------------------


def test_up_refuses_uninitialized_database_without_starting_children(launcher):
    launcher.state.initialized = False
    assert launcher.up() == 2
    assert launcher.runner.spawned == []


def test_down_never_signals_a_pid_without_our_wrapper_token(launcher):
    launcher.state.processes = [ManagedProcess(role="api", pid=123, token="ours")]
    launcher.inspector.command_for_pid[123] = "python unrelated.py"
    assert launcher.down() == 0
    assert launcher.runner.signalled_pids == []


def test_up_reports_foreign_port_without_killing_it(launcher):
    launcher.ports.in_use[8000] = "foreign"
    assert launcher.up() == 2
    assert launcher.runner.signalled_pids == []


# ---------------------------------------------------------------------------
# init sequencing (decision 3)
# ---------------------------------------------------------------------------


def test_init_validates_settings_before_any_command(launcher):
    launcher.settings_factory = lambda: local_settings(provider_mode="fake")
    assert launcher.init() == 1
    assert "LOCAL_PROVIDER_MODE_INVALID" in joined_output(launcher)
    assert launcher.runner.commands == []
    assert launcher.database_ensure.calls == []
    assert launcher.bootstrap.calls == 0
    assert launcher.state.initialized is False


def test_init_creates_database_runs_migrations_and_bootstraps(launcher):
    assert launcher.init() == 0
    assert len(launcher.database_ensure.calls) == 1
    live = launcher.database_ensure.calls[0]
    assert live.database_url.endswith("/tennix_live_local")
    assert launcher.migrations.calls >= 1
    assert launcher.bootstrap.calls == 1
    assert launcher.state.initialized is True
    assert launcher.state.schema_head == "rev_test"
    text = joined_output(launcher)
    assert "players=3" in text
    assert "matches=7" in text
    assert "rev_test" in text
    for secret in SECRET_MATERIAL:
        assert secret not in text
    # state file was persisted under the state dir, not the repo
    state_file = launcher.state_dir / "state.json"
    assert state_file.is_file()
    payload = json.loads(state_file.read_text())
    assert payload["initialized"] is True
    assert payload["schema_head"] == "rev_test"


def test_init_ensure_compose_before_database_creation(launcher):
    launcher.runner.results[
        ("docker", "compose", "up", "-d", "--wait", "postgres", "redis")
    ] = CommandResult(1, "", "boom")
    assert launcher.init() == 1
    assert "LOCAL_COMPOSE_FAILED" in joined_output(launcher)
    assert launcher.database_ensure.calls == []
    assert launcher.state.initialized is False


def test_init_stores_only_newly_created_containers(launcher):
    launcher.runner.sequences[("docker", "compose", "ps", "-q", "postgres")] = [
        CommandResult(0, "cpg-existing\n", ""),
        CommandResult(0, "cpg-existing\n", ""),
    ]
    launcher.runner.sequences[("docker", "compose", "ps", "-q", "redis")] = [
        CommandResult(0, "", ""),
        CommandResult(0, "crd-new\n", ""),
    ]
    assert launcher.init() == 0
    assert launcher.state.containers == {"redis": "crd-new"}


def test_init_database_creation_failure_exits_nonzero_without_marker(launcher):
    launcher.database_ensure.error = RuntimeError(
        "connection refused postgresql+asyncpg://tennix:tennix@127.0.0.1:5432/x"
    )
    assert launcher.init() == 1
    text = joined_output(launcher)
    assert "LOCAL_DATABASE_CREATE_FAILED" in text
    for secret in SECRET_MATERIAL:
        assert secret not in text
    assert launcher.bootstrap.calls == 0
    assert launcher.state.initialized is False


def test_init_bootstrap_failure_exits_nonzero_without_marker(launcher):
    launcher.bootstrap.error = RuntimeError("ranking sync failed")
    assert launcher.init() == 1
    assert "LOCAL_BOOTSTRAP_FAILED" in joined_output(launcher)
    assert launcher.state.initialized is False
    assert launcher.state.schema_head is None


# ---------------------------------------------------------------------------
# up sequencing (decision 4)
# ---------------------------------------------------------------------------


def test_up_spawns_tokenized_children_in_order_and_writes_state(
    launcher, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    env_before = dict(os.environ)

    assert launcher.up() == 0

    assert spawned_roles(launcher.runner) == ["runtime", "api", "frontend"]
    runtime_call, api_call, frontend_call = launcher.runner.spawned

    # Every child is a tokenized app.runtime.child wrapper.
    for call in launcher.runner.spawned:
        token, role, inner = parse_child_args(call.argv[3:])
        assert token
        assert role in {"runtime", "api", "frontend"}
        assert "--token" in call.argv and token in call.argv
        assert "NO_PROXY" not in call.env
        assert "no_proxy" not in call.env

    token, role, inner = parse_child_args(runtime_call.argv[3:])
    assert role == "runtime"
    assert inner[-2:] == ["-m", "app.runtime.daemon_main"]
    assert runtime_call.env["TENNIX_LOCAL_RUNTIME_ROLE"] == "runtime"
    assert runtime_call.env["TENNIX_PROVIDER_MODE"] == "api_tennis"
    assert runtime_call.env["TENNIX_P3_MODE"] == "paper"
    assert runtime_call.env["TENNIX_DATABASE_URL"].endswith("/tennix_live_local")
    assert runtime_call.env["TENNIX_REDIS_URL"].endswith("/11")
    assert runtime_call.cwd == str(launcher.root_dir / "backend")

    token_api, role_api, inner_api = parse_child_args(api_call.argv[3:])
    assert role_api == "api"
    assert token_api != token
    assert "uvicorn" in inner_api
    assert "app.main:app" in inner_api
    assert api_call.env["TENNIX_LOCAL_RUNTIME_ROLE"] == "api"

    _, role_front, inner_front = parse_child_args(frontend_call.argv[3:])
    assert role_front == "frontend"
    assert inner_front[0] == "pnpm"
    assert "3100" in inner_front
    assert frontend_call.env["TENNIX_BACKEND_URL"] == "http://127.0.0.1:8000"
    assert frontend_call.cwd == str(launcher.root_dir / "frontend")

    # Ownership state: PIDs/tokens/log paths only, persisted under state dir.
    assert [p.role for p in launcher.state.processes] == [
        "runtime",
        "api",
        "frontend",
    ]
    assert [p.token for p in launcher.state.processes] == [
        token,
        token_api,
        parse_child_args(frontend_call.argv[3:])[0],
    ]
    for process, call in zip(launcher.state.processes, launcher.runner.spawned):
        assert process.log_path == call.log_path
        assert str(launcher.state_dir) in process.log_path
    state_file = launcher.state_dir / "state.json"
    payload = json.loads(state_file.read_text())
    assert [p["role"] for p in payload["processes"]] == [
        "runtime",
        "api",
        "frontend",
    ]

    # up never runs init/enrichment/LLM work.
    assert launcher.bootstrap.calls == 0
    assert launcher.database_ensure.calls == []

    # Parent environment untouched; no secrets or tokens in output.
    assert dict(os.environ) == env_before
    text = joined_output(launcher)
    assert "http://127.0.0.1:3100" in text
    for secret in SECRET_MATERIAL:
        assert secret not in text
    for process in launcher.state.processes:
        assert process.token not in text


def test_up_rejects_schema_head_mismatch_without_spawning(launcher):
    launcher.database_probe.schema_head = "some_other_revision"
    assert launcher.up() == 2
    assert launcher.runner.spawned == []
    assert "init" in joined_output(launcher)


def test_up_rejects_missing_database_marker_without_spawning(launcher):
    launcher.database_probe.initialized = False
    assert launcher.up() == 2
    assert launcher.runner.spawned == []


def test_up_waits_for_persisted_healthy_first_discovery(launcher):
    launcher.health_probe.results = [None, None]
    assert launcher.up() == 0
    assert launcher.health_probe.calls >= 3
    assert spawned_roles(launcher.runner) == ["runtime", "api", "frontend"]


def test_up_health_wait_timeout_stops_only_the_owned_runtime_child(launcher):
    launcher.health_probe = FakeHealthProbe(final=None)
    assert launcher.up() == 1
    assert spawned_roles(launcher.runner) == ["runtime"]
    runtime_pid = launcher.state.processes[0].pid if launcher.state.processes else None
    assert launcher.runner.signalled_pids == [runtime_pid]
    assert launcher.runner.signals == [(runtime_pid, signal.SIGTERM)]
    assert "LOCAL_RUNTIME_UNHEALTHY" in joined_output(launcher)


def test_up_api_health_timeout_stops_owned_children_only(launcher):
    launcher.http_probe = FakeHttpProbe(final=False)
    assert launcher.up() == 1
    assert spawned_roles(launcher.runner) == ["runtime", "api"]
    runtime_pid, api_pid = (
        launcher.state.processes[0].pid,
        launcher.state.processes[1].pid,
    )
    assert set(launcher.runner.signalled_pids) == {runtime_pid, api_pid}
    assert all(sig == signal.SIGTERM for _, sig in launcher.runner.signals)
    assert "LOCAL_API_UNHEALTHY" in joined_output(launcher)


def test_up_reports_owned_port_as_already_running_without_signalling(launcher):
    launcher.state.processes = [ManagedProcess(role="api", pid=777, token="tok-own")]
    launcher.inspector.register(
        777, "python -m app.runtime.child --token tok-own --role api -- uvicorn"
    )
    launcher.ports.in_use[8000] = "777"
    assert launcher.up() == 2
    assert launcher.runner.signalled_pids == []
    assert launcher.runner.spawned == []


def test_up_reports_occupied_frontend_port_without_killing(launcher):
    launcher.ports.in_use[3100] = "foreign"
    assert launcher.up() == 2
    assert launcher.runner.signalled_pids == []
    assert launcher.runner.spawned == []


# ---------------------------------------------------------------------------
# down sequencing and ownership (decisions 5 and 6)
# ---------------------------------------------------------------------------


def test_down_stops_runtime_first_then_api_frontend_then_owned_containers(launcher):
    assert launcher.up() == 0
    processes = {p.role: p for p in launcher.state.processes}
    launcher.state.containers = {"postgres": "cpg-owned", "redis": "crd-owned"}
    launcher.runner.results[("docker", "compose", "ps", "-q", "postgres")] = (
        CommandResult(0, "cpg-owned\n", "")
    )
    launcher.runner.results[("docker", "compose", "ps", "-q", "redis")] = CommandResult(
        0, "crd-owned\n", ""
    )

    assert launcher.down() == 0

    assert launcher.runner.signalled_pids == [
        processes["runtime"].pid,
        processes["api"].pid,
        processes["frontend"].pid,
    ]
    assert all(sig == signal.SIGTERM for _, sig in launcher.runner.signals)
    assert ["docker", "stop", "cpg-owned"] in launcher.runner.commands
    assert ["docker", "stop", "crd-owned"] in launcher.runner.commands
    # Never compose down, never remove volumes, never destructive commands.
    for command in launcher.runner.commands:
        assert "down" not in command
        assert "rm" not in command
        assert "rmi" not in command
    assert launcher.state.processes == []
    assert launcher.state.containers == {}
    payload = json.loads((launcher.state_dir / "state.json").read_text())
    assert payload["processes"] == []
    assert payload["containers"] == {}


def test_down_never_stops_a_container_whose_id_changed(launcher):
    launcher.state.containers = {"postgres": "cpg-old"}
    launcher.runner.results[("docker", "compose", "ps", "-q", "postgres")] = (
        CommandResult(0, "cpg-new\n", "")
    )
    assert launcher.down() == 0
    assert ["docker", "stop", "cpg-old"] not in launcher.runner.commands
    assert ["docker", "stop", "cpg-new"] not in launcher.runner.commands


def test_down_tolerates_already_stopped_processes(launcher):
    launcher.state.processes = [
        ManagedProcess(role="runtime", pid=31, token="tok-a"),
        ManagedProcess(role="api", pid=32, token="tok-b"),
    ]
    assert launcher.down() == 0
    assert launcher.runner.signalled_pids == []
    assert launcher.state.processes == []


def test_down_escalates_to_sigkill_only_for_owned_stubborn_process(launcher):
    launcher.state.processes = [
        ManagedProcess(role="runtime", pid=900, token="tok-r"),
    ]
    launcher.inspector.register(
        900, "python -m app.runtime.child --token tok-r --role runtime -- x"
    )
    launcher.inspector.stubborn.add(900)
    assert launcher.down() == 0
    assert launcher.runner.signals == [
        (900, signal.SIGTERM),
        (900, signal.SIGKILL),
    ]


# ---------------------------------------------------------------------------
# status and logs (decisions 7 and 8)
# ---------------------------------------------------------------------------


def runtime_gap_health() -> RuntimeHealth:
    return RuntimeHealth(
        generated_at=NOW,
        sources={
            "tennis_live": source_health(
                RuntimeSourceStatus.GAP, "UPSTREAM_DISCONNECTED"
            ),
            "polymarket": source_health(RuntimeSourceStatus.OK),
            "live_catalog": source_health(RuntimeSourceStatus.OK),
            "upcoming_catalog": source_health(
                RuntimeSourceStatus.DEGRADED, "SYNC_FAILED"
            ),
            "rankings": source_health(RuntimeSourceStatus.OK),
        },
        paper_status="paper_only",
        model_status="not_promoted",
    )


def test_status_reports_processes_and_persisted_health(launcher):
    launcher.state.processes = [
        ManagedProcess(role="runtime", pid=5000, token="tok-s", log_path="x")
    ]
    launcher.inspector.register(
        5000, "python -m app.runtime.child --token tok-s --role runtime -- y"
    )
    launcher.health_probe = FakeHealthProbe(final=runtime_gap_health())
    launcher.runner.results[("docker", "compose", "ps", "-q", "postgres")] = (
        CommandResult(0, "cpg-x\n", "")
    )
    launcher.runner.results[
        ("docker", "inspect", "-f", "{{.State.Health.Status}}", "cpg-x")
    ] = CommandResult(0, "healthy\n", "")
    launcher.runner.results[("docker", "compose", "ps", "-q", "redis")] = CommandResult(
        0, "crd-x\n", ""
    )
    launcher.runner.results[
        ("docker", "inspect", "-f", "{{.State.Health.Status}}", "crd-x")
    ] = CommandResult(0, "healthy\n", "")

    assert launcher.status() == 0
    text = joined_output(launcher)
    for row in (
        "stack",
        "database",
        "redis",
        "runtime",
        "api",
        "frontend",
        "sports_stream",
        "schedule",
        "rankings",
        "polymarket",
        "paper",
        "model",
    ):
        assert row in text
    # Process absent vs source disconnected are distinguishable.
    assert "running" in text  # runtime process alive
    assert "stopped" in text  # api/frontend processes absent
    assert "gap" in text and "UPSTREAM_DISCONNECTED" in text
    assert "degraded" in text and "SYNC_FAILED" in text
    assert "paper_only" in text
    assert "not_promoted" in text
    assert "tok-s" not in text
    for secret in SECRET_MATERIAL:
        assert secret not in text


def test_status_json_is_parseable_and_secret_free(launcher):
    launcher.health_probe = FakeHealthProbe(final=runtime_gap_health())
    assert launcher.status(as_json=True) == 0
    data = json.loads(joined_output(launcher))
    assert data["stack"] in {"running", "partial", "stopped"}
    components = data["components"]
    for name in (
        "database",
        "redis",
        "runtime",
        "api",
        "frontend",
        "sports_stream",
        "schedule",
        "rankings",
        "polymarket",
        "paper",
        "model",
    ):
        assert name in components
        assert "state" in components[name]
    assert components["paper"]["state"] == "paper_only"
    assert components["model"]["state"] == "not_promoted"
    assert components["api"]["state"] == "stopped"
    raw = joined_output(launcher)
    for secret in SECRET_MATERIAL:
        assert secret not in raw


def test_status_reads_persisted_health_when_every_process_is_down(launcher):
    launcher.health_probe = FakeHealthProbe(final=runtime_gap_health())
    assert launcher.status() == 0
    text = joined_output(launcher)
    assert "UPSTREAM_DISCONNECTED" in text
    assert "stack" in text and "stopped" in text


def test_logs_reads_only_the_current_launcher_log_file(launcher):
    launcher.state_dir.mkdir(parents=True, exist_ok=True)
    (launcher.state_dir / "api.log").write_text("api line one\napi line two\n")
    assert launcher.logs("api") == 0
    text = joined_output(launcher)
    assert "api line one" in text and "api line two" in text


def test_logs_missing_file_reports_clearly(launcher):
    assert launcher.logs("runtime") == 1
    assert "runtime" in joined_output(launcher)


def test_logs_rejects_unknown_role(launcher):
    assert launcher.logs("database") == 2
    assert launcher.logs("postgres") == 2


# ---------------------------------------------------------------------------
# CLI surface (decision 1) and wrapper script
# ---------------------------------------------------------------------------


def test_cli_verify_command_accepts_with_llm_flag():
    """T80: `verify` is a real bounded check, no longer a placeholder."""
    from app.runtime.cli import build_parser

    args = build_parser().parse_args(["verify"])
    assert args.command == "verify"
    assert args.with_llm is False
    assert build_parser().parse_args(["verify", "--with-llm"]).with_llm is True


def test_cli_logs_rejects_unknown_role_argument():
    from app.runtime.cli import main

    with pytest.raises(SystemExit) as excinfo:
        main(["logs", "database"])
    assert excinfo.value.code == 2


def test_cli_without_command_exits_nonzero():
    from app.runtime.cli import main

    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code != 0


def test_wrapper_script_matches_brief_and_is_executable():
    script = REPO_ROOT / "scripts" / "tennix-live"
    assert script.is_file()
    assert os.access(script, os.X_OK)
    assert script.read_text() == BRIEF_WRAPPER


# ---------------------------------------------------------------------------
# State directory and child wrapper contract
# ---------------------------------------------------------------------------


def test_default_state_dir_is_under_tempdir_not_the_repo():
    state_dir = default_state_dir()
    assert state_dir.parent == Path(tempfile.gettempdir())
    assert state_dir.name == f"tennix-live-{os.getuid()}"
    assert not state_dir.is_relative_to(REPO_ROOT)


def test_state_persists_only_pids_tokens_containers_and_log_paths(launcher):
    assert launcher.up() == 0
    payload = json.loads((launcher.state_dir / "state.json").read_text())
    assert set(payload) == {"initialized", "schema_head", "processes", "containers"}
    for process in payload["processes"]:
        assert set(process) == {"role", "pid", "token", "log_path"}


def test_child_parse_requires_token_role_and_separator():
    with pytest.raises(SystemExit):
        parse_child_args(["--role", "runtime", "--", "echo", "hi"])
    with pytest.raises(SystemExit):
        parse_child_args(["--token", "t", "--role", "runtime", "echo", "hi"])
    token, role, inner = parse_child_args(
        ["--token", "t", "--role", "runtime", "--", "echo", "hi"]
    )
    assert (token, role, inner) == ("t", "runtime", ["echo", "hi"])


def test_launcher_state_roundtrip(launcher):
    state = LauncherState(
        initialized=True,
        schema_head="rev_x",
        processes=[ManagedProcess(role="api", pid=1, token="t", log_path="l")],
        containers={"postgres": "cid"},
    )
    launcher.state_dir.mkdir(parents=True, exist_ok=True)
    state.save(launcher.state_dir / "state.json")
    loaded = LauncherState.load(launcher.state_dir / "state.json")
    assert loaded == state


# ---------------------------------------------------------------------------
# Runtime daemon factory smoke test (decision 2) — fully offline
# ---------------------------------------------------------------------------


async def test_build_local_runtime_daemon_constructs_offline():
    from app.runtime.assembly import build_local_runtime_daemon

    settings = local_settings(local_runtime_role="runtime")
    live = require_live_local(settings)
    graph = build_local_runtime_daemon(settings, live)
    try:
        assert isinstance(graph.daemon, LocalRuntimeDaemon)
        assert graph.realtime is not None
        assert graph.market_worker is not None
        assert graph.decision_worker is not None
        assert graph.health is not None
        assert graph.paper is not None
    finally:
        await graph.aclose()


def test_daemon_main_module_exists_with_entrypoint():
    import app.runtime.daemon_main as daemon_main

    assert callable(daemon_main.main)


# ---------------------------------------------------------------------------
# Review-finding regressions (T79 code review)
# ---------------------------------------------------------------------------


def test_second_up_with_live_owned_child_refuses_and_keeps_state(launcher):
    # Finding 1: a live, correctly-tokenized recorded child must never be
    # orphaned by a second up spawning a duplicate upstream owner.
    assert launcher.up() == 0
    recorded_before = [p.to_dict() for p in launcher.state.processes]
    spawns_before = len(launcher.runner.spawned)
    launcher.output.clear()

    assert launcher.up() == 2

    text = joined_output(launcher)
    assert "LOCAL_ALREADY_RUNNING" in text
    assert f"role=runtime pid={recorded_before[0]['pid']}" in text
    # Zero new spawns, nothing signalled.
    assert len(launcher.runner.spawned) == spawns_before
    assert launcher.runner.signalled_pids == []
    # The state file still records the first children, not a replacement.
    payload = json.loads((launcher.state_dir / "state.json").read_text())
    assert payload["processes"] == recorded_before


def test_second_up_proceeds_after_all_recorded_children_died(launcher):
    assert launcher.up() == 0
    for process in launcher.state.processes:
        launcher.inspector.alive.discard(process.pid)
        launcher.inspector.command_for_pid.pop(process.pid, None)

    assert launcher.up() == 0
    assert len(launcher.runner.spawned) == 6
    assert spawned_roles(launcher.runner) == [
        "runtime",
        "api",
        "frontend",
        "runtime",
        "api",
        "frontend",
    ]


def test_up_refuses_to_overwrite_record_of_alive_unowned_pid(launcher):
    # Finding 1: alive-but-not-ours means state integrity is broken — refuse,
    # never overwrite the record, never signal anything.
    launcher.state.processes = [ManagedProcess(role="api", pid=123, token="ours")]
    launcher.inspector.command_for_pid[123] = "python unrelated.py"
    assert launcher.up() == 2
    assert "LOCAL_PROCESS_UNOWNED" in joined_output(launcher)
    assert launcher.runner.spawned == []
    assert launcher.runner.signalled_pids == []
    assert [p.pid for p in launcher.state.processes] == [123]


def test_init_failure_persists_cleared_marker(launcher):
    # Finding 2: a failing init must leave the on-disk state without the
    # initialized marker, not just the in-memory copy.
    launcher.state.save(launcher.state_dir / "state.json")
    payload_before = json.loads((launcher.state_dir / "state.json").read_text())
    assert payload_before["initialized"] is True

    launcher.bootstrap.error = RuntimeError("ranking sync failed")
    assert launcher.init() == 1

    payload = json.loads((launcher.state_dir / "state.json").read_text())
    assert payload["initialized"] is False
    assert payload["schema_head"] is None


def test_state_save_creates_file_with_mode_0600(tmp_path: Path):
    # Finding 3: the state file (carrying tokens) is 0600 from creation and
    # its directory 0700 — never world/group-readable at any point.
    path = tmp_path / "nested" / "state.json"
    LauncherState().save(path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700


def test_sigkill_escalation_rechecks_ownership_after_grace(launcher):
    # Finding 4: a PID that dies during the grace period and is "reused" by a
    # foreign command must NOT receive SIGKILL.
    launcher.state.processes = [ManagedProcess(role="runtime", pid=900, token="tok-r")]
    launcher.inspector.register(
        900, "python -m app.runtime.child --token tok-r --role runtime -- x"
    )
    launcher.inspector.stubborn.add(900)
    original_signal_group = launcher.runner.signal_group

    def signal_group(pid: int, signum: int) -> bool:
        result = original_signal_group(pid, signum)
        if signum == signal.SIGTERM:
            # The child exits and the PID is reused by a foreign command
            # between the grace period and the escalation.
            launcher.inspector.command_for_pid[900] = "totally foreign command"
        return result

    launcher.runner.signal_group = signal_group
    assert launcher.down() == 0
    assert launcher.runner.signals == [(900, signal.SIGTERM)]
    assert (900, signal.SIGKILL) not in launcher.runner.signals
    assert "LOCAL_PROCESS_UNOWNED" in joined_output(launcher)
    # The unstopped record is kept for the next reconciliation (Finding 5).
    assert [p.pid for p in launcher.state.processes] == [900]


def test_down_keeps_records_it_refused_or_failed_to_stop(launcher):
    # Finding 5: down clears only what actually stopped or was already dead.
    launcher.state.processes = [
        ManagedProcess(role="runtime", pid=31, token="tok-a"),  # already dead
        ManagedProcess(role="api", pid=32, token="tok-b"),  # alive, not ours
    ]
    launcher.inspector.command_for_pid[32] = "python unrelated.py"
    assert launcher.down() == 0
    assert launcher.runner.signalled_pids == []
    assert [p.pid for p in launcher.state.processes] == [32]
    payload = json.loads((launcher.state_dir / "state.json").read_text())
    assert [p["pid"] for p in payload["processes"]] == [32]


def test_real_spawn_pins_start_new_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # Finding 6: without start_new_session the child shares the launcher's
    # process group and killpg would target the launcher itself.
    captured: dict[str, Any] = {}

    class FakePopen:
        def __init__(self, argv: Any, **kwargs: Any) -> None:
            captured["argv"] = argv
            captured.update(kwargs)
            self.pid = 424242

    monkeypatch.setattr("app.runtime.launcher.subprocess.Popen", FakePopen)
    pid = SubprocessCommandRunner().spawn(
        ["python", "-m", "app.runtime.child"],
        cwd=str(tmp_path),
        env={},
        log_path=str(tmp_path / "runtime.log"),
    )
    assert pid == 424242
    assert captured["start_new_session"] is True


def test_real_signal_group_uses_killpg(monkeypatch: pytest.MonkeyPatch):
    # Finding 6: the real signal path must kill the child's process group
    # (os.killpg), never the launcher's own group. Nothing real is killed.
    calls: list[tuple[int, int]] = []
    monkeypatch.setattr(
        "app.runtime.launcher.os.killpg",
        lambda pid, signum: calls.append((pid, signum)),
    )
    assert SubprocessCommandRunner().signal_group(424242, signal.SIGTERM) is True
    assert calls == [(424242, signal.SIGTERM)]


def test_real_is_alive_reaps_zombie_children(monkeypatch: pytest.MonkeyPatch):
    # Review finding: children are spawned but never reaped, so an exited
    # child stays a zombie and os.kill(pid, 0) keeps reporting it alive —
    # the fail-fast exit codes would never fire and SIGKILL would be wasted.
    # Nothing is spawned or killed: os.waitpid / os.kill are both mocked.
    waitpid_results: list[tuple[int, int]] = []
    waitpid_errors: list[Exception | None] = []
    kill_errors: list[Exception | None] = []

    def fake_waitpid(pid: int, flags: int) -> tuple[int, int]:
        assert flags == os.WNOHANG
        error = waitpid_errors.pop(0)
        if error is not None:
            raise error
        return waitpid_results.pop(0)

    monkeypatch.setattr("app.runtime.launcher.os.waitpid", fake_waitpid)

    def fake_kill(pid: int, signum: int) -> None:
        assert signum == 0
        error = kill_errors.pop(0)
        if error is not None:
            raise error

    monkeypatch.setattr("app.runtime.launcher.os.kill", fake_kill)
    inspector = PsProcessInspector()

    # Reaped (zombie collected): reported dead without consulting kill(0).
    waitpid_errors.append(None)
    waitpid_results.append((424242, 0))
    assert inspector.is_alive(424242) is False

    # Still running: waitpid reports no exit, kill(pid, 0) succeeds.
    waitpid_errors.append(None)
    waitpid_results.append((0, 0))
    kill_errors.append(None)
    assert inspector.is_alive(424242) is True

    # Not our child (or already reaped elsewhere): fall back to kill(0),
    # which finds no such process.
    waitpid_errors.append(ChildProcessError())
    kill_errors.append(ProcessLookupError())
    assert inspector.is_alive(424242) is False

    # Non-positive pids must never reach waitpid (it would target a group).
    waitpid_errors.append(AssertionError("waitpid must not be called"))
    kill_errors.append(ProcessLookupError())
    assert inspector.is_alive(0) is False
    assert len(waitpid_errors) == 1  # sentinel unconsumed: waitpid never ran


# ---------------------------------------------------------------------------
# Hardening fixes (pre-T80): dead-child fast fail, frontend liveness,
# truthful status age
# ---------------------------------------------------------------------------


def _mark_dead(inspector: FakeProcessInspector, pid: int) -> None:
    inspector.alive.discard(pid)
    inspector.command_for_pid.pop(pid, None)


def test_up_fails_fast_when_runtime_child_dies_during_health_wait(launcher):
    # Fix 2a: a dead runtime child can never persist health — fail fast with
    # a stable code and exit 2 instead of burning the full health timeout.
    async def probe() -> None:
        for process in launcher.state.processes:
            if process.role == "runtime":
                _mark_dead(launcher.inspector, process.pid)
        return None

    launcher.health_probe = probe
    assert launcher.up() == 2
    text = joined_output(launcher)
    assert "LOCAL_RUNTIME_CHILD_EXITED" in text
    assert "LOCAL_RUNTIME_UNHEALTHY" not in text
    # The fake clock barely advanced: no timeout burn, no poll sleeps.
    assert launcher.time.now < launcher.poll_interval
    # The spawned record is persisted so down/status can reconcile it.
    payload = json.loads((launcher.state_dir / "state.json").read_text())
    assert [p["role"] for p in payload["processes"]] == ["runtime"]
    # Nothing was signalled: the child was already dead.
    assert launcher.runner.signalled_pids == []


def test_up_still_times_out_for_live_but_unhealthy_runtime_child(launcher):
    # Fix 2a must not change the existing timeout path for a live child.
    launcher.health_probe = FakeHealthProbe(final=None)
    assert launcher.up() == 1
    assert "LOCAL_RUNTIME_UNHEALTHY" in joined_output(launcher)
    assert launcher.time.now >= launcher.health_timeout


def test_up_reports_frontend_child_exiting_immediately(launcher):
    # Fix 2b: a frontend child that dies right after spawn must be reported
    # with a stable code — never a fake "up complete".
    original_spawn = launcher.runner.spawn

    def spawn(argv: list[str], **kwargs: Any) -> int:
        pid = original_spawn(argv, **kwargs)
        role = argv[argv.index("--role") + 1]
        if role == "frontend":
            _mark_dead(launcher.inspector, pid)
        return pid

    launcher.runner.spawn = spawn
    assert launcher.up() == 1
    text = joined_output(launcher)
    assert "LOCAL_FRONTEND_EXITED" in text
    assert "up complete" not in text
    assert spawned_roles(launcher.runner) == ["runtime", "api", "frontend"]


def test_up_happy_path_survives_frontend_liveness_window(launcher):
    # Fix 2b bounded window: an alive frontend child proceeds as before.
    assert launcher.up() == 0
    assert "up complete" in joined_output(launcher)
    assert launcher.time.now <= launcher.frontend_startup_seconds + 0.001


def test_status_text_includes_health_generated_at_and_age(launcher):
    # Fix 3: persisted health must never look fresher than it is.
    launcher.health_probe = FakeHealthProbe(final=runtime_gap_health())
    launcher._wall_clock = lambda: NOW + timedelta(seconds=37)
    assert launcher.status() == 0
    text = joined_output(launcher)
    assert "generated 2026-09-18T12:00:00+00:00" in text
    assert "(37s ago)" in text


def test_status_json_includes_health_generated_at_and_age(launcher):
    launcher.health_probe = FakeHealthProbe(final=runtime_gap_health())
    launcher._wall_clock = lambda: NOW + timedelta(seconds=7200)
    assert launcher.status(as_json=True) == 0
    data = json.loads(joined_output(launcher))
    assert data["health_generated_at"] == NOW.isoformat()
    assert data["health_age_seconds"] == 7200


def test_status_age_distinguishes_old_record_from_fresh(launcher):
    launcher.health_probe = FakeHealthProbe(final=runtime_gap_health())
    launcher._wall_clock = lambda: NOW + timedelta(seconds=5)
    assert launcher.status(as_json=True) == 0
    fresh = json.loads(joined_output(launcher))
    launcher.output.clear()
    launcher._wall_clock = lambda: NOW + timedelta(days=1)
    assert launcher.status(as_json=True) == 0
    old = json.loads(joined_output(launcher))
    assert fresh["health_age_seconds"] == 5
    assert old["health_age_seconds"] == 86400


def test_status_without_health_reports_no_persisted_record(launcher):
    launcher.health_probe = FakeHealthProbe(final=None)
    assert launcher.status() == 0
    assert "health record: none persisted" in joined_output(launcher)
    launcher.output.clear()
    assert launcher.status(as_json=True) == 0
    data = json.loads(joined_output(launcher))
    assert data["health_generated_at"] is None
    assert data["health_age_seconds"] is None
