# TennixAI 项目总路书

> 本文件回答“项目要经过哪些阶段、现在整体走到哪里、每项完成有什么证据”。
> 项目定位见 [PROJECT.md](./PROJECT.md)，唯一当前任务见 [CURRENT.md](./CURRENT.md)。

**最后更新：** 2026-09-09 10:49 CST

**总体状态：** `in_progress`（P1 已完成；P2 保持 planned，等待明确启动）

**当前里程碑：** P1 — 比赛信息查询助手（`done`；下一里程碑 P2 尚未启动）

**当前阶段：** P1.6 — Acceptance and hardening（`done`）

## 状态说明

| 状态 | 含义 |
|---|---|
| `planned` | 已进入路线，但尚未达到可领取条件 |
| `ready` | 前置条件已满足，可以成为唯一当前任务 |
| `in_progress` | 正由 `CURRENT.md` 记录的唯一执行者推进 |
| `blocked` | 已开始但被明确条件阻塞 |
| `done` | 验收实际通过，且附有提交和证据 |
| `deferred` | 经明确决策推迟，不属于当前执行序列 |

同一时间最多一个任务可以标记为 `in_progress`。只有验收命令实际通过后才能标记 `done`。

## 总体路线

| 里程碑 | 状态 | 目标 | 进入/完成条件 |
|---|---|---|---|
| P1 — Match Information Assistant | `done` | 跑通真实结构化比赛查询、卡片、Match Page 与上下文 Chat | T17/T18/T19 均已完成（`69c8238`、`5572960`、`fdb0131`）；P1 关闭，P2 保持 planned |
| P2 — Live Match Intelligence | `planned` | 技术统计、PBP、Momentum、持久化和多进程实时协调 | P1 全部门通过；API-Tennis 能力与迁移设计另行批准 |
| P3 — Market & Decision Support | `planned` | 市场状态、预测、edge、confidence 和 paper trading | P2 数据可信；映射、模型评估和风控设计另行批准 |
| Optional — Automated Execution | `deferred` | 在满足法律、风控、安全和可审计条件后考虑自动下单 | 不属于 P3 默认范围，必须单独批准 |

## P1 阶段状态

| 阶段 | 状态 | 核心交付 | Exit gate / 当前缺口 |
|---|---|---|---|
| P1.0 — Design freeze | `done` | 架构路线、原型状态清单、桌面/移动视觉基线 | 已完成：10 张基线入 Git（最终版 `c035f5a`，排除 dev overlay），重建后连续复跑 10/10，build exit 0 |
| P1.1 — Foundation | `done` | FastAPI、配置、健康检查、测试骨架、Next.js 薄代理 | 已完成：T02/T09；浏览器级 health/SSE smoke 由 T15 p1-flow 与 llm-live E2E 验证（同源代理 + SSE 透传） |
| P1.2 — Domain and provider | `done` | canonical models、provider protocol、fake/live adapters、进程内 identity | 已完成：T03–T06 + T08 公开 DTO 泄漏门（`test_match_list_never_exposes_provider_ids` 等断言响应零供应商 ID） |
| P1.3 — Service and REST | `done` | TennisService、时间语义、缓存、确定性 REST | 已完成：T07（`000ca1a`）+ T08（`039d144`）——事实问题不经 LLM 可答；时区/歧义/不可用字段/stale/429 均有确定性测试 |
| P1.4 — Real frontend data | `done` | typed client、Home、动态 Match Page、加载/错误/刷新状态 | 已完成：T09/T12/T13/T14；Home→Match 内部 ID 链路经单元与视觉门验证，预览路由像素稳定 |
| P1.5 — Conversational path | `done` | 三个业务工具、Qwen tool loop、SSE、全局与比赛 Chat | 已完成：T10/T11 + 前端消费（T12–T14）；chat 与 REST 同一事实、LLM/供应商失败不产生虚构结果经 orchestrator 测试与 E2E 验证 |
| P1.6 — Acceptance and hardening | `done` | 验收集、真实服务 opt-in 测试、Playwright、真实运行时边界与修复 | T16/T17/T18/T19 已完成；确定性、真实 provider/LLM、浏览器、降级、Markdown 展示和结果卡片可见性均有证据 |

