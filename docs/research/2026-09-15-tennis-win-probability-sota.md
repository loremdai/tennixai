# P3 网球胜率预测与决策支持：论文与 SOTA 调研

**状态：** 研究结论，供 T55 设计决策使用；不是已冻结规格，也不授权实现

**调研日期：** 2026-09-15

**适用范围：** 赛前与赛中、职业网球单打、单场比赛胜者市场、固定 `$10` paper stake、每场一次入场与最多一次规则化退出（否则持有至结算）

## 1. 结论先行

当前没有一个可以被 TennixAI 直接选为“唯一 SOTA”的模型。公开研究在赛事范围、男女巡回赛、预测时点、数据字段、时间切分、评估单位和是否使用市场赔率方面并不一致；论文中的最高命中率通常不可横向比较，更不能直接等同于可交易 edge。

这次调研支持的方向不是“现在拍板选一个可解释模型”，也不是“直接上深度学习”，而是建立一套 **结构模型 + 统计学习 challenger + 独立校准 + 诚实弃权** 的 champion/challenger 体系：

1. 赛前用 surface-aware Elo、Glicko 或动态 Bradley–Terry 构成可复现基线，再让特征化 HGBM 等模型挑战它。
2. 赛中以网球计分规则的精确 Markov recursion 为骨架，将赛前实力转换为当前比分下的胜率。
3. 用 Bayesian / empirical-Bayes shrinkage 根据已经发生的发球分动态修正能力，避免开场少量样本把概率拉飞。
4. 让 HGBM 叠加结构模型输出、比分、PBP 与可靠技术统计，作为 hybrid challenger；是否晋升 champion 只由时间外实验决定。
5. 每个候选模型都必须单独做概率校准，并输出数据质量、适用域和不确定性；证据不足时不给 BUY。
6. 模型概率与 Polymarket 数据严格分层。独立网球模型不能把当前 Polymarket 价格作为输入，否则再拿两者比较就是循环论证。
7. 决策层使用真实可成交 ask、订单簿深度、价差和市场实际费率计算净 edge，不能使用页面展示的 midpoint。
8. LLM 只把结构化证据翻译成用户可读解释，不生成、覆盖或“修正”模型概率。

因此，本阶段应冻结的是 **实验协议、模型边界和晋升规则**，而不是未经内部基准验证的具体算法冠军。

## 2. 为什么论文里没有可直接照搬的统一 SOTA

### 2.1 任务不同

- 赛前预测只使用开赛前已知信息；赛中预测还要处理当前比分、发球方、PBP 和不断增长的小样本统计。
- “预测整场赢家”“预测下一分”和“从当前状态预测最终赢家”是三个不同任务。
- 25%、50%、75% 比赛进度的命中率不能与全 point-state 平均命中率直接比较。比赛越接近结束，胜率本来就越容易判断。

### 2.2 数据不同

- 有些研究只含男子 ATP，有些同时含 ATP/WTA；有些只含大满贯，有些覆盖普通巡回赛。
- Hawk-Eye 轨迹、球速、落点等研究字段不在当前 API-Tennis 稳定契约内，不能据此承诺产品能力。
- 高级别赛事上的结果不能自动外推到 Challenger 或 ITF；低级别赛事数据缺失、球员冷启动和退赛比例都更严重。

### 2.3 验证方法不同

- 随机切分历史比赛会让未来信息进入过去；将同一场比赛的不同 point state 拆到训练集和测试集更是直接泄漏。
- 一个超长比赛会产生更多 point state。若只报告逐点平均指标，长比赛会被过度加权。
- 只报告 accuracy 会掩盖过度自信。P3 要比较的是概率与价格，校准错误会直接制造虚假 edge。

### 2.4 赔率作为输入会改变研究问题

把博彩公司赔率作为特征，往往能提高预测表现，但这类模型是在拟合市场共识，不再是独立的 tennis probability。它可以作为 market-informed benchmark，却不能作为 TennixAI 与 Polymarket 比较时的独立一侧。

## 3. 关键研究证据

