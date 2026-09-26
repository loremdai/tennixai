# T104 全站球员照片设计规格

**状态：** 已冻结并按用户指示直接进入实施（2026-09-26）  
**任务：** [T104](../../../CURRENT.md#t104-全站球员照片贯通in_progress)  

## 目标

让 TennixAI 中每个代表真实球员的界面位置都展示该球员的真实照片；不再用姓名首字母作圆形头像。照片只在能可靠关联到内部 `player_id` 时使用。上游没有照片或球员身份不确定时，展示中性人像占位，不伪造照片、不猜身份。

## 已核实的数据能力

- API-Tennis `get_players` 的 `player_logo` 提供球员图片 URL；当前球员资料页已能使用 `PlayerProfileData.image_url`。
- API-Tennis standings 响应不包含照片，因此排名列表不能仅靠排名数据获得照片。
- fixtures/livescore 可提供双方的球员 logo 字段，但供应商可能返回空值。
- `players.image_url` 数据库列与 `DirectoryPlayer.image_url` 已存在；目前资料接口取得的照片没有系统性写回目录，通用 `Player`、排名和 P3 展示 DTO 也没有统一的照片字段。
- 官方接口契约与条款：[API-Tennis REST 文档](https://api-tennis.com/documentation)、[使用条款](https://api-tennis.com/terms-of-use)。图片 URL 按供应商字段使用，不下载、镜像或生成图片；权利仍归相关权利人，条款不等于图片版权许可。

## 产品与数据规则

1. **唯一来源：** 使用 API-Tennis 明确返回的 `player_logo` / 比赛球员 logo。此任务不接第二图片供应商、不爬网页、不按姓名拼接第三方图片 URL、不调用 LLM/图片生成。
2. **唯一关联：** 通过 canonical `player_id` 传递图片。市场行只有在已有严格内部球员 ID 时才显示匹配照片；未匹配或双打队名不得按文本猜测球员照片。
3. **缓存：** 复用 `players.image_url`；比赛 feed 提供的图片随 canonical 球员目录保存。排名页只在当前页需要且目录无图时按球员 profile 接口补取，并限制并发；不在 `init` / `up` 阶段批量读取最多 400 名排名球员。成功照片长期复用，资料缓存和请求合并沿用现有服务缓存。
4. **空图与加载失败：** 全站共享 `PlayerAvatar`；图片为空、加载失败或身份未知时显示中性人像图标。永不回退到姓名首字母。
5. **展示范围：** Home 赛程/直播/赛果/结构化问答卡/球员消歧候选；Match 详情主球员区；Markets 的全部市场、机会、Paper 与 Home 市场脉搏；Players 排名、搜索、详情、当前比赛及历史结果对手；以及代码审查发现的其他真实球员头像位。非球员图标（导航、提醒、空状态插画等）不在范围。
6. **语义边界：** 不改市场匹配、排名、预测、机会筛选、paper 状态/金额、历史结果或任何网球事实。供应商没有返回照片时如实使用占位，不发明覆盖率承诺。

## 数据/API 契约

- canonical `Player` 新增可空 `image_url`。旧 JSON/API 输入缺字段继续按 `null` 兼容。
- 目录读取把现有数据库 `players.image_url` 映射进 `Player.image_url`；目录提供按内部 ID 幂等更新非空图片的方法。
- provider 将赛事响应的双方 logo 映射到对应内部球员；资料响应同时保留现有 profile `image_url` 并在 `Player.image_url` 中表达同一图片。
- rankings 当前页缺少图片时，仅为该页的缺图球员按需查询 profile；有界并发，供应商异常不影响排名响应。新 URL 写入既有列。没有图片则继续返回 null。
- P3 `MarketSummaryDto`、`OpportunityDto`、`PaperPositionDto` 与 `PulseRowDto` 增加与 `player_ids` / `player_names` 顺序一致的可空 `player_images` 二元组。未映射市场的该字段为 null；不新增第三方 ID。
- 前端 DTO runtime decoder 对新字段作严格校验；图片展示组件只读 URL，不自行推导球员身份。

## 验收条件

- 全站玩家头像位由同一个 `PlayerAvatar` 渲染；DOM/代码中不再把姓名首字母用作人像 fallback。
- API-Tennis 比赛球员 logo 经 provider → canonical match → 存储/读取 → API → 前端能显示；null logo 不破坏其它球员字段。
- 排名列表仅在页面需要时补取当前页缺图球员资料；URL 写进既有目录列后，排名/搜索/比赛/市场共享，不在每次请求重取已有图片；外部 API 失败时仍正常显示排名和占位。
- 匹配市场/Paper/机会按内部 player ID 展示两侧照片；无 ID 的 market-only 行不误配。
- 搜索、档案、历史结果和 Home/Match 使用相同照片与占位规则；桌面/移动布局不挤压姓名或关键比赛信息。
- 不改变 `init/up` 请求数、LLM 用量、P3 决策/纸面交易行为；不新增数据库 migration 或图片资源文件。
- 相关后端/前端确定性测试与静态类型检查通过；真实运行时只在不重启/不中断用户服务的前提下验收，否则明确记录未能做的浏览器检查。

## 实施计划

详见 [T104 实施计划](../plans/2026-09-26-tennixai-t104-global-player-photos-implementation.md)。
