"""Opt-in end-to-end gate: real Qwen plus real LiveTennisAPI.

Run with: uv run pytest -m end_to_end_live
Requires TENNIX_LLM_API_KEY, TENNIX_LLM_BASE_URL and TENNIX_LIVETENNIS_API_KEY.
"""

import os
from datetime import datetime, timezone

import httpx
import pytest

from app.cache import AsyncTTLCache
from app.chat.client import OpenAICompatibleChatModel
from app.chat.models import ChatEventType, ChatMessage, ChatRequest
from app.chat.orchestrator import ChatOrchestrator
from app.chat.tools import BusinessTools
from app.identity import MemoryIdentityRepository
from app.providers.livetennis import LiveTennisProvider
from app.service import TennisService

pytestmark = pytest.mark.end_to_end_live


def _require_all_credentials() -> tuple[str, str, str]:
    llm_key = os.environ.get("TENNIX_LLM_API_KEY", "")
    llm_url = os.environ.get("TENNIX_LLM_BASE_URL", "")
    provider_key = os.environ.get("TENNIX_LIVETENNIS_API_KEY", "")
    if not llm_key.strip() or not llm_url.strip() or not provider_key.strip():
        pytest.skip(
            "end_to_end_live requires TENNIX_LLM_API_KEY, TENNIX_LLM_BASE_URL and "
            "TENNIX_LIVETENNIS_API_KEY"
        )
    return llm_key, llm_url, provider_key


@pytest.mark.asyncio
async def test_end_to_end_live_question_returns_structured_or_honest_empty() -> None:
    llm_key, llm_url, provider_key = _require_all_credentials()

    client = httpx.AsyncClient(
        base_url=os.environ.get(
            "TENNIX_LIVETENNIS_BASE_URL", "https://api.livetennisapi.com/api/public/v1"
        ),
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
            base_url=llm_url,
            model=os.environ.get("TENNIX_LLM_MODEL", "qwen3.8-max-0902"),
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
