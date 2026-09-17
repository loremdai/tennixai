"""Safe repository-root launcher for the P4.1 local real runtime (T79).

Ownership discipline (non-negotiable):

* launcher state lives under ``tempfile.gettempdir()/tennix-live-{uid}``,
  never in the repository;
* every managed process is a tokenized ``app.runtime.child`` wrapper in its
  own process group; the launcher signals a PID only after the process
  command line is verified to carry both the wrapper module and our token —
  never by port, never on suspicion;
* Compose accounting stores only container IDs newly created by this
  launcher invocation; ``down`` stops a container only on an exact
  current-ID match and never runs ``docker compose down``, never removes
  volumes and never stops pre-existing containers;
* ``up`` never runs initialization or enrichment and never invokes the LLM;
  only ``init`` may spend LLM quota through ``RuntimeBootstrapper``;
* no secret, key, URL-with-query, provider identifier or token value ever
  appears in launcher output, logs, or persisted state (state files hold
  PIDs, tokens, container IDs and log paths only — tokens are ownership
  material and stay inside the 0600 state file, never in printed output).
"""

import asyncio
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

import httpx
from sqlalchemy import text

from app.config import Settings
from app.runtime.config import child_environment, require_live_local
from app.runtime.models import (
    LiveLocalConfigurationError,
    LocalRuntimeSettings,
    RuntimeHealth,
    RuntimeInitRecord,
    RuntimeSourceStatus,
)

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_PRECONDITION = 2

CHILD_MODULE = "app.runtime.child"
RUNTIME_ENTRY_MODULE = "app.runtime.daemon_main"
MANAGED_ROLES: tuple[str, ...] = ("runtime", "api", "frontend")
COMPOSE_SERVICES: tuple[str, ...] = ("postgres", "redis")
API_PORT = 8000
FRONTEND_PORT = 3100
API_HEALTH_URL = f"http://127.0.0.1:{API_PORT}/api/v1/health"
FRONTEND_URL = f"http://127.0.0.1:{FRONTEND_PORT}"
LIVE_LOCAL_DATABASE_NAME = "tennix_live_local"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
HEALTHY_FIRST_DISCOVERY_SOURCES = ("tennis_live", "polymarket", "live_catalog")
STATUS_SOURCE_ROWS = {
    "sports_stream": "tennis_live",
    "schedule": "upcoming_catalog",
    "rankings": "rankings",
    "polymarket": "polymarket",
}
LOG_TAIL_LINES = 400
COMMAND_TIMEOUT_SECONDS = 600.0
STOP_POLL_SECONDS = 0.25
STRIPPED_PROXY_VARS = ("NO_PROXY", "no_proxy")


@dataclass
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


@dataclass
class ManagedProcess:
    role: str
    pid: int
    token: str
    log_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "pid": self.pid,
            "token": self.token,
            "log_path": self.log_path,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ManagedProcess":
        return cls(
            role=str(payload["role"]),
            pid=int(payload["pid"]),
            token=str(payload["token"]),
            log_path=payload.get("log_path"),
        )


@dataclass
class LauncherState:
    """Persisted ownership state: PIDs, tokens, container IDs, log paths."""

    initialized: bool = False
    schema_head: str | None = None
    processes: list[ManagedProcess] = field(default_factory=list)
    containers: dict[str, str] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "initialized": self.initialized,
            "schema_head": self.schema_head,
            "processes": [process.to_dict() for process in self.processes],
            "containers": dict(self.containers),
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_payload(), indent=2) + "\n")
        os.chmod(path, 0o600)

    @classmethod
    def load(cls, path: Path) -> "LauncherState":
        if not path.is_file():
            return cls()
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return cls()
        return cls(
            initialized=bool(payload.get("initialized", False)),
            schema_head=payload.get("schema_head"),
            processes=[
                ManagedProcess.from_dict(entry)
                for entry in payload.get("processes", [])
            ],
            containers=dict(payload.get("containers", {})),
        )


@dataclass(frozen=True)
class DatabaseStatus:
    initialized: bool
    schema_head: str | None


