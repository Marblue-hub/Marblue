<!-- 用户确认的两项口径修订；原桌面文件保持不变。 -->
# DataCo Supply Chain Analytics 修正案与开发规范（v1.1，本地实施修订）

> **文档状态**：可进入开发；未标记“已实现”的内容均为改造需求。  
> **版本日期**：2026-10-21  
> **目标项目**：DataCo Supply Chain Intelligence（DSCI）  
> **目标岗位**：通用数据分析、商业分析、供应链运营分析、BI 分析  
> **原仓库**：https://github.com/Mo-210/dataco-supplychain-analytics  
> **原数据**：https://data.mendeley.com/datasets/8gx2fvg2k6/5  
> **原则**：先保证数据和指标正确，再形成分析结论，最后扩展模型与交互。

## 0. 执行摘要与范围

本修正案不是原仓库的运行说明，而是**后续代码生成、重构、测试和验收的唯一需求基线**。原项目已经拥有数据清洗 Notebook、SQLite/SQL、EDA、4 页 Power BI 报表；本次升级将其改造成“数据治理 → 统一指标 → 业务诊断 → 可视化决策”的可复现分析项目。

**P0（必须完成）**：原数据加载与审计；订单级/明细级建模；统一 KPI；SQL/Python 跨端对账；描述性业务诊断；可刷新的 Power BI；一键执行和测试。  
**P1（建议完成）**：经营指标贡献度分解；运输模式与区域运营优先级；情景模拟；业务分析报告。  
**P2（可选）**：严格事前特征约束的延期风险预测；模型评估及风险队列；轻量 Streamlit 页面。

**明确不做**：实时车辆/仓储调度、采购供应商评级、真实库存优化、因果效果评估、企业级实时数据平台、未经数据支持的成本节省承诺。

## 1. 改造事项总表（Issue Register）

| 编号 | 优先级 | 原状 / 风险 | 修正后的约束 | 验收依据 |
|---|---|---|---|---|
| FIX-01 | P0 | 部分 SQL 用订单明细计数，Notebook 用独立订单计数 | 明确双事实表，运营 KPI 以独立订单为主，商品 KPI 以明细为主 | 多商品订单单元测试；指标跨端一致 |
| FIX-02 | P0 | “shipping/delivery”容易被解释为末端签收 | 核心 KPI 命名为“实际运输时长超过计划时长”，不推断末端签收、司机/线路根因 | README、图表、报告术语一致 |
| FIX-03 | P0 | 取消订单、缺失日期与风险标记可能混淆 | 三态时效标签：超期 / 未超期 / 不适用；取消/未知单独统计 | 互斥完整性测试 |
| FIX-04 | P0 | 源码部分 KPI 与 README 统计检验口径不一致 | 重新执行订单级分析，更新全部文字与数值，废弃旧 p 值的直接引用 | Notebook、SQL、README 对账 |
| FIX-05 | P0 | 2018-01 日期覆盖完整但业务完整性未验证，趋势易误读 | partial_month 仅标日期覆盖；按用户确认保留金额趋势，2017-10 及以后同比/环比列为待核验，不作经营升降结论 | 月报完整度检查 |
| FIX-06 | P0 | First Class 历史超期率 100%，可能包含规则/字段定义问题 | 专项审计计划天数与实际天数分布；展示“需验证”，不直接声称服务差 | 诊断表和审计备注 |
| FIX-07 | P0 | 原仓库手动运行较多，缺版本锁定 | 模块化 ETL、配置、依赖锁、命令行入口与 pytest | 新机器按 README 能重复执行 |
| FIX-08 | P1 | 仅排名，缺业务影响规模和决策逻辑 | 同时报告超期率、超期订单数、涉及订单销售额、样本规模 | 优先级表可追溯 |
| FIX-09 | P1 | 原情景模拟将假设改善幅度直接映射业务收益 | 明示情景是算术测算，成本须用户输入，禁称真实收益 | 假设清单、公式与边界检查 |
| FIX-10 | P2 | 预测容易使用结果字段发生泄漏 | 定义下单时特征白名单、时间切分、独立订单样本与泄漏审计 | 训练特征和模型验证报告 |
| FIX-11 | P0 | 原始字段含姓名、电邮、地址等敏感内容 | 输出脱敏；不把原始 CSV、凭据或个人信息上传仓库 | Git ignore 与输出检查 |

