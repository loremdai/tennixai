# Scope-Aware Multi-Tool Chat Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 修复全局聊天在结构化数据成功后误调用比赛专属工具导致的 invalid_request，并让无依赖工具并行、有依赖工具分阶段串行、部分失败可降级且过程在 SSE/UI 中可见。

**Architecture:** 在现有 ChatOrchestrator 前增加轻量 capability registry，按 scope + phase + intent + 已解析上下文裁剪工具目录；独立 tool calls 交给有界的 ToolBatchExecutor 并行执行，依赖调用进入下一轮，非法调用只生成 tool-level rejected outcome 并最多重规划一次。最终 synthesis 使用 tool_choice=none 且不再传 tools，结构化事实和 warning 与 terminal error 分离。

**Tech Stack:** Python 3.12、FastAPI、Pydantic v2、asyncio、OpenAI Python SDK；Next.js 16、React 19、TypeScript、Vitest、Testing Library、Playwright；阿里云 Model Studio OpenAI-compatible Chat Completions。

**Spec:** docs/superpowers/specs/2026-09-12-tennixai-scope-aware-multi-tool-chat-design.md

## Global Constraints

- 只使用仓库根目录 .env；任何 API key、Authorization、供应商原始 payload、供应商 URL 和完整用户 prompt 不得进入代码、测试 fixture、日志、SSE 或提交。
- 依据 Alibaba Model Studio Function Calling 官方文档和 OpenAI-compatible Chat Completions 官方文档使用 parallel_tool_calls=true 表示无依赖并行，使用 false 表示依赖链由服务端分轮处理。
- 不增加第二个路由大模型、数据库迁移、供应商镜像或 P3 的 odds/prediction/market/trading 能力。
- 保留现有 status、data、text_delta、done、error SSE 事件；新增 warning 必须让旧客户端安全忽略。
- 固定边界：最多 3 个工具规划轮次、每请求最多 8 个唯一 tool calls、每并行批次最多 4 个 calls、单工具默认 8 秒、非法调用最多自动重规划 1 次、总请求沿用现有 45 秒上限。
- Match scope 在请求开始冻结 match_id/state_version/as_of；所有回答事实不得被后续实时更新覆盖。
- 遵循 TDD：每个生产行为变更先写一个会失败的行为测试，运行并确认失败原因正确，再写最小实现、回归测试和小提交。
- 保留工作区已有未跟踪文件：.codex/、REALTIME_LATENCY_INVESTIGATION.md、frontend/AGENTS.md、frontend/CLAUDE.md、frontend/next-env.d.ts。

## File Map

- Create backend/app/chat/capabilities.py：phase、requiredness 和六个现有工具的 capability registry，以及按 scope/phase/intent 计算有序工具名。
- Create backend/app/chat/executor.py：scope/schema/dependency 校验、幂等去重、受限并行、超时和统一 ToolOutcome。
- Modify backend/app/chat/models.py：warning event、status progress payload 的类型支持，以及 executor 使用的 outcome 类型。
- Modify backend/app/chat/tools.py：支持按工具名和 scope 生成 catalog，并让 global get_match schema 要求显式 match_id。
- Modify backend/app/chat/client.py：parallel_tool_calls 适配、Fake model 记录调用参数、最终流式请求不传 tools。
- Modify backend/app/chat/orchestrator.py：phase state machine、batch executor、replan、降级和 SSE 事件顺序。
- Modify backend/tests/test_chat_tools.py、backend/tests/test_chat_client.py、backend/tests/test_chat_orchestrator.py、backend/tests/test_chat_api.py：后端行为、SDK payload、SSE contract 和真实回归覆盖。
- Modify frontend/lib/api/types.ts：status progress、warning 和 ChatEvent union。
- Modify frontend/hooks/use-chat-stream.ts：warnings/progress state，重试/取消/新问题的清理语义。
- Create frontend/components/chat-warnings.tsx：Home 与 Match 共用的可访问 warning 展示。
- Modify frontend/components/home/home-assistant.tsx、frontend/components/match/match-sidebar.tsx：warning 和可选批次进度展示，不把 warning 当 terminal error。
- Modify frontend/hooks/use-chat-stream.test.tsx、frontend/components/home-page.test.tsx、frontend/components/match-page.test.tsx：hook、Home、Match 真实渲染回归。
- Modify CURRENT.md、ROADMAP.md：记录计划节点、验证证据和最终提交；不记录凭据。

