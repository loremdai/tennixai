# T124：共享容器内存清理与全部市场分页

日期：2026-09-30

## 资源清理

清理前共 82 个 Docker 容器：Tennix 的 PostgreSQL、Redis 两个容器在运行；其他项目有 54 个运行中容器和 26 个已停止容器。先核实了容器 Compose 项目标记和名称，再给运行中的其他容器最多 45 秒正常退出时间，最后删除这 80 个非 Tennix 容器。

PostgreSQL 和 Redis 的容器及其挂载卷保持运行和健康。删除容器时没有使用 `--volumes`；没有执行 volume、image 或 system prune。清理后 `docker ps -a` 只显示两个 Tennix 容器，Docker volume 列表仍保留既有数据卷。官方 [`docker container rm` 文档](https://docs.docker.com/reference/cli/docker/container/rm/)说明 `--volumes` 才会删除容器关联的匿名卷。

Colima VM 清理前总内存 7,922 MiB、可用 40 MiB、swap 为 0；memory PSI `full avg10` 为 64.57%。清理后一次读取显示可用 7,113 MiB、swap 仍为 0、`some avg10` 与 `full avg10` 均为 0.00%。这是同一台 VM 在移除其他容器后的实际观测值。

## 数据库分页

之前前端已经按每页 50 行调用 `/api/markets`，但后端先取回全部 2,497 个市场，装配比赛资料、报价和决策数据，再截取 50 行。现在 PostgreSQL 在市场查询中按赛事级别、性别、阶段筛选，按既有 `updated_at DESC, market_id ASC` 排序后使用 `LIMIT/OFFSET`；响应的 `total` 由同一筛选条件的 `COUNT` 查询得到。服务默认每页 50 行，并将上限固定在 50。

报价快照、Redis 热报价、球员与赛事资料、预测快照及决策观测都只按当前页市场/比赛 ID 批量装载。仅市场列表路径改用分页查询；机会摘要、市场流快照等其他读路径保留原有语义。前端原有的 `PAGE_SIZE=50` 和“加载更多”按需翻页行为保持不变。

查询按活动 `market_match_links` 关联比赛和赛事，因此未映射市场仍能出现在无筛选的全部市场列表，旧链接仍不会成为市场—比赛关系。阶段条件与原有映射一致：已关闭市场或完赛比赛为 `closed`，非关闭市场的 `live` 比赛为 `live`，非关闭市场的 `scheduled` 比赛为 `prematch`。

## 实际核验

- 重启前：`./scripts/tennix-live status` 为运行中，数据库和 Redis 健康。随后执行支持的 `down`/`up`；无 init、migration、LLM、订单或数据删除。
- 重启后直接请求后端默认第一页：HTTP 200，`page_size=50`，返回 50 行、`total=2497`。一次样本耗时约 95 ms。
- 第二页返回 50 行，第一页和第二页的市场 ID 不重叠。
- ATP 筛选返回 50 行、`total=100`，本页所有行的赛事级别均为 ATP。
- 通过 Next `/api/markets?page=1&page_size=50` 请求也返回 HTTP 200 和 50 行。
- 最终 `tennix-live status` 复核显示本地栈运行中，数据库/Redis healthy，sports stream 和 schedule 为 `ok`；排名上游仍为 `TIMEOUT_ERROR`，Polymarket 已恢复 `ok`。市场列表端点独立实测正常。
- 四个修改的 Python 源文件通过 `ast.parse`；Ruff 检查通过；`git diff --check` 通过。本任务未新增测试文件，也未运行测试套件。

SQLAlchemy 的 [`SELECT` 文档](https://docs.sqlalchemy.org/en/20/tutorial/data_select.html)记录了 `Select.limit()` 与 `Select.offset()` 生成分页查询的用法。
