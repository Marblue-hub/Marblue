# Power BI 四页打开、刷新与重建

正式交付为 DataCoSupplyChain_P0.pbix，已在 Desktop 2.159.883.0 实际刷新、保存和重开。DataCoSource/DataCoSupplyChain.pbip 为对应可编辑源项目，46 个测量值、四页 83 个原生视觉对象。实际验收见 ACCEPTANCE.md；legacy 下的旧 PBIX 仅为历史参考。

## 直接使用

1. 在 Desktop 打开 DataCoSupplyChain_P0.pbix，可直接查看已导入的数据和四页图表。
2. 数据更新后，先执行项目 run_pipeline.ps1，再在 Desktop 选择“刷新”；Python 管道不会自动更新已保存的 PBIX。
3. 迁移目录或电脑时，在“转换数据 → 编辑参数”修改 DataFolder，指向新位置的 powerbi/data 绝对路径；然后应用更改、刷新、保存。
4. 需要改代码或布局时，编辑 DataCoSource 的 PBIR/model.bim，或修改 scripts/build_powerbi_project.py 后执行。新生成的 PBIP 首次打开后须应用查询并刷新。
5. 验收命令：.venv/Scripts/python.exe scripts/verify_powerbi_desktop.py --pid <当前 Desktop PID>。本机 ADOMD 库默认位于 D:/Apps/Power BI Desktop/bin；更换安装位置需相应调整查询脚本参数。

本地作者工具是 @microsoft/powerbi-report-authoring-cli 0.5.0，桥接工具是 @microsoft/powerbi-desktop-bridge-cli 1.0.0，安装在被忽略的 .tools 目录。截图脚本 scripts/capture_powerbi_pages.mjs 通过官方 Desktop Bridge 获取原生画布，不重绘报表。

新环境只查看 PBIX 无需作者工具。重跑 DAX 验收需 Python 环境安装 psutil==7.2.2，并安装 Desktop；使用 Node 作者/截图工具时，执行 npm install --prefix .tools/pbi-author @microsoft/powerbi-report-authoring-cli@0.5.0。Desktop 工作副本位于 powerbi/DataCo，代码源项目位于 DataCoSource；建议在工作副本中应用和保存，保留源项目供代码重建。

## 连接与关系

1. 先运行项目 run_pipeline.ps1，生成 powerbi/data 的 7 张无姓名/邮箱/地址/经纬度表和 build_metadata.csv。
2. 在 Power BI Desktop 创建 DataFolder 文本参数，设置为本机本项目 powerbi/data 的绝对路径。
3. 按 queries.pq 建立 LoadData 函数及 8 个独立查询。加载前检查空白转换为 null；订单、商品、客户键为整数；date_key 为日期；金额为小数（不要改为固定两位货币型，会改变源精度）。
4. 关系均单向：dim_date[date_key]、dim_customer[customer_id]、dim_geography[geo_key]、dim_shipping[shipping_mode_key] 各一对多到 fact_orders；fact_orders[order_id] 一对多到 fact_order_items；dim_product[product_id] 一对多到 fact_order_items。不要再把公共维度连到 fact_order_items 形成第二条路径。
5. build_metadata 不建关系。dim_date 标为日期表。粘贴 measures.dax 的每条测量值，比例设置为百分比、金额显示两位小数但不改变存储精度。

## 四页布局

画布为 1280×720；左上标题、右上源数据载入 UTC；底部解释金额和时效口径。色彩用深蓝、青绿、橙色；无有效分母的比例保留空白，空样本计数为 0。源数据载入时间与 Desktop 刷新时间分别记录，后者见 reports/powerbi/desktop_refresh_metadata.json。

| 页面 | 上部卡片 | 主图 | 下部诊断和切片器 |
|---|---|---|---|
| 经营总览 | Sales、Reported Profit、Reported Profit Margin、Orders、Canceled Order Rate、Over Schedule Order Rate | 月度 Sales 与 Reported Profit；日期表的 is_comparable 与月份核验提示 | 市场销售与记录利润；取消、未知时效分别显示；年月/市场切片器 |
| SLA 与异常诊断 | Eligible Orders、Over Schedule Orders、Over Schedule Order Rate、Average Positive Over Days | 运输模式超期率与超期量分开展示；地区影响规模 | 按 Shipping Mode 与 planned_days 矩阵；First Class 审计提示；Small Sample Note |
| 商品与利润分析 | Sales、Reported Profit、Negative Profit Item Rate | 品类折扣后销售与记录利润；负利润绝对额 Pareto | SKU 表和类目切片器；订单指标必须使用涉及该商品的去重订单集 |
| 客户与市场分析 | Orders、Sales、Average Order Value、Reported Profit Margin | Customer Segment、Market 和 Region 的贡献 | 国家/地区聚合；不放客户 ID 明细或任何个人身份字段 |

图表显示金额单位为“源数据金额单位（币种未核验）”。超期统一解释为实际运输时长超过计划时长，不使用“签收迟到”。

## 商品筛选的专门口径

Orders、Eligible Orders、Over Schedule Orders 和 Average Positive Over Days 内使用 TREATAS(VALUES(fact_order_items[order_id]), fact_orders[order_id])。因此商品筛选后仍按涉及商品的独立订单计数；不靠双向关系。

Sales 在商品筛选下表示选中商品明细的金额；Over Schedule Order Sales Exposure 则表示涉及商品的超期订单整篮金额，二者不会被相加。取消暴露额默认仅选中明细口径。报告标题须说明金额范围。

## 对账与刷新检查

- reports/powerbi_expected_kpis.csv 是全样本期望值，reports/powerbi_filter_checks.csv 包含运输方式与商品筛选后的期望值。金额误差 ≤0.01，比例误差 ≤0.0001（0.01 个百分点），订单数必须精确相同。
- 加载后逐项核对全样本卡片，至少验证 First Class、Standard Class、一个多明细商品、取消状态、时间切片；检查组合筛选后的去重订单数。
- 取消订单不得落入超期或未超期分母；BLANK 时效不得被 DAX 的松散 = 0 误当未超期，因此测量值使用严格 == 0。
- 月度金额趋势使用 Sales 保留全部月份；2017-10 及以后月份的同比/环比按已确认政策列为“待核验”，不计算变化率、不作经营升降结论。日期表 comparison_status 提供该显示标记，is_comparable=0。2018-01 日期覆盖完整但业务完整性未核验。
- 刷新一次，在记录表写入 Desktop 版本、刷新时间、核对差异、四页截图，再另存新版 PBIX。

Gate 3 已通过。reports/powerbi/desktop_dax_results.json 是实际引擎查询结果；desktop_acceptance.json 记录 404 项逐项比较。期望值 CSV 保留为独立控制数，不冒充实测结果。以后数据发生变化，应重新刷新并执行验收，不沿用本次状态。

函数与空值运算核对依据：[Microsoft TREATAS 文档](https://learn.microsoft.com/en-us/dax/treatas-function-dax)、[DAX 运算符与 BLANK 比较规则](https://learn.microsoft.com/en-us/dax/dax-operator-reference)。这些文档核查不替代 Desktop 实测。

