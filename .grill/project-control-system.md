# Grill: 项目总控与跨 ADE 接力机制

Date: 2026-09-08

## Intent

建立一套由人和 Agent 共同使用的项目总控机制。无论项目暂停多久，或在 Codex 与 Claude Code 之间切换，使用者都应能在 5 分钟内恢复对项目目标、整体进度、当前任务、验证状态和下一步动作的理解。

## Constraints

- 根目录的 `PROJECT.md`、`ROADMAP.md`、`CURRENT.md` 是唯一的项目总控文件。
- 三份总控必须以中文和人类阅读体验为主，同时保留稳定的英文状态标识、路径和命令供 Agent 精确执行。
- 同一时间只允许一个当前主任务，且必须绑定一个执行者、环境和工作分支。
- Codex 与 Claude Code 都需要各自的启动入口，但入口文件不得复制项目状态。
- 任务只有在验收命令实际通过并留下证据后才能标记为 `done`。
- 未提交改动必须保留；无法确认归属时，Agent 必须停下询问，不能覆盖。
- P1 保持轻量，不为总控机制增加数据库、锁服务、Git hook 或其他自动协调系统。

## Key decisions

- Decision: 使用 `PROJECT.md`、`ROADMAP.md`、`CURRENT.md` 作为根目录三份总控。 Reason: 分离稳定背景、全局路线与短期执行状态，避免单文件膨胀。 Alternative considered: 用一个总文档承载全部内容，因长期可读性和更新冲突而放弃。
- Decision: 产品意图与优先级以三份总控为准；运行事实以代码、测试和 Git HEAD 为准，出现冲突时立即修正总控。 Reason: 避免过期文档覆盖已验证事实，同时保持产品决策的唯一来源。 Alternative considered: 无条件以文档或代码单方为准，均无法覆盖两类不同事实。
- Decision: `PROJECT.md` 在产品边界或架构原则改变时更新；`ROADMAP.md` 在阶段、任务或验收门变化时更新；`CURRENT.md` 在任务开始、完成可验证节点、阻塞或交接时更新。 Reason: 兼顾稳定性与接力所需的新鲜度。 Alternative considered: 仅在阶段完成时统一更新，因过程状态会长期过期而放弃。
- Decision: `ROADMAP.md` 同时跟踪 P1.0–P1.6 阶段和 15 个实施任务。 Reason: 阶段适合看全局，任务粒度才足以准确接力。 Alternative considered: 只跟踪阶段，信息过粗。
- Decision: `CURRENT.md` 只保留一个主任务、最近一次交接和最多 5 条近期变更。 Reason: 保持快速阅读；长期证据进入路线图，完整历史由 Git 保存。 Alternative considered: 把它作为无限追加的工作日志，因会逐渐失去可读性而放弃。
- Decision: 任务领取、完成、阻塞或交接时更新总控、提交并推送；开发过程中允许未提交改动，但此时不得跨 ADE 接手。 Reason: 让远程仓库成为可靠同步点，同时避免为每个微小步骤制造提交。 Alternative considered: 每一步都提交，开销过高；完全依赖本地文件，无法跨设备同步。
- Decision: 为 Codex 创建 `AGENTS.md`，为 Claude Code 创建 `CLAUDE.md`，二者只负责引导读取共同总控。 Reason: Git 中存在文件不代表每个 ADE 会自动读取。 Alternative considered: 在每个入口复制项目状态，因必然产生漂移而放弃。
- Decision: 当前任务占用不自动过期。接手者必须检查 Git、保留已有成果、显式更新执行者和交接说明。 Reason: 项目可能暂停数月，时间不能证明工作已经废弃。 Alternative considered: 基于时间自动释放任务，可能导致成果被覆盖。
- Decision: 使用 GitHub `origin` 作为跨设备同步通道。 Reason: 项目需要超越本机工作目录的连续性。 Alternative considered: 只做本机跨 ADE 同步，覆盖范围不足。
- Decision: P1 的唯一主任务直接在 `main` 领取、执行、交接和完成。 Reason: 若只在功能分支更新 `CURRENT.md`，从 `main` 启动的另一个 ADE 无法看到任务占用；单人单任务阶段直接使用 `main` 最轻且同步语义明确。 Alternative considered: 每任务功能分支，因需要额外的跨分支协调源而暂缓；隔离实验仍可在用户明确批准并先写回 `main` 后使用分支。

## Surfaced assumptions

- “跨 ADE 同步”同时包含 Agent 自动发现上下文和人类长期恢复上下文，两者缺一不可。
- Git 是同步与审计基础，但不能代替显式交接，也不能锁住另一个 Agent。
- 详细规格和实施计划继续保留在 `docs/`，三份总控只摘要并链接，不重复整篇内容。
- Codex 与 Claude Code 是当前实际使用的两个 ADE；不为尚未使用的工具提前增加入口。
- P1 是单人、单主任务工作流；若以后需要多人或并行任务，必须重新设计分支与锁定策略。

## Out of scope

- 自动任务锁、租约和超时释放。
- Git hook、CI 强制校验或外部协调服务。
- 为 Cursor 或其他尚未使用的 ADE 创建入口。
- 默认使用功能分支或并行 worktree。
- 在总控文件中复制详细技术规格或逐步实施说明。