| 研究 | 数据与验证 | 主要发现 | 对 TennixAI 的含义 | 主要限制 |
|---|---|---|---|---|
| Xie & Muppidi, *Forecasting the Winner of a Live Tennis Match*（2026，arXiv v1） | 8,222 场大满贯、约 150.5 万个赛前下一分状态；2011–2021 训练、2022 验证、2023–2024 测试 | hybrid “Trace” 将 Elo/serve-shrink Markov 输出与 HGBM 叠加；25%/50%/75% 进度 accuracy 为 76.06%/82.15%/88.34%，相应 log loss 为 0.4753/0.3530/0.2002 | 与现有 API-Tennis 的比分、server、PBP 能力最接近；支持“规则骨架 + shrinkage + boosting” | 未同行评审；仅大满贯；未使用 surface Elo；不能证明在普通巡回赛、Challenger/ITF 或 Polymarket 上有效 |
| Poudel 等，*A Unified Benchmark...*（2026） | 133,138 场高等级 ATP，1968–2024；16 个紧凑特征，按时间切分 | 增强 Elo 约 65.87%，HGB 约 66.30%，DNN 约 66.15–66.22%；Elo-ML 约 67.5%；大型 DNN 没有显著胜过经典 ML | 赛前优先做好动态实力、surface 与时间特征；模型规模不是首要杠杆 | ATP-only；无赛中 PBP；无 WTA/低级别赛事；无可执行市场收益验证 |
| Gorgi、Koopman、Lit（2019） | 17 年、约 4.3 万场 ATP，严格样本外预测 | time-varying、surface-specific 的动态 Bradley–Terry 显著优于静态排名类基线 | 动态且分场地的球员能力应成为强赛前基线 | 男子数据；实现与运维复杂度高于 Elo；不是赛中模型 |
| Ingram（2019） | point-based Bayesian hierarchical model，按时间评估 | 分离发球/接发能力，并建模 surface、赛事和随时间变化的球员能力，优于较简单 point model | 比单一“综合 Elo 差”更贴近 Markov recursion 所需的发球分参数 | 需要高质量历史 point/stat 数据；冷启动与供应商字段覆盖仍需验证 |
| Gollub（2017） | ATP 三盘制；2011–2013 训练、2014 测试 | Elo + hierarchical Markov + beta shrinkage 的 live model，报告 all-point accuracy 约 76.5%、log loss 约 0.477 | 给出低复杂度、可复现的 live baseline；小样本 shrinkage 是核心，不是装饰 | 学位论文；年代与赛事范围有限；数据契约需重建 |
| Kovalchik & Reid（2019） | 赛前 calibration + 赛中 dynamic empirical-Bayes update | 报告相对固定能力模型降低赛中发球预测误差，并改善赢家预测 | 支持将“赛前 prior”和“赛中 evidence”显式分开 | 不能直接替代我们自己的时序复验与 tour-specific calibration |
| Glicko 网球研究（2022） | 2000–2019 大满贯，滚动窗口，ATP/WTA | Glicko 在 ATP/WTA 均优于官方排名；rating deviation 能表达久疏战阵后的不确定性 | Glicko 是 Elo 之外值得保留的 challenger，尤其适合缺赛后不确定性 | 赛事范围窄；仍不等于净市场 edge |
| Penn、Michael、Bhatt（2026） | 2024–2025 七项 major，预测 bookmaker odds | 实际赔率本身的 accuracy/Brier/log loss 约为 .741/.174/.523，优于其图模型和常见基线 | 市场是必须正面对比的强 benchmark，不能只超过官方排名就宣称有价值 | 目标是预测博彩公司赔率；依赖历史赔率；不能充当独立 tennis model |
| Wilkens（2021） | 约 39,000 场 ATP/WTA，2010–2019，滚动训练与真实赔率 | 多数 ML 约 70% accuracy，未稳定超过赔率；多数投注策略长期为负且高波动 | P3 必须把“概率模型好”与“扣成本后值得买”分开，并默认允许 NO BET | 博彩市场与 Polymarket 微结构不同，但“市场很难稳定击败”的结论仍是重要先验 |

主要来源：