## 2. 数据事实、边界与禁止推断

### 2.1 固定的数据事实

- 输入优先使用 Mendeley 的 DataCo SMART SUPPLY CHAIN FOR BIG DATA ANALYSIS 第 5 版；下载后记录文件 SHA256、版本、文件名和载入时间。
- 原始记录约 **180,519 行订单明细**，对应约 **65,752 笔独立订单**；时间覆盖 2015 年至 2018 年 1 月，最后一个月日期覆盖完整，业务数据完整性未验证。原始数据包含约 53 个字段。上述值是**原版数据参考值**，不是对所有镜像文件的一律硬编码断言。
- `Order Item Id` 为明细粒度候选主键；`Order Id` 为独立订单标识。同一 `Order Id` 可能存在多行商品明细。
- `Days for shipping (real)` 和 `Days for shipment (scheduled)` 分别是源数据的实际/计划运输时长字段。`shipping date (DateOrders)` 是发运时间字段；**没有可核验的最终签收时间**。项目不得从该字段推断末端签收迟到或真实物流费用。
- `Order Profit Per Order` 虽名称含“Per Order”，原仓库将其按明细累加。须保留“记录利润（reported profit）”的来源说明，对同订单多明细抽样检查重复记账风险，再决定利润口径。
- 未提供仓库产能、运单承运商、路线、仓库工时、成本台账、真实采购价、库存流水、供应商主数据、退款和客户满意度。相关问题只能作为未来补充数据需求或明确假设。

### 2.2 统计原则

- **订单运营指标**：以 `fact_orders` 中一行一订单计算。
- **商品销售指标**：以 `fact_order_items` 中一行一明细计算。
- **销售额口径**：按用户确认使用 `SUM(Order Item Total)` 作为折扣后主销售额；`SUM(Sales)` 保留为折扣前辅助金额，并核查折扣一致性；不可同时相加这几个候选金额字段。
- **记录利润口径**：默认 `SUM(Order Profit Per Order)`，与实际财务净利润、发运成本、延期损失作明确区分。
- **超期指标**：仅在未取消且计划与实际时长有效时，定义 `is_over_schedule = 1(actual_days > planned_days)`，否则设为 `0` 或 `NULL`（不适用）；`NULL` 不得当作“按时”。
- **取消状态**：默认使用 `Delivery Status == 'Shipping canceled'` 作为源数据运营取消定义，同时单独审计 `Order Status == 'CANCELED'` 的冲突；不可将两个字段默默合并。
- **月份核验**：2018-01 日期覆盖完整但业务完整性未验证，排除该月经营同比环比，不将低销售额解释为经营下滑。
- **关联不等于因果**：不可声称发运超期导致利润下降、某运输方式造成超期、改造减少了实际延期或节约真实费用。

## 3. 目标架构及目录约定

