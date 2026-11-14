# MRO 维修数据仓库（Python + dbt + DuckDB + Flask）

面向飞机维修公司数据组的维修数据仓库示例：把散落在维修系统与 Excel 里的
**工卡、部件拆装、飞行日志**统一入仓，支持序号件履历一键查询、适航指令适用性
判断、时寿件寿命预警与机队可靠性指标，网页控制台带模型血缘。

## 架构与数据流

```
维修系统/Excel 模拟                DuckDB 仓库                      dbt 三层建模                Flask 控制台
─────────────────              ──────────────                  ─────────────────           ─────────────
landing/ (xlsx/csv)  ──增量──▶  raw.* (主键幂等)        ──▶  staging.*   规范化+测试       /            总览
  按业务日期每日文件             ingest_state 高水位            intermediate.* 区间折叠     /sources     数据源
                                                              · 装机区间(INSTALL/REMOVE配对) /lineage   模型血缘(SVG)
                                                              · 机/日飞行聚合               /components  部件履历
                                                              · 区间小时/循环+窗口累计       /airworthiness AD+时寿件
                                                              · AD 机型/序号适用性           /metrics     可靠性指标
                                                              marts.* SCD2/履历/预警/指标
                                                                     │
                                                          dbt tests（error 级失败 → 下游 SKIP）
```

## 八项需求的落点

| # | 需求 | 实现位置 |
|---|------|----------|
| 1 | 工卡/拆装/飞行日志每日增量导入 | `seed/landing.py` 按业务日期切日文件；`ingest/loader.py` 高水位 + `INSERT OR REPLACE` 幂等 |
| 2 | dbt 三层建模、模型都带测试 | `dbt/models/{staging,intermediate,marts}`，每层 `schema.yml` 含 not_null/unique/relationships/accepted_values 等 |
| 3 | 部件装机位置按时间段留历史 | `marts/fct_component_position_history.sql`（SCD2，valid_from/valid_to/is_current） |
| 4 | 按装机区间累计部件小时和循环 | `int_installation_periods` → `int_installation_usage` → `int_part_cumulative_usage`（窗口函数） |
| 5 | AD 按机型和序号范围判断适用/完成 | `int_ad_applicability.sql`、`marts/fct_ad_status.sql` |
| 6 | 时寿件剩余寿命与预警 | `marts/fct_life_limited_parts.sql`（≤20% WARNING，≤0 EXPIRED） |
| 7 | 数据测试不过阻断下游 | `dbt build` 语义 + error 级测试；演示 `scripts/demo_blocking.sh` |
| 8 | 机队可靠性指标 | `marts/fct_reliability_monthly.sql`、`fct_reliability_fleet_monthly.sql` |

## 测试数据场景（确定性，随机种子固定）

- **SN-5001**：同一架 B-1001 上 **3 次拆下又装回**（4 个装机区间）
- **SN-5002**：B-1002 拆下 → 串到 B-1003 → 装回 B-1002
- **SN-5007**：B737 拆下后跨机型装到 A320
- **SN-5003**：全程在位无拆装；**SN-5004**：从未装机的备件
- **SN-5009**：时寿件 800h 上限，累计已超 → EXPIRED
- **SN-5005**：装机日动态选取，使其累计落在 1400~1450h（1500h 上限）→ WARNING
- **SN-5008**：2025-04 才装机的新时寿件 → HEALTHY

勾稽保证：`dbt/tests/assert_part_hours_reconcile.sql` 独立从机/日飞行聚合
重算每个部件的累计小时/循环，与窗口累计结果逐部件比对，不一致即测试失败。

## 快速开始

```bash
# 1. 建虚拟环境并安装（建议内网镜像 -i <mirror>）
uv venv --python 3.13 .venv
uv pip install -e .

# 2. 一键造数 + 入库 + dbt 建模（含全部测试）
.venv/bin/mro-dw run-all

# 3. 打开网页控制台 http://127.0.0.1:5050
.venv/bin/mro-dw web
```

分步执行：

```bash
.venv/bin/mro-dw init-db          # 初始化 DuckDB 与 raw 表
.venv/bin/mro-dw make-landing     # 生成 landing 日文件
.venv/bin/mro-dw ingest           # 增量导入（可 --until 2024-06-30 模拟每日批次）
.venv/bin/mro-dw ingest           # 再跑一次：幂等，行数不变
.venv/bin/mro-dw build            # dbt build（模型+测试，失败阻断下游）
```

阻断演示与自动化测试：

```bash
bash scripts/demo_blocking.sh     # 注入负小时脏数据，观察测试 fail、marts SKIP
.venv/bin/pytest                  # 端到端：幂等、增量水位、勾稽、SCD2、AD、预警、阻断
```

## 目录结构

```
src/mro_dw/
  seed/        测试数据生成 + landing 落地（xlsx/csv）
  ingest/      raw DDL + 高水位增量加载器
  runner/      dbt Python API 封装
  web/         Flask 控制台（只读连接 + 服务端 SVG 血缘）
dbt/
  models/      staging / intermediate / marts 三层
  macros/      自定义 schema 命名、通用测试
  tests/       singular 测试（勾稽、交替性、区间重叠、SCD2）
tests/         pytest 端到端测试
scripts/       阻断演示脚本
```

## 关键设计与排障

- **勾稽链路**：`int_flight_daily`（机/日聚合）是唯一使用量来源；区间小时在
  `int_installation_usage` 归集，部件累计在 `int_part_cumulative_usage` 用窗口函数计算；
  singular 测试 `assert_part_hours_reconcile` 从日聚合**独立重算**逐部件累计并比对，
  保证"累计 = 逐段相加"可被机器验证而不仅是口径声明。
- **增量幂等双保险**：raw 层主键 `ON CONFLICT DO UPDATE`；staging 层 dbt
  `incremental_strategy='merge' + unique_key`。重复 `ingest`/`build` 行数不变。
- **阻断语义**：`dbt build`（非 run+test 分离）把测试节点接入 DAG，error 级测试失败时
  其下游模型与测试自动 `SKIP`，命令退出码非零。
- **DuckDB 连接限制**：同一进程内不能以不同配置（读写/只读）并发打开同一库文件；
  测试中统一使用读写连接，网页控制台才用 `read_only=True`。
- dbt 1.11 对 `accepted_values: {values: [...]}` 旧式写法有弃用 **WARNING**（不影响
  119 个测试通过与构建结果），可在后续迁移到 `arguments:` 嵌套写法。
- 安装若遇到 `dbt-core-experimental-parser` 本地 Rust 编译卡住，用纯预编译 wheel：
  `uv pip install --only-binary :all: dbt-duckdb`。