- [Xie & Muppidi 2026：Live Tennis Forecasting](https://arxiv.org/html/2609.07617v1)
- [Poudel et al. 2026：Unified Tennis Prediction Benchmark](https://doi.org/10.3390/analytics5030022)
- [Gorgi, Koopman & Lit 2019：Dynamic Surface-Specific Model](https://doi.org/10.1111/rssa.12464)
- [Ingram 2019：Bayesian Hierarchical Point-Based Model](https://martiningram.github.io/papers/bayes_point_based.pdf)
- [Gollub 2017：Pre-match and In-play Tennis Models](https://dash.harvard.edu/server/api/core/bitstreams/dc501d43-9be0-4c8a-8066-480bd5ff5be5/content)
- [Kovalchik & Reid 2019：Calibration with Dynamic Updates](https://doi.org/10.1016/j.ijforecast.2017.11.008)
- [Glicko Rating Study](https://pmc.ncbi.nlm.nih.gov/articles/PMC8992979/)
- [Penn, Michael & Bhatt 2026：Forecasting Bookmakers' Odds](https://doi.org/10.1098/rsos.252512)
- [Wilkens 2021：Tennis Prediction and Betting Models](https://doi.org/10.3233/JSA-200463)

## 4. 推荐的 P3 概率体系

### 4.1 赛前层：不要先指定唯一冠军

至少同时保留以下内部基线：

1. **Overall + surface Elo**：最低复杂度和最容易审计的基线。
2. **Glicko 或 dynamic Bradley–Terry**：表达球员能力随时间变化、场地差异和不活跃期不确定性。
3. **HGBM challenger**：输入只能由开赛前可得且可稳定复算的特征构成，例如动态实力差、surface 能力、近期负荷、赛事级别、轮次、赛制、年龄/排名差和受控 H2H；不得使用未来统计。

深度神经网络暂不作为默认方案。不是因为它理论上无效，而是现有较大统一基准没有显示其相对精心构造的 Elo/树模型有稳定优势，而 TennixAI 当前的数据量、许可与可重复训练链路尚未证明足以支撑它。只要以后在同一内部基准上胜出，它仍可作为 challenger 晋升。

### 4.2 赛中层：规则骨架优先

网球有明确的 point → game → set → match 计分结构。给定：

- 当前盘、局、分；
- 当前发球方；
- 比赛赛制与决胜盘/tiebreak 规则；
- 两位球员各自在发球时赢下下一分的概率；

就可以用递归或动态规划计算当前状态下的整场胜率。该层应是独立、确定、可单元测试的 `ScoringProbabilityEngine`，而不是由 LLM 或黑盒模型学习计分规则。

[Klaassen & Magnus](https://doi.org/10.1016/S0377-2217(02)00682-3) 的层级 Markov 研究是这一方向的经典依据；其关于 point independence 的工作也提示，连续分并非严格 IID，但偏离通常没有大到让规则模型失去基线价值。

### 4.3 赛中能力更新：prior 与 live evidence 分开

开赛时，发球分胜率来自赛前能力 prior。比赛开始后，不能把“前 10 个发球分赢了 9 个”直接当成真实 90% 发球能力。应使用 beta-binomial 或等价 empirical-Bayes shrinkage：

- 样本少时主要相信赛前 prior；
- 随观测发球分增加，逐步提高 live evidence 权重；
- ATP/WTA、surface 和赛事层级使用独立拟合或校准；
- 若 PBP 缺失或乱序，则退化为只依赖比分与赛前 prior 的 Markov 概率，并降低 confidence，而不是伪造统计。

### 4.4 Hybrid challenger

HGBM 可以接收以下结构化输入：

- 赛前模型概率；
- pure-score Markov 概率；
- shrinkage-Markov 概率；
- 当前比分、server、赛制与比赛进度；
- 仅由当前 point 之前数据计算的 PBP 聚合；
- 已通过字段覆盖和一致性门的统计；
- 数据质量与样本量特征。

它学习结构模型尚未捕捉的非线性残差。这个设计比“完全黑盒地从比分猜赢家”更符合现有论文证据，也允许在缺少 live stats 时安全降级。

### 4.5 校准层

每个原始模型的概率都要在独立时间窗口上校准。Platt/logistic scaling、isotonic、beta calibration 或其他方法只能通过验证集选择；不能因为 temperature scaling 在深度学习中常用就默认适合所有树模型或分层人群。

最低报告集合：

- log loss（主指标）；
- Brier score；
- reliability diagram / cumulative calibration plot；
- ECE 等摘要及 bootstrap 置信区间；
- accuracy（只作辅助）；
- ATP 与 WTA、surface、赛前/赛中阶段分别报告。

[Gneiting & Raftery](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf) 说明 proper scoring rule 对概率预测的重要性；[JMLR 的 calibration metrics 研究](https://www.jmlr.org/papers/v23/22-0658.html) 也提醒，单一分箱 ECE 会受 bin 选择影响，不能作为唯一校准证据。

### 4.6 不确定性与弃权

P3 的核心能力不是“每场都给建议”，而是在证据不足时可靠地拒绝建议。应区分：

- `MODEL_UNAVAILABLE`：该 tour/赛事级别没有验证过的模型；
- `DATA_INCOMPLETE`：比分、server、PBP 或关键 prior 不完整；
- `OUT_OF_DISTRIBUTION`：赛制、场地、赛事或球员冷启动超出训练域；
- `MODEL_DISAGREEMENT`：结构模型与 challenger 分歧过大；
- `MARKET_UNMAPPED`：比赛与市场无法高置信映射；
- `INSUFFICIENT_LIQUIDITY`：`$10` 也无法在可接受滑点内成交；
- `NO_NET_EDGE`：扣除价差、手续费和安全边际后没有正 edge。

弃权要用 risk–coverage curve 评估：覆盖率提高时，剩余建议的错误率和校准如何变化。选择性预测的理论依据可参考 [Geifman & El-Yaniv 2017](https://proceedings.neurips.cc/paper_files/paper/2017/hash/4a8423d5e91fda00bb7e46540e2b0cf1-Abstract.html)。

## 5. 市场比较与“可执行 edge”

### 5.1 概率模型与市场模型必须隔离

建议保留两条不同实验轨道：

- **Independent model**：只使用网球数据，作为 TennixAI 对比赛真实胜率的估计。
- **Market-informed benchmark**：允许使用历史市场信息，用于研究市场是否带来增量，但绝不拿它与同一个当前市场价格做“独立 edge”比较。

LLM 不进入任何一条概率计算轨道。

### 5.2 不能拿页面展示价格直接相减

Polymarket 当前使用 CLOB。官方文档说明，页面展示通常是 bid/ask midpoint；买入时实际支付 ask，卖出时取得 bid。P3 对固定 `$10` paper stake 必须逐档读取订单簿，计算该金额的预期平均成交价，并记录未成交部分、价差和深度。[Polymarket Prices & Orderbook](https://docs.polymarket.com/concepts/prices-orderbook)

截至本调研日期，官方费用文档给出的 sports taker `feeRate` 是 `0.05`，公式为：

```text
fee = shares × feeRate × price × (1 - price)
```

例如价格为 `$0.50`、买入 `$10` 名义金额约为 20 shares，仅 taker fee 约为 `$0.25`。这已足以吃掉 2.5 个百分点的表面 edge。费率属于外部可变配置，运行时必须读取市场参数，不能把 `0.05` 永久硬编码。[Polymarket Fees](https://docs.polymarket.com/trading/fees)

决策层应计算：

```text
gross_edge = calibrated_model_probability - executable_average_price
net_edge   = gross_edge - fee_equivalent - slippage_buffer - uncertainty_margin
```

只有 `net_edge` 的保守估计仍为正，并且满足模型适用域、数据质量、映射和流动性门，才可生成 paper `BUY`; 否则输出明确的 `NO BET` 原因。

### 5.3 赛中不是低延迟套利产品

关于网球 in-play 市场的研究表明，现场快速交易者会在极短时间内把 point result 反映到价格中。API 传输、本地处理和用户手动操作都无法与 courtsider/专业 market maker 做纯延迟竞争。因此 P3 的定位应是 **校准后的决策支持与错价筛选**，不能承诺“比分先于市场”的 latency arbitrage。

Polymarket 市场数据可通过官方 [WebSocket market channel](https://docs.polymarket.com/api-reference/wss/market) 接收，API-Tennis 也提供 [live/PBP WebSocket](https://api-tennis.com/documentation_websocket)。两条流应各自保留 provider timestamp、received timestamp、sequence/version 与 stale 状态，再由服务层对齐；不能假定同时到达就代表同一真实时点。

## 6. 数据可行性与许可风险

### 6.1 当前 API-Tennis 能支持什么

[API-Tennis REST 文档](https://api-tennis.com/documentation) 和 WebSocket 文档表明，当前供应商可提供 fixtures、livescore、score、server、statistics 和 PBP；部分字段在具体赛事中可能为空。它足以支持 P3 runtime inference 的数据骨架，但不能仅凭“接口存在”推断所有 tour 都有相同覆盖率。

在冻结训练方案前，必须对真实样本做字段覆盖审计：按 ATP/WTA、赛事层级、surface、赛前/赛中、比赛阶段统计比分、server、PBP、关键 stats 的可用率、延迟、乱序、修订和退赛情况。

### 6.2 历史训练数据不能默认等于 runtime API

API-Tennis 条款目前没有清晰授予“长期归档并用于模型训练/商业衍生”的权利。这里不是法律结论，但在得到供应商书面确认前，不应把 API-Tennis 自动视为可永久积累的商业训练语料。[API-Tennis Terms](https://api-tennis.com/terms-of-use)

Jeff Sackmann 数据的现存归档镜像可用于复现实验，包含 ATP/WTA 历史赛果和大满贯 PBP，但镜像标注为 CC BY-NC-SA 4.0。它适合当前私人、非商业 R&D 基准；未来商业化前需要重新确认来源、归属、完整性和许可，不应形成无法替换的生产依赖。[Tennis Sackmann Archive](https://github.com/Aneeshers/tennis-sackmann-archive)

2026 Trace 论文公开了代码仓库，但仓库目前没有明确 LICENSE。我们可以根据论文独立复现方法，不能直接复制无许可代码。[Trace research repository](https://github.com/cx-57/live-tennis-research)

## 7. TennixAI 内部 SOTA 基准协议

### 7.1 数据切分

- 只做 chronological walk-forward；绝不随机打散比赛。
- 同一场比赛的所有 point states 必须属于同一个 split。
- 球员 rating、近期状态、H2H 和聚合统计只能使用预测时点之前的比赛。
- train 用于拟合，validation 用于模型/参数/校准选择，test 冻结且只在最终比较时打开。
- 另保留最近赛事的 shadow/paper 窗口，观察供应商数据与市场结构变化。

### 7.2 报告单位

同时报告：

- 每场固定 checkpoint（赛前、25%、50%、75%）；
- all-point state，但必须补充 match-weighted 指标，避免长比赛支配结果；
- ATP/WTA 分开；
- hard/clay/grass 分开；
- best-of-3/best-of-5、普通 tiebreak/特殊决胜盘规则分开；
- 已覆盖与被弃权样本分开。

### 7.3 Champion 晋升门

候选模型只有同时满足以下条件才可晋升：

1. 在 untouched out-of-time test 上，相对当前 champion 的 log loss 与 Brier 至少不恶化，并有可报告的 bootstrap 区间；若声称“更优”，差值区间必须支持该主张。
2. calibration 不因总体平均掩盖 ATP/WTA、surface 或比赛阶段的系统偏差。
3. 数据缺失时能确定性降级或弃权，不产生看似精确的概率。
4. 推理延迟、可重放性和版本追踪满足本地实时链路。
5. 用当时可执行订单簿和实际费率回放后，paper 决策不是由 midpoint、未来价格或结算结果泄漏制造的。

绝对 ECE、最低样本数、最大模型分歧和最低 net-edge 阈值现在不应凭直觉填写；应在数据审计和第一轮 walk-forward 结果出来后冻结。

## 8. 对 P3 产品设计的直接影响

### `/markets` 扫描页

- 默认只展示已高置信映射、模型可用、数据新鲜的单场胜者市场。
- 卡片同时展示 calibrated model probability、executable market price、net edge、confidence/data quality 和明确状态。
- `NO BET` 是一等结果，不应被隐藏成错误或空白。
- 赛前与赛中使用同一条概率轨迹，但明确标注当前依据是 pre-match prior、score-only、PBP-updated 还是 hybrid。

### Match Page

- 概率轨迹同时画 model 与 market；断流或 stale 时出现断点/阴影，不能插值伪装连续数据。
- 解释区列出“哪些证据改变了概率”和“为什么现在不建议买”，不输出 LLM 自造的数值归因。
- 退赛、取消、walkover 和 Polymarket 特定结算规则必须作为 market mapping 与 paper settlement 的输入，而不是仅看 API-Tennis 的赢家字段。

### Paper ledger

- 每场最多一次固定 `$10` 入场和一次规则化退出；市场价格向独立模型估值收敛、剩余 edge 消失或反转时可卖出，否则持有到结算。同场不复利、不加仓、不换边、不重新入场。
- 保存 prediction/model/calibration/data/market/rule 版本，以及入场与退出时的订单簿快照、预期成交、费用和弃权原因。
- 提前退出时并行计算“若持有到结算”的反事实 P&L，但反事实不计作另一笔交易；用于区分模型判断、入场质量和退出时机的贡献。
- P&L、ROI、最大回撤、机会数、覆盖率和按原因拆分的 NO BET 同时报告；不能只展示盈利交易。

## 9. 本轮不建议采用的捷径

- 不依据单篇论文的最高 accuracy 直接指定模型。
- 不把大满贯结果外推为 Challenger/ITF 已验证能力。
- 不把当前市场价送进独立概率模型后再宣称发现 edge。
- 不用 LLM 估概率、补统计或决定买卖。
- 不用 displayed midpoint 代替可执行价格。
- 不在训练许可未明确时无限期积累第三方原始数据。
- 不在 P3 混入加仓、换边、重新入场、任意止盈止损、Kelly 仓位、自动下单或 latency-arbitrage 承诺；除一次预先冻结的价值收敛退出外，其余复杂交易策略保留给有证据后的 P4/独立阶段。

## 10. 建议的下一步

1. 用户先审阅并批准本报告的研究方向；此时仍不选 champion。
2. 在 T55 规格中冻结概率/市场分层、候选模型集合、数据降级、弃权语义和内部 benchmark 协议。
3. 先做 API-Tennis 历史与 live 字段覆盖审计，以及 Polymarket 网球市场映射/深度/费率采样。
4. 用可合法使用的历史数据建立 reproducible benchmark：Elo → dynamic rating → Markov → shrinkage → HGBM challenger。
5. 根据统一 out-of-time 结果选择首个 champion，再让 v0 按真实状态与解释契约修改原型。
6. 首版只运行 paper decision。若没有模型在扣成本的市场回放中显示可信增量，产品应诚实停在概率对照和 `NO BET`，而不是为了“功能完整”强行给 BUY。

## 11. T55 后续批准：Market-to-Match 组合方式

**批准日期：** 2026-09-15

Polymarket 的网球 moneyline 提供完整 outcome 球员名、赛事上下文和独立 event/market/token ID，但实际网球事件的 `gameId` 可以为空，因此不能假设存在可与 API-Tennis 直接连接的公共比赛 ID。

T55 已批准使用 **市场独立展示 + 内部 Player ID 运行时精确组合**：

- Polymarket 与 API-Tennis 各自保留 provider identity，不创建人工维护的永久 link。
- 两个 Polymarket outcome 通过已有 Player Identity Registry 解析为内部 Player ID。
- API-Tennis 比赛也转换为同一内部 Player ID 对。
- 只有无序双方 ID 完全相同且候选唯一、上下文无冲突时，才临时组成 `DecisionContext`。
- 不使用 LLM、模糊相似度或人工确认完成最终连接。
- 未连接市场仍正常展示；只有大满贯及 ATP/WTA 主巡赛单打的成功连接项显示 `模型覆盖`，Challenger/ITF 不显示未覆盖警告。

只读真实 spike 使用 2026-09-15 至 09-16 窗口：125 个有效 Polymarket 网球 moneyline 对 477 条 API-Tennis 记录，得到 79 个唯一连接（63.2%）、0 个多候选；成功项时间差中位数 0 分钟、最大 45 分钟。成功项包含 18 场 WTA Singles、42 场男子 Challenger 和 19 场女子 Challenger；该窗口没有 ATP 主巡赛样本。25 个失败来自市场球员目录缺口，21 个来自无 API 当期球员对，主要集中在低级别赛事。

该 spike 证明“精确连接不会被迫退化为模糊人工绑定”，但不证明所有高级别赛事已经达到生产覆盖。P3 实施计划必须包含 ATP/WTA/大满贯 shadow coverage gate；连接缺失只能抑制模型标记，不能猜测或误绑。

---

这份研究的核心判断是：**TennixAI 的 SOTA 不应是一篇论文的名字，而应是一套不会被数据泄漏、概率失准和不可成交价格欺骗的持续基准与晋升机制。**
