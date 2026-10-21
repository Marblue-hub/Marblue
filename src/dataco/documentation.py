"""Generate source dictionary without publishing identity values."""
import csv
import pandas as pd
from .ingestion import FIELDS, fingerprint

CN = dict(zip([
"Type","Days for shipping (real)","Days for shipment (scheduled)","Benefit per order","Sales per customer",
"Delivery Status","Late_delivery_risk","Category Id","Category Name","Customer City","Customer Country",
"Customer Email","Customer Fname","Customer Id","Customer Lname","Customer Password","Customer Segment",
"Customer State","Customer Street","Customer Zipcode","Department Id","Department Name","Latitude","Longitude",
"Market","Order City","Order Country","Order Customer Id","order date (DateOrders)","Order Id",
"Order Item Cardprod Id","Order Item Discount","Order Item Discount Rate","Order Item Id",
"Order Item Product Price","Order Item Profit Ratio","Order Item Quantity","Sales","Order Item Total",
"Order Profit Per Order","Order Region","Order State","Order Status","Order Zipcode","Product Card Id",
"Product Category Id","Product Description","Product Image","Product Name","Product Price","Product Status",
"shipping date (DateOrders)","Shipping Mode"],
[
"交易类型","实际运输天数（源字段）","计划运输天数","记录收益（与记录利润重复）","客户销售额（与明细总额重复）",
"源运输状态","源超期风险标签","品类代码","品类名称","客户城市","客户国家",
"客户邮箱","客户名","客户代码","客户姓","客户密码字段","客户类型",
"客户州/省","客户街道地址","客户邮编","部门代码","部门名称","位置纬度","位置经度",
"交付市场","订单目的城市","订单目的国家","订单关联客户代码","下单时间","订单代码",
"明细商品代码","明细折扣金额","明细折扣比例","订单明细代码",
"明细商品折扣前单价","源明细利润比例","明细商品数量","折扣前记录销售额","折扣后明细金额（主销售额）",
"记录利润","订单所属区域","订单目的州/省","源订单状态","订单目的邮编","商品代码",
"商品品类代码","商品描述","商品图片链接","商品名称","商品标价","商品库存状态标识（不可替代库存流水）",
"源发运时间（非最终签收）","运输模式"
]))
PRIVATE = {"Customer City","Customer Country","Customer Email","Customer Fname","Customer Lname",
           "Customer Password","Customer State","Customer Street","Customer Zipcode",
           "Order City","Order Zipcode","Latitude","Longitude"}
AFTER = {"Days for shipping (real)","Benefit per order","Sales per customer","Delivery Status",
         "Late_delivery_risk","Order Item Profit Ratio","Order Profit Per Order","Order Status",
         "shipping date (DateOrders)","Product Status"}

