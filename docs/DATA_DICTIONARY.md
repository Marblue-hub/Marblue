# 数据字典 v1.1.0

源表粒度为订单明细；Order Item Id 是明细主键，Order Id 关联多条商品。
本文件仅展示字段与聚合范围，不输出姓名、电邮、地址、密码、经纬度或客户明文样本。
“下单时待确认”表示没有字段生成时间的外部证明，不能据此直接建立事前模型。P2 不在本次范围。

## 源字段

| 字段 | 中文解释 | 转换后字段/使用 | 取值范围或类型 | 可用时点 | 敏感性/风险 | 缺失率 |
|---|---|---|---|---|---|---|
| Type | 交易类型 | 不进入分析模型 | 分类/文本 | 下单时待确认 | 业务属性 | 0.0000% |
| Days for shipping (real) | 实际运输天数（源字段） | actual_days | 数值 [0, 6] | 事后或时点不明；禁作事前特征 | 业务属性；字段定义待核验 | 0.0000% |
| Days for shipment (scheduled) | 计划运输天数 | planned_days | 数值 [0, 4] | 下单时待确认 | 业务属性 | 0.0000% |
| Benefit per order | 记录收益（与记录利润重复） | benefit_per_order；仅审计，不重复计入金额 | 数值 [-4274.98, 911.8] | 事后或时点不明；禁作事前特征 | 业务属性；字段定义待核验 | 0.0000% |
| Sales per customer | 客户销售额（与明细总额重复） | sales_per_customer；仅审计，不重复计入金额 | 数值 [7.49, 1939.99] | 事后或时点不明；禁作事前特征 | 业务属性；字段定义待核验 | 0.0000% |
| Delivery Status | 源运输状态 | delivery_status | 分类/文本 | 事后或时点不明；禁作事前特征 | 业务属性；字段定义待核验 | 0.0000% |
| Late_delivery_risk | 源超期风险标签 | source_late_risk | 数值 [0, 1] | 事后或时点不明；禁作事前特征 | 业务属性；字段定义待核验 | 0.0000% |
| Category Id | 品类代码 | category_id | 数值 [2, 76] | 下单时待确认 | 本地关系标识，衍生行级数据不提交 | 0.0000% |
| Category Name | 品类名称 | category | 分类/文本 | 下单时待确认 | 业务属性 | 0.0000% |
| Customer City | 客户城市 | 不进入分析模型 | 文本；不输出身份取值 | 下单时待确认 | 身份/精细位置，不导出 | 0.0000% |
| Customer Country | 客户国家 | 不进入分析模型 | 文本；不输出身份取值 | 下单时待确认 | 身份/精细位置，不导出 | 0.0000% |
| Customer Email | 客户邮箱 | 不进入分析模型 | 文本；不输出身份取值 | 下单时待确认 | 身份/精细位置，不导出 | 0.0000% |
| Customer Fname | 客户名 | 不进入分析模型 | 文本；不输出身份取值 | 下单时待确认 | 身份/精细位置，不导出 | 0.0000% |
| Customer Id | 客户代码 | 不进入分析模型 | 分类/文本 | 下单时待确认 | 本地关系标识，衍生行级数据不提交 | 0.0000% |
| Customer Lname | 客户姓 | 不进入分析模型 | 文本；不输出身份取值 | 下单时待确认 | 身份/精细位置，不导出 | 0.0044% |
| Customer Password | 客户密码字段 | 不进入分析模型 | 文本；不输出身份取值 | 下单时待确认 | 身份/精细位置，不导出 | 0.0000% |
| Customer Segment | 客户类型 | customer_segment | 分类/文本 | 下单时待确认 | 业务属性 | 0.0000% |
| Customer State | 客户州/省 | 不进入分析模型 | 文本；不输出身份取值 | 下单时待确认 | 身份/精细位置，不导出 | 0.0000% |
| Customer Street | 客户街道地址 | 不进入分析模型 | 文本；不输出身份取值 | 下单时待确认 | 身份/精细位置，不导出 | 0.0000% |
| Customer Zipcode | 客户邮编 | 不进入分析模型 | 文本；不输出身份取值 | 下单时待确认 | 身份/精细位置，不导出 | 0.0017% |
| Department Id | 部门代码 | department_id | 数值 [2, 12] | 下单时待确认 | 本地关系标识，衍生行级数据不提交 | 0.0000% |
| Department Name | 部门名称 | department | 分类/文本 | 下单时待确认 | 业务属性 | 0.0000% |
| Latitude | 位置纬度 | 不进入分析模型 | 文本；不输出身份取值 | 下单时待确认 | 身份/精细位置，不导出 | 0.0000% |
| Longitude | 位置经度 | 不进入分析模型 | 文本；不输出身份取值 | 下单时待确认 | 身份/精细位置，不导出 | 0.0000% |
| Market | 交付市场 | market | 分类/文本 | 下单时待确认 | 业务属性 | 0.0000% |
| Order City | 订单目的城市 | 不进入分析模型 | 文本；不输出身份取值 | 下单时待确认 | 身份/精细位置，不导出 | 0.0000% |
| Order Country | 订单目的国家 | country | 分类/文本 | 下单时待确认 | 业务属性 | 0.0000% |
| Order Customer Id | 订单关联客户代码 | customer_id | 数值 [1, 20757] | 下单时待确认 | 本地关系标识，衍生行级数据不提交 | 0.0000% |
| order date (DateOrders) | 下单时间 | order_date | 2015-01-01 00:00:00 至 2018-01-31 23:38:00 | 下单时待确认 | 业务属性 | 0.0000% |
| Order Id | 订单代码 | order_id | 数值 [1, 77204] | 下单时待确认 | 本地关系标识，衍生行级数据不提交 | 0.0000% |
| Order Item Cardprod Id | 明细商品代码 | 不进入分析模型 | 分类/文本 | 下单时待确认 | 本地关系标识，衍生行级数据不提交 | 0.0000% |
| Order Item Discount | 明细折扣金额 | discount | 数值 [0, 500] | 下单时待确认 | 业务属性 | 0.0000% |
| Order Item Discount Rate | 明细折扣比例 | discount_rate | 数值 [0, 0.25] | 下单时待确认 | 业务属性 | 0.0000% |
| Order Item Id | 订单明细代码 | order_item_id | 数值 [1, 180519] | 下单时待确认 | 本地关系标识，衍生行级数据不提交 | 0.0000% |
| Order Item Product Price | 明细商品折扣前单价 | unit_price | 数值 [9.99, 1999.99] | 下单时待确认 | 业务属性 | 0.0000% |
| Order Item Profit Ratio | 源明细利润比例 | source_profit_ratio | 数值 [-2.75, 0.5] | 事后或时点不明；禁作事前特征 | 业务属性；字段定义待核验 | 0.0000% |
| Order Item Quantity | 明细商品数量 | quantity | 数值 [1, 5] | 下单时待确认 | 业务属性 | 0.0000% |
| Sales | 折扣前记录销售额 | gross_sales | 数值 [9.99, 1999.99] | 下单时待确认 | 业务属性 | 0.0000% |
| Order Item Total | 折扣后明细金额（主销售额） | sales | 数值 [7.49, 1939.99] | 下单时待确认 | 业务属性 | 0.0000% |
| Order Profit Per Order | 记录利润 | reported_profit | 数值 [-4274.98, 911.8] | 事后或时点不明；禁作事前特征 | 业务属性；字段定义待核验 | 0.0000% |
| Order Region | 订单所属区域 | region | 分类/文本 | 下单时待确认 | 业务属性 | 0.0000% |
| Order State | 订单目的州/省 | state | 分类/文本 | 下单时待确认 | 业务属性 | 0.0000% |
| Order Status | 源订单状态 | order_status | 分类/文本 | 事后或时点不明；禁作事前特征 | 业务属性；字段定义待核验 | 0.0000% |
| Order Zipcode | 订单目的邮编 | 不进入分析模型 | 文本；不输出身份取值 | 下单时待确认 | 身份/精细位置，不导出 | 86.2397% |
| Product Card Id | 商品代码 | product_id | 数值 [19, 1363] | 下单时待确认 | 本地关系标识，衍生行级数据不提交 | 0.0000% |
| Product Category Id | 商品品类代码 | 不进入分析模型 | 分类/文本 | 下单时待确认 | 本地关系标识，衍生行级数据不提交 | 0.0000% |
| Product Description | 商品描述 | 不进入分析模型 | 分类/文本 | 下单时待确认 | 业务属性 | 100.0000% |
| Product Image | 商品图片链接 | 不进入分析模型 | 分类/文本 | 下单时待确认 | 业务属性 | 0.0000% |
| Product Name | 商品名称 | product_name | 分类/文本 | 下单时待确认 | 业务属性 | 0.0000% |
| Product Price | 商品标价 | 不进入分析模型 | 分类/文本 | 下单时待确认 | 业务属性 | 0.0000% |
| Product Status | 商品库存状态标识（不可替代库存流水） | 不进入分析模型 | 分类/文本 | 事后或时点不明；禁作事前特征 | 业务属性；字段定义待核验 | 0.0000% |
| shipping date (DateOrders) | 源发运时间（非最终签收） | shipping_date | 2015-01-03 00:00:00 至 2018-02-06 22:14:00 | 事后或时点不明；禁作事前特征 | 业务属性；字段定义待核验 | 0.0000% |
| Shipping Mode | 运输模式 | shipping_mode | 分类/文本 | 下单时待确认 | 业务属性 | 0.0000% |