```text
dataco-supply-chain-intelligence/
├─ README.md
├─ CHANGELOG.md
├─ pyproject.toml                   # 依赖及命令入口；锁定 Python/包版本
├─ .env.example                     # 仅放非敏感配置示例
├─ .gitignore
├─ config/
│  ├─ project.yaml                  # 文件位置、KPI、质量阈值、模式
│  └─ feature_whitelist.yaml        # P2 事前可用字段白名单
├─ data/
│  ├─ raw/                          # 原始 CSV；禁止提交
│  ├─ interim/                      # 规范化数据；禁止提交
│  ├─ processed/                    # 分析事实表及维度表
│  └─ db/dataco.sqlite
├─ src/dataco/
│  ├─ cli.py                        # validate / build / analyze / reconcile
│  ├─ ingestion.py                  # 读取、编码、schema 识别
│  ├─ quality.py                    # 数据质量规则与报告
│  ├─ transform.py                  # 字段派生、时效标签
│  ├─ mart.py                       # fact_orders、fact_order_items、维度表
│  ├─ metrics.py                    # Python 指标镜像及定义
│  ├─ analytics.py                  # 趋势、Pareto、风险分层、诊断
│  ├─ scenarios.py                  # P1 改善情景测算
│  └─ prediction.py                 # P2 事前风险预测
├─ sql/
│  ├─ 00_schema.sql
│  ├─ 01_kpi_views.sql
│  ├─ 02_commercial_analysis.sql
│  ├─ 03_fulfillment_analysis.sql
│  └─ 04_reconciliation.sql
├─ tests/
│  ├─ test_grain_and_keys.py
│  ├─ test_quality_and_labels.py
│  ├─ test_kpi_reconciliation.py
│  ├─ test_scenarios.py
│  └─ test_feature_leakage.py
├─ notebooks/                      # 仅用于探索和说明，不承担生产 ETL
├─ powerbi/                        # pbix、口径说明、布局截图
├─ reports/                        # KPI、质量、审计、研究结论及情景 CSV
└─ docs/
   ├─ DATA_DICTIONARY.md
   ├─ METRIC_CONTRACT.md
   ├─ REPRODUCTION.md
   ├─ LIMITATIONS.md
   └─ BUSINESS_CASE.md
```

**工程约定**：分析脚本不得依赖 Jupyter 的交互状态；所有路径从仓库根目录或配置解析；加载原始数据不修改源文件；在多次执行下产出相同结果；SQL 和 Python 调用同一派生标签规则；所有金额保留内部数值精度，仅在报表展示时四舍五入。

## 4. 数据模型与主键合同

| 表 | 粒度 | 主键 | 核心字段及关系 |
|---|---|---|---|
| `fact_orders` | 每个 `Order Id` 一行 | `order_id` | 订单时间、市场、配送模式、计划/实际天数、取消及超期状态、订单销售额、订单记录利润 |
| `fact_order_items` | 每个 `Order Item Id` 一行 | `order_item_id` | `order_id` 外键、`product_id`、数量、记录销售额、记录利润、折扣 |
| `dim_product` | 每个商品代码一行 | `product_id` | 品类、部门、商品名；冲突值须进质量报告 |
| `dim_customer` | 每个客户代码一行 | `customer_id` | 客户类型、可公开的聚合属性；不导出姓名/电邮/地址 |
| `dim_date` | 每个日期一行 | `date_key` | 年、月、季度、星期、完整月份标记 |
| `dim_geography` | 唯一标准地区组合 | `geo_key` | Market / Region / Country 等；不要假设同名城市唯一 |
| `dim_shipping` | 每个运输模式一行 | `shipping_mode_key` | 服务类型、计划天数范围的审计分布 |

**聚合前必须验证**：订单下 `Shipping Mode`、`Market`、订单日期、取消/超期状态、计划时长是否一致。不一致订单进入冲突报告并从订单级关键指标中按规则排除或隔离，不得用 `MAX`/`first` 静默覆盖。

**Power BI 关系**：`fact_orders` 一对多连接 `fact_order_items`；公共维度尽量单向筛选，禁止形成不必要的双向多对多关系。商品切片器若需筛选订单级超期率，必须通过“涉及该商品的去重订单集”专门编写 DAX / 桥表，不得简单交叉过滤后将明细行当订单。

## 5. 数据质量与标签规范

### 5.1 字段校验

