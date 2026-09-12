# v0 球员目录与球员详情页交付 Prompt

请在我现有的 TennixAI Next.js 项目视觉体系中，补齐两个生产级响应式页面：

1. `/players`：ATP/WTA 单打世界排名与球员搜索；
2. `/players/[playerId]`：球员个人详情与历史赛果。

这是现有产品的延伸，不是全站重设计。请严格复用项目已有的深色网球数据终端风格、颜色 token、字体、圆角、卡片、按钮、header、间距、信息密度和响应式习惯。不要修改 Home Page、Match Page 或它们的视觉语言。技术栈保持 Next.js 16 App Router、React 19、TypeScript、Tailwind CSS、shadcn/ui、lucide-react。

## 产品背景

TennixAI 是 Tennis Data / Intelligence Product + Conversational Interface，不是通用 chatbot。Home 用于全局发现、赛程和问答；Match Page 用于单场调查。新增 Player 页面用于排名发现、球员身份和历史结果，不增加 Player Chat。

所有 UI 只使用 TennixAI 内部 `player_id` / `match_id`。不要在界面、URL、样例文案或组件 props 中展示 API-Tennis 的 `player_key`、`event_key` 等供应商 ID。

球员名称展示规则固定为：

- 英文为主；
- 简体中文为辅；
- 例如主标题 `Ben Shelton`，副标题 `本·谢尔顿`；
- 不显示“AI 翻译”“系统生成”“可人工纠正”等来源标签。

## 全站导航

复用现有 `ProductHeader`。

- `球员` 导航链接到 `/players`；
- 两个 Player 页面都将 `球员` 标记为 active；
- 搜索框、通知、用户菜单和移动导航保持现状；
- 不重做 logo 或 header。

## 页面一：`/players`

### 页面目标

默认提供 ATP/WTA 单打 Top 200 世界排名；用户输入搜索词后切换为完整球员目录搜索，因此可以找到 Top 200 之外或暂无当前排名的球员。

### 默认排名状态

- 页面标题明确是“球员排名”或语义等价的产品化标题；
- ATP / WTA 两个主 tabs，默认 ATP；
- 只做单打，不出现双打 tab 或双打筛选；
- 每页 50 人，总范围 Top 200；
- 默认按官方排名从 1 到 200，不提供热度/积分排序切换；
- 国家筛选；
- 一个明显但不过度抢眼的“中国球员”快捷筛选；
- URL 状态应能表达 tour、page、country、q。

排名表每行包含：

- 当前名次；
- 排名变动：上升、下降、不变；
- 球员英文名；
- 球员中文名；
- 国家旗帜和国家信息；
- 积分；
- 清晰的整行可点击 affordance，进入 `/players/[playerId]`。

桌面端使用信息密度适中的数据表，不要做成巨型卡片瀑布流。移动端可以把每行压缩为卡片式列表，但必须保持排名、双语名、国家、积分和变动可读，触控目标足够大。

### 搜索状态

页面内有专门的球员搜索输入，支持示例：

- `Ben Shelton`
- `Shelton`
- `B. Shelton`
- `本·谢尔顿`
- `谢尔顿`

有搜索词时，不再只过滤当前 Top 200，而是显示“全目录搜索结果”。

搜索结果需要覆盖：

- Top 200 内球员；
- Top 200 外球员，例如排名 201；
- 暂无当前排名的球员，文案固定为“暂无当前排名”；
- 多个同姓候选；
- 无结果普通空态，不使用红色系统错误样式。

候选项显示英文主名、中文辅名、国家、ATP/WTA 身份、排名或“暂无当前排名”。

### 分页

- 排名每页 50；
- 显示当前 1–50 / 51–100 / 101–150 / 151–200 的清楚反馈；
- Previous/Next 在边界正确 disabled；
- 切换 ATP/WTA、国家或搜索词时回到第 1 页；
- 移动端分页不可横向溢出。

## 页面二：`/players/[playerId]`

### Profile header

必须包含：

- 球员头像；
- 英文主标题；
- 中文副标题；
- 国家旗帜和国家；
- 生日与年龄（数据可用时）；
- 当前单打排名；
- 当前积分；
- 排名变动。