def write_dictionary(raw, d, cfg, root):
    descriptions = {}
    if cfg["dictionary"].is_file():
        with cfg["dictionary"].open(encoding=cfg["encoding"], newline="") as f:
            for row in csv.DictReader(f):
                descriptions[row["FIELDS"].strip().lower()] = row["DESCRIPTION"].lstrip(": ").strip()
    lines = [
        "# 数据字典 v1.1.0", "",
        "源表粒度为订单明细；Order Item Id 是明细主键，Order Id 关联多条商品。",
        "本文件仅展示字段与聚合范围，不输出姓名、电邮、地址、密码、经纬度或客户明文样本。",
        "“下单时待确认”表示没有字段生成时间的外部证明，不能据此直接建立事前模型。P2 不在本次范围。",
        "", "## 源字段", "",
        "| 字段 | 中文解释 | 转换后字段/使用 | 取值范围或类型 | 可用时点 | 敏感性/风险 | 缺失率 |",
        "|---|---|---|---|---|---|---|",
    ]
    for col in raw:
        target = FIELDS.get(col)
        risk = "身份/精细位置，不导出" if col in PRIVATE else "本地关系标识，衍生行级数据不提交" if " Id" in col else "业务属性；字段定义待核验" if col in AFTER else "业务属性"
        when = "事后或时点不明；禁作事前特征" if col in AFTER else "下单时待确认"
        kind = "文本；不输出身份取值" if col in PRIVATE else "分类/文本"
        if target in d:
            values = d[target]
            if pd.api.types.is_numeric_dtype(values):
                v = values.dropna()
                kind = f"数值 [{v.min():g}, {v.max():g}]" if len(v) else "数值；全空"
            elif pd.api.types.is_datetime64_any_dtype(values):
                v = values.dropna()
                kind = f"{v.min()} 至 {v.max()}" if len(v) else "日期；全空"
        missing = float(raw[col].astype("string").str.strip().eq("").mean())
        usage = target or "不进入分析模型"
        if col in {"Benefit per order","Sales per customer"}:
            usage += "；仅审计，不重复计入金额"
        lines.append(f"| {col} | {CN.get(col, '源字典待补充')} | {usage} | {kind} | {when} | {risk} | {missing:.4%} |")
    lines.extend([
        "", "## 事实与维度", "",
        "| 表 | 粒度/主键 | 内容 |", "|---|---|---|",
        "| fact_orders | 一订单 / order_id | 经过一致性校验的订单属性、标签、整单金额、明细数 |",
        "| fact_order_items | 一明细 / order_item_id | order_id 外键、商品、数量、折扣后/前金额与记录利润 |",
        "| dim_product | 一商品 / product_id | 品类、部门、商品名；冲突属性置空 |",
        "| dim_customer | 一客户 / customer_id | 仅客户类型，无姓名、电邮、地址 |",
        "| dim_date | 一日期 / date_key | 日历属性、实观日期覆盖、完整性与比较政策标记 |",
        "| dim_geography | 唯一市场/区域/国家/州组合 / geo_key | 不使用城市作为唯一键 |",
        "| dim_shipping | 一运输模式 / shipping_mode_key | 运输模式及计划天数范围 |",
        "", "## 派生字段", "",
        "- is_canceled：Delivery Status 为 Shipping canceled 取 1；已知其他运输状态取 0；未知状态为空。",
        "- is_over_schedule：在未取消且有效天数、订单无冲突时，actual_days>planned_days 取 1，否则取 0；不适用为空。",
        "- timing_state：over_schedule / within_schedule / not_applicable_canceled / not_applicable_unknown / not_applicable_conflict。",
        "- positive_over_days：仅超期订单的实际减计划天数。",
        "- partial_month：月内有记录日数少于日历日数；不代表业务记录是否齐全。",
        "- business_completeness：unverified；不得从有记录日数推断业务完整。",
        "- is_comparable：满足用户确认的时间比较政策，仅可作观察值算术变化，不能直接解释为经营效果。",
        "- comparison_status：2017-10 及以后同比/环比为“待核验”，保留月度金额趋势，不作经营升降结论；此前依日期覆盖和比较政策标记。",
        "", "## 状态与金额注意", "",
        "Order Status 和 Delivery Status 是不同状态体系，不能默默合并。销售主口径为 Order Item Total；Sales 保留为折扣前金额。源字典没有完整解释利润组成和币种；记录利润仅作 reported profit。",
        "", "## 来源审计", "",
        f"源字段字典文件：{cfg['dictionary'].name}；SHA256：{fingerprint(cfg['dictionary']) if cfg['dictionary'].is_file() else 'missing'}。",
        "数据发布页：Fabian Constante、Fernando Silva、António Pereira，DataCo SMART SUPPLY CHAIN FOR BIG DATA ANALYSIS，Version 5，2019-03-12，DOI 10.17632/8gx2fvg2k6.5；发布页标注 CC BY 4.0。",
        "链接：https://data.mendeley.com/datasets/8gx2fvg2k6/5 。本地文件与站点的下载链仍未独立证实，记录本地指纹不代表官方校验和。",
    ])
    (root / "docs/DATA_DICTIONARY.md").write_text("\n".join(lines)+"\n", encoding="utf-8")


def amount_audit(d, root):
    identities = {
        "gross_minus_discount_vs_sales": (d.gross_sales-d.discount, d.sales, 0.011),
        "reported_profit_vs_benefit": (d.reported_profit, d.benefit_per_order, 0.011),
        "sales_vs_sales_per_customer": (d.sales, d.sales_per_customer, 0.011),
        "gross_sales_vs_price_times_quantity": (d.gross_sales, d.unit_price*d.quantity, 0.011),
    }
    rows = []
    for name,(a,b,tol) in identities.items():
        valid = a.notna() & b.notna()
        delta = (a-b)[valid]
        rows.append({"identity":name,"evaluated_rows":int(valid.sum()),"within_row_tolerance":int(delta.abs().le(tol).sum()),
                     "row_tolerance":tol,"max_abs_error":float(delta.abs().max()) if len(delta) else None,
                     "signed_total_residual":float(delta.sum()) if len(delta) else None})
    pd.DataFrame(rows).to_csv(root / "reports/amount_audit.csv", index=False, encoding="utf-8-sig")

