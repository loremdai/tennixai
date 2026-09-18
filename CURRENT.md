# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-18 17:17 CST

**当前任务：** T82 — 修复一键启动器对前端包管理器的错误依赖

**任务状态：** `in_progress`

**执行者 / ADE：** Codex

**分支：** `main`

**起始提交：** `7b0bf13`

**当前动作：** 先关闭现有本地栈；为 `up` 增加前端启动器回归测试，将前端直接交给仓库已安装的 Next，不再调用 PATH 上不确定版本的 pnpm。

## T82 领取说明（2026-09-18）

- 用户已明确要求先关闭当前服务，再修复一键启动。
- 已执行 `./scripts/tennix-live down`，服务进程已停止，数据与外部容器保留。
- 起始提交：`7b0bf13`；工作区既有未跟踪保护项保持不变。

## T81 关闭证据（2026-09-18，全部实际运行；详见 ROADMAP T81 行）

- 领取 `f14babb`（起始 `7bd453a`）；实现 `2c1186c`（6 个 spec 的 19 个快照测试声明加原生组级 `@visual` tag；`home-history.spec.ts` 只标记 `Home history visual` describe，功能测试未标记）+ `9f5a459`（`frontend/package.json`：`test:e2e:functional`=`--grep-invert @visual`、`test:e2e:visual`=`--grep @visual --workers=1`、`test:e2e`=两条顺序 lane、`test:e2e:update` 只走串行视觉 lane）。
- lane 选择证明：`pnpm exec playwright test --list --grep @visual` 38 项（19×desktop/mobile，恰为 6 个快照面）；`--list --grep-invert @visual` 116 项且保留 home-history 两个功能测试。
- 验证（fnm Node 22.22.0 + pnpm 10.30.1，未动 node_modules）：`pnpm test` 395 passed；`pnpm typecheck` 干净；`pnpm build` exit 0；`pnpm run test:e2e:functional` 76 passed/40 skipped；`pnpm run test:e2e:visual` 34 passed/4 skipped（4 项为 replay-off 按设计跳过）；默认 `pnpm test:e2e` 连续两次均 `110 passed/44 skipped/0 failed`（76+34/40+4 精确对账）。
- 视觉真相零改动：`git diff --exit-code -- frontend/e2e/__screenshots__` 零 PNG diff；`git diff --check` 通过；未改 UI/CSS/Next/FastAPI/`playwright.config.ts`/阈值/viewport/截图参数，无 mask/skip/fixme/retry，未运行 live/LLM/API 配额门。
- P4.1 仍为历史已关闭事实（证据见 ROADMAP T73–T80 与 Completion Gate 摘要）；本机栈保持 `down`，外部容器与 `tennix_live_local` 数据保留；T81 未重开真实 runtime 设计。

## 未跟踪文件保护

以下既有未跟踪文件/目录不得修改、删除或提交：`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-18 | （T82 领取） | 已关闭本地栈；T82 开始修复 `up` 对 PATH 上 pnpm 的错误依赖，起始提交 `7b0bf13` |
| 2026-09-18 | `7b0bf13` | T81 关闭：`@visual` tag（`2c1186c`）+ 功能/串行视觉两条顺序 lane（`9f5a459`）；`pnpm test:e2e` 连续两次 110/44/0，PNG 零 diff；三份总控同步 |
| 2026-09-18 | `f14babb` | T81 领取：执行者 Claude Code（Fable 5），`main`，起始提交 `7bd453a` |
| 2026-09-18 | `7bd453a` | T81 计划与总控交接：后验定位为跨文件 worker 并发下的移动端视觉门不稳定；冻结 `@visual` + 功能/串行视觉两 lane 方案 |
| 2026-09-18 | `2270049` | P4.1 关闭：T80 `done`（真实 init/verify 7/7/浏览器 6/6/手工全流程/重启持久性）+ Completion Gate 九条核验摘要入 ROADMAP |
| 2026-09-18 | `002da61` | 实机修复 2：`LOCAL_PNPM_MISSING` 前置快速失败（launcher 61 passed；确定性 1199/5/32） |

## 下一步

1. 完成 T82：通过焦点回归测试，并用无环境覆盖的 `./scripts/tennix-live up` 做一次真实启动验证；验证后按用户要求保持栈关闭。
2. P4 后续候选（待用户排期与批准，均未领取）：真实历史数据与模型晋升证据链、退出阈值/仓位优化（需 paper 证据）、per-match freshness overlay（模型晋升前置条件）、性能打磨、RuntimeDemand 死代码清理等延期 Minor。日常本地使用仍是 `./scripts/tennix-live up`（不调用 LLM）→ `status`/`logs` → `down`；详见 `docs/runbooks/local-real-runtime.md`。
3. 边界不变：自动下单永久 `deferred` 直至单独批准；任何后续工作不得回溯放宽 P3 边界（只读 provider、one-shot FOK、PostgreSQL 权威、独立 cursor、未晋升即 NO BET）；外部安静窗口必须诚实 SKIP。T81 建立的两条 E2E lane 不得以调阈值、mask、skip/retry 或重录 PNG 的方式“修复”视觉失败；快照更新仅在用户单独批准的受审视觉变更下进行。
