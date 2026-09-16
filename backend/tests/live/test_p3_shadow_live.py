"""T71 real read-only shadow gate.

Run with:
    TENNIX_RUN_P3_SHADOW_LIVE=1 uv run pytest -m end_to_end_live \
        tests/live/test_p3_shadow_live.py -v

Assembles the shadow backend against the real API-Tennis provider and the
public Polymarket REST surface (read-only by construction), observes mapped
tennis moneylines when any exist, and proves the unpromoted model can only
abstain: every decision stays MARKET_ONLY/NO BET, the public surface carries
no provider identifiers or wallet material, and the configuration model has
no trading credentials at all. A quiet market is an honest dated skip with
discovery counts, never a fabricated observation.
"""

import contextlib
import json
import os
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.config import Settings
from app.errors import AppError
from app.decision.engine import DecisionEngine, DecisionInput
from app.decision.models import DecisionAction
from app.decision.policy import PolicyArtifact
from app.persistence.database import Database
from app.prediction.models import ModelAvailability
from app.prediction.service import PredictionService

pytestmark = pytest.mark.end_to_end_live

TODAY = datetime.now(UTC).date().isoformat()


def _require_enabled() -> Settings:
    if os.environ.get("TENNIX_RUN_P3_SHADOW_LIVE") != "1":
        pytest.skip("TENNIX_RUN_P3_SHADOW_LIVE not set")
    settings = Settings(p3_mode="shadow", provider_mode="api_tennis")
    key = settings.api_tennis_api_key
    if key is None or not key.get_secret_value().strip():
        pytest.skip("TENNIX_API_TENNIS_API_KEY not configured")
    return settings


@pytest.fixture()
async def database():
    settings = Settings(_env_file=None)
    db = Database(settings.database_url)
    try:
        async with db.engine.connect() as connection:
            mapped = (
                await connection.execute(
                    text("SELECT to_regclass('public.decision_observations')")
                )
            ).scalar()
    except Exception as exc:  # pragma: no cover - environment dependent
        await db.dispose()
        pytest.skip(f"PostgreSQL not reachable ({type(exc).__name__})")
    if mapped is None:
        await db.dispose()
        pytest.skip("P3 schema not migrated; run `uv run alembic upgrade head`")
    try:
        yield db
    finally:
        await db.dispose()


async def test_configuration_has_no_trading_credentials() -> None:
    settings = _require_enabled()
    forbidden = [
        name
        for name in Settings.model_fields
        if any(
            fragment in name
            for fragment in ("wallet", "private_key", "signing", "secret_key")
        )
    ]
    assert forbidden == [], f"trading credential settings must not exist: {forbidden}"
    # Polymarket endpoints stay public read-only hosts.
    assert settings.polymarket_gamma_base_url.startswith(
        "https://gamma-api.polymarket.com"
    )
    assert settings.polymarket_clob_base_url.startswith("https://clob.polymarket.com")


async def test_unpromoted_model_abstains_on_real_snapshot(database: Database) -> None:
    _require_enabled()
    from app.domain import (
        CircuitTier,
        DataFreshness,
        Discipline,
        Gender,
        Match,
        MatchSnapshot,
        MatchStatus,
        Player,
        Tournament,
    )
    from p3_fakes import make_book

    service = PredictionService(artifact_dir="artifacts/p3")
    match = Match(
        id="mat_shadow",
        status=MatchStatus.SCHEDULED,
        players=(
            Player(id="ply_a", name="Alpha One"),
            Player(id="ply_b", name="Beta Two"),
        ),
        tournament=Tournament(
            id="trn_shadow",
            name="Shadow Open",
            tour="atp",
            circuit=CircuitTier.ATP,
            gender=Gender.MEN,
            discipline=Discipline.SINGLES,
        ),
        scheduled_at=datetime.now(UTC),
        surface="hard",
        format="3",
        live_state=None,
        freshness=DataFreshness(provider="shadow", observed_at=datetime.now(UTC)),
    )
    snapshot = MatchSnapshot(
        match=match,
        points=(),
        state_version=0,
        as_of=datetime.now(UTC),
    )
    prediction = service.predict(snapshot)
    assert prediction.availability is ModelAvailability.UNPROMOTED
    assert prediction.outcomes == ()

    policy = PolicyArtifact.load("tests/fixtures/decision/policy-v1.json")
    engine = DecisionEngine(policy=policy, stake=Decimal("10"))
    observation = engine.evaluate(
        DecisionInput(
            match_id=match.id,
            market_id="mkt_shadow",
            mapped=True,
            observation_version=1,
            as_of=datetime.now(UTC),
            prediction=prediction,
            book=make_book("mkt_shadow"),
            metadata=None,
            rules_current_hash="rules_shadow",
        )
    )
    assert observation.action in (DecisionAction.NO_BET, DecisionAction.MARKET_ONLY)
    assert observation.action not in (DecisionAction.BUY, DecisionAction.SELL)


