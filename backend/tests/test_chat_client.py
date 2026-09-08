import asyncio
from types import SimpleNamespace

import openai
import pytest
from pydantic import SecretStr

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


@pytest.mark.asyncio
async def test_choose_timeout_is_typed(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeCompletions:
        async def create(self, **kwargs):
            captured["request"] = kwargs
            await asyncio.sleep(1)

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
        await model.choose([], [])

    assert error_info.value.code == "llm_unavailable"
    assert captured["timeout"] == 0.01


def test_llm_timeout_is_configurable() -> None:
    settings = Settings(_env_file=None, llm_timeout_seconds=12.5)

    assert settings.llm_timeout_seconds == 12.5


def test_create_app_wires_llm_timeout(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeModel:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    import app.main as main

    monkeypatch.setattr(main, "OpenAICompatibleChatModel", FakeModel)
    main.create_app(
        Settings(
            _env_file=None,
            llm_mode="openai_compatible",
            llm_api_key=SecretStr("test-key"),
            llm_base_url="https://example.test/v1",
            llm_timeout_seconds=12.5,
        )
    )

    assert captured["timeout_seconds"] == 12.5
