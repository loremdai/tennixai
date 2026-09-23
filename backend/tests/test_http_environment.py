"""Regression proof for malformed host proxy-exclusion environment entries."""

import ast
import os
from pathlib import Path
import subprocess
import sys
import textwrap


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_PYTHON_ROOTS = (BACKEND_ROOT / "app",)
MALFORMED_LOOPBACK_NO_PROXY = "127.0.0.1,localhost,::1,127.0.0.0/8,::1/128"


def _run_with_malformed_no_proxy(source: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update(
        {
            "NO_PROXY": MALFORMED_LOOPBACK_NO_PROXY,
            "no_proxy": MALFORMED_LOOPBACK_NO_PROXY,
            "TENNIX_PROVIDER_MODE": "api_tennis",
            "TENNIX_API_TENNIS_API_KEY": "test-key",
            "TENNIX_LLM_MODE": "openai_compatible",
            "TENNIX_LLM_API_KEY": "test-key",
            "TENNIX_LLM_BASE_URL": "https://example.test/v1",
            "TENNIX_P3_MODE": "disabled",
            "TENNIX_LOCAL_RUNTIME_ROLE": "off",
        }
    )
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source)],
        cwd=BACKEND_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def test_application_boots_with_ipv6_loopback_no_proxy() -> None:
    result = _run_with_malformed_no_proxy("import app.main")

    assert result.returncode == 0, result.stderr


def test_offline_translator_constructs_with_ipv6_loopback_no_proxy() -> None:
    result = _run_with_malformed_no_proxy(
        """
        from app.players.enrichment import OpenAICompatibleTranslator

        OpenAICompatibleTranslator(
            api_key="test-key",
            base_url="https://example.test/v1",
            model="test-model",
        )
        """
    )

    assert result.returncode == 0, result.stderr


def test_every_project_owned_httpx_client_disables_host_proxy_inheritance() -> None:
    missing: list[str] = []
    for root in PROJECT_PYTHON_ROOTS:
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text())
            httpx_modules = {
                alias.asname or alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
                if alias.name == "httpx"
            }
            async_client_names = {
                alias.asname or alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module == "httpx"
                for alias in node.names
                if alias.name == "AsyncClient"
            }
            for node in ast.walk(tree):
                if not (
                    isinstance(node, ast.Call)
                    and (
                        (
                            isinstance(node.func, ast.Attribute)
                            and node.func.attr == "AsyncClient"
                            and isinstance(node.func.value, ast.Name)
                            and node.func.value.id in httpx_modules
                        )
                        or (
                            isinstance(node.func, ast.Name)
                            and node.func.id in async_client_names
                        )
                    )
                ):
                    continue
                trust_env = next(
                    (
                        keyword.value
                        for keyword in node.keywords
                        if keyword.arg == "trust_env"
                    ),
                    None,
                )
                if (
                    not isinstance(trust_env, ast.Constant)
                    or trust_env.value is not False
                ):
                    missing.append(str(path.relative_to(BACKEND_ROOT)))

    assert not missing, "missing trust_env=False: " + ", ".join(sorted(missing))


def test_default_websocket_clients_disable_host_proxy_inheritance(monkeypatch) -> None:
    from app.identity import MemoryIdentityRepository
    from app.markets import live as market_live
    from app.providers import api_tennis_live

    calls: list[tuple[str, dict[str, object]]] = []

    def connect(uri: str, **kwargs: object) -> object:
        calls.append((uri, kwargs))
        return object()

    monkeypatch.setattr(api_tennis_live.websockets, "connect", connect)
    monkeypatch.setattr(market_live.websockets, "connect", connect)

    tennis_feed = api_tennis_live.ApiTennisLiveFeedProvider(
        api_key="test-key",
        identities=MemoryIdentityRepository(),
        now=lambda: None,
    )
    market_feed = market_live.PolymarketMarketFeed()

    tennis_feed._connect("wss://tennis.example.test")
    market_feed._connect("wss://market.example.test")

    assert calls == [
        ("wss://tennis.example.test", {"proxy": None}),
        ("wss://market.example.test", {"proxy": None}),
    ]


def test_every_direct_websocket_connection_disables_host_proxy_inheritance() -> None:
    missing: list[str] = []
    for root in PROJECT_PYTHON_ROOTS:
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text())
            websocket_modules = {
                alias.asname or alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
                if alias.name == "websockets"
            }
            for node in ast.walk(tree):
                if not (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "connect"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id in websocket_modules
                ):
                    continue
                proxy = next(
                    (
                        keyword.value
                        for keyword in node.keywords
                        if keyword.arg == "proxy"
                    ),
                    None,
                )
                if not isinstance(proxy, ast.Constant) or proxy.value is not None:
                    missing.append(str(path.relative_to(BACKEND_ROOT)))

    assert not missing, "missing proxy=None: " + ", ".join(sorted(missing))