## 事实与维度

| 表 | 粒度/主键 | 内容 |
|---|---|---|
| fact_orders | 一订单 / order_id | 经过一致性校验的订单属性、标签、整单金额、明细数 |
| fact_order_items | 一明细 / order_item_id | order_id 外键、商品、数量、折扣后/前金额与记录利润 |
| dim_product | 一商品 / product_id | 品类、部门、商品名；冲突属性置空 |
| dim_customer | 一客户 / customer_id | 仅客户类型，无姓名、电邮、地址 |
| dim_date | 一日期 / date_key | 日历属性、实观日期覆盖、完整性与比较政策标记 |
| dim_geography | 唯一市场/区域/国家/州组合 / geo_key | 不使用城市作为唯一键 |
| dim_shipping | 一运输模式 / shipping_mode_key | 运输模式及计划天数范围 |

## 派生字段

- is_canceled：Delivery Status 为 Shipping canceled 取 1；已知其他运输状态取 0；未知状态为空。
- is_over_schedule：在未取消且有效天数、订单无冲突时，actual_days>planned_days 取 1，否则取 0；不适用为空。
- timing_state：over_schedule / within_schedule / not_applicable_canceled / not_applicable_unknown / not_applicable_conflict。
- positive_over_days：仅超期订单的实际减计划天数。
- partial_month：月内有记录日数少于日历日数；不代表业务记录是否齐全。
- business_completeness：unverified；不得从有记录日数推断业务完整。
- is_comparable：满足用户确认的时间比较政策，仅可作观察值算术变化，不能直接解释为经营效果。
- comparison_status：2017-10 及以后同比/环比为“待核验”，保留月度金额趋势，不作经营升降结论；此前依日期覆盖和比较政策标记。

## 状态与金额注意

Order Status 和 Delivery Status 是不同状态体系，不能默默合并。销售主口径为 Order Item Total；Sales 保留为折扣前金额。源字典没有完整解释利润组成和币种；记录利润仅作 reported profit。

## 来源审计

源字段字典文件：DescriptionDataCoSupplyChain.csv；SHA256：9828e34669bd6d77e3b4463364cc44a5d52446b5e246fc258758cfe592566c4b。
数据发布页：Fabian Constante、Fernando Silva、António Pereira，DataCo SMART SUPPLY CHAIN FOR BIG DATA ANALYSIS，Version 5，2019-03-12，DOI 10.17632/8gx2fvg2k6.5；发布页标注 CC BY 4.0。
链接：https://data.mendeley.com/datasets/8gx2fvg2k6/5 。本地文件与站点的下载链仍未独立证实，记录本地指纹不代表官方校验和。
