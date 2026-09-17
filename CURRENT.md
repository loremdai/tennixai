# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-18 07:39 CST

**当前任务：** T80: Add Explicit Real Verification, Browser Acceptance, and the Human Runbook（P4.1）

**任务状态：** `blocked`（阻塞条件：根 `.env` 的 LLM token-plan 配额耗尽，`init` 的必需中文补齐步骤无法完成；只有用户可恢复配额或更换 key）

**执行者 / ADE：** Claude Code（Fable 5）

**分支：** `main`

**起始提交：** `da6dcdd`（T80 交付物已提交为 `1ba5e5c`+`559b4c2` 并推送）

**当前动作与阻塞诊断（systematic-debugging 已完成根因定位）：**

- T80 交付物阶段已完成并经 opus 评审 Approved：`verify.py`（有界只读、诚实 pass/fail/skip）、`local_runtime_live` marker、opt-in 浏览器验收 spec、runbook、`.env.example` 注释、CLI verify 接线；e2e 配置隔离修复（默认 Playwright 后端钉死 `TENNIX_P3_MODE=disabled` 等模式变量，凭据仍从根 `.env` 流入 opt-in live spec）。交付物阶段门：verify 25 passed、vitest 392 + typecheck + build、确定性 backend 1188/5/32、infra 62、默认 Playwright 110 passed/44 skipped/0 failed。
- 阶段 2 真实门（已如实完成的部分，2026-09-18）：
  - `./scripts/tennix-live init`：**FAIL（诚实失败，非缺陷）** — Compose healthy、`tennix_live_local` 创建成功、alembic 0001→0005 全部升级成功后，bootstrap 在中文补齐步骤按设计 fail-closed：`LOCAL_BOOTSTRAP_FAILED`、退出非零、marker 未写、已成功数据保留。逐步诊断证明 rankings（ATP 2342/WTA 1602，updated=3944）、known aliases（15913）、catalog（live=6/upcoming=290）、new aliases 全部 OK；单批 enrichment 诊断 `failed=1`，底层错误为 `openai.RateLimitError 429 insufficient_quota`（LLM token-plan 配额耗尽）。系统各层行为完全符合设计（`llm_unavailable`→typed AppError→非零退出→数据保留）。
  - `TENNIX_RUN_LOCAL_RUNTIME_VERIFY=1 ./scripts/tennix-live verify`（无 --with-llm）：**exit 0** — atp_rankings/tennis_catalog/tennis_websocket/market_discovery/market_book 5 项真实 passed（含真实 live 比赛 WS 订阅收帧）；market_websocket 诚实 skipped（RECEIVE_TIMEOUT 安静窗口）；llm_chat 诚实 skipped（NOT_REQUESTED）。
  - `TENNIX_RUN_LOCAL_RUNTIME_VERIFY=1 pytest -m local_runtime_live tests/live/test_local_runtime_verify.py`：**1 passed, 1 skipped**（skip 为 with-LLM 变体门控）。
- 被阻塞的剩余项：重跑 `init` 至完成（含一次性 LLM 中文补齐）→ `verify --with-llm` → `up` → `status` → 浏览器验收（`TENNIX_E2E_LOCAL_RUNTIME=1`）→ `down` → `up` → `status` → 重启持久性人工核对 → Completion Gate 逐条核验与最终整枝评审。
- 恢复方式：用户在根 `.env` 恢复/更换 LLM 凭据配额后告知，即可从 `init` 重跑继续（幂等，只补缺失项；既有 rankings/aliases/catalog 数据保留）。

## P3 关闭证据摘要（详见 ROADMAP T57–T71 行）

- 设计/原型冻结：T55 `d7cc25e`、T56 `f29a789`（26 场景 × desktop/mobile 52 张基线，逐张审阅）。
- 数据与实时：T57–T60（只读 Polymarket、精确 mapping、replay；真实 REST/WS 验证）。
- 预测与决策：T61–T65（fail-closed benchmark `not_promoted`、quote/policy/engine、one-shot paper、双流编排与延迟门）。
- 产品面：T66–T69（只读 REST/SSE/Chat、typed transport、Home Pulse/`/markets`、Match workbench）。
- 完成门：T70 `01e6ba0`（dual-stream replay/recovery/latency/全回归/视觉门）、T71 `3fde00a`（真实只读 shadow + 证据表）。
- 回归基线：backend 855 确定性 + 50 infrastructure；frontend 392 单测、typecheck/build 干净、Playwright 110 passed/38 skipped（live 门按 env 跳过）。
- 诚实缺口转入 P4：真实历史数据与模型晋升证据、artifact 键对齐、`match_info` 真实来源、退出阈值/仓位优化、性能打磨；自动下单永久 `deferred` 直至单独批准。

## 未跟踪文件保护

以下既有未跟踪文件/目录不得修改、删除或提交：`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-18 | （本提交） | T80 转 `blocked`：真实 init 诚实失败，根因=LLM 配额耗尽（429 insufficient_quota）；真实 verify 门 5 passed/2 honest skipped、live pytest 门 1 passed/1 skipped 已如实记录 |
| 2026-09-18 | `559b4c2` | T80 修复：默认 Playwright e2e 后端模式与根 `.env` 隔离（P4.0 规格 §11）；全套 e2e 110 passed/44 skipped/0 failed |
| 2026-09-18 | `1ba5e5c` | T80 交付物完成：verify.py/CLI 接线/local_runtime_live marker/浏览器验收 spec/runbook/.env.example（verify 25 passed；确定性 1188/5/32；infra 62） |
| 2026-09-18 | `da6dcdd` | T79 修复 3：`waitpid WNOHANG` 收割僵尸，存活探测/快速失败真实生效 |
| 2026-09-18 | `fb49cdc` | T79 加固：SIGTERM 竞态闭合、runtime 死亡快速失败、frontend 存活窗、status 健康年龄（opus 复审 Approved） |

## 下一步

1. **等待用户恢复 LLM 配额**（根 `.env` 的 token-plan 充值或更换 key；只有用户可执行）。恢复后从 `./scripts/tennix-live init` 重跑继续：幂等只补缺失中文名，既有 rankings/aliases/catalog 数据保留。
2. init 成功后依序执行剩余真实门：`verify --with-llm` → `up` → `status` → 浏览器验收（`TENNIX_E2E_LOCAL_RUNTIME=1`，先经 `status` 确认 runtime 真实在跑）→ `down` → `up` → `status` → 重启持久性人工核对（内部 ID/canonical 数据/paper ledger/cursor）。
3. 全部通过后：T80 转 `done` 附完整证据表；逐条核验 P4.1 Completion Gate 与计划 Completion Gate for T73–T80；最终整枝评审（分诊各任务遗留 Minor）；对齐 PROJECT/ROADMAP/CURRENT/runbook/Git HEAD 与 origin/main；确认工作区除受保护未跟踪项外干净。
4. 任何 P4 工作不得回溯放宽 P3 边界；外部安静窗口必须诚实 SKIP，不得写成通过。