---

### Task 1: 建立 capability registry 和 scope-aware catalog

**Files:**
- Create: backend/app/chat/capabilities.py
- Modify: backend/app/chat/models.py
- Modify: backend/app/chat/tools.py
- Test: backend/tests/test_chat_tools.py
- Test: backend/tests/test_chat_orchestrator.py

**Interfaces:**
- ChatPhase(StrEnum) 提供 DISCOVERY = "discovery"、CONTEXT = "context"、ENRICHMENT = "enrichment"。
- ToolRequiredness(StrEnum) 提供 CORE = "core"、OPTIONAL = "optional"。
- ToolCapability 是 frozen dataclass，字段为 name: str、allowed_scopes: frozenset[ChatScope]、phases: frozenset[ChatPhase]、requires: frozenset[str]、parallel_safe: bool、requiredness: ToolRequiredness、timeout_seconds: float = 8.0。
- capability_for(name: str) -> ToolCapability | None 返回注册元数据。
- allowed_tool_names(scope: ChatScope, phase: ChatPhase, *, history_requested: bool, has_discovered_matches: bool) -> tuple[str, ...] 按现有 TOOL_NAMES 顺序返回目录名。
- BusinessTools.catalog(*, names: Iterable[str] | None = None, scope: ChatScope | None = None) -> list[dict[str, Any]] 保留无参数调用返回完整兼容 catalog；传 scope=global 时，get_match 参数 schema 的 match_id 必须是 required。

- [ ] **Step 1: Write the failing tests**

在 backend/tests/test_chat_tools.py 增加以下行为断言；在 backend/tests/test_chat_orchestrator.py 增加全局目录回归：

~~~python
def test_global_scoped_catalog_hides_match_only_tool(tools: BusinessTools) -> None:
    names = allowed_tool_names(
        ChatScope.GLOBAL,
        ChatPhase.DISCOVERY,
        history_requested=False,
        has_discovered_matches=False,
    )
    catalog = tools.catalog(names=names, scope=ChatScope.GLOBAL)

    assert "get_match_intelligence" not in names
    assert "get_match_intelligence" not in {
        item["function"]["name"] for item in catalog
    }


def test_global_get_match_schema_requires_explicit_id(tools: BusinessTools) -> None:
    names = allowed_tool_names(
        ChatScope.GLOBAL,
        ChatPhase.ENRICHMENT,
        history_requested=False,
        has_discovered_matches=True,
    )
    item = next(
        item for item in tools.catalog(names=names, scope=ChatScope.GLOBAL)
        if item["function"]["name"] == "get_match"
    )

    assert item["function"]["parameters"]["required"] == ["match_id"]


def test_match_current_catalog_keeps_history_tools_out(tools: BusinessTools) -> None:
    names = allowed_tool_names(
        ChatScope.MATCH,
        ChatPhase.CONTEXT,
        history_requested=False,
        has_discovered_matches=False,
    )

    assert names == ("get_match_intelligence",)
~~~

在 orchestrator 测试中使用 CatalogRecordingModel 验证真实 stream 的 global 首轮目录不含 get_match_intelligence。

- [ ] **Step 2: Run tests to verify they fail**

Run:

~~~bash
cd backend && uv run pytest tests/test_chat_tools.py::test_global_scoped_catalog_hides_match_only_tool tests/test_chat_tools.py::test_global_get_match_schema_requires_explicit_id tests/test_chat_tools.py::test_match_current_catalog_keeps_history_tools_out -q
~~~

Expected: FAIL because没有 capability registry，BusinessTools.catalog 也没有按 scope 生成目录。

- [ ] **Step 3: Write the minimal implementation**

在 capabilities.py 注册六个工具：global discovery 为 find_player_matches、get_live_matches；global enrichment 才允许 get_match；明确历史意图时才加入 get_player_results、get_head_to_head；match context 只向模型提供 get_match_intelligence；get_match_intelligence 的 allowed_scopes 仅为 match。

在 tools.py 新增 GlobalGetMatchArgs(match_id: str = Field(min_length=1))，让 catalog() 根据 scope 选择 schema；保留旧的 catalog() 完整 surface 测试和 execute() 的 match context 注入行为。

- [ ] **Step 4: Run tests to verify they pass**

Run:

~~~bash
cd backend && uv run pytest tests/test_chat_tools.py tests/test_chat_orchestrator.py -q
~~~

