# TennixAI 球员目录、多语言身份与历史赛果设计规格

**状态：** 已批准；用户已免除设计审阅停点，可直接进入实施计划
**日期：** 2026-09-12
**所属阶段：** P2.6 — Player Discovery and Multilingual Identity
**交付目标：** 本地完整运行、私人测试、最多分享给少量好友
**前置基线：** P2.5 已完成，当前产品提交 `5c3d469`，最新总控基线 `aa8b11e`
**实施计划：** [P2.6 实施计划](../plans/2026-09-12-tennixai-player-directory-multilingual-identity-implementation.md)
**v0 交付：** [球员页面 v0 Prompt](../../v0/2026-09-12-player-pages-prompt.md)

## 1. 结论

TennixAI 增加一个共享的球员身份层，把 `/players`、球员详情、历史赛果、Home Chat 和 Match Chat 统一到同一个内部 `player_id`。系统先在离线同步阶段建立英文名、中文名及常见缩写/变体的别名库，运行时只做确定性解析，不调用翻译 LLM。

用户可从 `/players` 查看 ATP/WTA 单打 Top 200，搜索目录内全部已知球员，再进入 `/players/[playerId]` 查看资料、赛季统计和历史赛果。显示以英文为主、中文为辅；搜索同时支持英文、中文、姓氏、姓名顺序、供应商缩写、大小写、标点和重音差异。

```text
API-Tennis standings / players / fixtures
                  ↓
          PlayerDirectorySync
                  ↓
 Player + PlayerExternalId + Ranking
                  ↓
 PlayerAliasEnricher（可信来源优先，LLM 补缺）
                  ↓
              PlayerAlias
                  ↓
              PlayerResolver
        resolved | ambiguous | not_found
                  ↓
 TennisService / REST DTO / Home Chat / Match Chat
```

该设计解决当前 `Ben Shelton` 无法匹配供应商 `B. Shelton`、中文姓名无法查询、页面与 Chat 可能各维护一套名字的问题。供应商、LLM 或 UI 可以替换，内部球员身份、别名语义和 resolver 契约保持稳定。

## 2. 当前问题与证据

### 2.1 已验证的失败链路

当前 Home 全局助手调用 `find_player_matches` 后，`TennisService._resolve_player()` 依赖 provider 的 `search_players()`。API-Tennis adapter 只扫描 live 和未来三天 fixtures，并对供应商返回的比赛内联姓名做字符串包含匹配。

供应商比赛数据可能使用 `B. Shelton`，因此：

- `B. Shelton` 可以命中；
- `Shelton` 可以命中；
- `Ben Shelton` 不能命中；
- `本·谢尔顿`、`谢尔顿` 不能命中。

未命中随后成为 `not_found`，核心工具失败又被提升为终止 SSE `error`。这同时暴露了三个结构性问题：

1. 搜索候选受“正在比赛或近期有赛程”限制，不是真正的球员目录；
2. 业务层仍通过名字反查供应商，而不是先解析内部身份再按外部 ID 查询；
3. 合理的 `ambiguous` / `not_found` 被当作系统故障，Chat 无法自然追问。

### 2.2 供应商能力边界