同时设计头像缺失、生日缺失、排名缺失状态。缺失时保持卡片结构稳定，不猜测内容。

### 赛季概览

展示当前选中赛季：

- 胜场；
- 负场；
- 胜率；
- 冠军数；
- 硬地胜负；
- 红土胜负；
- 草地胜负。

某种场地统计缺失时显示 unavailable 语义，不显示 `0–0` 冒充真实统计。视觉上保持网球分析终端风格，但不要增加预测概率、赔率、edge 或市场模块。

### 当前状态

使用一个紧凑、可点击的区块：

1. 有 live 比赛时优先展示 live 状态、对手、赛事、当前比分；
2. 无 live 但有下一场时展示对手、赛事和开赛时间；
3. 两者都没有时精确显示：`暂无比赛信息`。

比赛存在时点击进入 `/matches/[matchId]`。不要在该区块实现自动轮询或 WebSocket 逻辑，只完成视觉和交互结构。

### 历史赛果

默认当前赛季，可选择当前赛季及前四个赛季。包含叠加筛选：

- season；
- tournament tier：全部、ATP/WTA、Challenger、ITF；
- outcome：全部、胜、负。

明确不提供 surface 筛选。

每页 20 场。每场至少展示：

- 日期；
- 赛事和轮次；
- 对手；
- 胜/负；
- 终场比分；
- 已知时可显示场地，未知时不留误导占位；
- 点击进入现有 `/matches/[matchId]` Finished Match Page。

需要设计：

- 有结果；
- 筛选后无结果；
- 历史能力 partial；
- 历史能力 unavailable；
- loading skeleton；
- provider/error + retry；
- stale 数据仍展示并带轻量提示。

## 状态和数据样例

请在独立 preview data 文件中提供确定性样例，覆盖：

- ATP 与 WTA；
- 中国与非中国球员；
- rank 1、rank 50、rank 200、rank 201、无排名；
- movement up/down/same；
- `Ben Shelton / 本·谢尔顿`；
- `Qinwen Zheng / 郑钦文`；
- `Novak Djokovic / 诺瓦克·德约科维奇`；
- 两个同姓候选；
- profile 有头像和无头像；
- live、next、`暂无比赛信息`；
- 当前及前四赛季；
- 足够触发 20 场分页的数据。

样例数据必须只存在于 preview/demo 路径，不能混入未来 production fetch 路径。

## 响应式与可访问性

- 桌面基准：1440×1000；
- 移动基准：390×844；
- 无横向滚动；
- sticky header 保持可用；
- tabs、筛选、分页、搜索和行点击支持键盘；
- 有语义化 heading、table/list、label、aria-current 和可见 focus；
- 不只靠颜色表达升降、胜负、live 和 error；
- 尊重 `prefers-reduced-motion`；
- 中文与英文长姓名不能截断到无法辨认。

## 视觉约束

- 保持现有深色 `#09110f` 附近背景和项目 token，不硬编码另一套主题；
- 保持 Noto Sans SC + Geist Mono 体系；
- 重点用现有 primary/live/premium 等语义色；
- 卡片边框、阴影、圆角、blur 与现有 Home/Match 一致；
- 数据表可紧凑，但不能像传统后台管理系统；
- 不使用大面积渐变 hero、营销插画、玻璃拟态重做或与现有产品无关的网球照片墙；
- 不新增依赖，优先复用已有 shadcn/ui 和 lucide-react。

## 代码交付要求

请输出可直接合入现有仓库的代码，组件按职责拆分，不把两个页面都塞入一个巨型文件。至少包含：

```text
app/players/page.tsx
app/players/[playerId]/page.tsx
components/players/players-page.tsx
components/players/rankings-table.tsx
components/players/player-search-results.tsx
components/players/player-profile-page.tsx
components/players/player-profile-header.tsx
components/players/player-season-summary.tsx
components/players/player-current-status.tsx
components/players/player-results.tsx
components/players/player-preview-data.ts
```

页面组件通过 props 消费 typed preview data；此轮不要连接真实 API，不要读取环境变量，不要改变 Home/Match 数据逻辑。输出后请给出桌面和移动两种页面的完整可视预览，确保所有状态都有可以切换检查的展示方式。

