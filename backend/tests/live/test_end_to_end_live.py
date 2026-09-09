"""Opt-in end-to-end gate: real Qwen plus real LiveTennisAPI.

Run with: uv run pytest -m end_to_end_live
Reads LLM and LiveTennisAPI credentials from the repository-root .env.
"""

from datetime import datetime, timezone

import httpx
import pytest

from app.cache import AsyncTTLCache
from app.chat.client import OpenAICompatibleChatModel
from app.chat.models import ChatEventType, ChatMessage, ChatRequest
from app.chat.orchestrator import ChatOrchestrator
from app.chat.tools import BusinessTools
from app.config import Settings
from app.identity import MemoryIdentityRepository
from app.providers.livetennis import LiveTennisProvider
from app.service import TennisService

pytestmark = pytest.mark.end_to_end_live


def _require_all_credentials() -> tuple[Settings, str, str]:
    settings = Settings(provider_mode="fake", llm_mode="fake")
    llm_key = settings.llm_api_key
    provider_key = settings.livetennis_api_key
    if (
        llm_key is None
        or not llm_key.get_secret_value().strip()
        or not settings.llm_base_url
        or provider_key is None
        or not provider_key.get_secret_value().strip()
    ):
        pytest.skip(
            "end_to_end_live requires TENNIX_LLM_API_KEY, TENNIX_LLM_BASE_URL and "
            "TENNIX_LIVETENNIS_API_KEY"
        )
    return settings, llm_key.get_secret_value(), provider_key.get_secret_value()


@pytest.mark.asyncio
async def test_end_to_end_live_question_returns_structured_or_honest_empty() -> None:
    settings, llm_key, provider_key = _require_all_credentials()

    client = httpx.AsyncClient(
        base_url=settings.livetennis_base_url,
        timeout=10.0,
    )
    try:
        provider = LiveTennisProvider(
            client=client,
            identities=MemoryIdentityRepository(),
            api_key=provider_key,
            now=lambda: datetime.now(timezone.utc),
        )
        cache: AsyncTTLCache[str, object] = AsyncTTLCache(max_entries=256)
        service = TennisService(
            provider, cache, now=lambda: datetime.now(timezone.utc), timezone="Asia/Macau"
        )
        tools = BusinessTools(service)
        model = OpenAICompatibleChatModel(
            api_key=llm_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
        )
        orchestrator = ChatOrchestrator(tools, model)

        request = ChatRequest(
            scope="global",
            messages=[ChatMessage(role="user", content="现在有什么比赛？")],
        )
        events = [event async for event in orchestrator.stream(request)]

        assert events[-1].type in (ChatEventType.DONE, ChatEventType.ERROR)
        data = [event.payload for event in events if event.type is ChatEventType.DATA]
        if data:
            assert isinstance(data[0]["matches"], list)
            dumped = str(data[0])
            assert "event_key" not in dumped
            assert "event_first_player" not in dumped
        text = "".join(
            event.payload["delta"] for event in events if event.type is ChatEventType.TEXT_DELTA
        )
        assert text.strip(), "model prose must be non-empty on the live end-to-end path"
    finally:
        await client.aclose()
