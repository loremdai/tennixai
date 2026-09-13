# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-13 13:34 CST

**当前任务：** T53 — P2 Final Completion Gate Repair

**任务状态：** `done`

**执行者 / ADE：** Codex / Codex

**分支：** `main`

**任务起始提交：** `7bbb541`

**领取提交：** `891b4d5`

**完成提交：** `348110c`（任务修复、配置清理、E2E 断言和十张 prototype 视觉基线）

**当前状态：** P2 正式关闭；当前没有进行中的任务；P3 — Market & Decision Support 保持 `planned`，已达到 `ready for design`，仍需用户明确授权后才能启动；本任务未开始 P3。

## T53 完成事实

- Home 默认“全部性别”现行契约是显式序列化 `gender=men`、`gender=women`、`gender=mixed`、`gender=unknown`；只更新过期 Playwright 断言，未改变筛选状态、请求构造或产品语义。
- 删除 `backend/app/config.py` 中重复的 `api_tennis_ws_url` 声明；保留唯一默认值 `wss://wss.api-tennis.com/live`。
- 14 个 Playwright 失败已逐项关闭：4 个 Home filter 断言更新后通过，10 个 prototype.visual 差异经人工审查后只更新对应十张旧基线；没有修改页面生产代码。

## prototype.visual 十张基线审查

下表覆盖 `home-initial`、`home-answer`、`match-upcoming`、`match-live`、`match-finished` 的 desktop/mobile 每一张 expected、actual、diff 三元组；只在确认当前展示是已批准演进后更新 expected。

| 状态 | desktop 审查结论 | mobile 审查结论 | 处理 |
|---|---|---|---|
| Home initial | T38 已批准的球员国旗、T52 已批准的零值 inactive `unknown` chip 隐藏；旧 expected 少国旗且多出 chip，整体高度约少 34px，无页面回归 | 同一批准演进；结构、间距和文案无非批准回归 | 更新 2 张 |
| Home answer | 叠加 T38 国旗、T52 chip 隐藏和 T41 已批准的 Home source footer 移除；旧 expected 高约 55px，答案与结构化卡片完整 | 同一批准演进，旧 expected 高约 55px，未见结构回归 | 更新 2 张 |
| Match upcoming | 仅 T38 已批准的两处球员国旗，约 647–648 个像素变化；无布局/文案回归 | 同一局部国旗变化；无布局/文案回归 | 更新 2 张 |
| Match live | 仅 T38 已批准的两处球员国旗，约 647–648 个像素变化；无布局/文案回归 | 同一局部国旗变化；无布局/文案回归 | 更新 2 张 |
| Match finished | 仅 T38 已批准的两处球员国旗，约 647–648 个像素变化；无布局/文案回归 | 同一局部国旗变化；无布局/文案回归 | 更新 2 张 |

## 实际验证证据

| 门 | 实际结果 |
|---|---|
| PostgreSQL/Redis | `docker compose up -d postgres redis`；两个容器均 `healthy` |
| Backend deterministic | `463 passed, 45 deselected` |
| Backend infrastructure | `22 passed, 486 deselected` |
| Config regression | `tests/test_config.py`: `2 passed`；默认 WebSocket URL import/assertion 通过 |
| Frontend | `pnpm test`: `206 passed (206)`；`pnpm typecheck` exit 0；`pnpm build` exit 0 |
| Full Playwright | `pnpm test:e2e`: `56 passed, 32 skipped, 0 failed`，退出码 0 |
| Focused browser gates | `p2-home-filters`: `6 passed`；prototype.visual：`10 passed`；目录/P1/P2/prototype 聚焦门：`36 passed, 4 skipped` |
| Hygiene | `git diff --check` 通过；生产代码供应商字段扫描零命中；凭据模式扫描零命中 |

T53 未修改 provider、resolver 或 Chat runtime 路径，因此复用 T52 已通过的真实 API-Tennis、真实 LLM、真实目录与真实浏览器证据，没有消耗配额进行无意义重跑。

## 未跟踪文件保护

以下既有未跟踪文件/目录保持原样，未修改、删除或提交：`.codex/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/AGENTS.md`、`frontend/CLAUDE.md`、`frontend/next-env.d.ts`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-13 | `348110c` | T53 修复 Home 断言、删除配置重复声明、审查并更新十张 approved prototype 基线；完整确定性门零失败 |
| 2026-09-13 | `891b4d5` | 领取 T53，锁定 `main` 与起始提交 `7bbb541` |
| 2026-09-13 | `7bbb541` | T52 真实服务与 P2.6 数据门证据入库；遗留的 14 个确定性 Playwright 失败由 T53 收口 |
| 2026-09-13 | `501f229` | T51 球员页面接入真实结构化 API，保留 v0 preview 视觉真源 |

## 下一步

等待用户授权后，才可创建并领取 P3 设计任务。当前不得实现 P3、odds、prediction、market、trading、双打、Player Chat、运行时翻译/RAG 或云部署。