详细阶段设计见 [产品路线设计 §12](./docs/superpowers/specs/2026-09-08-tennixai-product-roadmap-design.md#12-p1-execution-roadmap)。

## P1 任务登记表

任务按实施顺序排列。详细步骤只存在于 [P1 实施计划](./docs/superpowers/plans/2026-09-08-tennixai-p1-implementation.md)，此处只维护状态和完成证据。

| ID | 主要阶段 | 任务 | 状态 | 完成提交 | 验收证据 |
|---|---|---|---|---|---|
| T01 | P1.0 | Freeze the Existing Prototype Visually | `done` | `c035f5a` | 10 张桌面/移动基线入 Git（排除 dev overlay）；重建后 `--update-snapshots` 10/10 + 连续两次 plain 复跑 10/10；`pnpm build` exit 0；10 张 PNG 逐张审阅；历史：首版 `d13d6dd`、回退重开 `c37ad36`（2026-09-08） |
| T02 | P1.1 | Establish the FastAPI Foundation | `done` | `8b15efe` | `uv run pytest tests/test_health.py -v` 1/1 通过（health 200 `{"status":"ok","service":"tennix-api"}`、`X-Request-ID` 原样透传）；`uv run python -c "from app.config import Settings; print(Settings(_env_file=None).llm_model)"` 输出恰为 `qwen3.8-max-0902`，无凭据打印；uv.lock 已入库（2026-09-08） |
| T03 | P1.2 | Define Canonical Models and In-Memory Identity | `done` | `5ed8a18` | `uv run pytest tests/test_domain.py tests/test_identity.py -v` 10/10 通过（naive datetime 拒绝、frozen/extra=forbid、内部 ID 稳定可逆且不含外部 ID、三前缀 mat_/ply_/trn_）；全套确定性 suite 11/11 通过（2026-09-08） |
| T04 | P1.2 | Add the Provider Contract and Deterministic Fake | `done` | `20735bd` | `uv run pytest tests/test_provider_contract.py -v` 8/8 通过（五方法 protocol 全部行使、canonical models 返回、公共 ID 无 `fake-` 外部 ID、大小写不敏感搜索、player 过滤、not_found AppError）；全套确定性 suite 19/19 通过（2026-09-08） |
| T05 | P1.2 | Implement the LiveTennisAPI Adapter | `done` | `16a0688` | `uv run pytest tests/test_livetennis_provider.py tests/test_provider_contract.py -v` 21/21 通过（X-API-Key/search/status=live 参数、player-major→SetScore 转置、server→内部 ID、completed→finished、Postponed→postponed、null 时间保持 None、unknown field 忽略、404/429+retry_after/403/500 精确翻译、fixture 与 match 同命名空间、vendor 字段零泄漏断言）；全套确定性 suite 32/32；全部用 `httpx.MockTransport`，无真实网络调用（2026-09-08） |
| T06 | P1.2/P1.3 | Add the Bounded Async TTL Cache | `done` | `6605ecb` | `uv run pytest tests/test_cache.py -v` 8/8 通过（fresh 命中、并发 coalescing 仅 1 次 loader、stale fallback 标记、超 stale_ttl re-raise、LRU 257 驱逐、value-based TTL 负缓存 30s、过期重载）；全套确定性 suite 40/40；注入 FakeClock，无长 sleep（2026-09-08） |
| T07 | P1.3 | Implement TennisService and Time Semantics | `done` | `000ca1a` | `uv run pytest tests/test_service.py tests/test_cache.py tests/test_provider_contract.py -v` 35/35 通过：tonight 三边界参数化（02:00/12:00/20:00 +08:00）、精确命中优先、ambiguous_player 409+candidates、not_found 404、空 query 422、next/today/tonight 选择规则、过期 fixture 排除、live 60/300 与 upcoming 600/1800 stale 界限、player 3600s、空结果负缓存 30s、match 详情 60/600 与负缓存——全部由 provider 调用计数证明；全套确定性 suite 59/59（2026-09-08） |
| T08 | P1.3 | Expose Deterministic REST APIs | `done` | `039d144` | `uv run pytest tests/test_api.py -v` 16/16 通过（错误信封 `{error:{code,message,details},request_id}`、422/404/409/503/429+Retry-After、request ID 生成与透传、响应零供应商 ID、fixed_now 校验、live 模式凭据校验、provider 注入）；全套确定性 suite 75/75（2026-09-08） |
| T09 | P1.1/P1.4 | Add Thin Next.js Route Handler Proxies | `done` | `e6d59ca` | `pnpm test -- lib/server/backend-proxy.test.ts` 8/8 通过（SSE body 原样透传、query/method/content-type 转发、429+Retry-After、authorization/cookie 不转发、fetch 失败→502 internal_error、未配置→500、零 base URL 泄漏、POST 流式 duplex half）；`pnpm typecheck` 通过；`pnpm build` exit 0（四个代理路由均 dynamic）；`pnpm test:e2e --grep prototype` 10/10 视觉基线不受影响（2026-09-08） |
| T10 | P1.5 | Define Chat Models, Historical Guard, and Business Tools | `done` | `9d988ed` | `uv run pytest tests/test_chat_tools.py tests/test_service.py -v` 34/34 通过（catalog 恰为三工具且 time_scope enum 内联、match scope 注入并忽略模型提供 ID、global get_match 缺 ID→422、malformed args→invalid_request+tool、未知工具拒绝、service 错误透传、9 个历史短语大小写不敏感守卫、StructuredToolResult 含 domain models、ChatRequest 1–12 条边界）；全套确定性 suite 90/90（2026-09-08） |
| T11 | P1.5 | Add the OpenAI-Compatible Tool Loop and SSE Route | `done` | `174866a` | `uv run pytest tests/test_chat_orchestrator.py tests/test_chat_api.py -v` 17/17 通过（事件顺序 status→data→text_delta→done、LLM 失败保留结构化结果+固定 fallback、历史守卫零 model/provider 调用、provider 异常仅 status,error、第三轮工具→invalid_request、match scope system message 含内部 ID、SSE 帧恰以两个换行结束、`/api/v1/chat/stream` 端到端 fake 模式、422 请求体校验）；全套确定性 suite 107/107；未调用真实 LLM（2026-09-08） |
| T12 | P1.4/P1.5 | Add Typed Frontend API, SSE Parsing, and View Models | `done` | `bd79e84` | `pnpm test` 40/40 通过（SSE 跨 chunk 分裂帧、多字节字符切分、CRLF、注释/多 data 行、REST data 信封解包、ApiError code/details、abort 不变 internal_error、view-model Asia/Macau 时间/`暂未提供`/stale 标签/比分行/initials、useChatStream 全生命周期/12 条历史/abort/cancel/reset/unmount）；`pnpm typecheck` 通过；`pnpm build` exit 0（2026-09-08） |
| T13 | P1.4 | Connect Home to Real Structured Data Without Redesigning It | `done` | `4a29050` | `pnpm test -- components/home-page.test.tsx` 13/13 + 全套 `pnpm test` 53/53 通过（结构化卡片只来自 stream data、initial question 一次、slate live/upcoming 各一次且无轮询、刷新新一对调用、loading 禁重复提交、unsupported 无卡片、stale 徽章、空外壳、typed 重试、无样例数据文案）；`pnpm typecheck`、`pnpm build` 通过；`pnpm test:e2e --grep prototype` 10/10——4 张 home 基线经逐张 diff 审阅后更新（真实数据替换 mock、占位文案、footer 文案；布局几何保留），6 张 match 基线零变化（2026-09-08） |
| T14 | P1.4/P1.5 | Add the Internal-ID Match Page and Contextual Chat | `done` | `d76821b` | `pnpm test -- components/match-page.test.tsx` 13/13 + 全套 `pnpm test` 66/66 通过（match scope 注入且用户 prompt 不含上下文、upcoming/live/finished hero 映射、server 高亮、缺失字段 `暂未提供`、stale 指示、显式刷新、404/错误重试、生产 stats/momentum 永远 `P2 数据暂不可用`、preview 保留样例）；`pnpm typecheck`、`pnpm build` 通过；`pnpm test:e2e --grep prototype` 10/10 且 6 张 match 基线逐像素零变化（经 4 轮 diff 审阅修复预览文案/图标/中文盘数后达成，未更新任何基线）（2026-09-08） |
| T15 | P1.6 | Complete Browser E2E, Live Gates, and the P1 Runbook | `done` | `98075ef` | 干净工作区重跑：backend `pytest -m "not llm_live and not provider_live and not end_to_end_live"` 117 passed；frontend `pnpm test` 66/66、`typecheck` 通过、`build` exit 0、`pnpm test:e2e` 32 passed + 4 skipped（live specs 无标志）；验收矩阵 `test_p1_acceptance.py` 10/10（9 supported 工具路径 + 历史行零 provider/模型调用）；`llm_live` 后端 4/4、浏览器 `llm-live.spec.ts` 2/2（真实 Qwen，DEUCE 凭据经 env 注入）；`provider_live`/`end_to_end_live` 与浏览器 end-to-end 如实 skip（缺 LiveTennisAPI key）；p1.visual 12 张新基线逐张审阅入库；泄漏检查 `git grep -nE 'event_key|event_first_player|score\[0\]\[1\]' -- ':!docs'` 仅治理/策略文档命中、业务代码零命中；Final Gate 八条人工核对通过（凭据仅服务端、无轮询、无超范围实现、结构化事实、失败降级、预览/生产分离、双视口视觉）（2026-09-08） |
| T16 | P1.6 | Harden the Real Live Runtime | `done` | `5dcaa6a` | `pytest -m "not llm_live and not provider_live and not end_to_end_live"` 124 passed；frontend `pnpm test` 66/66、typecheck、build、全 E2E 32 passed + 4 skipped；真实 `provider_live` 1/1、`llm_live` 4/4、`end_to_end_live` 1/1；真实浏览器 `end-to-end-live.spec.ts` desktop/mobile 2/2；手动 Djokovic 返回 `status → data(empty) → text_delta → done`；完整 SSE data 保留，LLM tool context 限 12 条摘要，超时降级保留结构化数据；配置与 runbook 已更新，计划见 [T16 计划](./docs/superpowers/plans/2026-09-08-tennixai-t16-real-runtime-hardening.md) |
| T17 | P1.6 | Repair Real Upcoming Provider and Partial Failure Handling | `done` | `69c8238` | `/matches?status=upcoming` 使用当前 nested payload 并映射 canonical ID；指定球员查询使用 provider external ID 过滤；全局列表只读供应商一页，不做无界分页；Home live/upcoming 单侧失败独立降级；429 保留 `Retry-After` 并显示友好重试文案。backend 确定性 126 passed、frontend 69/69、typecheck/build 通过，Playwright 32 passed + 4 skipped；真实 REST 返回 50 场 upcoming，Qinwen Zheng 指定查询与真实浏览器 Home→Match→上下文问答通过 |
| T18 | P1.6 | Render Markdown in Conversational Answers | `done` | `5572960` | 根因是 Home/Match 使用普通 `<p>` 输出 Markdown 字符串；新增共享 `MarkdownAnswer`，默认跳过原始 HTML，统一渲染粗体、列表和段落。TDD 回归测试先失败后通过；frontend 71/71、typecheck/build、隔离服务 Playwright 10/10；真实浏览器确认 `strong=10`、`ul=1`、无原始 `**` |
| T19 | P1.6 | Keep Structured Match Cards Visible After Markdown Answers | `done` | `fdb0131` | 新增结果区域 ref、视口检测和 `scroll-mt-24`；回答完成且结果不在视口时滚动到卡片，尊重 reduced-motion。Home 单元 72/72、typecheck/build、长 Markdown P1 flow 桌面/移动 12/12；完整 Playwright 34 passed + 4 skipped，视觉基线通过 |

> T17 的已知非范围限制：LiveTennisAPI 的 `/players?search` 尚不能直接解析中文显示名“郑钦文”；canonical English name `Qinwen Zheng` 的真实查询已通过。中文别名/名称归一化需另立任务，不影响 T17 的 provider 修复验收。

## P1 验收矩阵

| 用户问题 | 预期结果 |
|---|---|
| 今晚 Sinner 几点打？ | 解析球员与澳门本地时间，返回结构化比赛卡片 |
| Alcaraz 今天有比赛吗？ | 确定性 yes/no 或消歧，并附 canonical data |
| Djokovic 下一场对谁？ | 返回最早的非终态比赛和对手 |
| 这是什么赛事？ | 当前比赛赛事或明确 unavailable |
| 第几轮？ | 当前比赛轮次或明确 unavailable |
| 什么场地？ | 当前比赛场地或明确 unavailable |
| 比赛开始了吗？ | canonical lifecycle status |
| 现在比分多少？ | canonical score 与 freshness |
| 谁在发球？ | canonical server 或明确 unavailable |
| 昨天 Sinner 赢了吗？ | typed `unsupported`，不得猜测 |

## 长期边界与升级触发

- PostgreSQL：P2 在需要跨重启身份、观察历史和稳定映射时设计并引入。
- Redis：P2 在需要多 worker 共享缓存、配额、polling lock 和事件分发时引入。
- 自动轮询：P2 基于比赛生命周期和供应商配额单独设计。
- 历史结果：只有确认数据 entitlement 与保存策略后才进入，不因接数据库自动获得。
- 自动交易：不属于 P3 默认范围，必须经过独立法律、风控、安全和执行设计。

## 更新纪律

- 阶段、任务、顺序、验收门或延期决策改变时更新本文件。
- 标记 `done` 时必须同时写入完成提交与实际验证证据。
- 任务的执行者、工作分支、当前动作和阻塞只写入 `CURRENT.md`。
- 完整变更历史由 Git 保存；本文件不追加逐日流水账。
