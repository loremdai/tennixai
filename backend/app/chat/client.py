"""Chat model clients: deterministic fake and OpenAI-compatible (Qwen).

The fake model is the default for tests and fake-mode runtime. The
OpenAI-compatible client talks to any Chat Completions endpoint with native
function calling; failures translate to typed `llm_unavailable` errors so the
orchestrator can keep structured data visible.
"""

import asyncio
import json
import re
from collections.abc import AsyncIterator
from typing import Any, Protocol

from app.chat.models import ModelTurn, ToolCall
from app.errors import AppError


class ChatModel(Protocol):
    async def choose(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ModelTurn: ...

    def stream_text(self, messages: list[dict[str, Any]]) -> AsyncIterator[str]: ...


MATCH_CONTEXT_MARKER = "current match id:"


class FakeChatModel:
    """Deterministic scripted model with a small runtime default heuristic."""

    def __init__(
        self,
        *,
        turns: list[ModelTurn] | None = None,
        text_chunks: list[str] | None = None,
        choose_error: Exception | None = None,
        stream_error: Exception | None = None,
    ) -> None:
        self._turns = list(turns) if turns is not None else None
        self._text_chunks = text_chunks
        self._choose_error = choose_error
        self._stream_error = stream_error
        self.choose_calls: list[list[dict[str, Any]]] = []
        self.stream_calls: list[list[dict[str, Any]]] = []

    async def choose(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ModelTurn:
        self.choose_calls.append(messages)
        if self._choose_error is not None:
            raise self._choose_error
        if self._turns is not None:
            if self._turns:
                return self._turns.pop(0)
            return ModelTurn()
        return self._default_turn(messages)

    async def stream_text(self, messages: list[dict[str, Any]]) -> AsyncIterator[str]:
        self.stream_calls.append(messages)
        if self._stream_error is not None:
            raise self._stream_error
        chunks = self._text_chunks
        if chunks is None:
            chunks = [self._default_text(messages)]
        for chunk in chunks:
            yield chunk

    @staticmethod
    def _last_user_message(messages: list[dict[str, Any]]) -> str:
        for message in reversed(messages):
            if message.get("role") == "user":
                return str(message.get("content") or "")
        return ""

    def _default_turn(self, messages: list[dict[str, Any]]) -> ModelTurn:
        if messages and messages[-1].get("role") == "tool":
            return ModelTurn()

        system = str(messages[0].get("content") or "") if messages else ""
        if MATCH_CONTEXT_MARKER in system:
            return ModelTurn(
                tool_calls=[ToolCall(id="call_fake_match", name="get_match", arguments={})]
            )

        last_user = self._last_user_message(messages)
        lowered = last_user.casefold()
        player_tokens = re.findall(r"[A-Za-z]{2,}", last_user)
        if player_tokens:
            if "今天" in last_user or "today" in lowered:
                time_scope = "today"
            elif "下一" in last_user or "next" in lowered:
                time_scope = "next"
            else:
                time_scope = "tonight"
            return ModelTurn(
                tool_calls=[
                    ToolCall(
                        id="call_fake_player",
                        name="find_player_matches",
                        arguments={"player_name": player_tokens[0], "time_scope": time_scope},
                    )
                ]
            )
        return ModelTurn(
            tool_calls=[ToolCall(id="call_fake_live", name="get_live_matches", arguments={})]
        )

    @staticmethod
    def _default_text(messages: list[dict[str, Any]]) -> str:
        for message in reversed(messages):
            if message.get("role") == "tool":
                try:
                    result = json.loads(str(message.get("content") or "{}"))
                except json.JSONDecodeError:
                    result = {}
                kind = result.get("kind")
                matches = result.get("matches") or []
                if kind == "match" and matches:
                    return "已获取本场比赛的结构化数据。"
                if kind == "unsupported":
                    return "P1 暂不支持历史比赛结果查询。"
                if matches:
                    return f"已为你找到 {len(matches)} 场比赛的结构化数据。"
                return "当前没有查到符合条件的比赛。"
        return "我可以帮你查询今天、今晚或下一场比赛。"


class OpenAICompatibleChatModel:
    """Qwen via an OpenAI-compatible Chat Completions endpoint."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 45.0,
    ) -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(
            api_key=api_key, base_url=base_url, timeout=timeout_seconds
        )
        self._model = model
        self._timeout_seconds = timeout_seconds

    async def choose(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ModelTurn:
        from openai import OpenAIError

        try:
            async with asyncio.timeout(self._timeout_seconds):
                response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                )
        except (OpenAIError, TimeoutError) as error:
            raise AppError("llm_unavailable", "LLM request failed", 503) from error

        message = response.choices[0].message
        calls: list[ToolCall] = []
        for tool_call in message.tool_calls or []:
            try:
                arguments = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError as error:
                raise AppError(
                    "llm_unavailable", "LLM returned invalid tool arguments", 503
                ) from error
            calls.append(
                ToolCall(
                    id=tool_call.id,
                    name=tool_call.function.name,
                    arguments=arguments,
                )
            )
        return ModelTurn(tool_calls=calls)

    async def stream_text(self, messages: list[dict[str, Any]]) -> AsyncIterator[str]:
        from openai import OpenAIError

        try:
            async with asyncio.timeout(self._timeout_seconds):
                stream = await self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    stream=True,
                    tool_choice="none",
                )
                async for chunk in stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    if delta is not None and delta.content:
                        yield delta.content
        except (OpenAIError, TimeoutError) as error:
            raise AppError("llm_unavailable", "LLM streaming failed", 503) from error
