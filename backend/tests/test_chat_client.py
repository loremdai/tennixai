import asyncio
from types import SimpleNamespace

import openai
import pytest

from app.chat.client import OpenAICompatibleChatModel
from app.config import Settings
from app.errors import AppError


class NeverEndingStream:
    def __aiter__(self):
        return self

    async def __anext__(self):
        await asyncio.sleep(1)
        raise StopAsyncIteration


@pytest.mark.asyncio
async def test_stream_timeout_is_typed_and_passed_to_sdk(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeCompletions:
        async def create(self, **kwargs):
            captured["request"] = kwargs
            return NeverEndingStream()

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(openai, "AsyncOpenAI", FakeAsyncOpenAI)
    model = OpenAICompatibleChatModel(
        api_key="test-key",
        base_url="https://example.test/v1",
        model="test-model",
        timeout_seconds=0.01,
    )

    with pytest.raises(AppError) as error_info:
        async for _ in model.stream_text([]):
            pass

    assert error_info.value.code == "llm_unavailable"
    assert captured["timeout"] == 0.01


def test_llm_timeout_is_configurable() -> None:
    settings = Settings(_env_file=None, llm_timeout_seconds=12.5)

    assert settings.llm_timeout_seconds == 12.5