def _shadow_match():
    from app.domain import (
        CircuitTier,
        DataFreshness,
        Discipline,
        Gender,
        Match,
        MatchStatus,
        Player,
        Tournament,
    )

    return Match(
        id="mat_shadow_live",
        status=MatchStatus.SCHEDULED,
        players=(
            Player(id="ply_a", name="Alpha One"),
            Player(id="ply_b", name="Beta Two"),
        ),
        tournament=Tournament(
            id="trn_shadow",
            name="Shadow Open",
            tour="atp",
            circuit=CircuitTier.ATP,
            gender=Gender.MEN,
            discipline=Discipline.SINGLES,
        ),
        scheduled_at=datetime.now(UTC),
        surface="hard",
        format="3",
        live_state=None,
        freshness=DataFreshness(provider="shadow", observed_at=datetime.now(UTC)),
    )


async def test_shadow_observes_mapped_markets_read_only(database: Database) -> None:
    from app.main import create_app

    settings = _require_enabled()
    app = create_app(settings)
    provider = app.state.market_provider
    assert provider is not None, "shadow mode must assemble the market provider"
    markets = await provider.list_tennis_moneylines()
    if not markets:
        await provider.aclose()
        pytest.skip(
            f"no mapped tennis moneylines on {TODAY}; discovery returned 0 mapped "
            "markets from the public gamma surface (honest quiet-market skip)"
        )

    observed = 0
    shadow_book = None
    shadow_metadata = None
    shadow_rules_hash = None
    for market in markets[:2]:
        book = await provider.get_order_book(market.id)
        metadata = await provider.get_execution_metadata(market.id)
        assert len(book.books) == 2
        assert metadata.tick_size > 0 and metadata.min_order_size >= 0
        assert metadata.sports_delay_seconds >= 0
        rules_hash = None
        with contextlib.suppress(AppError):
            # Rules text missing on a live listing is honest: the rules gate
            # must fail closed, never invent a hash.
            rules_hash = (await provider.get_rules(market.id)).rules_hash
        if shadow_book is None:
            shadow_book, shadow_metadata, shadow_rules_hash = book, metadata, rules_hash
        observed += 1
    assert observed >= 1

    # One shadow decision cycle: unpromoted model + live book must abstain.
    from app.domain import MatchSnapshot

    service = PredictionService(artifact_dir="artifacts/p3")
    prediction = service.predict(
        MatchSnapshot(
            match=_shadow_match(),
            points=(),
            state_version=0,
            as_of=datetime.now(UTC),
        )
    )
    engine = DecisionEngine(
        policy=PolicyArtifact.load("tests/fixtures/decision/policy-v1.json"),
        stake=Decimal("10"),
    )
    observation = engine.evaluate(
        DecisionInput(
            match_id="mat_shadow_live",
            market_id=markets[0].id,
            mapped=True,
            observation_version=1,
            as_of=datetime.now(UTC),
            prediction=prediction,
            book=shadow_book,
            metadata=shadow_metadata,
            rules_current_hash=shadow_rules_hash,
        )
    )
    assert observation.action in (DecisionAction.NO_BET, DecisionAction.MARKET_ONLY)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for path in ("/api/v1/markets/opportunities", "/api/v1/markets/pulse"):
            response = await client.get(path)
            assert response.status_code == 200
            blob = json.dumps(response.json())
            for fragment in ("wallet", "private_key", "9900"):
                assert fragment not in blob.lower()
    await provider.aclose()


async def test_public_surface_hides_provider_material(database: Database) -> None:
    from app.main import create_app

    settings = _require_enabled()
    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/markets")
        assert response.status_code == 200
        blob = json.dumps(response.json()).lower()
    assert "wallet" not in blob
    assert "private" not in blob
    await app.state.market_provider.aclose()