class CommandRunner(Protocol):
    def run(
        self,
        argv: list[str],
        *,
        cwd: str | None = ...,
        env: dict[str, str] | None = ...,
    ) -> CommandResult: ...

    def spawn(
        self,
        argv: list[str],
        *,
        cwd: str | None,
        env: dict[str, str],
        log_path: str,
    ) -> int: ...

    def signal_group(self, pid: int, signum: int) -> bool: ...


class ProcessInspector(Protocol):
    def command_line(self, pid: int) -> str | None: ...

    def is_alive(self, pid: int) -> bool: ...


class PortProber(Protocol):
    def listener(self, port: int) -> str | None: ...


class MigrationRunnerLike(Protocol):
    async def upgrade_head(self) -> str: ...


def default_state_dir() -> Path:
    """Launcher state directory — always under the OS temp dir, never in
    the repository."""
    return Path(tempfile.gettempdir()) / f"tennix-live-{os.getuid()}"


def _is_healthy_first_discovery(health: RuntimeHealth | None) -> bool:
    if health is None:
        return False
    return all(
        (source := health.sources.get(name)) is not None
        and source.status is RuntimeSourceStatus.OK
        for name in HEALTHY_FIRST_DISCOVERY_SOURCES
    )


class RuntimeLauncher:
    """One-command local lifecycle: init / up / status / down / logs."""

    def __init__(
        self,
        *,
        root_dir: Path,
        state_dir: Path,
        settings_factory: Callable[[], Settings],
        runner: CommandRunner,
        inspector: ProcessInspector,
        ports: PortProber,
        clock: Callable[[], float],
        sleep: Callable[[float], Awaitable[None]],
        sleep_sync: Callable[[float], None],
        output: Callable[[str], None],
        token_factory: Callable[[], str],
        database_ensure: Callable[[LocalRuntimeSettings], Awaitable[None]],
        migrations_factory: Callable[[LocalRuntimeSettings], MigrationRunnerLike],
        bootstrap: Callable[
            [Settings, LocalRuntimeSettings, MigrationRunnerLike],
            Awaitable[RuntimeInitRecord],
        ],
        database_probe: Callable[[], Awaitable[DatabaseStatus]],
        health_probe: Callable[[], Awaitable[RuntimeHealth | None]],
        http_probe: Callable[[str], Awaitable[bool]],
        health_timeout: float = 180.0,
        api_timeout: float = 60.0,
        poll_interval: float = 1.0,
        stop_grace_seconds: float = 10.0,
        python_executable: str | None = None,
        pnpm_executable: str = "pnpm",
    ) -> None:
        self.root_dir = Path(root_dir)
        self.backend_dir = self.root_dir / "backend"
        self.frontend_dir = self.root_dir / "frontend"
        self.state_dir = Path(state_dir)
        self.settings_factory = settings_factory
        self.runner = runner
        self.inspector = inspector
        self.ports = ports
        self._output = output
        self._clock = clock
        self._sleep = sleep
        self._sleep_sync = sleep_sync
        self._token_factory = token_factory
        self.database_ensure = database_ensure
        self.migrations_factory = migrations_factory
        self.bootstrap = bootstrap
        self.database_probe = database_probe
        self.health_probe = health_probe
        self.http_probe = http_probe
        self.health_timeout = health_timeout
        self.api_timeout = api_timeout
        self.poll_interval = poll_interval
        self.stop_grace_seconds = stop_grace_seconds
        self.python_executable = python_executable or sys.executable
        self.pnpm_executable = pnpm_executable
        self.state = LauncherState.load(self.state_dir / "state.json")

    # ------------------------------------------------------------------
    # init
    # ------------------------------------------------------------------

    def init(self) -> int:
        # init is the only authority for the initialized marker: clear any
        # stale marker up front so a failed init never leaves fake-looking
        # partial success behind.
        self.state.initialized = False
        self.state.schema_head = None
        try:
            settings, live = self._validated_settings()
        except LiveLocalConfigurationError as exc:
            self._say(
                f"init failed: {exc.code} (root .env is not valid live-local configuration)"
            )
            return EXIT_FAILURE
        if self._ensure_compose() is None:
            return EXIT_FAILURE
        try:
            asyncio.run(self.database_ensure(live))
        except Exception as exc:  # noqa: BLE001 - never echo exception text (may embed DSN)
            self._say(
                "init failed: LOCAL_DATABASE_CREATE_FAILED "
                f"(could not ensure the dedicated {LIVE_LOCAL_DATABASE_NAME} database: {type(exc).__name__})"
            )
            return EXIT_FAILURE
        migrations = self.migrations_factory(live)
        try:
            record = asyncio.run(self.bootstrap(settings, live, migrations))
        except Exception as exc:  # noqa: BLE001 - stable code only, no payloads
            self._say(
                "init failed: LOCAL_BOOTSTRAP_FAILED "
                f"(bootstrap did not complete: {type(exc).__name__}; fix the cause and re-run init)"
            )
            return EXIT_FAILURE
        self.state.initialized = True
        self.state.schema_head = record.migration_revision
        self._persist()
        self._say(
            "init complete: "
            f"revision={record.migration_revision} "
            f"players={record.player_count} matches={record.match_count}"
        )
        self._say("next: ./scripts/tennix-live up")
        return EXIT_OK

    # ------------------------------------------------------------------
    # up
    # ------------------------------------------------------------------

    def up(self) -> int:
        try:
            settings, _live = self._validated_settings()
        except LiveLocalConfigurationError as exc:
            self._say(
                f"up failed: {exc.code} (root .env is not valid live-local configuration)"
            )
            return EXIT_FAILURE
        if self._ensure_compose() is None:
            return EXIT_FAILURE
        if not self.state.initialized:
            self._say(
                "up refused: LOCAL_NOT_INITIALIZED "
                "(run ./scripts/tennix-live init first; up never initializes or enriches)"
            )
            return EXIT_PRECONDITION
        database_status = asyncio.run(self.database_probe())
        if (
            not database_status.initialized
            or database_status.schema_head is None
            or database_status.schema_head != self.state.schema_head
        ):
            self._say(
                "up refused: LOCAL_SCHEMA_BEHIND "
                "(the database does not carry the initialized schema head; "
                "run ./scripts/tennix-live init first)"
            )
            return EXIT_PRECONDITION
        port_failure = self._check_ports()
        if port_failure is not None:
            return port_failure

        spawned: list[ManagedProcess] = []
        runtime_process = self._spawn_child(
            settings,
            role="runtime",
            inner=[self.python_executable, "-m", RUNTIME_ENTRY_MODULE],
            cwd=self.backend_dir,
        )
        spawned.append(runtime_process)
        self.state.processes = spawned
        self._persist()
        if not asyncio.run(self._wait_for_healthy_runtime()):
            self._say(
                "up failed: LOCAL_RUNTIME_UNHEALTHY "
                "(the runtime child did not persist a healthy first discovery in time; "
                f"see {runtime_process.log_path})"
            )
            self._stop_processes(spawned)
            return EXIT_FAILURE

        api_process = self._spawn_child(
            settings,
            role="api",
            inner=[
                self.python_executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(API_PORT),
            ],
            cwd=self.backend_dir,
        )
        spawned.append(api_process)
        self._persist()
        if not asyncio.run(self._wait_for_api_health()):
            self._say(
                "up failed: LOCAL_API_UNHEALTHY "
                f"(the API child did not answer {API_HEALTH_URL} in time; "
                f"see {api_process.log_path})"
            )
            self._stop_processes(spawned)
            return EXIT_FAILURE

        frontend_process = self._spawn_child(
            settings,
            role="frontend",
            inner=[
                self.pnpm_executable,
                "dev",
                "--hostname",
                "127.0.0.1",
                "--port",
                str(FRONTEND_PORT),
            ],
            cwd=self.frontend_dir,
            runtime_role=None,
            extra_env={"TENNIX_BACKEND_URL": f"http://127.0.0.1:{API_PORT}"},
        )
        spawned.append(frontend_process)
        self.state.processes = spawned
        self._persist()

        self._say(
            "up complete: runtime, api and frontend children are owned by this launcher"
        )
        self._say(f"  open the browser at {FRONTEND_URL}")
        self._say(f"  api health: {API_HEALTH_URL}")
        self._say(
            "  hints: ./scripts/tennix-live status | logs runtime | logs api | logs frontend | down"
        )
        return EXIT_OK

    # ------------------------------------------------------------------
    # status
    # ------------------------------------------------------------------

    def status(self, *, as_json: bool = False) -> int:
        health = asyncio.run(self._safe_health_probe())
        components: dict[str, dict[str, str | None]] = {}

        for service, row in (("postgres", "database"), ("redis", "redis")):
            container_id = self._compose_container_id(service)
            if not container_id:
                components[row] = {"state": "absent", "detail": "no compose container"}
                continue
            result = self.runner.run(
                ["docker", "inspect", "-f", "{{.State.Health.Status}}", container_id],
                cwd=str(self.root_dir),
            )
            container_health = result.stdout.strip() or "unknown"
            ownership = (
                "owned"
                if self.state.containers.get(service) == container_id
                else "external"
            )
            components[row] = {
                "state": container_health,
                "detail": f"container {ownership}",
            }

        running = 0
        for role in MANAGED_ROLES:
            process = next(
                (entry for entry in self.state.processes if entry.role == role), None
            )
            if process is None:
                components[role] = {
                    "state": "stopped",
                    "detail": "not started by this launcher",
                }
                continue
            if not self.inspector.is_alive(process.pid):
                components[role] = {
                    "state": "stopped",
                    "detail": f"pid {process.pid} exited",
                }
            elif not self._owned(process):
                components[role] = {
                    "state": "unknown",
                    "detail": f"pid {process.pid} is not our wrapper; not owned",
                }
            else:
                running += 1
                components[role] = {"state": "running", "detail": f"pid {process.pid}"}

        if health is None:
            for row in (*STATUS_SOURCE_ROWS, "paper", "model"):
                components[row] = {
                    "state": "unknown",
                    "detail": "no persisted health (runtime never reported)",
                }
        else:
            for row, source in STATUS_SOURCE_ROWS.items():
                entry = health.sources.get(source)
                if entry is None:
                    components[row] = {
                        "state": "unknown",
                        "detail": f"source {source} absent",
                    }
                else:
                    components[row] = {
                        "state": entry.status.value,
                        "detail": entry.reason_code,
                    }
            components["paper"] = {
                "state": health.paper_status or "unknown",
                "detail": None,
            }
            components["model"] = {
                "state": health.model_status or "unknown",
                "detail": None,
            }

        containers_healthy = all(
            components[name]["state"] == "healthy" for name in ("database", "redis")
        )
        if running == len(MANAGED_ROLES) and containers_healthy:
            stack = "running"
        elif running > 0 or containers_healthy:
            stack = "partial"
        else:
            stack = "stopped"

        if as_json:
            self._say(json.dumps({"stack": stack, "components": components}, indent=2))
        else:
            self._say(f"stack: {stack}")
            width = max(len(name) for name in components)
            for name, component in components.items():
                detail = component["detail"] or ""
                state = component["state"] or "unknown"
                self._say(f"{name.ljust(width)}  {state.ljust(11)} {detail}".rstrip())
        return EXIT_OK

    # ------------------------------------------------------------------
    # down
    # ------------------------------------------------------------------

    def down(self) -> int:
        self._say(
            "down: stopping the runtime first (graceful flush), then api/frontend, "
            "then exactly-owned compose containers"
        )
        for role in MANAGED_ROLES:
            for process in list(self.state.processes):
                if process.role == role:
                    self._stop_process(process)
        for service, container_id in list(self.state.containers.items()):
            current = self._compose_container_id(service)
            if current and current == container_id:
                self.runner.run(
                    ["docker", "stop", container_id], cwd=str(self.root_dir)
                )
                self._say(f"down: stopped owned {service} container")
            else:
                self._say(
                    f"down: {service} container is not an exact owned match; left untouched"
                )
        self.state.processes = []
        self.state.containers = {}
        self._persist()
        self._say(
            "down complete: all data preserved (no volumes touched, no destructive commands)"
        )
        return EXIT_OK

    # ------------------------------------------------------------------
    # logs
    # ------------------------------------------------------------------

    def logs(self, role: Literal["runtime", "api", "frontend"] | str) -> int:
        if role not in MANAGED_ROLES:
            self._say(f"logs: unknown role {role!r} (choose runtime, api or frontend)")
            return EXIT_PRECONDITION
        path = self.state_dir / f"{role}.log"
        if not path.is_file():
            self._say(f"logs: no {role} log yet ({path} does not exist)")
            return EXIT_FAILURE
        lines = path.read_text(errors="replace").splitlines()
        for line in lines[-LOG_TAIL_LINES:]:
            self._say(line)
        return EXIT_OK

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _say(self, line: str) -> None:
        self._output(line)

    def _persist(self) -> None:
        self.state.save(self.state_dir / "state.json")

    def _validated_settings(self) -> tuple[Settings, LocalRuntimeSettings]:
        from pydantic import ValidationError

        try:
            settings = self.settings_factory()
        except ValidationError:
            # Never echo offending values; a stable code is enough.
            raise LiveLocalConfigurationError("LOCAL_SETTINGS_INVALID") from None
        return settings, require_live_local(settings)

    def _compose_container_id(self, service: str) -> str:
        result = self.runner.run(
            ["docker", "compose", "ps", "-q", service], cwd=str(self.root_dir)
        )
        return result.stdout.strip()

    def _ensure_compose(self) -> dict[str, str] | None:
        """Ensure postgres/redis are up; store only newly created container
        IDs so ``down`` may stop exactly what this launcher created."""
        before = {
            service: self._compose_container_id(service) for service in COMPOSE_SERVICES
        }
        result = self.runner.run(
            ["docker", "compose", "up", "-d", "--wait", "postgres", "redis"],
            cwd=str(self.root_dir),
        )
        if result.returncode != 0:
            self._say(
                "compose failed: LOCAL_COMPOSE_FAILED "
                "(docker compose up -d --wait postgres redis did not become healthy)"
            )
            return None
        for service in COMPOSE_SERVICES:
            after = self._compose_container_id(service)
            if not after:
                self._say(
                    f"compose failed: LOCAL_COMPOSE_UNAVAILABLE (service {service} reports no container id)"
                )
                return None
            if after != before[service]:
                self.state.containers[service] = after
        self._persist()
        return dict(self.state.containers)

    def _check_ports(self) -> int | None:
        owned_pids = {str(process.pid) for process in self.state.processes}
        for port in (API_PORT, FRONTEND_PORT):
            listener = self.ports.listener(port)
            if listener is None:
                continue
            if listener in owned_pids:
                self._say(
                    f"up refused: LOCAL_ALREADY_RUNNING "
                    f"(port {port} is held by our pid {listener}; "
                    "use ./scripts/tennix-live status or down)"
                )
                return EXIT_PRECONDITION
            self._say(
                f"up refused: LOCAL_PORT_OCCUPIED "
                f"(port {port} is in use by another process; the launcher never kills foreign processes)"
            )
            return EXIT_PRECONDITION
        return None

    def _child_env(
        self,
        settings: Settings,
        *,
        runtime_role: str | None,
        extra_env: dict[str, str] | None,
    ) -> dict[str, str]:
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in STRIPPED_PROXY_VARS
        }
        if runtime_role is not None:
            env.update(child_environment(settings, role=runtime_role))
        if extra_env:
            env.update(extra_env)
        return env

    def _spawn_child(
        self,
        settings: Settings,
        *,
        role: str,
        inner: list[str],
        cwd: Path,
        runtime_role: str | None = ...,  # type: ignore[assignment]
        extra_env: dict[str, str] | None = None,
    ) -> ManagedProcess:
        if runtime_role is ...:
            runtime_role = role if role in ("runtime", "api") else None
        token = self._token_factory()
        argv = [
            self.python_executable,
            "-m",
            CHILD_MODULE,
            "--token",
            token,
            "--role",
            role,
            "--",
            *inner,
        ]
        env = self._child_env(settings, runtime_role=runtime_role, extra_env=extra_env)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.state_dir / f"{role}.log"
        pid = self.runner.spawn(argv, cwd=str(cwd), env=env, log_path=str(log_path))
        return ManagedProcess(role=role, pid=pid, token=token, log_path=str(log_path))

    def _owned(self, process: ManagedProcess) -> bool:
        command = self.inspector.command_line(process.pid)
        return (
            command is not None and CHILD_MODULE in command and process.token in command
        )

    async def _wait_for(
        self, predicate: Callable[[], Awaitable[bool]], timeout: float
    ) -> bool:
        deadline = self._clock() + timeout
        while True:
            if await predicate():
                return True
            if self._clock() >= deadline:
                return False
            await self._sleep(self.poll_interval)

    async def _wait_for_healthy_runtime(self) -> bool:
        async def healthy() -> bool:
            try:
                health = await self.health_probe()
            except Exception:  # noqa: BLE001 - transient probe failure keeps waiting
                return False
            return _is_healthy_first_discovery(health)

        return await self._wait_for(healthy, self.health_timeout)

    async def _wait_for_api_health(self) -> bool:
        async def answered() -> bool:
            try:
                return await self.http_probe(API_HEALTH_URL)
            except Exception:  # noqa: BLE001 - connection refused keeps waiting
                return False

        return await self._wait_for(answered, self.api_timeout)

    async def _safe_health_probe(self) -> RuntimeHealth | None:
        try:
            return await self.health_probe()
        except Exception:  # noqa: BLE001 - status must never crash on a probe error
            return None

    def _stop_process(self, process: ManagedProcess) -> None:
        if not self.inspector.is_alive(process.pid):
            return
        if not self._owned(process):
            self._say(
                f"stop: LOCAL_PROCESS_UNOWNED role={process.role} pid={process.pid} "
                "was NOT signalled (its command line does not carry our wrapper token)"
            )
            return
        self.runner.signal_group(process.pid, signal.SIGTERM)
        deadline = self._clock() + self.stop_grace_seconds
        while self.inspector.is_alive(process.pid) and self._clock() < deadline:
            self._sleep_sync(STOP_POLL_SECONDS)
        if self.inspector.is_alive(process.pid):
            self.runner.signal_group(process.pid, signal.SIGKILL)

    def _stop_processes(self, processes: list[ManagedProcess]) -> None:
        for role in MANAGED_ROLES:
            for process in processes:
                if process.role == role:
                    self._stop_process(process)


