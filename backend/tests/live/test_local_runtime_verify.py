"""T80 opt-in real local-runtime verification gate.

Run with:
    TENNIX_RUN_LOCAL_RUNTIME_VERIFY=1 uv run pytest -m local_runtime_live \
        tests/live/test_local_runtime_verify.py -v

Executes `verify_runtime` against real adapters built from the root `.env`
(never a subdirectory env file). The test is honest in both directions:

* an unset gate env is a real skip, never a fabricated pass;
* unreachable live-local configuration or database is a dated skip pointing
  at `./scripts/tennix-live init`;
* per source, `passed` OR `skipped` outcomes are both accepted — a quiet
  external window is a factual state, not a failure;
* the test FAILS only on a genuinely `failed` outcome or on a hygiene
  violation (provider IDs, keys, tokens or URLs leaking into outcomes).

The LLM path runs only when BOTH `TENNIX_RUN_LOCAL_RUNTIME_VERIFY=1` and
`TENNIX_RUN_LLM_LIVE=1` are set, so this gate never spends LLM quota by
accident. The verifier never writes fixtures, never sends orders and never
touches the paper ledger.
"""

import json
import os
import re
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from app.config import Settings
from app.persistence.database import Database
from app.runtime.cli import format_verify_results
from app.runtime.models import LiveLocalConfigurationError
from app.runtime.verify import build_verify_dependencies, verify_runtime

pytestmark = pytest.mark.local_runtime_live

TODAY = datetime.now(UTC).date().isoformat()

REASON_CODE = re.compile(r"^[A-Z][A-Z0-9_]*$")
FORBIDDEN_PATTERNS = (
    re.compile(r"APIkey", re.IGNORECASE),
    re.compile(r"wss?://"),
    re.compile(r"https?://"),
    re.compile(r"0x[0-9a-fA-F]{16,}"),
    re.compile(r"\b\d{20,}\b"),
    re.compile(r"private[-_ ]?key", re.IGNORECASE),
    re.compile(r"wallet", re.IGNORECASE),
)


def _require_enabled() -> Settings:
    if os.environ.get("TENNIX_RUN_LOCAL_RUNTIME_VERIFY") != "1":
        pytest.skip("TENNIX_RUN_LOCAL_RUNTIME_VERIFY not set")
    settings = Settings()  # root .env only, per project convention
    try:
        from app.runtime.config import require_live_local

        require_live_local(settings)
    except LiveLocalConfigurationError as exc:
        pytest.skip(f"live-local configuration incomplete ({exc.code}) on {TODAY}")
    return settings


async def _require_database(settings: Settings) -> None:
    from app.runtime.config import require_live_local

    live = require_live_local(settings)
    database = Database(live.database_url)
    try:
        async with database.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:  # environment dependent
        await database.dispose()
        pytest.skip(
            f"tennix_live_local not reachable ({type(exc).__name__}) on {TODAY}; "
            "run `./scripts/tennix-live init` first"
        )
    await database.dispose()


def _assert_outcome_hygiene(outcomes, settings: Settings) -> None:
    assert outcomes, "verifier must report every source"
    blob = json.dumps([outcome.model_dump(mode="json") for outcome in outcomes])
    rendered = format_verify_results(outcomes)
    for surface in (blob, rendered):
        for pattern in FORBIDDEN_PATTERNS:
            assert not pattern.search(surface), (
                f"provider material leaked into verification output: {pattern.pattern}"
            )
        for secret in (settings.api_tennis_api_key, settings.llm_api_key):
            if secret is not None:
                value = secret.get_secret_value()
                if value:
                    assert value not in surface, "credential leaked into output"
    for outcome in outcomes:
        assert outcome.status in {"passed", "failed", "skipped"}
        assert outcome.reason_code is None or REASON_CODE.fullmatch(outcome.reason_code)


async def _run_real_verify(settings: Settings, *, with_llm: bool):
    dependencies = build_verify_dependencies(settings)
    try:
        return await verify_runtime(with_llm=with_llm, **dependencies.verify_kwargs())
    finally:
        await dependencies.aclose()


async def test_real_verify_reports_honest_outcomes_without_leaking_material():
    settings = _require_enabled()
    await _require_database(settings)
    outcomes = await _run_real_verify(settings, with_llm=False)
    print(format_verify_results(outcomes))
    _assert_outcome_hygiene(outcomes, settings)
    # The gate fails ONLY on a genuinely failed source; skipped is honest.
    failed = [
        f"{outcome.name}:{outcome.reason_code}"
        for outcome in outcomes
        if outcome.status == "failed"
    ]
    assert failed == [], f"real verification failed sources on {TODAY}: {failed}"
    # Without the flag the LLM is never exercised.
    llm = next(o for o in outcomes if o.name == "llm_chat")
    assert llm.status == "skipped"
    assert llm.reason_code == "NOT_REQUESTED"


async def test_real_verify_with_llm_is_opt_in_and_bounded():
    settings = _require_enabled()
    if os.environ.get("TENNIX_RUN_LLM_LIVE") != "1":
        pytest.skip("TENNIX_RUN_LLM_LIVE not set; real Chat contract not exercised")
    await _require_database(settings)
    outcomes = await _run_real_verify(settings, with_llm=True)
    print(format_verify_results(outcomes))
    _assert_outcome_hygiene(outcomes, settings)
    failed = [
        f"{outcome.name}:{outcome.reason_code}"
        for outcome in outcomes
        if outcome.status == "failed"
    ]
    assert failed == [], f"real verification failed sources on {TODAY}: {failed}"
