# v0 P3 Market & Decision Support 页面交付 Prompt

请在我现有的 TennixAI Next.js 项目视觉体系中，完成 P3 Market & Decision Support 的生产级响应式原型。你需要扩展三个现有产品面：

1. Home：把现有 `Market Intelligence` 占位升级为紧凑「市场脉搏」；
2. `/markets`：新增“机会 / 全部市场 / Paper 账本”页面；
3. Match Page：在现有 Hero 后加入全宽 `DecisionSummary`，并补齐概率—市场轨迹、判断依据和 paper lifecycle。

这是现有产品的严格延伸，不是全站重设计。必须复用当前深色网球数据终端风格、颜色 token、字体、圆角、卡片、按钮、header、间距、信息密度和响应式习惯。不要修改 Home 的搜索/赛程主体、Player 页面、Match Hero、比分、统计、PBP 或助手的既有视觉语言。

技术栈保持 Next.js 16 App Router、React 19、TypeScript、Tailwind CSS、shadcn/ui、lucide-react、Recharts。不要引入新的 UI 框架、图标包、CSS-in-JS 或状态库。

## 产品语义

TennixAI 是 Tennis Data / Intelligence Product + Conversational Interface。P3 是研究型市场情报与 paper decision support，不是真实交易终端。

- 首版只展示网球单场比赛胜者市场；
- 模型覆盖只用于大满贯和 ATP/WTA 主巡赛单打；
- Challenger/ITF 仍展示市场，但不显示“未覆盖”“低级别”等负向标签，也不给模型建议；
- 固定 paper stake 为 `$10`；
- 不显示真实下单、钱包、充值、余额、Connect Wallet 或交易确认按钮；
- 不提供手动 paper BUY/SELL 按钮；动作和生命周期由后台状态驱动；
- 所有链接只使用内部 `match_id` / `market_id`，样例使用 `mat_preview_*` / `mkt_preview_*`，不得出现 provider ID、condition ID、token ID 或 API key。

## 全站导航

复用现有 `ProductHeader`：

- 将现有“市场 BETA”链接到 `/markets`；
- `/markets` 将“市场”标记为 active；
- Match Page 保持“赛程/直播”现有 active 语义；
- 不重做 logo、搜索、通知、用户菜单或移动导航；
- BETA 可以保留，但不要增加“自动交易”暗示。

## 全局状态语言

以下状态必须保持语义一致：

- `MARKET ONLY / 仅市场`：只显示市场价格、深度和 freshness；
- `NO BET / 暂不参与`：当前没有可论证的正 edge，必须显示原因；
- `WAIT / 等待价格`：已有明确低估方向，但当前价格未过门，显示“最高可接受价”；
- `BUY / 发现机会`：后台刚产生首个合格 signal，随后立即进入 pending；
- `ENTRY PENDING / 模拟入场中`：等待 sports delay 后的 FOK 检查，绝不能表现成已成交；
- `MISSED / 未成交`：唯一入场尝试未完整成交，不再追价；
- `HOLD / 继续持有`：paper position 已存在，当前继续持有价值更高；
- `SELL / 建议退出`：后台产生唯一退出 intent；
- `EXIT PENDING / 模拟退出中`：等待全仓 FOK 检查；
- `EXITED / 已退出`：显示 realized P&L；
- `EXIT MISSED / 退出未成交`：不再重试，持有至结算；
- `SETTLED / 已结算`：显示 EV 主轨道、HODL 与 convergence-lock 对照；
- `STALE / GAP / 数据暂不可验证`：覆盖在现有状态上，保留最后可信数字与时间，但撤销新的 BUY/SELL。

状态不能只用红绿颜色表达。每种状态需要文字、Lucide icon、badge/边框或底色的组合；pending 使用中性或琥珀色，不使用成功绿色。

## 页面一：Home「市场脉搏」

用一个紧凑模块替换当前 `Market Intelligence` 占位，不新增第二个市场区块。

### 布局

- 标题“市场脉搏”，副标题表达“模型与可执行市场价格的实时对照”；
- 右上角提供“查看全部”链接到 `/markets`；
- 最多三行，不做巨型卡片、图表或横向 ticker；
- 有开放 paper position 时固定占一行；剩余行展示 live BUY、upcoming BUY、WAIT；
- 整行可点击到 `/matches/{matchId}`，不放行内交易按钮。

### 每行字段

- Live / Upcoming / Position / Stale 状态；
- 赛事与两位球员，英文主名、中文辅名遵循现有展示规则；
- 当前模型方向和概率；
- 固定 `$10` 可执行市场概率；
- 当前动作；
- freshness，例如“刚刚”“12 秒前”“数据暂不可验证”。

