# T98 — 全产品缺陷与字段真相审计规格

**状态：** 按当前 Goal 执行中
**日期：** 2026-09-24
**目标来源：** 当前 Goal：“走查全部问题，修正所有 bug。除此之外其他的字段都要查清楚。”

## 目标与成功标准

从普通用户看到的页面出发，沿每个字段追到其数据契约与来源，找出并修复审计中可复现的缺陷。完成时，所有用户可见字段和支撑它们的公开 API、SSE、Chat 结构化字段都能说明：来源是供应商事实、内部计算还是展示派生；经过哪些转换；单位/时区是什么；在缺失、无效、部分、过期、断流或错误时如何表现；由什么测试或浏览器证据证明。

“查清楚”不等于把未知供应商行为猜成确定值。官方资料未说明的语义必须明确标成未知，并保持空值/不可用，不得伪造。对全部范围完成代码和 fixture 验收，不代表真实供应商、本地数据库或真实运行时已经通过。

## 已知用户约束

- 目前继续使用演示数据和 fixtures；不运行 `tennix-live init`，不做数据库初始化。
- 不调用真实网球数据 API、LLM 或 Polymarket；不执行任何真实交易。
- 根目录 `.env` 是敏感配置，不读取、输出、修改或提交；不访问/修改 `.next`。
- 保留开始任务前已存在的所有工作区改动，不覆盖、不顺手提交。
- 沿用产品边界：canonical model 是业务事实来源，供应商字段不泄漏到业务/UI；无依据的值保持未知；Paper 始终是模拟交易。

## 审计范围

### 用户页面

- Home：赛事发现、筛选、Live/Upcoming、球员搜索、结构化结果、全局问答和历史问答。
- Players：ATP/WTA 排名目录、搜索/别名解析、球员资料、赛季摘要、当前比赛、历史赛果及分页/筛选。
- Match：比赛身份/状态/时间/双方/赛事/场地/比分/发球方、统计、PBP、momentum、数据质量、实时连接、上下文 Chat、市场与决策工作台及 Paper 生命周期。
- Markets：机会、全部市场、Paper 账本各视图中的筛选、报价、深度、概率、动作、可用性、空态和导航。
- 跨页：加载、错误、空、partial、stale、gap、未知枚举、时间/金额/百分比格式、响应式布局，以及返回/刷新和 SSE 重连行为。

### 数据契约与链路

审计所有公开 REST/Next.js 代理、SSE 和 Chat 事件 DTO 字段（即使当前页面没有消费，也要标出“未消费/仅技术用途”），以及支撑它们的 canonical/domain 字段。对每个链路按以下顺序查证：

`Provider DTO / official contract → provider mapping → canonical model / reducer → persistence or cache → service / API / SSE / Chat → frontend decoder / view model → rendered field`

覆盖至少以下领域：

1. 比赛目录与筛选：Match/Player/Tournament 标识、状态、级别、性别、单双打、日期、轮次、场地及分页/facets。
2. 比赛实时信息：比分、盘/局/分、发球方、连接状态、版本、freshness、PBP、统计、momentum 和 capability quality。
3. 球员与历史：内部身份、多语言别名、国籍、排名/积分/日期/变动、资料/年龄/赛季记录、当前比赛、赛果和 H2H 的完整性。
4. Chat：请求范围/上下文、工具结果、结构化数据、历史结果、进度、警告、错误、完成事件和答案字段。
5. Markets/P3：市场身份和映射、赛前/赛中状态、双边 quote、quote source/state/time、spread/depth、模型覆盖/概率、机会理由、决策 gates、Paper 资金/份额/状态/事件/P&L/freshness。
6. 跨域运行质量：运行健康和来源状态中实际影响用户数据可用性的字段，以及错误、空值、时钟、重连和状态恢复。

只存在于内部、不会影响用户可见内容或上述公开契约的实现临时字段不要求展示；若它们改变对外结果，必须追到产生该影响的位置并纳入相关字段行。

## 审计方法与证据等级

采用推荐的端到端字段域方式，而不是只截图逐页扫视，也不是只检查 schema：