Expected: 新增 scope/schema 断言和既有 deterministic chat tests 全部 PASS；此时还不宣称真实 Qwen 回归已修复。

- [ ] **Step 5: Commit**

~~~bash
git add backend/app/chat/capabilities.py backend/app/chat/models.py backend/app/chat/tools.py backend/tests/test_chat_tools.py backend/tests/test_chat_orchestrator.py
git commit -m "feat: add scope-aware chat tool catalog"
~~~

### Task 2: 让模型适配器显式表达并行策略并收紧 final synthesis

**Files:**
- Modify: backend/app/chat/client.py
- Modify: backend/app/chat/orchestrator.py
- Test: backend/tests/test_chat_client.py
- Test: backend/tests/test_chat_orchestrator.py

**Interfaces:**
- ChatModel.choose(messages, tools, *, parallel_tool_calls: bool = False) -> ModelTurn。
- FakeChatModel.choose 保持相同签名，并在 choose_parallel_calls: list[bool] 记录每次规划参数。
- ChatModel.stream_text(messages, *, tools: list[dict[str, Any]] | None = None) 保留兼容参数；编排器 final 调用时不传 tools，OpenAI request 中也不生成 tools key。

- [ ] **Step 1: Write the failing tests**

在 test_chat_client.py 扩展现有 request capture：

~~~python
@pytest.mark.asyncio
async def test_choose_sends_explicit_parallel_tool_call_policy(monkeypatch) -> None:
    request: dict[str, object] = {}

    class FakeCompletions:
        async def create(self, **kwargs):
            request.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=[]))]
            )

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(openai, "AsyncOpenAI", FakeAsyncOpenAI)
    model = OpenAICompatibleChatModel(
        api_key="test-key",
        base_url="https://example.test/v1",
        model="test-model",
    )

    await model.choose([], [], parallel_tool_calls=True)

    assert request["parallel_tool_calls"] is True
~~~

把现有 final streaming test 改为调用 model.stream_text([])，并断言 "tools" not in final_request。在 orchestrator 测试中断言 FakeChatModel.choose_parallel_calls 的首个独立规划轮为 True、依赖阶段为 False。

- [ ] **Step 2: Run tests to verify they fail**

Run:

~~~bash
cd backend && uv run pytest tests/test_chat_client.py::test_choose_sends_explicit_parallel_tool_call_policy tests/test_chat_client.py::test_qwen_chat_requests_disable_thinking_for_responsive_factual_answers -q
~~~

Expected: FAIL because现有 SDK request 没有 parallel_tool_calls，final request 仍可能带 tools。

- [ ] **Step 3: Write the minimal implementation**

在 OpenAI-compatible create() 中加入 parallel_tool_calls=parallel_tool_calls；Fake model 接收并记录同名参数，测试用的 CatalogRecordingModel 同步扩展 keyword-only 参数后再传给父类。编排器 final synthesis 调用 stream_text(messages)，不把上一阶段 catalog 传入。

- [ ] **Step 4: Run tests to verify they pass**

Run:

~~~bash
cd backend && uv run pytest tests/test_chat_client.py tests/test_chat_orchestrator.py -q
~~~

Expected: client payload、Fake model、已有 planning/final stream tests 全部 PASS。

- [ ] **Step 5: Commit**

~~~bash
git add backend/app/chat/client.py backend/app/chat/orchestrator.py backend/tests/test_chat_client.py backend/tests/test_chat_orchestrator.py
git commit -m "feat: expose chat parallel call policy"
~~~

### Task 3: 实现有界 ToolBatchExecutor

**Files:**
- Create: backend/app/chat/executor.py
- Modify: backend/app/chat/models.py
- Test: backend/tests/test_chat_orchestrator.py

**Interfaces:**
- ToolOutcomeStatus(StrEnum) 提供 SUCCESS、PARTIAL、UNAVAILABLE、FAILED、REJECTED。
- ToolOutcome 是内部 Pydantic model，字段为 tool_name: str、call_id: str、status: ToolOutcomeStatus、requiredness: ToolRequiredness、result: StructuredToolResult | None、code: str | None、reason: str | None、retryable: bool、duration_ms: int、duplicate_of: str | None。
- ToolBatchExecutor.execute(calls: list[ToolCall], *, allowed_names: set[str], known_match_ids: set[str]) -> list[ToolOutcome] 保持输入顺序返回 outcome。
- Executor 构造接收 BusinessTools 和 ChatContext；每个 call 用 asyncio.wait_for(..., timeout=capability.timeout_seconds) 执行。