### Home preview states

1. `pulse-populated`：一条开放 HOLD position、一条 live BUY、一条 upcoming WAIT；
2. `pulse-position-stale`：开放 position 保留最后可信数值并显示 stale overlay；
3. `pulse-empty`：文案“暂无可执行机会”，保留“查看全部市场”。

## 页面二：`/markets`

### 页面头部

- 标题“市场与决策”；
- 简短说明“Polymarket 单场胜者市场 · `$10` paper evaluation”；
- 不显示钱包、账户余额或下单 CTA；
- 页面级 tabs：`机会`、`全部市场`、`Paper 账本`；
- tab 可键盘操作、焦点清晰，移动端不横向溢出。

### 视图 A：机会

只展示模型覆盖的大满贯与 ATP/WTA 主巡赛单打中的 `BUY` 和 `WAIT`。排序为 Live 在前、Upcoming 在后。

桌面采用高密度列表/宽卡，移动端采用单列紧凑卡。每项显示：

- Live/Upcoming、开赛时间、赛事/轮次/场地；
- 两位球员；
- 当前模型方向；
- 模型概率；
- `$10` executable average price；
- conservative net edge；
- `BUY` 或 `WAIT`；
- WAIT 时显示最高可接受价格；
- model + market freshness；
- 整项点击进入 Match Page。

不得显示“立即买入”按钮。

状态：populated、empty（“当前没有通过全部条件的机会”）、partial stale（保留列表并在受影响项上降级）。

### 视图 B：全部市场

展示所有可用 tennis moneyline，默认按 ATP/WTA → Challenger → ITF → Other，再按 Live → 开赛时间。

筛选项采用现有 Home chip 语言，可叠加：

- 赛事级别：ATP/WTA、Challenger、ITF、Other；
- 性别：男子、女子、全部；
- 阶段：赛中、赛前、全部。

模型覆盖项目显示双边模型概率、可执行价格及 `NO BET` reason；低级别比赛只显示两边可执行价格、spread/depth、freshness，不显示“未覆盖”badge。

区分三个空态：

- 供应商当前没有网球市场；
- 当前筛选没有结果；
- 市场可见但实时订单簿暂不可验证。

### 视图 C：Paper 账本

顺序固定为：pending → open positions → recent exited/missed/settled。

每项显示：

- 比赛和持仓方向；
- `$10` entry cost、average entry price、shares；
- 当前 executable exit value；
- 主轨道状态；
- net P&L；
- freshness；
- terminal 项显示 realized/settled P&L；
- 点击进入 Match Page 查看完整 lifecycle。

HODL 与 convergence-lock 是对照结果，不要渲染成另外两笔真实持仓。

状态：open + recent、empty（“暂无 Paper 记录”）、resolution pending、stale。

## 页面三：Match Page

### 桌面结构

严格按下列顺序：

1. 保留现有 Match Hero；
2. Hero 下新增跨越主栏和侧栏的全宽 `DecisionSummary`；
3. 下方继续两栏；
4. 主栏依次是：比赛概览、详细比分/比赛进程、概率—市场轨迹、判断依据与 hard gates、技术统计、近期控制/PBP、paper lifecycle；
5. 右侧粘性栏只保留 Match Assistant 和关键事实；
6. 删除现有侧栏 `MarketCard` 占位；
7. 删除主栏重复的 AI Insights/问题建议卡，示例问题归入 Assistant。

### `DecisionSummary`：持仓前

顶部先给一句结构化结论和唯一当前动作，例如：

- “模型认为 Sinner 被低估，但当前价格尚未达到入场条件”；
- `WAIT · 最高可接受价 0.58`。

主体必须双边对照，两位球员分别显示：

- model probability；
- `$10` executable average buy price；
- conservative net edge。

推荐方向可以高亮，但不得隐藏另一边。两侧市场价格不要强制归一成 100%。

底部显示：hard gates、最高可接受价格（适用时）、两条输入 freshness、decision/model version。详细图表不塞进摘要。

### `DecisionSummary`：position

paper fill 后同一组件原地变为 position 管理，不在下面叠加第二张 BUY 卡。显示：

- 持仓球员；
- entry cost / average price / shares；
- 当前 executable exit value；
- net P&L；
- uncertainty-adjusted hold value；
- 主动作 `HOLD` 或 `SELL`；
- `LOCK PROFIT` 如适用，必须单独标为“可选降风险”，不能与主动作同级。

### Probability & Market Trajectory