# ---------------------------------------------------------------------------
# Real collaborator implementations (used by build_launcher / the CLI only)
# ---------------------------------------------------------------------------


class SubprocessCommandRunner:
    def run(
        self,
        argv: list[str],
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> CommandResult:
        try:
            completed = subprocess.run(  # noqa: S603 - fixed launcher argv
                argv,
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=COMMAND_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired):
            return CommandResult(1, "", "command failed")
        return CommandResult(completed.returncode, completed.stdout, completed.stderr)

    def spawn(
        self,
        argv: list[str],
        *,
        cwd: str | None,
        env: dict[str, str],
        log_path: str,
    ) -> int:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "ab") as log_file:
            process = subprocess.Popen(  # noqa: S603 - launcher-controlled argv
                argv,
                cwd=cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        return process.pid

    def signal_group(self, pid: int, signum: int) -> bool:
        try:
            os.killpg(pid, signum)
            return True
        except (ProcessLookupError, PermissionError):
            return False


class PsProcessInspector:
    def command_line(self, pid: int) -> str | None:
        try:
            completed = subprocess.run(  # noqa: S603
                ["ps", "-o", "command=", "-p", str(pid)],
                capture_output=True,
                text=True,
                timeout=10.0,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        line = completed.stdout.strip()
        return line or None

    def is_alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True


class LsofPortProber:
    """Read-only listener probe. When the owner cannot be determined the
    port is reported as occupied by ``unknown`` — the launcher then fails
    clearly instead of ever killing by port."""

    def listener(self, port: int) -> str | None:
        try:
            completed = subprocess.run(  # noqa: S603
                ["lsof", "-nP", "-ti", f"tcp:{port}", "-sTCP:LISTEN"],
                capture_output=True,
                text=True,
                timeout=10.0,
            )
        except (OSError, subprocess.TimeoutExpired):
            completed = None
        if completed is not None and completed.returncode == 0:
            lines = [
                line.strip() for line in completed.stdout.splitlines() if line.strip()
            ]
            return lines[0] if lines else None
        with socket.socket() as probe:
            probe.settimeout(0.5)
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                return "unknown"
        return None


class AlembicMigrationRunner:
    """Programmatic Alembic ``upgrade head`` against the live-local URL.

    Honors the ``MigrationRunner`` protocol consumed by ``RuntimeBootstrapper``.
    ``migrations/env.py`` runs ``asyncio.run`` at import, so the upgrade is
    executed in a worker thread and never inside the running event loop.
    """

    def __init__(self, database_url: str, *, backend_dir: Path | None = None) -> None:
        self._database_url = database_url
        self._backend_dir = backend_dir or Path(__file__).resolve().parents[2]

    def _config(self) -> Any:
        from alembic.config import Config

        config = Config(str(self._backend_dir / "alembic.ini"))
        config.set_main_option("script_location", str(self._backend_dir / "migrations"))
        config.set_main_option("sqlalchemy.url", self._database_url.replace("%", "%%"))
        return config

    async def upgrade_head(self) -> str:
        return await asyncio.to_thread(self._upgrade_head)

    def _upgrade_head(self) -> str:
        from alembic import command
        from alembic.script import ScriptDirectory

        config = self._config()
        command.upgrade(config, "head")
        head = ScriptDirectory.from_config(config).get_current_head()
        if head is None:
            raise LiveLocalConfigurationError("LOCAL_MIGRATIONS_FAILED")
        return head


async def ensure_live_local_database(live: LocalRuntimeSettings) -> None:
    """Idempotently create the dedicated ``tennix_live_local`` database.

    Re-verifies the target name and loopback host immediately before any
    database command. Never drops anything and never touches the legacy
    ``tennix`` database.
    """
    import asyncpg
    from sqlalchemy.engine import make_url

    url = make_url(live.database_url)
    if (
        url.database != LIVE_LOCAL_DATABASE_NAME
        or (url.host or "") not in LOOPBACK_HOSTS
    ):
        raise LiveLocalConfigurationError("LOCAL_DATABASE_NAME_INVALID")
    connection = await asyncpg.connect(
        host=url.host,
        port=url.port or 5432,
        user=url.username,
        password=url.password,
        database="postgres",
    )
    try:
        exists = await connection.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", LIVE_LOCAL_DATABASE_NAME
        )
        if not exists:
            # The identifier is the fixed constant re-verified above, never
            # user input; there is no CREATE DATABASE parameter binding.
            await connection.execute(f'CREATE DATABASE "{LIVE_LOCAL_DATABASE_NAME}"')
    finally:
        await connection.close()


async def probe_database_status(live: LocalRuntimeSettings) -> DatabaseStatus:
    from app.persistence.database import Database
    from app.persistence.repositories import RuntimeStateRepository

    database = Database(live.database_url)
    try:
        initialized = await RuntimeStateRepository(database).is_initialized()
        schema_head: str | None = None
        async with database.session() as session:
            result = await session.execute(
                text("SELECT version_num FROM alembic_version")
            )
            row = result.first()
            schema_head = str(row[0]) if row else None
        return DatabaseStatus(initialized=initialized, schema_head=schema_head)
    except Exception:  # noqa: BLE001 - unreachable database reads as not initialized
        return DatabaseStatus(initialized=False, schema_head=None)
    finally:
        await database.dispose()


async def probe_persisted_health(live: LocalRuntimeSettings) -> RuntimeHealth | None:
    from app.persistence.database import Database
    from app.persistence.repositories import RuntimeStateRepository

    database = Database(live.database_url)
    try:
        return await RuntimeStateRepository(database).load_health()
    except Exception:  # noqa: BLE001 - health is unknown while the DB is unreachable
        return None
    finally:
        await database.dispose()


async def probe_http_health(url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(url)
            return response.status_code == 200
    except Exception:  # noqa: BLE001 - connection refused keeps the wait loop going
        return False


async def run_runtime_bootstrap(
    settings: Settings,
    live: LocalRuntimeSettings,
    migrations: MigrationRunnerLike,
) -> RuntimeInitRecord:
    """Real ``init`` bootstrap: rankings/aliases/catalog sync plus the only
    step allowed to spend LLM quota for missing Chinese names."""
    from app.persistence.database import Database
    from app.persistence.player_directory import PostgresPlayerDirectoryRepository
    from app.persistence.repositories import (
        MatchCatalogRepository,
        PostgresIdentityRepository,
        RuntimeStateRepository,
    )
    from app.players.enrichment import OpenAICompatibleTranslator, PlayerAliasEnricher
    from app.players.sync import PlayerDirectorySync
    from app.providers.api_tennis import ApiTennisProvider
    from app.runtime.bootstrap import RuntimeBootstrapper
    from app.runtime.catalog import CatalogSynchronizer

    api_key = settings.api_tennis_api_key
    llm_key = settings.llm_api_key
    if api_key is None or llm_key is None or not settings.llm_base_url:
        raise LiveLocalConfigurationError("LOCAL_CREDENTIALS_MISSING")

    def clock() -> datetime:
        return datetime.now(UTC)

    database = Database(live.database_url)
    client = httpx.AsyncClient(base_url=settings.api_tennis_base_url, timeout=15.0)
    try:
        identities = PostgresIdentityRepository(database)
        directory = PostgresPlayerDirectoryRepository(database)
        provider = ApiTennisProvider(
            client=client,
            identities=identities,
            api_key=api_key.get_secret_value(),
            now=clock,
            directory=directory,
        )
        translator = OpenAICompatibleTranslator(
            api_key=llm_key.get_secret_value(),
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            timeout_seconds=float(settings.llm_timeout_seconds),
        )
        bootstrapper = RuntimeBootstrapper(
            migrations=migrations,
            directory=PlayerDirectorySync(provider, directory, now=clock),
            catalog=CatalogSynchronizer(
                provider, MatchCatalogRepository(database), now=clock
            ),
            enricher=PlayerAliasEnricher(
                directory, translator, model=settings.llm_model
            ),
            state=RuntimeStateRepository(database),
            now=clock,
        )
        return await bootstrapper.initialize()
    finally:
        await client.aclose()
        await database.dispose()


def build_launcher(*, root_dir: Path | None = None) -> RuntimeLauncher:
    """Wire the real launcher for ``python -m app.runtime.cli``."""
    root = root_dir or Path(__file__).resolve().parents[3]

    async def database_ensure(live: LocalRuntimeSettings) -> None:
        await ensure_live_local_database(live)

    def migrations_factory(live: LocalRuntimeSettings) -> MigrationRunnerLike:
        return AlembicMigrationRunner(live.database_url)

    async def database_probe() -> DatabaseStatus:
        return await probe_database_status(require_live_local(Settings()))

    async def health_probe() -> RuntimeHealth | None:
        return await probe_persisted_health(require_live_local(Settings()))

    return RuntimeLauncher(
        root_dir=root,
        state_dir=default_state_dir(),
        settings_factory=Settings,
        runner=SubprocessCommandRunner(),
        inspector=PsProcessInspector(),
        ports=LsofPortProber(),
        clock=time.monotonic,
        sleep=asyncio.sleep,
        sleep_sync=time.sleep,
        output=print,
        token_factory=lambda: secrets.token_hex(8),
        database_ensure=database_ensure,
        migrations_factory=migrations_factory,
        bootstrap=run_runtime_bootstrap,
        database_probe=database_probe,
        health_probe=health_probe,
        http_probe=probe_http_health,
    )