- [ ] **Step 1: Write the failing tests**

在 orchestrator test 文件中新增一个只统计并发的工具替身，委托 catalog、freeze_match_context 给真实 BusinessTools，并为 execute 增加 in_flight/max_in_flight 计数。加入以下行为测试：

~~~python
@pytest.mark.asyncio
async def test_independent_tool_calls_execute_in_parallel() -> None:
    model = FakeChatModel(
        turns=[
            ModelTurn(
                tool_calls=[
                    ToolCall(id="call_a", name="find_player_matches", arguments={"player_name": "Sinner", "time_scope": "tonight"}),
                    ToolCall(id="call_b", name="get_live_matches", arguments={}),
                ]
            ),
            ModelTurn(),
        ],
        text_chunks=["已完成。"],
    )
    tools = ConcurrentBusinessTools()
    events = [
        event async for event in ChatOrchestrator(tools, model).stream(
            global_request("今晚和现在的比赛？")
        )
    ]

    assert tools.max_in_flight == 2
    assert [event.type for event in events][-1] is ChatEventType.DONE
~~~

另加三项最小断言：无 match_id 的 global get_match 在同批被 rejected 而不执行；同一签名第二次调用只执行一次；同一请求最多执行 8 个唯一 call，超出后保留已有 data 或产生 typed terminal error。

- [ ] **Step 2: Run tests to verify they fail**

Run:

~~~bash
cd backend && uv run pytest tests/test_chat_orchestrator.py::test_independent_tool_calls_execute_in_parallel -q
~~~

Expected: FAIL because当前编排器逐个 await self._tools.execute()，没有 executor、outcome、去重或调用预算。

- [ ] **Step 3: Write the minimal implementation**

实现 ToolBatchExecutor：

1. 先用 capability_for() 校验工具存在、scope 在 ChatContext 中允许、名称属于当前 catalog；失败形成 REJECTED，不调用业务工具。
2. 用 json.dumps(arguments, sort_keys=True, separators=(",", ":")) 加 scope/match snapshot 标识生成签名；重复签名复用首次 outcome，并保留新的 call_id 映射。
3. 对 parallel_safe=True 且依赖已满足的调用用 asyncio.gather 并发执行；每批最多 4 个；依赖 resolved_match_id 未满足的调用形成 rejected，不在同一批猜测执行。
4. 把 ValidationError、AppError、超时分别转为稳定 code/reason；不把异常对象、URL 或 provider payload 放进 outcome。
5. 以 duration_ms 和输入顺序返回结果，不让单个 optional timeout 取消其他调用。

- [ ] **Step 4: Run tests to verify they pass**

Run:

~~~bash
cd backend && uv run pytest tests/test_chat_orchestrator.py::test_independent_tool_calls_execute_in_parallel tests/test_chat_orchestrator.py -q
~~~

Expected: 并行 barrier、依赖拒绝、去重和预算测试 PASS；既有 match snapshot 和 optional lookup 测试仍 PASS。

- [ ] **Step 5: Commit**

~~~bash
git add backend/app/chat/executor.py backend/app/chat/models.py backend/tests/test_chat_orchestrator.py
git commit -m "feat: execute chat tools in bounded batches"
~~~

### Task 4: 接入 phase state machine、replan 和 SSE 降级语义

**Files:**
- Modify: backend/app/chat/orchestrator.py
- Modify: backend/app/chat/models.py
- Test: backend/tests/test_chat_orchestrator.py
- Test: backend/tests/test_chat_api.py

**Interfaces:**
- ChatEventType.WARNING = "warning"。
- status payload 支持 stage 外的可选 phase、completed、total、tool。
- warning payload 使用 {code: str, message: str, details: dict[str, object]}，details 只放稳定的非敏感字段。
- Orchestrator 使用 MAX_TOOL_ROUNDS = 3、MAX_TOOL_CALLS = 8、MAX_REPLANS = 1，并按 global → discovery → enrichment、match → context → enrichment 计算下一轮 catalog。

- [ ] **Step 1: Write the failing tests**

新增真实回归测试，固定复现用户报告：