- 同一时间轴显示 model probability 与 executable market probability；
- model line 和 market line 使用颜色 + 线型双重区分；
- model uncertainty 使用半透明 band；
- stale/gap 必须断线或阴影，不得插值成连续曲线；
- 标记 entry、exit intent、fill/no-fill 和 settlement；
- tooltip 包含本地时间、score context、model、market、action 和 freshness；
- 图下提供可访问的最新值摘要或数据表；
- 不使用 flashing、自动滚动或持续动画。

### Decision Evidence & Gates

只展示结构化证据：surface rating、赛前 prior、当前比分/发球方、live evidence、data quality、model disagreement、market mapping、rules、liquidity、freshness 等。

- 分为“支持当前判断”“限制与风险”“硬门状态”；
- 每项有确定性 label、方向和简短解释；
- 不显示 LLM 自造的“某因素贡献 +12%”；
- `NO BET` 必须直接指明哪个 gate 失败。

### Paper lifecycle

从未产生 intent 时整块隐藏。产生后永久保留时间线：

- signal observation；
- ENTRY_PENDING；
- FILLED 或 MISSED；
- HOLD/SELL observations；
- EXIT_PENDING；
- EXITED 或 EXIT_MISSED；
- resolution pending / SETTLED；
- HODL 与 convergence-lock 的最终对照。

每个节点显示本地时间、价格/费用/book version 的用户可读摘要和状态原因。不要显示 provider IDs 或完整 raw order book。

### Match mobile 顺序

移动端必须重排为：

1. Hero；
2. `DecisionSummary`；
3. 详细比分；
4. 关键事实/比赛概览；
5. 概率—市场轨迹；
6. 判断依据/hard gates；
7. 技术统计；
8. 近期控制/PBP；
9. paper lifecycle（若存在）；
10. Match Assistant。

Hero 和 Summary 都保留“问这场比赛”入口，点击后滚动并聚焦 Assistant。不要增加永久占屏的 BUY/SELL 浮动按钮。

## Match preview state switcher

原型必须可切换以下全部状态，切换只用于 preview，不出现在生产页面：

```text
market_only
no_bet
wait
buy
entry_pending
missed
hold
sell
exit_pending
exited
exit_missed
settled
stale
gap
```

`stale/gap` 应可叠加在 wait、entry_pending、hold 和 exit_pending 上。pending + unverifiable 的样例必须显示“无法验证订单簿，因此未模拟成交”，不能自动跳成 filled。

## Loading、错误与局部降级

- 页面首次加载使用与最终结构同形的 skeleton；
- 单一数据源失败时保留另一侧和最后可信数据；
- stale 不把数字清成 `—`，显示最后可信时间并撤销动作；
- 完整页面失败才显示居中 error + retry；
- empty 不使用红色 error 样式；
- WebSocket 恢复时用低打扰 status，不能自动滚动；
- 所有更新区域避免 layout shift，并尊重 `prefers-reduced-motion`。

## 可访问性与视觉约束

- 不使用 emoji 作为 icon，统一 Lucide；
- heading 层级连续；
- 所有可点击卡片、tabs、chips 和链接有 keyboard focus 与 hover feedback；
- 颜色不是唯一状态编码；正文对比度至少 4.5:1；
- 图表有 legend、line pattern 和文本摘要；
- 触控目标至少 44px；
- 在 `390×844`、`768px`、`1024px`、`1440×1000` 无横向滚动；
- hover 不使用导致布局移动的 scale；
- 使用现有设计 token，不在组件内硬编码一套新品牌色或字体。

## Preview data 要求

样例必须覆盖：

- ATP/WTA 主巡模型覆盖；
- Challenger/ITF market-only；
- Live 与 Upcoming；
- 两侧 ask 不互补；
- 有费用/深度影响的 `$10` executable average；
- WAIT max price；
- NO BET 的 model agreement、stale、liquidity、rules changed 原因；
- FOK fill/no-fill；
- positive、negative 和 50–50 settlement；
- rule/resolution pending；
- HODL、EV exit、convergence-lock 三轨结果。

所有金额、概率、时间和分数必须内部一致。例如 `$10 / 0.50 = 20 shares`，费用和 P&L 不能出现明显算术矛盾。

## 交付范围

请输出：

- Home 新 Market Pulse preview；
- `/markets` 完整 preview 页面；
- Match Page P3 preview 扩展；
- 明确拆分、可复用的组件；
- 确定性 preview data；
- preview state switcher；
- 桌面 `1440×1000` 与移动 `390×844` 均可检查的状态。

不要接真实 API，不要实现后端，不要加入 wallet/真实交易，不要修改现有业务调用。原型的职责是冻结视觉和状态行为，后续 ADE 会严格按这个设计接真实 structured response。