- 必需字段：`Order Id`、`Order Item Id`、`order date (DateOrders)`、`Shipping Mode`、`Delivery Status`、`Days for shipping (real)`、`Days for shipment (scheduled)`、`Sales`、`Order Profit Per Order`。
- 校验：主键空值与重复、日期解析失败、负运输天数、负销售额、异常折扣比例、`Order Item Quantity <= 0`、发运时间早于下单时间、标签冲突、订单内属性不一致。
- `Late_delivery_risk` 作为**标签一致性校验字段**，不得直接用于事前模型特征；源数据中的取消单与状态冲突单单独审计。
- 未知或格式错误的数据先生成 `issues.csv`，保留原始值、规则编号、行标识及处理动作；默认不做没有业务依据的填补或删除。
- 输出总体行数、独立订单数、异常数、缺失率、源文件 SHA256、规则版本；可以展示质量评分，但不能把自定义评分当作客观行业标准。

### 5.2 时效标签真值表

| 状态 | 实际/计划时长 | `is_canceled` | `is_over_schedule` | 参与超期率分母 |
|---|---|---:|---:|---|
| 已取消 | 任意 | 1 | NULL | 否 |
| 未取消且时长有效，实际 > 计划 | 有效 | 0 | 1 | 是 |
| 未取消且时长有效，实际 <= 计划 | 有效 | 0 | 0 | 是 |
| 未取消但任一时长缺失/非法 | 缺失或非法 | 0 | NULL | 否，另报未知比例 |

如果源数据中同订单明细状态冲突，应先记录并执行明确隔离策略，不允许静默取第一行。`Order Status` 和 `Delivery Status` 的业务差异要在数据字典中单列。

## 6. 统一指标字典（Metric Contract）

| 指标 | 分子 / 公式 | 分母及粒度 | 特别说明 |
|---|---|---|---|
| 独立订单数 | `COUNT(fact_orders)` | 订单 | 含取消及异常，但需标识 |
| 订单明细数 | `COUNT(fact_order_items)` | 明细 | 不能当订单量 |
| 销售额 | `SUM(fact_order_items.sales)` | 明细 | 核查折扣与总额口径 |
| 记录利润 | `SUM(fact_order_items.reported_profit)` | 明细 | 不叫净利润或延期损失 |
| 记录利润率 | `记录利润 / 销售额` | 明细聚合 | 分母为 0 则 NULL |
| 订单客单价 | `销售额 / 独立订单数` | 订单/明细混合 | 明确取消单纳入政策，默认全部订单 |
| 取消订单率 | `取消订单数 / 全部订单数` | 订单 | 按 `Delivery Status` 的运营取消定义 |
| 超期订单率 | `超期有效订单数 / 时长有效且未取消订单数` | 订单 | 核心运营 KPI |
| 明细超期率 | `超期明细数 / 有效未取消明细数` | 明细 | 仅作诊断，不替代上行 |
| 平均超期天数 | `AVG(actual_days - planned_days)` | 超期且有效订单 | 只对正差计算 |
| 超期订单占比贡献 | `某分层超期订单数 / 全体超期订单数` | 订单 | 与分层内超期率不同 |
| 取消销售暴露额 | `SUM(已取消订单明细的记录销售额)` | 明细 | 是暴露额，不等于真实损失 |
| 负利润明细比例 | `利润<0 的明细数 / 明细总数` | 明细 | 不等于亏损订单率 |

**历史与本地对账值（主金额口径已修订）**：180,519 明细、65,752 订单、2,855 取消订单、36,048 超期有效订单、约 57.31% 订单级超期率；旧仓库的 36,784,735.01 对应折扣前 Sales。当前主销售额采用 Order Item Total，本地复现为 33,054,402.38；记录利润 3,966,902.97。若源版本不一致，输出差异，不允许强行调平。

## 7. 分析模块与输出合同

### A. 数据治理（P0）

**输入**：原始订单 CSV 和字段字典。  
**处理**：schema、类型、业务规则、粒度、订单内一致性检查；构造事实表和维度表。  
**输出**：`reports/data_quality.json`、`reports/data_quality_issues.csv`、Parquet 事实表、`data/db/dataco.sqlite`。  
**完成定义**：全部核查规则可追溯；重复跑结果一致；异常数据有去向；原始 CSV 不变。