~~~python
@pytest.mark.asyncio
async def test_global_illegal_match_tool_replans_without_invalid_request() -> None:
    model = CatalogRecordingModel(
        turns=[
            tool_turn("find_player_matches", {"player_name": "Sinner", "time_scope": "tonight"}, "call_find"),
            tool_turn("get_match_intelligence", {"topic": "overview"}, "call_illegal"),
            ModelTurn(),
        ],
        text_chunks=["已找到 Sinner 的比赛。"],
    )
    orchestrator, _ = build_orchestrator(model)

    events = [event async for event in orchestrator.stream(global_request("Sinner 的比赛如何了"))]

    assert any(event.type is ChatEventType.DATA for event in events)
    assert any(event.type is ChatEventType.DONE for event in events)
    assert not any(
        event.type is ChatEventType.ERROR and event.payload.get("code") == "invalid_request"
        for event in events
    )
    rejected = next(message for message in model.choose_calls[-1] if message.get("tool_call_id") == "call_illegal")
    assert json.loads(rejected["content"])["kind"] == "rejected"
~~~

新增 optional 失败断言：已有 intelligence data 后 get_player_results 返回 not_found 时，事件包含 warning、不包含 terminal error、最终以 done 结束；核心 provider 在没有任何 data 时仍返回原 typed error。

- [ ] **Step 2: Run tests to verify they fail**

Run:

~~~bash
cd backend && uv run pytest tests/test_chat_orchestrator.py::test_global_illegal_match_tool_replans_without_invalid_request tests/test_chat_api.py -q
~~~

Expected: 当前 global catalog 包含 match-only 工具，第二轮 execute() 抛出 invalid_request，测试失败。

- [ ] **Step 3: Write the minimal implementation**

重写 orchestrator 的工具循环但保留现有快照冻结和 data-first 顺序：

1. 每轮先计算 phase catalog，向模型传当前 catalog 和 parallel_tool_calls=(phase in {DISCOVERY, CONTEXT})；每轮 status 带 phase 和当前 batch 进度。
2. 把一个 ModelTurn 交给 ToolBatchExecutor；先发 assistant tool_calls 消息，再为每个 outcome 追加对应的 role=tool 消息和 tool_call_id。
3. success/partial result 发 data；optional unavailable/failed 发 warning 并继续；rejected 只追加可供模型纠正的 kind=rejected tool 内容，累计一次 replan，不向用户发 invalid_request。
4. 非法调用超过一次重规划、工具预算、规划轮次时：已有核心数据则发 warning 后 synthesis；没有核心数据则发稳定 terminal error。
5. synthesis 发 generating，调用 stream_text(messages)，成功后 done；流式 LLM 失败时保留已发结构化 data 和 fallback 文本，只有没有可用核心事实时才把它作为 terminal error。
6. 保持 Match scope 的 answer_context 取自冻结 snapshot，禁止把 get_match_intelligence 的 global scope 错误泄露为用户 422。

- [ ] **Step 4: Run tests to verify they pass**

Run:

~~~bash
cd backend && uv run pytest tests/test_chat_orchestrator.py tests/test_chat_api.py -q
~~~

Expected: 用户报告的 global 回归、Match snapshot、optional history、provider/LLM terminal failure、SSE 顺序全部 PASS；API raw response 中 warning 不破坏既有 frame parser。

- [ ] **Step 5: Commit**

~~~bash
git add backend/app/chat/orchestrator.py backend/app/chat/models.py backend/tests/test_chat_orchestrator.py backend/tests/test_chat_api.py
git commit -m "fix: replan invalid chat tool calls"
~~~

### Task 5: 前端区分 progress、warning 和 terminal error

**Files:**
- Modify: frontend/lib/api/types.ts
- Modify: frontend/hooks/use-chat-stream.ts
- Create: frontend/components/chat-warnings.tsx
- Modify: frontend/components/home/home-assistant.tsx
- Modify: frontend/components/match/match-sidebar.tsx
- Test: frontend/hooks/use-chat-stream.test.tsx
- Test: frontend/components/home-page.test.tsx
- Test: frontend/components/match-page.test.tsx

**Interfaces:**
- ChatStatusPayload = { stage: string; phase?: string; completed?: number; total?: number; tool?: string }。
- ChatWarning = { code: string; message: string; details: Record<string, unknown> }。
- ChatEvent 新增 { type: 'warning'; payload: ChatWarning }，status 使用 ChatStatusPayload。
- ChatViewState 新增 warnings: ChatWarning[] 和 progress: { completed: number; total: number; tool: string | null } | null；IDLE_STATE、send、cancel、reset 都明确清理它们。
- chatProgressLabel(stage, progress) 返回已有阶段文案，并在 completed/total 有效时追加（completed/total）。