- 每个页面/字段域先列完整字段，再追踪数据链路，最后用对应组件、用例和桌面/窄屏浏览器状态验证。
- provider 语义优先查供应商官方文档与官方示例；Polymarket 规则/报价语义查 Polymarket 官方资料。只引用确实支持该字段的文档；未公开的语义不得类推。
- 每行字段至少记录：canonical/API 名称、类型和单位、权威来源、转换/持久化、消费位置、null/invalid/partial/stale 规则、证据、结论。
- 结论使用明确状态：`contract-verified`（公开/官方契约、代码映射到前端消费均有确定性测试证据，不代表真实在线 API 已验证）、`code-tested`（代码与 fixture 有证据但供应商语义或完整链路仍未证实）、`provider-unknown`、`unavailable-by-contract`、`not-consumed`、`bug-fixed`、`blocked`。不得把 mocked/fixture 测试写成真实数据验收。
- 每个 bug 必须有可重复的输入或状态转换、根因位置、失败测试、最小修复和通过后的回归证据；未经定位不做猜测性重构。
- 新发现的字段记入现有 T95–T97 字段矩阵附录；若新领域使矩阵难以理解，再拆出独立附录并互相链接。

## 修复与验证原则

- 按独立领域串行推进：字段清单 → 源头/契约 → mapping/存储/传输 → UI 与状态 → 回归测试。只修复已证明的问题，不扩展产品功能或改变已确认语义。
- 改动逻辑前先为根因写失败测试；修复后跑最小定向测试，再跑受影响模块及相应 UI 用例。
- 全部字段域完成后，执行前后端确定性测试、前端类型检查和覆盖所有产品页/核心状态的桌面与窄屏 Playwright；逐项确认测试确实覆盖目标字段，而非只看总通过数。
- 集成门若需要 Redis/PostgreSQL，但当前演示环境未运行，仅标明实际限制；不得为绕过限制运行首次初始化或把本地演示数据当成真实验证。
- 完成记录必须保留尚不能验证的 provider/运行时边界，并更新 `CURRENT.md`、`ROADMAP.md` 与字段矩阵。

## 当前验证进度（2026-09-25）

- 首次 Home 目录读取的懒加载竞态已通过 RED→GREEN 修复：目录排名与别名同步完成前不读取并覆盖比赛卡球员资料；并发首调会等待同一轮同步结束。后端定向服务、目录同步、球员解析和 Chat 工具测试 `103 passed`；Ruff lint 通过。四个被检查的 Python 文件在任务起始 HEAD 已不符合当前 Ruff formatter，故没有对整文件进行格式重排。
- 当前 UI 在隔离 `/tmp` 副本以 fake provider/LLM、P3 disabled、固定时钟运行；`env -i` 清洁环境，不复制 `.env`，不读项目 `.next`，不初始化数据库或调用真实服务。功能 Playwright `80 passed`，首页问答另 `4 passed`，视觉 Playwright `30 passed / 4 skipped`；P2 Replay 的 4 项在 fake mode 跳过，P1 Match live/upcoming 截图视觉用例因 Redis 依赖未计入通过。76 张桌面/移动截图由演示数据重生成，并经同一隔离环境逐屏比对；不代表真实 API/运行时验收。
- Vitest `36 files / 484 passed`、隔离副本 Next production build（含 TypeScript 检查）、source check `173 files` 及 DTO 字段名矩阵盘点（TS 211 / Pydantic 100，零遗漏）均通过。后端最新完整确定性套件以 `env -i` 运行，为 `1332 passed / 128 skipped`。pytest bootstrap 在导入模块级 ASGI app 前让未显式指定的 `Settings` 使用 `_env_file=None`，但不改生产 `Settings.model_config` 的根 `.env` 默认；临时非敏感哨兵 `.env` 回归先红后绿，随后完整测试在仓库通过，根 `.env` 未读取。API/Chat 测试注入已有内存 `RealtimeBundle`，不依赖本机 Redis/PostgreSQL。REST `FINAL` 现经 publisher 发出 `resolution_delta`；WS 提示核验、定时兜底与公开 SSE 契约均有测试覆盖，相同终态不会重复广播。改动文件 Ruff lint 与 `git diff --check` 通过。真实 provider/LLM/Polymarket 与需要 Redis/PostgreSQL 的实时集成验收仍未执行；用户已明确选择暂不初始化。

## 不在此规格授权内

- `init`、真实 API/LLM/Polymarket 请求、数据库初始化或真实交易。
- 引入新供应商、产品能力、数据模型层、预测/交易策略或架构迁移。
- 仅为消除测试失败而改变用户未授权的本地数据或共享运行服务。
