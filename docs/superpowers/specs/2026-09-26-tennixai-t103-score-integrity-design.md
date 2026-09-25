# T103 历史赛果盘分/局分完整性设计

状态：待用户审阅；本文件是设计规格，不代表实现完成。

## 目标

让 API-Tennis 已提供的逐盘局分和抢七小分从供应商响应完整通过 canonical model、已存比赛快照、REST DTO 到球员历史和比赛详情页面。真实未知值继续未知，不按胜负、胜盘数或比赛常识补造比分。

## 已验证事实

- 本机球员赛果接口 2026 赛季返回 47 场。含抢七的多场在 `sets_won` 有值时，部分 `SetScore.player1_games/player2_games` 却为 `null`；普通数字局分正常。
- 对其中一场做的有界只读 API-Tennis 核验返回 `event_final_result="3 - 1"`，逐盘原值依次为 `6.7–7.9`、`7.7–6.2`、`6–3`、`6–4`。同一响应中抢七最后一步的 `pointbypoint.score` 分别为 `7 - 9` 和 `7 - 2`，证明点号后是双方抢七小分，点号前是局数。
- `backend/app/providers/api_tennis.py::parse_non_negative_int` 仅用 `str.isdigit()` 接受纯数字；因此 `6.7`、`7.9` 被解析成 `None`。球员结果的 REST DTO 随后带着空值返回；前端球员历史 formatter 只展示双方局分都存在的盘，故该盘被跳过。
- 比赛详情的数据库快照也有同样空值（本地 `as_of=2026-09-25T16:29:48Z`、`state_version=1`）。因此单修 provider parser 不能自动修复既有快照：`resolve_match_snapshot` 优先读 Redis/PostgreSQL，只有在缓存/快照未命中时才直接请求 provider。
- [API-Tennis REST 文档](https://api-tennis.com/documentation)说明 `get_fixtures` 的每场比赛内联携带 `scores` 与 `pointbypoint`，但没有定义点号抢七编码；本设计的编码语义由上述同一场真实响应的逐盘字段和 point-by-point 终分交叉验证。凭据和完整供应商 payload 均未保存。

## 设计

### 1. 解析并保留来源给出的抢七分

- provider 对 `score_first` / `score_second` 接受严格的 `games` 或 `games.tiebreak_points` 格式，例如 `6`、`6.7`；不接受或猜测其他格式。无效/缺失值仍映射为 `None`。
- 扩展 canonical `SetScore`，为两位球员各增加一个可选抢七小分字段。常规盘中其值为 `None`；API/前端 DTO 采用可选、向后兼容字段。
- 旧 PostgreSQL JSONB 快照没有抢七字段，读取时按 `None` 处理，不迁移 schema，也不重置数据库。

### 2. 防止已有比分被稀疏更新清空

- 实时 reducer 对同一场比赛按 `SetScore.number` 合并：新候选中的非空值优先（允许权威更正），只有候选缺值时才保留旧的已知局数/抢七分。候选若提供更新的非空值，不以旧值覆盖。
- 参与者/比赛身份仍按现有稳定 ID 约束；不跨比赛、盘号或球员方向合并。

### 3. 有界修复已存的结束比赛快照

- 用户打开比赛详情时，若已存快照属于 `finished` 且总盘分显示仍有盘缺局分，则复用现有 `match-metadata` provider/cache 流程刷新并把更完整分数并入/持久化。provider 的 `get_match_snapshot` 增加默认开启的可选 surface enrichment 参数；此次仅补比分时关闭它，避免为已存好的赛事资料额外调用 `get_draw`，只请求该场 `get_fixtures(match_key=...)`。API-Tennis、LiveTennis、Replay 和 Fake provider 均接受同一可选参数；默认值不改变既有行为。
- 沿用该缓存对同一比赛的请求抑制；供应商不可用或仍未提供分数时，继续显示已有已知数据，不清空、不猜测，并遵守现有错误/陈旧状态语义。
- 完整快照不增加请求；实时/未开始比赛不走历史补齐路径。不开启批量历史扫描，不在启动/init 时拉历史。

### 4. 消费者展示

- 球员历史行显示整场逐盘比分，并在抢七盘附双方小分，例如 `6–7（7–9） 7–6（7–2） 6–3 6–4`；显示视角仍按当前球员排序。
- 比赛比分表和 Home 实时比分行保留原本的每人/每盘结构，抢七小分以附属信息展示（如 `6（7）`、`7（9）`），常规盘视觉不变。
- 只在局分确实缺失时保留现有部分比分/暂无文案；不把 `sets_won` 当作逐盘局分，也不从 point-by-point 重建局分。

## 验收

1. Provider RED→GREEN 回归覆盖普通局分、`6.7` / `7.9` 抢七、保留双边小分、`-`/空值、格式错误和 `score_set` 顺序；领域/API 序列化测试覆盖新旧 JSON。score-only refresh 要验证只调用 `get_fixtures`，不调用 `get_draw`。
2. Reducer 测试证明稀疏输入不清除已知局分/抢七分，非空权威更正会覆盖旧值，且不串盘。
3. Service 测试证明仅不完整的结束快照触发有界刷新、完整/Live/Upcoming 快照不触发、不完整仍缺时保留未知、修复后持久化并能下一次读回。
4. Frontend 单元/组件测试覆盖历史比分、详情比分表、Home 分数行的抢七显示及未知/部分比分；运行前端全量测试与 TypeScript 检查。
5. 运行相关后端测试、确定性后端套件、改动 Python 文件 Ruff、`git diff --check`；用当前真实本地服务只读复核同一历史样本的球员历史 API 和比赛详情页面。不得记录 API key、供应商 URL 查询凭据或原始 payload。

## 不在范围内

- 不从胜负/胜盘数反推局分，不从 point-by-point 派生新比分。
- 不建立本地完整历史比赛库、不批量抓取、不提高轮询频率。
- 不执行 `init`、数据库 reset 或 schema migration；不改 Polymarket、LLM、排名或其他比分规则。
- 保留用户已有 `backend/app/service.py` P3 freshness 改动及所有未跟踪文件，不纳入 T103。

## 风险/实现边界

- API-Tennis 文档没有正式描述点号格式；当前语义由一条真实比赛响应中的 `score_first/second` 与同盘 PBP 最终比分逐项吻合验证。实现必须严格匹配该格式，其他非数字形式保持 unknown，不作宽松数值截断。
- 旧快照刷新只发生在用户查看一场已结束且比分不完整的比赛时；若账户数据额度进一步受限，可由用户审阅后另行调整缓存周期，但不得退化为无界抓取。