- [ ] **Step 1: Write the failing tests**

在 hook 测试中加入：

~~~typescript
it('keeps optional warnings separate from terminal errors', async () => {
  streamChatMock.mockImplementation(
    scriptedStream([
      { type: 'warning', payload: { code: 'optional_data_unavailable', message: '球员背景资料暂未提供。', details: {} } },
      { type: 'text_delta', payload: { delta: '当前比赛分析已完成。' } },
      { type: 'done', payload: { ok: true } },
    ]),
  )

  const { result } = renderHook(() => useChatStream('match', 'mat_42'))
  await act(async () => {
    await result.current.send('分析当前比赛和球员特点')
  })

  expect(result.current.state.phase).toBe('success')
  expect(result.current.state.error).toBeNull()
  expect(result.current.state.warnings).toEqual([
    { code: 'optional_data_unavailable', message: '球员背景资料暂未提供。', details: {} },
  ])
})
~~~

另加 status completed=2,total=3,tool=... 会写入 progress、再次 send/cancel/reset 会清空 warnings/progress 的断言。Home/Match component test 的 mock stream 各加入一个 warning，并断言提示可见且不出现“查询未完成”。

- [ ] **Step 2: Run tests to verify they fail**

Run:

~~~bash
cd frontend && pnpm test -- hooks/use-chat-stream.test.tsx components/home-page.test.tsx components/match-page.test.tsx
~~~

Expected: TypeScript union 不接受 warning，hook state 没有 warnings/progress，组件也不会渲染 warning。

- [ ] **Step 3: Write the minimal implementation**

在 useChatStream 的 warning 分支追加稳定 warning，在 status 分支保存阶段进度；新问题开始时清空旧 warning/progress，cancel 时清空但不伪造 error。新增 ChatWarnings 使用 role=status、列表语义和短文案；Home 与 Match 在回答卡片中渲染它。已有 chat.error 仍只代表 terminal failure，warning 不进入 error。

把两处阶段文案调用切换到 chatProgressLabel，保持原有中文文案和 reduced-motion/滚动行为不变。

- [ ] **Step 4: Run tests to verify they pass**

Run:

~~~bash
cd frontend && pnpm test -- hooks/use-chat-stream.test.tsx components/home-page.test.tsx components/match-page.test.tsx && pnpm typecheck
~~~

Expected: warning/progress/清理断言以及现有所有 Home/Match chat、markdown、snapshot 测试 PASS，typecheck PASS。

- [ ] **Step 5: Commit**

~~~bash
git add frontend/lib/api/types.ts frontend/hooks/use-chat-stream.ts frontend/components/chat-warnings.tsx frontend/components/home/home-assistant.tsx frontend/components/match/match-sidebar.tsx frontend/hooks/use-chat-stream.test.tsx frontend/components/home-page.test.tsx frontend/components/match-page.test.tsx
git commit -m "feat: show chat progress and partial warnings"
~~~

### Task 6: 完成端到端回归、官方参数检查和真实业务流程

**Files:**
- Modify: backend/tests/live/test_llm_live.py
- Modify: frontend/e2e/llm-live.spec.ts
- Modify: CURRENT.md
- Modify: ROADMAP.md

**Interfaces:**
- live LLM gate 增加 global query tiafoe 的比赛如何了 的重复回归，验证 data 后最终 done，不得出现 invalid_request。
- Playwright 保持真实鼠标/键盘流程，不直接调用后端 endpoint 代替浏览器业务路径。

- [ ] **Step 1: Write the failing live/e2e assertions**

在真实门中使用现有 .env 配置但不打印凭据：

~~~python
@pytest.mark.asyncio
async def test_qwen_global_live_question_never_fails_after_structured_data() -> None:
    orchestrator, _, _ = _build()
    events = [
        event async for event in orchestrator.stream(
            ChatRequest(
                scope="global",
                messages=[ChatMessage(role="user", content="tiafoe 的比赛如何了")],
            )
        )
    ]

    assert any(event.type is ChatEventType.DATA for event in events)
    assert events[-1].type is ChatEventType.DONE
    assert not any(
        event.type is ChatEventType.ERROR and event.payload.get("code") == "invalid_request"
        for event in events
    )
~~~