### B. 经营分析（P0）

**问题**：规模、利润集中在哪里？哪些品类或市场“高销售低利润”？  
**分析**：月度销售/记录利润、市场与品类贡献、负利润 Pareto、客户类型分层。  
**输出**：`reports/commercial_summary.csv`、`reports/loss_pareto.csv`、趋势图及分析结论。  
**注意**：最后一个月份日期覆盖完整、业务完整性未核验，月度可比性需注明；“高销售低利润”只说明值得排查，不证明价格或采购成本问题。

### C. SLA 与业务异常分析（P0）

**问题**：哪些运输模式/市场/区域“超期率高”或“超期订单最多”？  
**分析**：订单级超期率、超期量、平均正超期天数、涉及订单销售额、分组样本量、按计划天数分层后的比较、First Class 100% 专项审计。  
**输出**：`reports/fulfillment_segments.csv`、`reports/first_class_audit.csv`。  
**默认显示规则**：少于 100 笔有效订单的分层打上“小样本”标记；排序同时提供“严重程度”和“影响规模”，不预设单一最优策略。

### D. 异常贡献度与业务优先级（P1）

**问题**：整体指标变化由哪些品类、区域或运输模式贡献？  
**分析**：使用同一总分母进行分组贡献拆解；同比/环比仅对可比周期；区分样本结构变化和组内率变化。  
**输出**：`reports/metric_drivers.csv`、`reports/priority_queue.csv`。  
**排序原则**：默认先提供二维排序（超期率 × 超期订单规模），用户若选择成本/权重评分，必须披露权重及归一化公式，不能假装为客观最优解。

### E. 运营改善情景模拟（P1）

**输入**：指定运输模式/区域，假设“超期率下降 x 个百分点”，可选干预订单比例和单位干预成本。  
**核心公式**：

```text
baseline_rate = delayed_orders / eligible_orders
new_rate = max(0, baseline_rate - improvement_pp / 100)
estimated_avoided_delays = round(eligible_orders * (baseline_rate - new_rate))
estimated_new_delays = delayed_orders - estimated_avoided_delays
scenario_cost = intervened_orders * assumed_cost_per_intervened_order
```

**约束**：`0 <= improvement_pp <= 100`；不得出现负订单数；输入为假设，不是模型预测；不自动换算“利润增加”或“节约金额”，没有实际成本字段时只报告用户设定成本下的情景测算。  
**输出**：`reports/scenario_results.csv` 和参数审计记录。

### F. 事前超期风险识别（P2，可选）

**预测时点**：订单创建时；每订单一条训练样本；仅非取消且具有可靠真值的历史订单进入监督学习。  
**准入特征**（需按字段字典复查可用时间）：`Shipping Mode`、计划运输天数、下单时 Market/Region/Country、Customer Segment、下单时间特征、下单时已知商品数量/订单金额。  
**禁止特征**：实际运输天数、实际发运时间、Delivery Status、Late_delivery_risk、基于结果构造的时效差、事后 Order Status、实际利润、未来客户累计指标、Order Id / Order Item Id 等标识代理变量。  
**对照**：只用运输方式/计划时长的简单基线 → Logistic Regression → 树模型（可选）。  
**切分**：按订单日期先后划分 train/validation/test（建议约 70/15/15，按日期边界实现），不允许同一订单跨集；只使用训练集拟合编码器、缺失填补和阈值；严格检查特征在预测时刻是否可得。  
**指标**：PR-AUC、ROC-AUC、Precision/Recall@K、Brier score、校准曲线、分层表现；保留测试集一次性最终评估。  
**输出**：`reports/model_evaluation.json`、风险分层结果、特征审计报告。  
**警示**：First Class 的确定性强关联可能让预测指标偏高；任何异常高分都要先做标签/时间/标识泄漏审计，而不是直接宣传算法突破。

## 8. Power BI 修正要求

**建议保留 4 页核心页面，另增加 1 页可选扩展**：

