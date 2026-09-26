# T106 逐分得分者未知状态展示实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Match 逐分时间线不再把无法确认的得分者误写为“胜者待定”，同时保留已知球员和比分事实。

**Architecture:** 不改 provider 或 canonical winner 推断。只在 `MatchPointsTimeline` 把 `winner_player_id=null` 映射为可访问的中性占位，并在时间线顶部显示一次说明。

**Tech Stack:** Next.js、TypeScript、React、Vitest、Testing Library。

**Spec:** [T106 设计规格](../specs/2026-09-26-tennixai-t106-point-winner-clarity-design.md)

## Global Constraints

- 不将未知 winner 猜成某位球员；比分、顺序、分组、关键分、动量/API/存储均不改。
- 不增加依赖或供应商请求；不读取/输出根 `.env`，不重启共享服务。
- 在 `main` 按唯一任务规则实施；只暂存本计划列出的文件，保留工作区已有改动。

## Review Focus

- 未知胜者很多时，说明仍只出现一次，且未逐行显示误导性文案。
- 已知胜者、比分及当前分组默认展开行为保持不变。
- `aria`/屏幕阅读器仍能理解横线代表得分者无法确认。

### Task 1: 用回归测试固定错误与正确行为

**Files:**
- Modify: `frontend/components/match/match-points.test.tsx`

- [x] 构造同一展开局中的两个 null winner、一个无法对应到本场球员的 winner 和一个已知 winner；断言旧“胜者待定”不再出现，未知项有一条说明和三个可访问占位，已知球员名称与各行比分仍出现。
- [x] 运行 `cd frontend && ./node_modules/.bin/vitest run components/match/match-points.test.tsx`，确认新增断言针对当前 fallback 失败（RED）。

### Task 2: 在唯一负责的 UI 层最小修复

**Files:**
- Modify: `frontend/components/match/match-points.tsx`
- Modify: `docs/research/2026-09-24-tennixai-t95-match-field-integrity-matrix.md`

- [x] 对全部 points 检查是否存在 null 或无法对应参赛球员的 winner；存在时在时间线顶部只显示一次“部分逐分记录无法确认得分者”。
- [x] 每个未知 winner 行显示 `—`，并包含 sr-only 文本 `得分者未能确认`；移除可见的“胜者待定”。已知胜者仍通过现有 `PlayerName`。
- [x] 更新字段矩阵中 winner/quality 的页面消费事实，记录时间线中性显示和一次性说明。
- [x] 全量前端 Vitest（41 files / 524 tests）、TypeScript `tsc --noEmit` 与 `git diff --check` 通过；新增 UI 回归先 RED 后 GREEN。

### Task 3: 关闭任务并推送

**Files:**
- Modify: `CURRENT.md`, `ROADMAP.md`

- [ ] 审阅差异和精确暂存文件，确认用户既有的 P3 工作区改动未被暂存。
- [ ] 记录真实验证结果、实现提交、保留的边界和未执行的运行时检查；将 T106 标记 done。
- [ ] 提交并推送到 `origin/main`，最后核对远端 HEAD 与工作区状态。
