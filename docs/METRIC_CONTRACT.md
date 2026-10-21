# 统一指标合同 v1.1.0

用户已确认采用折扣后口径。金额保留源数值精度，展示时四舍五入两位；币种未核验，单位为“源数据金额单位”。取消订单默认纳入全部订单及金额。销售额、利润、折扣不得相加构成“收入”。

## 粒度与金额映射

- fact_orders：每 Order Id 一行。先验证订单内运营属性；冲突字段置空，整单从时效分母隔离，但仍保留订单和明细金额，冲突报告明确记录去向。
- fact_order_items：每 Order Item Id 一行，sales=Order Item Total，gross_sales=Sales，reported_profit=Order Profit Per Order。
- 主键空/非法/重复、主要金额缺失会阻止建模，validate 仍输出异常报告。无业务依据不自动填补、去重或删除。
- 维度同键冲突不任取值：冲突属性置空，质量报告保留该规则。
- SQLite 与 Python 使用同一经审计标签，金额计算独立，分组经营金额亦独立对账。Power BI 使用导出的相同事实表和 DAX，已通过 404 项实际 Desktop 引擎检查，明细见 reports/powerbi/desktop_acceptance.json。

## 时效与取消

只在 Delivery Status 为已知未取消状态、实际/计划天数均为非负有限整数、且订单运营属性一致时计算 actual_days > planned_days。等于计划判未超期。取消、非法天数、未知状态、冲突订单的 is_over_schedule=NULL，不能当 0。

运营取消定义为 Delivery Status='Shipping canceled'。Order Status='CANCELED' 为另一个业务状态，差异独立审计。本地 1,488 笔疑似欺诈订单被源数据标为运输已取消，不据此认定其实际发生了交易损失。

## KPI 映射

以下 SQL 列均来自 sql/01_kpi_views.sql 的 v_kpi，Python 键同名；DAX 见 powerbi/measures.dax。比例内部为 0—1。没有有效分母时返回 NULL / None / BLANK，不输出 0 或 Inf。

空筛选的计数返回 0，DAX 的 Orders 与 Order Items 通过 COALESCE 统一该行为；无记录的金额和没有有效分母的比例保留 BLANK。取消订单单独筛选时，有效、超期、未超期订单数均为 0，超期率为空。

| SQL/Python 指标 | 中文口径与公式 | DAX |
|---|---|---|
| orders | fact_orders 行数，含取消与异常 | Orders |
| order_items | fact_order_items 行数 | Order Items |
| sales | SUM(Order Item Total)，折扣后记录销售额 | Sales |
| gross_sales | SUM(Sales)，折扣前辅助金额 | Gross Sales |
| reported_profit | SUM(Order Profit Per Order)，记录利润，不叫净利润 | Reported Profit |
| recorded_discount | SUM(Order Item Discount)，不强行与汇总差额完全相等 | Recorded Discount |
| reported_profit_margin | 记录利润 / 折扣后记录销售额 | Reported Profit Margin |
| average_order_value | 折扣后记录销售额 / 全部独立订单数 | Average Order Value |
| canceled_orders | 运营取消独立订单数 | Canceled Orders |
| canceled_order_rate | 运营取消独立订单数 / 全部独立订单数 | Canceled Order Rate |
| eligible_orders | 时效标签非空的独立订单数 | Eligible Orders |
| over_schedule_orders | is_over_schedule=1 的独立订单数 | Over Schedule Orders |
| within_schedule_orders | is_over_schedule=0 的独立订单数，严格排除空值 | Within Schedule Orders |
| unknown_timing_orders | 全部订单 - 取消订单 - 有效时效订单 | Unknown Timing Orders |
| conflict_orders | 存在订单内属性冲突的订单数 | Conflict Orders |
| over_schedule_order_rate | 超期订单 / 有效时效订单 | Over Schedule Order Rate |
| avg_positive_over_days | 仅超期订单的 AVG(actual-planned) | Average Positive Over Days |
| eligible_items | 所属订单时效标签非空的明细数，仅诊断 | Eligible Items |
| over_schedule_items | 所属订单超期的明细数，仅诊断 | Over Schedule Items |
| over_schedule_item_rate | 超期明细数 / 有效时效明细数，仅诊断 | Over Schedule Item Rate |
| canceled_sales_exposure | 已取消订单明细折扣后金额，不等于真实损失 | Canceled Sales Exposure |
| over_schedule_sales_exposure | 超期订单涉及的完整订单折扣后金额 | Over Schedule Order Sales Exposure |
| negative_profit_items | reported_profit<0 的明细数 | Negative Profit Items |
| negative_profit_item_rate | 负利润明细数 / 全部明细数，不等于亏损订单率 | Negative Profit Item Rate |

计数容差为 0；金额容差为 0.01；比例容差为 0.0001，即 0.01 个百分点；平均正超期天数容差为 0.0001 天。展示层四舍五入不反写底层。

## 商品与其他筛选

常规经营切片器按明细金额求和。商品选中后，Orders 等运营 DAX 使用涉及该商品的去重 order_id 集合，通过 TREATAS 筛选 fact_orders；不建立双向多对多关系。

商品筛选下 Sales 是被选商品明细的金额，Over Schedule Order Sales Exposure 是涉及这些商品的超期订单的整篮金额。二者口径不同，不能相加。全样本下二者对应常规整单统计。

分层超期贡献 = 该分层超期订单数 / 同一全样本超期订单总数。该值与分层内超期率不同。少于 100 笔有效订单标小样本；分别提供严重程度与超期量排名，不给主观复合评分。计划天数分层仅为描述性比较，不是运输方式的因果效果。

## 月份与比较

partial_month 仅表示有记录的日数不足日历天数；它不能证明业务记录是否齐全。business_completeness 默认 unverified。2018-01 的 31 天有记录、partial_month=0，但按用户要求不做经营同比/环比。其他月份只有符合确认政策、具备对应前期且非零分母时才产生观察值变化率；不可直接解释为经营改善或下滑。

完整政策修订见 DECISIONS.md。不同时间的每单明细数、品类结构变化会显著影响可比性，原 README 对末月“不完整”的断言已废弃。

2017-10 起结构变化的比较政策已由用户确认。当前配置为 confirmed_withheld，这些月份的 is_comparable=0、comparison_status=“待核验”，同比/环比数值为空、报表单元格显示“待核验”。月度金额趋势保留，不计算变化率、不作经营升降结论；该标记不代表已经认定数据缺失。

## 源金额与利润审计

源 Sales、Order Item Total、Order Item Discount 逐行存在约 0.01 内舍入差；汇总残差单列报告，不能强行调平。Benefit per order 和 Order Profit Per Order 重复字段不相加；Sales per customer 与 Order Item Total 重复字段不相加。45,902 笔多明细订单的利润值均有变化，支持逐明细累加，但无法据此确认财务利润组成。