1. **经营总览**：销售额、记录利润、订单数、取消率、超期订单率、时间趋势；所有卡片标注统计单位。
2. **SLA 与异常诊断**：运输模式与地区超期率/超期订单量并列；计划天数分布和 First Class 审计提示。
3. **商品与利润分析**：品类销售、记录利润、负利润 Pareto、SKU 分层。
4. **客户与市场分析**：客户类型、地区市场、订单量、销售贡献、利润率。
5. **可选：情景模拟与风险队列**：参数输入、测算结果、业务优先级（必须标“假设情景”）。

要求统一 DAX 测量值来源；每个页面提供数据更新时间和指标解释；切片器不会导致订单级数值按明细重复计算；取消/未知状态分开；原 PBIX 可借鉴布局，但需替换误导性术语。**若无法自动生成/编辑 PBIX，必须至少提供干净的事实表、维度表、DAX 指标清单、页面布局规范，供 Power BI Desktop 连接实现。**

## 9. 接口、运行方式及工程验收

### 9.1 目标命令（新开发接口，原仓库尚无）

```bash
python -m dataco.cli validate --input data/raw/DataCoSupplyChainDataset.csv
python -m dataco.cli build --input data/raw/DataCoSupplyChainDataset.csv
python -m dataco.cli analyze
python -m dataco.cli reconcile
python -m dataco.cli scenario --mode "Standard Class" --improvement-pp 5
pytest -q
```

要求返回码 0 表示成功，非 0 表示失败；报错含字段、行标识、规则及建议；运行日志输出数据指纹、开始/完成时间和已生成产物，不包含个人明文信息。

### 9.2 必测用例

- 同一订单有 2 条商品明细：订单数为 1、明细数为 2；销售额正确求和。
- 同一订单混用不同 Shipping Mode：触发质量异常，不得任取一个值。
- 取消订单：不计入超期或未超期分母。
- 缺失/非法天数：时效标签为 NULL，未知率增加。
- 非取消且实际天数等于计划天数：判为未超期。
- 销售额为 0：利润率返回 NULL，不出现 Inf。
- 只有一个月份或经营完整性未核验的 2018-01：不能生成误导性完整环比结论。
- Python/SQL/Power BI KPI 对账：同名指标口径一致；金额展示差异容忍度不超过 0.01，比例不超过 0.01 个百分点（仅针对相同底层样本和四舍五入规则）。
- 情景模拟 `improvement_pp = 0`：避免超期单数为 0；超过现有率的改善幅度被截断到 0。
- P2 的训练特征：出现黑名单字段直接抛错；同一订单不跨训练集/测试集；无未来信息。
- `data/raw`、个人身份字段、`.env` 不被 Git 跟踪。

### 9.3 完成门槛

- **Gate 0 / 需求冻结**：数据字典、指标口径、字段风险标注确认。
- **Gate 1 / P0 数据层**：清洗、事实表、质量规则、SQL 对账全部通过。
- **Gate 2 / P0 分析层**：经营和超期分析能一键输出，图表指标与 SQL 一致。
- **Gate 3 / P0 BI**：4 页核心看板可刷新，问题点、口径、数据来源明确。
- **Gate 4 / P1**：贡献分解和情景模拟完成，含假设披露和测试。
- **Gate 5 / P2**：如需风险模型，完成时序实验、泄漏审计与独立测试。

**不得在 Gate 1 之前开始训练模型，也不得在 Gate 2 之前定稿业务结论。**

## 10. 项目文档与求职成果的验收定义

最终至少提交：

- `README.md`：业务问题、数据来源、架构图、如何运行、截图、主要发现、限制和仓库引用。
- `DATA_DICTIONARY.md`：字段中文释义、样本粒度、口径、数值取值、可用时点与敏感性。
- `METRIC_CONTRACT.md`：全部指标公式、过滤规则、粒度、空值规则、SQL/DAX 映射。
- `REPRODUCTION.md`：系统要求、数据获取、安装、命令、常见报错。
- `BUSINESS_CASE.md`：背景 → 问题 → 分析 → 证据 → 建议 → 假设与局限。
- 运行产物：质量报告、KPI 快照、对账报告、分析 CSV/图表、Power BI 文件或完整可重建说明。
- 单元测试与样例测试数据；仅展示**真实复现得到**的指标，禁止在简历中填写虚构的改进率或节省金额。

