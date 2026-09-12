import asyncio
import json
import time
from typing import Any

from app.chat.capabilities import ToolRequiredness, capability_for
from app.chat.models import (
    ChatContext,
    ChatScope,
    StructuredToolResult,
    ToolCall,
    ToolOutcome,
    ToolOutcomeStatus,
)
from app.chat.tools import BusinessTools
from app.errors import AppError


class ToolBatchExecutor:
    def __init__(
        self,
        tools: BusinessTools,
        context: ChatContext,
        *,
        max_calls: int = 8,
        max_batch_size: int = 4,
    ) -> None:
        self._tools = tools
        self._context = context
        self._max_calls = max_calls
        self._max_batch_size = max_batch_size
        self._unique_calls = 0
        self._cache: dict[str, ToolOutcome] = {}

    async def execute(
        self,
        calls: list[ToolCall],
        *,
        allowed_names: set[str],
        known_match_ids: set[str],
    ) -> list[ToolOutcome]:
        outcomes: list[ToolOutcome | None] = [None] * len(calls)
        runnable: list[tuple[int, ToolCall, Any, str]] = []
        pending_by_signature: dict[str, int] = {}
        duplicate_refs: list[tuple[int, int]] = []

        for index, call in enumerate(calls):
            capability = capability_for(call.name)
            if capability is None:
                outcomes[index] = self._rejected(call, "unknown_tool", "unknown_tool")
                continue
            if self._context.scope not in capability.allowed_scopes:
                outcomes[index] = self._rejected(
                    call, "tool_not_allowed", "scope_not_allowed", capability.requiredness
                )
                continue
            if (
                call.name not in allowed_names
                and not (
                    self._context.scope is ChatScope.MATCH
                    and call.name == "get_match"
                )
            ):
                outcomes[index] = self._rejected(
                    call, "tool_not_allowed", "catalog_scope_mismatch", capability.requiredness
                )
                continue
            if not self._dependencies_satisfied(call, capability.requires, known_match_ids):
                outcomes[index] = self._rejected(
                    call,
                    "missing_dependency",
                    "resolved_match_id_required",
                    capability.requiredness,
                )
                continue

            signature = self._signature(call)
            cached = self._cache.get(signature)
            if cached is not None:
                outcomes[index] = cached.model_copy(
                    update={"call_id": call.id, "duplicate_of": cached.call_id}
                )
                continue
            pending_index = pending_by_signature.get(signature)
            if pending_index is not None:
                duplicate_refs.append((index, pending_index))
                continue
            if self._unique_calls >= self._max_calls:
                outcomes[index] = self._rejected(
                    call,
                    "tool_budget_exhausted",
                    "tool_budget_exhausted",
                    capability.requiredness,
                )
                continue
            self._unique_calls += 1
            pending_by_signature[signature] = index
            runnable.append((index, call, capability, signature))

        for start in range(0, len(runnable), self._max_batch_size):
            batch = runnable[start : start + self._max_batch_size]
            parallel_batch = [item for item in batch if item[2].parallel_safe]
            serial_batch = [item for item in batch if not item[2].parallel_safe]
            if parallel_batch:
                results = await asyncio.gather(
                    *(self._run(call, capability) for _, call, capability, _ in parallel_batch)
                )
                for (index, _, _, signature), outcome in zip(
                    parallel_batch, results, strict=True
                ):
                    outcomes[index] = outcome
                    self._cache[signature] = outcome
            for index, call, capability, signature in serial_batch:
                outcome = await self._run(call, capability)
                outcomes[index] = outcome
                self._cache[signature] = outcome

        for duplicate_index, primary_index in duplicate_refs:
            primary = outcomes[primary_index]
            if primary is None:
                continue
            outcomes[duplicate_index] = primary.model_copy(
                update={
                    "call_id": calls[duplicate_index].id,
                    "duplicate_of": primary.call_id,
                }
            )

        return [outcome for outcome in outcomes if outcome is not None]

    async def _run(self, call: ToolCall, capability: Any) -> ToolOutcome:
        started = time.monotonic()
        try:
            result = await asyncio.wait_for(
                self._tools.execute(call.name, call.arguments, self._context),
                timeout=capability.timeout_seconds,
            )
        except asyncio.TimeoutError:
            return self._outcome(
                call,
                ToolOutcomeStatus.FAILED,
                capability.requiredness,
                code="tool_timeout",
                reason="tool_timeout",
                retryable=True,
                started=started,
            )
        except AppError as error:
            status = (
                ToolOutcomeStatus.REJECTED
                if error.code == "invalid_request"
                else ToolOutcomeStatus.UNAVAILABLE
                if error.code in {"not_found", "unsupported"}
                else ToolOutcomeStatus.FAILED
            )
            return self._outcome(
                call,
                status,
                capability.requiredness,
                code=error.code,
                reason=error.code,
                retryable=error.code in {"provider_unavailable", "rate_limited"},
                started=started,
            )
        except Exception:
            return self._outcome(
                call,
                ToolOutcomeStatus.FAILED,
                capability.requiredness,
                code="tool_failed",
                reason="tool_failed",
                retryable=False,
                started=started,
            )

        status = (
            ToolOutcomeStatus.UNAVAILABLE
            if result.kind == "unsupported"
            else ToolOutcomeStatus.SUCCESS
        )
        return self._outcome(
            call,
            status,
            capability.requiredness,
            result=result,
            started=started,
        )

    def _signature(self, call: ToolCall) -> str:
        snapshot = self._context.snapshot
        snapshot_key = (
            snapshot.state_version,
            snapshot.as_of.isoformat(),
        ) if snapshot is not None else None
        return json.dumps(
            (
                self._context.scope.value,
                self._context.match_id,
                snapshot_key,
                call.name,
                call.arguments,
            ),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @staticmethod
    def _dependencies_satisfied(
        call: ToolCall,
        dependencies: frozenset[str],
        known_match_ids: set[str],
    ) -> bool:
        if "resolved_match_id" not in dependencies:
            return True
        if call.name == "get_match" and call.arguments.get("match_id"):
            return True
        return bool(known_match_ids)

    @staticmethod
    def _rejected(
        call: ToolCall,
        code: str,
        reason: str,
        requiredness: ToolRequiredness = ToolRequiredness.CORE,
    ) -> ToolOutcome:
        return ToolOutcome(
            tool_name=call.name,
            call_id=call.id,
            status=ToolOutcomeStatus.REJECTED,
            requiredness=requiredness,
            code=code,
            reason=reason,
            duration_ms=0,
        )

    @staticmethod
    def _outcome(
        call: ToolCall,
        status: ToolOutcomeStatus,
        requiredness: ToolRequiredness,
        *,
        result: StructuredToolResult | None = None,
        code: str | None = None,
        reason: str | None = None,
        retryable: bool = False,
        started: float,
    ) -> ToolOutcome:
        return ToolOutcome(
            tool_name=call.name,
            call_id=call.id,
            status=status,
            requiredness=requiredness,
            result=result,
            code=code,
            reason=reason,
            retryable=retryable,
            duration_ms=max(0, int((time.monotonic() - started) * 1000)),
        )