Playwright 通过 Home 输入框完成同一问题，检查 progress 文案、结构化比赛卡片、回答完成和浏览器 console error/warn 为空；再进入一场 Match Page 提问统计+逐分+走势，检查多个取数阶段和 warning 不会变成错误卡片。

- [ ] **Step 2: Run isolated deterministic gates**

~~~bash
cd backend && env -u NO_PROXY -u no_proxy uv run pytest -m 'not llm_live and not provider_live and not end_to_end_live' -q
cd ../frontend && pnpm test && pnpm typecheck && pnpm build
~~~

Expected: backend 全确定性测试、frontend 全部 Vitest、typecheck、production build 全部 PASS。

- [ ] **Step 3: Run isolated fake-service Playwright gates**

~~~bash
cd frontend && pnpm test:e2e -- e2e/p1-flow.spec.ts e2e/llm-live.spec.ts
~~~

Expected: Home/Match 的 progress、warning、结构化 data、retry/cancel 和双视口关键路径 PASS；不更新原型视觉基线，除非截图差异由已批准的 warning/progress UI 直接造成并逐张审阅。

- [ ] **Step 4: Run official-compatible and real integration gates**

~~~bash
cd backend && env -u NO_PROXY -u no_proxy uv run pytest -m llm_live tests/live/test_llm_live.py -q
env -u NO_PROXY -u no_proxy uv run pytest -m api_tennis_live tests/live/test_api_tennis_live.py -q
~~~

检查真实 SSE 原始事件顺序为 resolving → planning → fetching_data → data → planning/generating → text_delta → done；确认 final request 的 payload 没有 tools，planning request 有明确 parallel_tool_calls，不输出 request body 中的 key。

- [ ] **Step 5: Run real-browser mouse workflow**

用 Chrome 真实鼠标完成 Home → 输入 tiafoe 的比赛如何了 → 等待进度 → 打开结果卡 → 进入 Match → 提问“根据当前比分、每盘统计和逐分走势分析趋势”→ 观察正文、warning、快照版本和浏览器 console；确认不出现“查询失败（invalid_request）”或“卡片成功后查询未完成”。

- [ ] **Step 6: Update control docs and commit**

在 CURRENT.md 写入实际测试命令、通过数量、真实 SSE/浏览器证据和完成提交；在 ROADMAP.md 将 T39 标记为 done，只填实际运行过的数字。最后运行：

~~~bash
git diff --check
git status --short --branch
git log -1 --oneline
git add CURRENT.md ROADMAP.md backend/tests/live/test_llm_live.py frontend/e2e/llm-live.spec.ts
git commit -m "test: verify multi-tool chat in real flows"
git push origin main
~~~

## Self-Review Checklist

- Spec 的 scope registry、phase catalog、global match-only 防线由 Task 1 覆盖。
- parallel_tool_calls 官方语义、final tool_choice=none 和不传 tools 由 Task 2 覆盖。
- ToolOutcome、并发批次、依赖顺序、去重、预算、超时由 Task 3 覆盖。
- replan、optional/core failure、SSE warning/status/done 顺序由 Task 4 覆盖。
- 前端 warnings/progress/terminal error 分离、重试/取消清理和 Home/Match 展示由 Task 5 覆盖。
- 重复真实 Qwen、API-Tennis、Playwright、真实鼠标业务流程和总控文档由 Task 6 覆盖。
- 没有新增数据库、路由 LLM、供应商能力或 P3 范围；没有把官方缺失数据猜成事实。
- 没有使用未完成标记或未定义的“稍后补充”步骤。

## Definition of Done

- tiafoe 的比赛如何了 在 deterministic、真实 LLM 和真实浏览器路径中均不会出现结构化 data 之后的 invalid_request。
- Global 从 catalog 到 executor 都无法执行 get_match_intelligence；Match snapshot 的 state_version/as_of 保持不变。
- 独立工具确实并行，依赖工具分轮串行，重复调用和预算边界均有测试。
- optional tool failure/rejected 只产生 warning 或内部 replan；没有核心事实时才产生 terminal error。
- SSE 和 UI 能同时展示阶段进度、结构化 data、正文和 partial warning，且 warning 不被当作失败卡片。
- backend/frontend 全量、typecheck/build、fake Playwright、真实 Qwen/API-Tennis 和真实 Chrome 鼠标流程均有实际证据。
- CURRENT.md、ROADMAP.md、代码、测试和 Git HEAD 一致；已有任务外未跟踪文件未被纳入提交。