## 11. 推荐实施顺序（供代码助手逐项接单）

| 批次 | 开发任务 | 前置依赖 | 交付验收 |
|---|---|---|---|
| T01 | 初始化新仓库/依赖/配置/CLI 基础 | 无 | 可安装并显示 help |
| T02 | 原数据读取、Schema、质量审计 | T01 | JSON/CSV 质量报告和测试 |
| T03 | 标签定义、事实表与维度表 | T02 | 主外键、订单粒度及冲突测试 |
| T04 | SQLite 建库、指标视图、Python/SQL 对账 | T03 | 统一 KPI 快照 |
| T05 | 经营分析、超期分析、First Class 审计 | T04 | 分析 CSV、图和说明 |
| T06 | Power BI 四页和 DAX 指标体系 | T04–T05 | BI 与 Python/SQL 对账 |
| T07 | 贡献度与情景模拟 | T05 | 可选 P1 结果和单元测试 |
| T08 | 事前风险模型与泄漏审计 | T03–T05 | 可选 P2 评估与模型卡 |
| T09 | README、复现指南、业务报告、最终 QA | T06 / T07 | 新环境端到端验收 |

**给代码助手的统一指令**：每次只实现一个批次；先写或更新测试，再实现代码；不要改动 `data/raw`；任何 KPI 更改同时更新 `METRIC_CONTRACT.md` 与对应测试；如数据不支持某业务结论，应输出限制与待补充字段，而非生成模拟“真实结果”；提交时说明新增文件、执行命令、运行结果、已知限制。

## 12. 数据来源、授权与审计备注

- 源码：Mo-210/dataco-supplychain-analytics，MIT 许可；引用和保留许可声明，改造后注明非官方派生项目。
- 数据：Mendeley Data / DataCo SMART SUPPLY CHAIN FOR BIG DATA ANALYSIS（第 5 版），注意原发布方署名与数据许可证要求；下游分发优先引导用户到源站下载。
- 原仓库报告的营业和履约数字均为**待复现的历史参考结果**；本修正案不声称已经在本地完整跑通源数据。
- 需特别审计：订单/明细粒度混用、README 与 Notebook 统计检验版本不一致、First Class 100% 超期、2018-01 业务完整性未验证、源字段包含个人身份信息。

**本修正案完成时，下一步应执行 T01 → T02 → T03 → T04；之后再开展业务分析与 BI。**

## 13. 本地实施修订与核验项（2026-10-21）

- 本次只做 P0，直接改造下载的原项目；P1、P2 不在范围。
- 主销售额改为 Order Item Total，记录利润率及全部销售暴露额同步变更。参考原仓库 36,784,735.01 为折扣前金额，不再作为主销售额验收值。
- 本地复现：折扣后记录销售额 33,054,402.38，记录利润 3,966,902.97，记录利润率约 12.00%。金额单位未核验币种。
- 2018-01 有 31 个有记录日；日期覆盖完整与业务完整性分开，不参与经营同比环比。
- 用户已确认：2017-10 起每单明细数和品类结构变化，保留月度金额趋势，相关同比/环比统一列为“待核验”，不计算变化率、不作经营升降结论。该呈现政策已冻结，数据结构变化原因仍待核验。
- 原始数据 SHA256：fa6d022ed437155e1a2f0378710602848703c8a7f203f7ff5d77805bf8480aa6。
- Power BI 已追加完成四页原生展板、正式 PBIX 与可编辑 PBIP；Desktop 实际刷新、404 项 DAX 检查、切片器交互和 PBIX 保存重开验收均通过，详见 powerbi/ACCEPTANCE.md。