[API-Tennis REST 文档](https://api-tennis.com/documentation) 当前确认：

- `get_standings` 以 `event_type=ATP|WTA` 返回排名、完整球员名、`player_key`、巡回赛、排名变动、国家和积分；
- `get_players` 可按 `player_key` 返回球员资料与分赛季单打/双打统计；
- `get_fixtures` 可按 `player_key` 和日期范围查询赛程与赛果；
- 文档没有语言参数或中文球员名能力；
- `get_players` 不是自由文本全库搜索接口。

因此 API-Tennis 继续作为比赛、排名、档案和历史赛果来源，但不能承担 TennixAI 的多语言搜索职责。

### 2.3 可选外部名称来源

[Sportradar Tennis 文档](https://developer.sportradar.com/tennis/reference/competitor-vs-competitor)列出简体中文 `zh`、繁体中文 `zht` 等语言；其 [FAQ](https://developer.sportradar.com/tennis/reference/faq) 说明 competitor/player name 可本地化。它是商业数据源，在价格、许可和覆盖率验证前，不作为首版依赖。

[Wikidata aliases](https://www.wikidata.org/wiki/Help%3AAliases) 可以作为公开参考，但内容由社区维护且覆盖不完整，不能单独成为权威目录。首版采用“可信匹配可用则用，否则离线 LLM 生成中文名”的轻量方案。

## 3. 产品范围

### 3.1 本阶段包含

- `/players` ATP/WTA 单打排名与搜索页；
- `/players/[playerId]` 球员详情页；
- ATP 男子单打与 WTA 女子单打 Top 200；
- 全部已知单打球员的中英文搜索；
- 英文主名、中文辅名及别名维护；
- 当前排名、赛季统计、当前状态、历史赛果；
- 当前赛季及前四个赛季选择；
- Home 与 Match Chat 共用 PlayerResolver；
- 合理的消歧和未找到对话结果；
- 离线、可重复执行、增量式的中文名生成；
- Next.js Route Handler 代理 FastAPI；
- v0 负责页面视觉补齐，ADE 负责接入真实数据并严格保持设计。

### 3.2 明确不包含

- 双打排名、双打队伍目录或双打球员页；
- Player Chat 独立入口；
- 运行时翻译 LLM；
- RAG、Vector DB、Elasticsearch、mGENRE 或独立搜索服务；
- 自动把两个供应商身份合并为同一球员；
- API-Tennis 全量历史镜像；
- 为每场历史比赛额外调用 `get_draw` 推导场地；
- 依赖 Sportradar 商业合同；
- 人工纠正后台或面向用户的“系统生成”标签；
- P3 odds、prediction、market、edge 或交易能力；
- 云部署、定时任务平台、队列或新常驻进程。

## 4. 页面与交互

### 4.1 `/players` 排名与搜索页

无搜索词时，页面展示官方排名快照：

- ATP / WTA 两个页签；
- 默认进入 ATP；
- 每页 50 人，覆盖 Top 200；
- 默认只按官方名次升序，不增加热度或推荐排序；
- 国家筛选；
- “中国球员”快捷筛选；
- 行字段：名次、排名变动、球员、国家/旗帜、积分；
- 球员显示为英文主名、中文辅名；
- 点击整行进入 `/players/[playerId]`。

有搜索词时，页面从完整本地球员目录查询，而不是只过滤当前 Top 200：

- Top 200 外球员可以出现；
- 有当前排名则展示排名，无当前排名则展示“暂无当前排名”；
- 结果仍显示英文主名、中文辅名、国家和巡回赛身份；
- 多个候选按解析得分、当前排名和稳定内部 ID 排序；
- 无结果使用普通空态，不显示系统错误。

第一版不提供自定义积分排序、分页大小切换、双打页签或无限滚动。

### 4.2 `/players/[playerId]` 球员详情页

头部展示：

- 英文名为标题；
- 中文名为副标题；
- 头像、国家/旗帜、生日和年龄在供应商可用时展示；
- 当前单打排名、积分和排名变动；
- 缺失字段使用统一 unavailable 语义，不猜测。

赛季概览展示：

- 胜场、负场、胜率；
- 冠军数；
- 硬地、红土、草地胜负；
- 数据严格来自 `get_players` 的对应 `season + singles` 项。

当前状态采用紧凑区块：

- 有 live 比赛时优先显示 live；
- 否则显示下一场已安排比赛；
- 两者都没有时固定显示“暂无比赛信息”；
- 比赛卡点击进入现有 Match Page。

历史赛果区：

- 默认当前赛季；
- 可选择当前赛季及前四个赛季；
- 每页 20 场；
- 可按赛事级别和胜/负筛选；
- 不提供场地筛选；
- 如果 canonical match 已有场地，结果卡可以显示；缺失时不额外请求供应商；
- 点击已结束比赛进入现有 Finished Match Page。

### 4.3 名称展示规则

- 页面标题、排名行、比赛卡和详情页一律英文主名、中文辅名；
- Chat 第一次提到球员时使用 `Ben Shelton（本·谢尔顿）`；
- 同一回答后续可以使用英文全名或姓氏，避免反复堆叠双语；
- 中文名缺失不阻塞英文展示，但正式目录发布门要求已纳入目录的首选中文名覆盖率为 100%；
- 不向用户显示名称来源是可信数据还是 LLM 生成。

## 5. 稳定领域模型

### 5.1 `Player`

扩展现有 canonical `Player`，同时保持已有 `name` 的兼容语义：

| 字段 | 语义 |
|---|---|
| `id` | TennixAI 稳定内部 ID，前端与 Chat 唯一可见身份 |
| `name` | 首选英文名；保留现有字段，避免破坏 P1/P2 DTO |
| `localized_name` | 可选首选中文名；对旧数据可为空 |
| `country_code` | 可选 canonical 国家代码 |
| `ranking` | 当前上下文可用的单打排名；不是身份字段 |

头像、生日、赛季统计等详情不塞入每个比赛里的轻量 `Player`，由单独 profile DTO 承载。

### 5.2 持久化实体

新增或扩展以下内部实体：

#### `players`

| 字段 | 约束 |
|---|---|
| `id` | 内部主键，沿用 `ply_` 命名空间 |
| `name` | 非空，沿用现有列并明确为首选英文展示名 |
| `localized_name` | 发布后为首选简体中文名；迁移兼容期允许空 |
| `country_code` | 可空 |
| `gender` | `men | women | unknown` |
| `birth_date` | 可空 |
| `image_url` | 可空 |
| `first_seen_at` / `last_seen_at` | 目录发现时间 |
| `updated_at` | 当前资料更新时间 |

#### `player_external_ids`

| 字段 | 约束 |
|---|---|
| `internal_id` | 关联内部 `players.id`；沿用现有 identity schema |
| `provider` | 如 `api_tennis` |
| `external_id` | 供应商球员 ID |
| `created_at` | 首次映射时间 |

`(provider, external_id)` 唯一。第三方 ID 永远不能替代内部主键，也不能泄漏到公共 DTO。

#### `player_aliases`

| 字段 | 约束 |
|---|---|
| `id` | 内部记录 ID |
| `player_id` | 关联内部球员 |
| `locale` | `en`、`zh-Hans` 或 `und` |
| `alias` | 原始可展示别名 |
| `normalized_alias` | 确定性归一化值 |
| `kind` | `preferred`、`full`、`surname`、`reordered`、`abbreviated`、`provider`、`transliterated` |
| `source` | `provider`、`trusted_external`、`llm`、`derived` |
| `source_ref` | 可空的内部来源标识，不进入公共 DTO |
| `model` / `prompt_version` | 仅 LLM 生成时记录 |
| `is_active` | 允许以后无损替换错误别名 |
| `created_at` / `updated_at` | 审计时间 |

`(player_id, locale, normalized_alias, kind)` 唯一。相同别名允许指向多个不同球员，这是消歧数据，不应由唯一约束强行合并。

#### `player_rankings`

| 字段 | 约束 |
|---|---|
| `player_id` | 内部球员 |
| `tour` | `ATP | WTA` |
| `ranking_date` | 排名快照日期 |
| `rank` | 正整数 |
| `points` | 非负整数 |
| `movement` | 供应商可用的变动语义 |
| `fetched_at` | 同步时间 |

`(tour, ranking_date, rank)` 和 `(tour, ranking_date, player_id)` 唯一。首版只需保留支持当前展示与故障回退的有限快照，不建设排名历史分析仓库。

### 5.3 详情与列表 DTO

稳定 API DTO 分为：

- `PlayerSummary`：内部 ID、英文名、中文名、国家、当前排名；
- `RankingEntry`：summary + tour、rank、points、movement；
- `PlayerProfile`：summary + 图片、生日、年龄、赛季统计、当前状态；
- `PlayerResultPage`：球员、筛选、分页、比赛列表和能力质量；
- `PlayerSearchResult`：summary + matched alias 类型、匹配状态；
- `PlayerResolution`：`resolved | ambiguous | not_found` 与候选。

公共响应不得包含 `player_key`、供应商 URL、原始 payload 或别名生成模型信息。

## 6. 目录同步与离线中文名生成

### 6.1 首次覆盖范围

初始目录由以下集合并集组成：

1. API-Tennis `get_standings(ATP)` 可枚举的单打排名球员；
2. API-Tennis `get_standings(WTA)` 可枚举的单打排名球员；
3. 已在 live、schedule、history 或本地 canonical 数据中观察到的 Challenger / ITF 单打球员。

页面默认只展示 ATP/WTA Top 200，但搜索可命中目录中的其他已知球员。首版不为了追求“全球绝对全量”无界扫描所有赛事。

### 6.2 `PlayerDirectorySync`

同步是本地可重复执行的离线命令，不增加 cron、队列或 daemon：

```text
fetch standings / observed external identities
        ↓
upsert internal player and external id
        ↓
refresh English preferred name, country, ranking
        ↓
derive deterministic English aliases
        ↓
collect players missing preferred Chinese name
```

行为约束：

- 同一供应商 external ID 必须收敛到同一内部 ID；
- 重复运行幂等；
- 不用姓名自动合并两个 external ID；
- 供应商名称从缩写升级为完整名时更新首选英文名，并保留旧名称为 provider alias；
- 单个档案补齐失败不得回滚已验证的其他球员；
- 同步输出新增、更新、跳过、冲突和失败计数，但不打印凭据或完整 LLM 请求。

### 6.3 `PlayerAliasEnricher`

中文名来源优先级：

1. 已验证的官方或商业多语言来源；
2. 可靠公开来源，且英文名、国家、生日等身份属性一致；
3. 离线 LLM 翻译。

首版不要求接入新的商业供应商，因此预期大部分缺失中文名由现有 OpenAI-compatible LLM 离线批量生成。

每个 LLM batch 输入仅包含：

- internal `player_id`；
- official/preferred English name；
- country；
- 可选 birth date；
- gender/tour。

模型只能为输入中的 ID 返回中文首选名和必要别名，不能创建 ID、合并球员或改写英文主名。输出先通过严格结构校验，再以单批事务写入；任何未知 ID、重复 ID、空姓名、非法字段或 JSON 结构错误都使整批不写入。

重复运行时只处理缺失中文首选名或显式指定重新生成的球员；已有有效名字不消耗 LLM。内部保留 source、model 和 prompt version，便于未来由更可信来源替换，但 UI 不展示这些元数据。

### 6.4 新球员增量

比赛、排名或历史查询发现新 external player ID 时先创建最小 `Player`：

- 立即可用英文名和内部 ID；
- 派生英文别名立即可搜索；
- 中文名在下一次离线增量 enrichment 补齐；
- 正式目录数据门以 enrichment 后覆盖率计算。

这避免运行时因等待翻译而阻断比赛数据，同时保持翻译调用离线化。

## 7. 名称归一化与别名

### 7.1 确定性归一化

所有 alias 写入和 query 解析使用同一个版本化函数：

1. Unicode NFKC；
2. `casefold`；
3. 标点、间隔点、连字符和多余空白归一；
4. 拉丁字母去重音版本作为额外派生 alias，不覆盖原始拼写；
5. 英文姓名 token 化，生成原顺序与可安全判定的姓在前变体；
6. 供应商首字母缩写标准化，如 `B. Shelton` → `b shelton`；
7. 中文名去空白和常见间隔点，保留完整名与已批准简称。

PostgreSQL 的 [`unaccent`](https://www.postgresql.org/docs/17/unaccent.html) 可用于拉丁重音归一化，[`pg_trgm`](https://www.postgresql.org/docs/17/pgtrgm.html) 可为后续受控模糊候选提供索引。本阶段仍以显式 alias 的精确归一化匹配为主，trigram 不得绕过消歧门直接认定身份。

### 7.2 自动派生 alias

从首选英文名和供应商名可确定性生成：

- 英文全名：`Ben Shelton`；
- 姓氏：`Shelton`；
- 首字母缩写：`B. Shelton`、`B Shelton`；
- 安全的姓名倒序：`Shelton Ben`；
- 去重音形式；
- 供应商曾返回的名称。

从首选中文名可保存：

- 完整中文名：`本·谢尔顿`；
- 去间隔点形式：`本谢尔顿`；
- 常用姓氏：`谢尔顿`。

姓氏和短 alias 天然可能冲突，必须保留多候选，不能通过“最后写入获胜”消除歧义。

## 8. `PlayerResolver`

### 8.1 输入与输出

Resolver 输入：

- `query`；
- 可选 `match_id`；
- 可选 tour/gender/country 等显式上下文；
- 可选候选数量上限。

输出是领域结果而不是异常：

```text
resolved(player, matched_alias, confidence)
ambiguous(candidates, reason)
not_found(normalized_query)
```

空查询仍属于输入校验错误。数据库不可达、供应商失败或内部不变量破坏才是基础设施错误。

### 8.2 匹配顺序

1. 内部 `player_id` 精确匹配（仅服务内部调用）；
2. active preferred/full/provider alias 精确归一化匹配；
3. reordered/abbreviated/transliterated alias 精确匹配；
4. surname/short alias 匹配；
5. 受控 trigram 候选，仅用于拼写容错和返回候选，不默认越过阈值硬选。

排序因素依次是：匹配类型、上下文一致性、当前排名存在性与名次、稳定内部 ID。排名只能帮助排序，不能把两个相同姓名自动合并。

### 8.3 上下文消歧

- Match Chat 带 `match_id`：若候选中恰有一人属于当前比赛，自动解析；
- Home Chat：完整别名唯一命中时解析；短姓氏只有一个明显候选且没有同级冲突时可解析；
- 仍有多个合理候选时返回 `ambiguous`，列出英文名、中文名、国家和排名，让用户选择；
- 未命中时返回 `not_found`，提示用户补充英文/中文全名、国家或赛事；
- LLM 不得根据常识自行生成 `player_id` 或把候选静默缩成一个。

### 8.4 核心验收样例

以下各组必须解析到组内同一个内部 ID：

- `Ben Shelton`、`Shelton`、`B. Shelton`、`本·谢尔顿`、`谢尔顿`；
- `Qinwen Zheng`、`Zheng Qinwen`、`Q. Zheng`、`郑钦文`；
- `Novak Djokovic`、`Djokovic`、`N. Djokovic`、`德约科维奇`。

另需覆盖大小写、标点、重音/无重音和多余空白。构造两个同姓球员时，Home 返回 candidates；当前 Match 只包含其中一人时自动解析。

## 9. Service 与 Provider 边界

### 9.1 查询方向

正确路径固定为：

```text
user query
   ↓
PlayerResolver → internal player_id
   ↓
IdentityRepository → provider external player_key
   ↓
TennisDataProvider.get_fixtures/get_player/get_recent_results
```

解析完成后，不再用名字过滤供应商返回值。Provider 方法继续只接内部 `player_id`，由 adapter 通过 identity repository 取得 `player_key`。

### 9.2 Provider contract 增量

目录同步需要显式、可测试的供应商能力，而不是复用有界比赛扫描：

- `get_rankings(tour)`：返回供应商 ranking records，经同步层落为 canonical ranking；
- `get_player(player_id)`：沿用现有方法，补齐 profile；
- `get_fixtures(player_id, date range/status)` 或等价历史查询：沿用/收紧现有历史能力；
- `search_players(query)` 不再承担 API-Tennis 全局身份发现，业务搜索迁移到本地 PlayerDirectory。

若现有 base protocol 不适合离线 catalog 枚举，可以建立窄的 `PlayerCatalogProvider` protocol；不要为了一个供应商把实时 provider 接口扩成万能接口。

### 9.3 历史数据策略

历史赛果按需来自 API-Tennis，不重复建设完整比赛历史仓库：

- 本地只持久化球员身份、别名、排名，以及已有 canonical/实时数据；
- 详情页历史请求由 service 按 player + season + tier + result + page 查询并短 TTL 缓存；
- 供应商支持的历史范围直接使用；范围外或能力不足返回 typed unavailable/partial；
- 不因为翻页把全部历史写入数据库；
- 已有 Finished Match 路由继续使用内部 match identity；
- 原始供应商 payload 的既有 14 天保留规则不变。

## 10. HTTP API

所有浏览器请求继续经过 Next.js Route Handler，同源代理 FastAPI；根 `.env` 仍是唯一人工配置入口。

### 10.1 Rankings

```http
GET /api/v1/players/rankings?tour=ATP&page=1&page_size=50&country=CHN
```

约束：

- `tour` 只允许 `ATP | WTA`；
- `page_size` 首版固定 50；
- 只返回 Top 200 范围内经过筛选的当前快照；
- 返回 `as_of`、`fetched_at` 与数据质量；
- 数据陈旧但仍可用时返回 stale 标记，不清空页面。

### 10.2 Directory search

```http
GET /api/v1/players/search?q=谢尔顿&limit=10
```

约束：

- 搜索整个本地目录，不限 Top 200；
- 返回 resolver 状态、候选和匹配信息；
- `ambiguous` / `not_found` 使用成功的领域响应，不映射为 5xx；
- 空 query 为 422。

### 10.3 Player profile

```http
GET /api/v1/players/{player_id}
```

返回 profile、当前单打 ranking、指定/默认赛季统计和 live/next 状态摘要。未知内部 ID 为 typed 404；供应商可选档案缺失不抹掉本地身份摘要。

### 10.4 Player results

```http
GET /api/v1/players/{player_id}/results?season=2026&tier=ATP&outcome=won&page=1&page_size=20
```

约束：

- season 只允许当前年及前四年；
- tier 使用既有 `ATP/WTA → Challenger → ITF` canonical 分类；
- outcome 为 `all | won | lost`；
- 每页固定 20；
- 返回 `available | partial | unavailable` 质量语义；
- 不提供 surface query；
- 结果 match 只暴露内部 ID。

### 10.5 Next.js 代理

对应新增同源 routes：

- `/api/players/rankings`；
- `/api/players/search`；
- `/api/players/[playerId]`；
- `/api/players/[playerId]/results`。

代理沿用现有凭据隔离、错误信封和 request ID 规则。浏览器不能看到 API-Tennis key、LLM key或 backend base URL。

## 11. Chat 集成

### 11.1 共用身份解析

Home 和 Match Chat 不增加一个“让 LLM 猜名字”的工具。现有业务工具参数可以继续接受 `player_query` / `player_name`，但工具执行器的第一步统一调用 `PlayerResolver`。

```text
find_player_matches(player_query="谢尔顿")
        ↓
PlayerResolver.resolve(query, optional match_id)
        ↓
resolved internal player_id
        ↓
TennisService query by ID
```

Match scope 已有 `match_id` 必须传入 resolver 作为消歧上下文。LLM 只看到公共候选与 internal ID，不看到 external ID 或 alias provenance。

### 11.2 非终止结果

- `resolved`：继续执行比赛、统计或历史查询；
- `ambiguous`：工具返回候选，Chat 用自然语言请用户选择；
- `not_found`：工具返回可恢复结果，Chat 请用户补充信息；
- 两者都必须以正常 SSE `done` 结束，不发送终止 `error`；
- provider/database/LLM 基础设施故障继续沿用现有错误和部分降级策略。

这项语义同时修复当前页面的“查询失败（not_found）”体验，但不吞掉真正的服务故障。

### 11.3 历史问答

Home 全局 Chat 可以使用相同的 player results service 回答赛季战绩或近期赛果；Player Page 第一版不增加专属 Chat。历史事实进入既有 compact fact packet 后再交给 LLM，LLM 不直接读取数据库或调用 API-Tennis。

## 12. 前端与 v0 交付契约

### 12.1 v0 负责的视觉范围

把本规格交给 v0 生成：

- `/players` 桌面与移动布局；
- `/players/[playerId]` 桌面与移动布局；
- 英文主名/中文辅名的清晰层级；
- 排名、搜索、筛选、分页和行点击交互；
- profile、赛季统计、当前状态、历史赛果；
- loading、empty、partial、error、stale；
- Top 200 外搜索结果和暂无当前排名状态；
- 精确文案“暂无比赛信息”。

v0 使用确定性展示数据，但不能把样例数据引入生产数据路径。

### 12.2 ADE 集成边界

- v0 产物成为该两页视觉真相；
- ADE 接真实 API 时保留组件结构、间距、排版、颜色、响应式和交互意图；
- preview/demo 路径与生产数据路径隔离；
- 既有 Home 和 Match 原型不因新增页面被重设计；
- 共享 header/navigation 可以只做支持 `/players` 导航所需的最小改动；
- API DTO 中 `name` 仍是英文，`localized_name` 为可选中文，旧组件渐进接入。

## 13. 新鲜度、缓存与本地运行

- 排名是快照数据，不需要 WebSocket；默认按供应商可接受频率由离线同步刷新；
- 目录和 alias 从 PostgreSQL 读取，可在进程内做短 TTL 缓存；
- profile 与历史结果沿用 bounded async TTL cache；
- Redis 不是球员目录的事实来源，也不承担 alias 持久化；
- 本地命令必须显式运行，失败可重试，不要求常驻调度；
- 未来有服务器后，可把相同 sync/enrich 命令交给调度器，不改变业务契约。

## 14. 安全、隐私与审计

- 根目录 `.env` 继续是唯一凭据入口；
- 离线 enrichment 通过现有服务端 LLM 配置调用，凭据不进入参数、日志或产物；
- 不把整份供应商 payload、API key 或外部 ID 发给翻译 LLM；
- LLM 只接收公开球员身份字段；
- 日志允许记录 internal ID、batch size、模型名、prompt version 和计数；
- 公共 API、HTML、SSE、fixture、截图和 Git 文档都不得包含供应商 key 或 LLM key；
- raw provider payload 保留 14 天的既有规则不变；alias provenance 长期保留但仅内部可见。

## 15. 测试与验收

### 15.1 数据和迁移门

- migration upgrade → downgrade → upgrade 可往返；
- 现有 identity 映射无损迁移到 player master data；
- 同一 `(provider, external_id)` 并发 upsert 收敛到一个 internal ID；
- alias 重复写入幂等；
- 同一 alias 可对应多个球员并正确返回 ambiguity；
- 目录首选英文名和中文名覆盖率均为 100%；
- 第二次 enrichment 不重新翻译已有名字；
- LLM batch 有未知 ID、缺失项或结构错误时整批零写入；
- 删除/回滚新功能不破坏既有 match identity 和历史 canonical observations。

### 15.2 Resolver 门

- 三组核心别名全部解析到各自同一个 internal ID；
- 姓名顺序、大小写、标点、重音和缩写覆盖；
- ambiguous surname 返回候选；
- Match context 唯一包含候选时自动解析；
- unknown query 返回 `not_found` 领域结果；
- runtime resolver 测试证明未调用翻译 LLM 或供应商文本搜索。

### 15.3 API 和 Chat 门

- rankings 仅返回 Top 200，官方顺序稳定，50 人分页；
- search 可返回 Top 200 外球员；
- profile 缺可选供应商字段仍可读；
- results 的 5 年、tier、W/L、20 人分页边界正确；
- 所有公共响应只含 internal ID；
- Home 与 Match tools 使用同一 resolver；
- `ambiguous` / `not_found` SSE 最终为 `done`，不出现终止 `error`；
- 基础设施失败仍保持现有 typed error/partial 行为。

真实 Chat 问题至少包括：

- “Ben Shelton 下一场什么时候？”
- “Shelton 今天有比赛吗？”
- “谢尔顿现在比分多少？”
- “郑钦文这个赛季战绩如何？”
- Match context：“谢尔顿这场一发怎么样？”
- Match context：“Shelton 现在在发球吗？”

### 15.4 前端和浏览器门

- 单元测试覆盖 loading、empty、partial、error、stale、分页与筛选；
- Playwright desktop `1440×1000`；
- Playwright mobile `390×844`；
- `/players` ATP/WTA、国家、中国快捷筛选和搜索流程；
- Top 200 外结果显示；
- row → profile → finished match 导航；
- profile 5 个赛季、tier、W/L 和分页；
- live/next/“暂无比赛信息”三态；
- 双语层级与 v0 基线视觉一致；
- 既有 Home、Match 与 Chat 回归通过。

### 15.5 真实服务门

- API-Tennis 真实 `get_standings` ATP/WTA 认证与字段映射 smoke；
- 至少一个 Top 200 和一个已观察到的 Top 200 外球员 profile/history smoke；
- 离线真实 LLM 小批翻译 smoke，只验证结构、幂等和安全写入；
- 真实浏览器完成排名 → 搜索中文名 → profile → 历史赛果 → Finished Match；
- 真实 Home/Match Chat 运行核心别名问题，并等待 SSE `done`；
- 真实门受 opt-in marker 和配额边界保护，不作为默认确定性 suite 的前提。

## 16. 迁移、发布与回滚

### 16.1 发布顺序

1. 先由 v0 生成 `/players` 与 `/players/[playerId]`，导入 preview 并冻结桌面/移动视觉基线；
2. 探测并冻结 API-Tennis 排名枚举、字段边界和 canonical ranking adapter；
3. 增加 player master、external IDs、aliases、rankings schema，并无损迁移现有 player identity；
4. 实现幂等目录同步与英文 alias 派生；
5. 用离线 enrichment 补齐中文名；
6. 实现 PlayerResolver 和按内部 ID 的 service/provider 路径，但先不切换生产 Chat；
7. 接 rankings/profile/results REST；
8. 将 Home/Match Chat 切到共享 resolver；
9. 把真实 API 与状态接入已冻结的 v0 组件，不改变视觉结构；
10. 运行确定性、真实供应商、真实 LLM 与双视口浏览器总门。

每一步都应是独立可提交任务，后一步不通过时可停在仍兼容 P2.5 的状态。

### 16.2 兼容策略

- `Player.name` 与现有 JSON `name` 保持英文语义；
- 新 `localized_name` 初期可空，旧前端无需同步切换；
- 旧 `/api/v1/players/search` 可以在 resolver 稳定后替换内部实现，保持 URL；
- provider contract 的按 ID 查询继续兼容；
- Chat 工具名称和主要参数尽量不变，只替换内部解析路径；
- schema migration 不删除既有 identity 表和数据，验证稳定后再决定是否收敛重复结构。

### 16.3 回滚

- UI 可通过移除 `/players` 导航入口回到 P2.5，不影响 Home/Match；
- Chat resolver 可切回旧 adapter 路径，仅作为短期故障回滚，不作为长期双写；
- 新表保留不会改变既有 match/realtime 数据；
- enrichment 记录按 `source/prompt_version` 可停用，不需要删除 Player；
- migration downgrade 必须先证明不会丢失原有 external identity；若无法无损则只做前向兼容回滚，不执行破坏性降级。

## 17. 实施任务拆分原则

后续实施计划按以下依赖方向拆分，具体任务 ID、文件和命令以计划为准：

1. v0 生成、导入并冻结两页视觉真相；
2. 供应商能力 probe 与 canonical ranking domain/adapter；
3. 目录 repository、迁移和幂等同步；
4. 离线中文名 enrichment；
5. PlayerResolver 与按 ID 的 service/provider 路径；
6. rankings/profile/results API；
7. Home/Match Chat 切换与非终止消歧；
8. 已冻结 v0 组件的真实数据集成；
9. 全量验收和总控关闭。

不得跨任务提前加入双打、运行时 LLM 搜索、全量历史镜像、Sportradar 依赖或 P3 能力。

## 18. 决策记录

| 决策 | 结果 |
|---|---|
| 排名覆盖 | ATP/WTA 单打 Top 200 |
| 排名分页 | 每页 50 |
| 默认排序 | 官方排名顺序 |
| 目录搜索 | 全部已知单打球员，不限 Top 200 |
| 展示语言 | 英文主、中文辅 |
| 名称生成 | 离线批量；可信来源优先、LLM 补缺 |
| 运行时解析 | 确定性 alias resolver |
| 历史范围 | 当前赛季 + 前四赛季，按需供应商查询 |
| 历史分页 | 每页 20 |
| 历史筛选 | season、tier、W/L；无 surface filter |
| 空比赛文案 | “暂无比赛信息” |
| Player Chat | 首版不做 |
| 双打 | 首版不做 |
| 数据库职责 | 球员身份、别名、排名及既有 canonical 数据；不镜像全部历史 |
| 视觉实现 | v0 补齐设计，ADE 严格集成 |

## 19. 参考资料

- [API-Tennis REST documentation](https://api-tennis.com/documentation)
- [Sportradar Tennis API basics](https://developer.sportradar.com/tennis/docs/tennis-ig-api-basics)
- [Sportradar Tennis language FAQ](https://developer.sportradar.com/tennis/reference/faq)
- [Wikidata aliases](https://www.wikidata.org/wiki/Help%3AAliases)
- [PostgreSQL pg_trgm](https://www.postgresql.org/docs/17/pgtrgm.html)
- [PostgreSQL unaccent](https://www.postgresql.org/docs/17/unaccent.html)
