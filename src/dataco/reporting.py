"""Human-readable report derived only from reconciled artifacts."""
import base64
import datetime as dt
import html
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BLUE, TEAL, ORANGE = "#245b9b", "#16877f", "#df8c35"


def charts(data, out):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.titleweight": "bold", "figure.facecolor": "white"})
    paths = []
    monthly = data["monthly_trends"]
    fig, ax = plt.subplots(figsize=(12, 4.4), layout="constrained")
    x = np.arange(len(monthly))
    ax.plot(x, monthly.sales / 1e6, color=BLUE, label="Sales after discount", lw=2.4)
    ax.plot(x, monthly.reported_profit / 1e6, color=TEAL, label="Reported profit", lw=2)
    for idx in x[monthly.is_comparable.eq(0).to_numpy(dtype=bool)]:
        ax.axvspan(idx-.45, idx+.45, color=ORANGE, alpha=.17)
    ax.set(xticks=x[::3], xticklabels=monthly.order_month.iloc[::3],
           ylabel="Million source units", title="Observed monthly sales and reported profit")
    ax.text(.01, .02, "Shading: comparisons withheld. Record/category mix changes from Oct 2017.",
            transform=ax.transAxes, fontsize=9, color="#555")
    ax.legend(loc="upper left", frameon=False)
    ax.grid(axis="y", alpha=.15)
    path = out / "monthly_sales_and_profit.png"
    fig.savefig(path, dpi=160); plt.close(fig); paths.append(path)

    modes = data["fulfillment_segments"].query("dimension == 'shipping_mode'").sort_values("over_schedule_rate")
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4), layout="constrained")
    axes[0].barh(modes.segment, modes.over_schedule_rate * 100, color=BLUE)
    axes[1].barh(modes.segment, modes.over_schedule_orders, color=TEAL)
    axes[0].set(xlabel="Eligible order rate (%)", title="Actual transport duration exceeds plan", xlim=(0, 113))
    axes[1].set(xlabel="Distinct orders", title="Order volume above schedule", xlim=(0, modes.over_schedule_orders.max()*1.2))
    for axis, values, fmt in [(axes[0], modes.over_schedule_rate*100, "{:.1f}%"), (axes[1], modes.over_schedule_orders, "{:,.0f}")]:
        for y, value in enumerate(values):
            axis.text(value + max(values)*.018, y, fmt.format(value), va="center", fontsize=9)
        axis.grid(axis="x", alpha=.15); axis.set_axisbelow(True)
    path = out / "fulfillment_by_mode.png"
    fig.savefig(path, dpi=160); plt.close(fig); paths.append(path)

    cats = data["commercial_summary"].query("dimension == 'category'").nlargest(10, "sales").sort_values("sales")
    fig, ax = plt.subplots(figsize=(12, 5.4), layout="constrained")
    y = np.arange(len(cats))
    ax.barh(y+.17, cats.sales/1e6, height=.32, color=BLUE, label="Sales after discount")
    ax.barh(y-.17, cats.reported_profit/1e6, height=.32, color=TEAL, label="Reported profit")
    ax.set(yticks=y, yticklabels=cats.segment, xlabel="Million source units",
           title="Top ten categories by recorded sales")
    ax.legend(loc="lower right", frameon=False)
    ax.grid(axis="x", alpha=.15); ax.set_axisbelow(True)
    path = out / "category_sales_profit.png"
    fig.savefig(path, dpi=160); plt.close(fig); paths.append(path)

    market = data["commercial_summary"].query("dimension == 'market'").sort_values("sales")
    loss = data["loss_pareto"].head(10)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.4), layout="constrained")
    axes[0].barh(market.segment, market.sales/1e6, color=BLUE)
    axes[0].set(xlabel="Million source units", title="Recorded sales by market")
    axes[1].barh(loss.category.iloc[::-1], loss.loss_amount.iloc[::-1]/1e6, color=ORANGE)
    axes[1].set(xlabel="Million source units", title="Negative item profit magnitude")
    for ax in axes:
        ax.grid(axis="x", alpha=.15); ax.set_axisbelow(True)
    path = out / "market_and_loss.png"
    fig.savefig(path, dpi=160); plt.close(fig); paths.append(path)
    return paths


def fmt_number(value, digits=2):
    return "不适用" if pd.isna(value) else f"{value:,.{digits}f}"


def table(frame, columns, limit=20):
    d = frame.loc[:, [c for c in columns if c in frame]].head(limit).copy()
    labels = {
        "segment": "分层", "sales": "记录销售额（折扣后）", "reported_profit": "记录利润",
        "reported_profit_margin": "记录利润率", "orders": "独立订单数",
        "order_items": "明细数", "eligible_orders": "有效订单数",
        "over_schedule_orders": "超期订单数", "over_schedule_rate": "超期订单率",
        "avg_positive_over_days": "平均正超期天数",
        "over_schedule_sales_exposure": "超期订单涉及销售额",
        "small_sample": "小样本", "category": "品类",
        "loss_amount": "负利润明细绝对额", "negative_items": "负利润明细数",
        "cumulative_loss_share": "累计占比", "order_month": "月份",
        "partial_month": "日期覆盖不完整", "is_comparable": "可作观察值比较",
        "comparison_status": "同比/环比状态",
        "observed_days": "有记录日数", "days_in_month": "日历天数",
        "planned_days": "计划天数", "actual_days": "实际天数",
        "delivery_status": "源运输状态", "order_status": "源订单状态",
        "sales_mom_change": "金额观察值环比", "sales_yoy_change": "金额观察值同比",
    }
    rates = {"over_schedule_rate", "reported_profit_margin", "cumulative_loss_share", "sales_mom_change", "sales_yoy_change"}
    for c in d:
        if c in rates:
            if c in {"sales_mom_change", "sales_yoy_change"} and "comparison_status" in frame:
                review_labels = frame.loc[d.index, "comparison_status"]
                d[c] = [label if pd.isna(v) and label in {"待核验", "待确认"} else
                        "不适用" if pd.isna(v) else f"{v:.2%}"
                        for v, label in zip(d[c], review_labels)]
            else:
                d[c] = d[c].map(lambda v: "不适用" if pd.isna(v) else f"{v:.2%}")
        elif pd.api.types.is_numeric_dtype(d[c]):
            digits = 0 if c in {"orders", "order_items", "eligible_orders", "over_schedule_orders", "negative_items", "observed_days", "days_in_month", "partial_month", "is_comparable", "small_sample"} else 2
            d[c] = d[c].map(lambda v: fmt_number(v, digits))
    return d.rename(columns=labels).to_html(index=False, border=0, classes="data", escape=True)


def evidence(data, kpi):
    commercial = data["commercial_summary"]
    top_categories = commercial.query("dimension == 'category'").nlargest(10, "sales")
    category = top_categories.iloc[0]
    market = commercial.query("dimension == 'market'").nlargest(1, "sales").iloc[0]
    modes = data["fulfillment_segments"].query("dimension == 'shipping_mode'")
    first = modes[modes.segment.eq("First Class")].iloc[0]
    volume = modes.nlargest(1, "over_schedule_orders").iloc[0]
    top_loss = data["loss_pareto"].head(3)
    below = top_categories[top_categories.reported_profit_margin.lt(kpi["reported_profit_margin"])]
    below_note = "；".join(f"{r.segment}（记录利润率 {r.reported_profit_margin:.2%}）" for r in below.head(3).itertuples())
    return [
        f"全样本含 {kpi['orders']:,} 笔独立订单、{kpi['order_items']:,} 条明细。记录销售额（折扣后）为 {kpi['sales']:,.2f}，记录利润为 {kpi['reported_profit']:,.2f}，记录利润率为 {kpi['reported_profit_margin']:.2%}。",
        f"销售规模最大的市场为 {market.segment}，记录销售额 {market.sales:,.2f}，占全样本 {market.sales_contribution:.2%}；销售规模最大的品类为 {category.segment}，记录销售额 {category.sales:,.2f}。",
        f"销售额前十的品类中，{below_note or '没有品类'}的记录利润率低于全样本水平。该对照可作为交易构成复查线索，不能证明定价或采购成本问题。",
        f"有效且未取消的 {kpi['eligible_orders']:,} 笔订单中，{kpi['over_schedule_orders']:,} 笔实际运输时长超过计划，比例 {kpi['over_schedule_order_rate']:.2%}；超期订单的平均正差为 {kpi['avg_positive_over_days']:.2f} 天。此指标不代表最终签收迟到。",
        f"First Class 的 {int(first.eligible_orders):,} 笔有效订单超期率为 {first.over_schedule_rate:.2%}。须先核验源数据计划规则与字段定义，现有记录不能解释物流根因。",
        f"{volume.segment} 的超期订单数量最多，为 {int(volume.over_schedule_orders):,} 笔，占全部超期订单 {volume.over_schedule_contribution:.2%}。这说明涉及样本规模；尚不能评估改善成本或效果。",
        f"负利润明细共 {kpi['negative_profit_items']:,} 条，占明细 {kpi['negative_profit_item_rate']:.2%}；负利润绝对额排名前三品类合计占 {top_loss.loss_share.sum():.2%}。负利润明细不等于亏损订单。",
        f"运营取消订单 {kpi['canceled_orders']:,} 笔，取消销售暴露额 {kpi['canceled_sales_exposure']:,.2f}；这是源数据记录金额，不代表确认损失。取消状态差异另见专项审计。",
        "2018 年 1 月有 31 个有记录日，不能据此证明全部业务记录已收齐。2017 年 10 月起明细数/订单数与品类结构变化，趋势比较按已确认政策限制，不把观察值下降直接解释为经营下滑。",
    ]


def write_business_case(lines, root):
    text = "# DataCo 业务分析报告（P0）\n\n"
    text += "## 背景与问题\n\n基于本地订单明细，识别规模与记录利润分布，核对订单运输时长相对于计划的偏差。该分析没有最终签收时间、承运商、真实成本、退款或库存流水。\n\n"
    text += "## 复现证据\n\n" + "\n\n".join(f"{idx}. {line}" for idx, line in enumerate(lines, 1))
    text += "\n\n## 建议与待补充数据\n\n"
    text += "先验证 First Class 的计划天数规则与实际时长字段生成方法；再结合运输方式、计划天数和地区分层定位涉及订单最多的组合。经营分析优先复查高销售但记录利润率较低的分层、负利润集中品类的交易构成。\n\n"
    text += "请数据提供方解释 2017 年第四季度起每单明细数与品类结构的变化；补充订单总额对账、币种、利润组成、运单承运商、路线、成本和退款信息后，再评估业务原因与干预预算。本次没有情景收益或预测模型。\n\n"
    text += "## 口径与限制\n\n销售额使用 Order Item Total；Sales 仅为折扣前辅助金额。所有金额为未核验币种的源数据金额单位。记录利润按明细累加，不等于财务净利润。同比/环比仅表示经政策许可的观察记录算术变化，不是因果证据。统计检验旧 p 值不沿用。\n\n"
    text += "证据文件：reports/kpi_snapshot.json、reconciliation.csv、commercial_summary.csv、monthly_trends.csv、fulfillment_segments.csv、first_class_audit.csv、cancellation_status_audit.csv。\n"
    (root / "docs/BUSINESS_CASE.md").write_text(text, encoding="utf-8")


def write_html(data, kpi, images, lines, cfg, root):
    def img(index):
        encoded = base64.b64encode(images[index].read_bytes()).decode()
        return '<img class="chart" alt="分析图表" src="data:image/png;base64,' + encoded + '">'
    def card(label, value, note):
        return f'<div class="card"><div>{label}</div><strong>{value}</strong><small>{note}</small></div>'
    def section(title, body):
        return f"<article><h2>{title}</h2>{body}</article>"
    commercial = data["commercial_summary"]
    segments = data["fulfillment_segments"]
    monthly = data["monthly_trends"]
    amount_cols = ["segment","orders","sales","reported_profit","reported_profit_margin"]
    ops_cols = ["segment","eligible_orders","over_schedule_orders","over_schedule_rate",
                "avg_positive_over_days","over_schedule_sales_exposure","small_sample"]
    cards = "".join([
        card("记录销售额（折扣后）", f"{kpi['sales']/1e6:.2f} 百万", "源数据金额单位，币种未核验"),
        card("记录利润", f"{kpi['reported_profit']/1e6:.2f} 百万", f"记录利润率 {kpi['reported_profit_margin']:.2%}"),
        card("独立订单数", f"{kpi['orders']:,}", f"明细 {kpi['order_items']:,} 条"),
        card("实际运输时长超过计划的订单率", f"{kpi['over_schedule_order_rate']:.2%}", f"分母 {kpi['eligible_orders']:,} 笔有效未取消订单"),
    ])
    overview = section("全样本核对结果", '<div class="cards">' + cards + '</div>' +
        '<p class="note">主销售额采用 Order Item Total。运营指标按独立订单计算，商品金额按明细汇总。取消、未知时效分别处理。</p>' +
        img(0)) + section("月份覆盖与比较状态", table(monthly.tail(8), [
            "order_month","orders","order_items","sales","reported_profit","observed_days","days_in_month",
            "is_comparable","comparison_status","sales_mom_change","sales_yoy_change"]))
    sla = section("运输模式：比例与涉及规模", img(1) + table(segments.query("dimension == 'shipping_mode'"), ops_cols)) + \
        section("地区：按超期订单数查看", table(segments.query("dimension == 'region'").nlargest(15,"over_schedule_orders"), ops_cols)) + \
        section("同计划时长分层", table(segments.query("dimension == 'shipping_mode_planned_days'"), ops_cols)) + \
        section("First Class 专项审计", '<p class="note">该模式结果需验证。没有承运商、路线和最终签收数据，不能直接判断服务质量原因。</p>' +
            table(data["first_class_audit"], ["planned_days","actual_days","delivery_status","order_status","orders","over_schedule_orders"]))
    products = section("品类销售与记录利润", img(2) +
        table(commercial.query("dimension == 'category'").nlargest(15,"sales"), amount_cols)) + \
        section("负利润明细 Pareto", table(data["loss_pareto"], ["category","negative_items","loss_amount","cumulative_loss_share"]))
    customers = section("市场与负利润分布", img(3) +
        table(commercial.query("dimension == 'market'").sort_values("sales", ascending=False), amount_cols)) + \
        section("客户类型", table(commercial.query("dimension == 'customer_segment'"), amount_cols))
    audit = json.loads((root / "reports/data_quality.json").read_text(encoding="utf-8"))
    when = dt.datetime.fromisoformat(audit["loaded_at_utc"]).astimezone(dt.timezone(dt.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M（北京时间）")
    bullets = "".join("<li>"+html.escape(line)+"</li>" for line in lines)
    downloads = "".join(f'<a href="{name}.csv">{label}</a>' for name,label in [
        ("commercial_summary","经营分层"),("monthly_trends","月度趋势"),("fulfillment_segments","时效分层"),
        ("loss_pareto","负利润 Pareto"),("first_class_audit","First Class 审计"),("reconciliation","SQL/Python 对账")])
    template = """<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>DataCo 源数据分析</title><style>
*{box-sizing:border-box}body{margin:0;background:#f0f4f8;color:#1e3043;font:15px/1.65 "Microsoft YaHei",sans-serif}
header{background:#112b46;color:#fff;padding:32px max(24px,calc((100vw - 1250px)/2))}
header h1{font-size:30px;margin:0 0 7px}header p{color:#b9cadb;margin:0}
main{max-width:1300px;margin:24px auto;padding:0 24px}
nav{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0}button{border:1px solid #c8d6e3;border-radius:6px;padding:11px 20px;background:#fff;color:#203c57;cursor:pointer;font:inherit}
button.active{background:#245b9b;color:#fff;border-color:#245b9b}article{padding:24px;background:#fff;border:1px solid #dde5ed;border-radius:10px;margin:18px 0;overflow-x:auto}
h2{font-size:19px;margin:0 0 16px}p{margin:10px 0}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.card{background:#f2f7fb;border-top:3px solid #16877f;border-radius:5px;padding:17px}
.card div{font-size:13px;color:#476075}.card strong{display:block;font-size:27px;line-height:1.6;white-space:nowrap}.card small{display:block;font-size:11px;color:#5a6b7a}
.note{padding:12px 15px;background:#fff4e4;border-left:3px solid #df8c35;color:#694b25}.chart{width:100%;height:auto;display:block;margin:12px 0}
table{border-collapse:collapse;width:100%;font-size:12px;white-space:nowrap}th{background:#eaf1f7;text-align:left;padding:10px}td{border-bottom:1px solid #e5ebf0;padding:9px 10px;text-align:right}td:first-child{text-align:left}tr:hover{background:#f7fafc}
.page{display:none}.page.active{display:block}details{background:#fff;border:1px solid #dde5ed;border-radius:8px;padding:15px 22px;margin:16px 0}summary{cursor:pointer;font-weight:600}li{margin:10px 0}
a{color:#245b9b}footer{font-size:12px;color:#52687c;padding:16px 0 32px}.downloads{display:flex;gap:20px;flex-wrap:wrap}
input{padding:9px 13px;border:1px solid #c8d6e3;border-radius:5px;font:inherit;width:280px}
@media(max-width:950px){.cards{grid-template-columns:repeat(2,1fr)}main{padding:0 14px}article{padding:16px}}
@media print{nav,input{display:none}.page{display:block}article{break-inside:avoid}header{padding:20px}}
</style><header><h1>DataCo 源数据分析</h1><p>P0 数据治理与业务诊断 · 2015-01 至 2018-01 · 非官方派生分析</p></header><main>
<p>数据载入：__WHEN__　SQL / Python：24 项 KPI 通过　金额：源数据金额单位</p>
<div class="note">2018 年 1 月日期覆盖完整，业务数据完整性未验证。2017 年 10 月起记录结构变化；同比/环比依已确认政策展示。超期仅指实际运输时长超过计划时长。</div>
<nav><button class="active" data-page="overview">经营总览</button><button data-page="sla">时效与异常</button><button data-page="products">商品与利润</button><button data-page="customers">客户与市场</button></nav>
<label>筛选当前表格文字 <input id="search" placeholder="输入地区、运输模式或品类"></label>
<div class="page active" id="overview">__OVERVIEW__</div><div class="page" id="sla">__SLA__</div>
<div class="page" id="products">__PRODUCTS__</div><div class="page" id="customers">__CUSTOMERS__</div>
<details open><summary>复现发现与解释边界</summary><ol>__BULLETS__</ol></details>
<details><summary>审计与口径</summary><p>源文件 SHA256：<code>__SHA__</code></p>
<p>审计记录 4,062 条明细状态差异，无阻断项、无订单属性冲突。全部保留；运营取消按 Delivery Status。记录利润按明细累加；未获得真实成本、库存、退款或最终签收时间。</p>
<p>报告只展示聚合信息。SQLite、事实表及详细质量记录保留在本地；原始 CSV 保持不变。Power BI Desktop 独立验收见 powerbi/ACCEPTANCE.md 与 reports/powerbi/desktop_acceptance.json；Python 管道不自动刷新 PBIX。</p></details>
<article><h2>可追溯数据输出</h2><div class="downloads">__DOWNLOADS__</div><p>完整口径见项目 docs/METRIC_CONTRACT.md，Power BI 重建见 powerbi/REBUILD.md。</p></article>
<footer>来源：本地 DataCo 订单 CSV 与字段字典。原版数据链接见项目 README。报告中的变化与关联均不能证明因果或实际干预收益。</footer></main>
<script>
const search=document.getElementById('search');
function filter(){const q=search.value.toLowerCase();document.querySelectorAll('.page.active tbody tr').forEach(row=>{row.hidden=!row.textContent.toLowerCase().includes(q)})}
document.querySelectorAll('button[data-page]').forEach(button=>button.onclick=()=>{
document.querySelectorAll('button[data-page],.page').forEach(e=>e.classList.remove('active'));
button.classList.add('active');document.getElementById(button.dataset.page).classList.add('active');filter()});
search.addEventListener('input',filter);
const initialTab=location.hash.slice(1);const initialButton=document.querySelector('button[data-page="'+initialTab+'"]');if(initialButton)initialButton.click();
if(initialTab){history.replaceState(null,"",location.pathname+location.search);window.scrollTo(0,0);window.addEventListener("load",()=>window.scrollTo(0,0));}
</script></html>"""
    values = {"WHEN":when,"OVERVIEW":overview,"SLA":sla,"PRODUCTS":products,"CUSTOMERS":customers,
              "BULLETS":bullets,"SHA":audit["source_sha256"],"DOWNLOADS":downloads}
    for key,value in values.items():
        template = template.replace("__"+key+"__",value)
    if cfg.get("comparison_policy_status") == "pending_user":
        template = template.replace("同比/环比依已确认政策展示。", "2017-10 起的同比/环比口径尚待用户确认，本版暂不计算这些比较。")
    elif cfg.get("comparison_policy_status") == "confirmed_withheld":
        template = template.replace("同比/环比依已确认政策展示。", "按用户确认保留月度金额趋势；2017-10 起的同比/环比统一标为“待核验”，不作经营升降结论。")
    template = template.replace("审计记录 4,062 条明细状态差异，无阻断项、无订单属性冲突。", f"审计记录 {audit['issue_count']:,} 项，阻断项 {audit['blocking_issue_count']:,} 项、订单属性冲突 {audit['conflict_orders']:,} 笔。")
    (root / "reports/analysis_report.html").write_text(template, encoding="utf-8")


def powerbi_checks(root, kpi, cfg):
    pd.DataFrame([{"metric":k,"expected_value":v} for k,v in kpi.items()]).to_csv(
        root / "reports/powerbi_expected_kpis.csv", index=False, encoding="utf-8-sig")
    orders = pd.read_parquet(root / "data/processed/fact_orders.parquet")
    items = pd.read_parquet(root / "data/processed/fact_order_items.parquet")
    from .metrics import python_metrics
    rows = []
    for kind, keys in [
        ("shipping_mode", sorted(orders.shipping_mode.unique())),
        ("product_id", sorted(items.product_id.dropna().unique())[:5]),
    ]:
        for key in keys:
            ids = orders.loc[orders.shipping_mode.eq(key), "order_id"] if kind == "shipping_mode" else items.loc[items.product_id.eq(key), "order_id"].drop_duplicates()
            o = orders[orders.order_id.isin(ids)]
            i = items[items.order_id.isin(ids)]
            if kind == "product_id":
                i = i[i.product_id.eq(key)]
            m = python_metrics({"fact_orders":o,"fact_order_items":i})
            m["over_schedule_sales_exposure"] = float(o.loc[o.is_over_schedule.eq(1), "sales"].sum())
            for metric, value in m.items():
                if metric not in {"conflict_orders"}:
                    rows.append({"filter_kind":kind,"filter_value":key,"metric":metric,"expected_value":value})
    pd.DataFrame(rows).to_csv(root / "reports/powerbi_filter_checks.csv", index=False, encoding="utf-8-sig")
    audit = json.loads((root / "reports/data_quality.json").read_text(encoding="utf-8"))
    pd.DataFrame([{"loaded_at_utc":audit["loaded_at_utc"],"source_sha256":audit["source_sha256"],
                   "rule_version":cfg["rule_version"],"sales_field":cfg["sales_field"]}]).to_csv(
        root / "powerbi/data/build_metadata.csv", index=False, encoding="utf-8-sig")


def deliver(data, kpi, cfg, root):
    paths = charts(data, root / "reports")
    lines = evidence(data, kpi)
    if cfg.get("comparison_policy_status") == "pending_user":
        lines[-1] = lines[-1].replace("趋势比较按已确认政策限制", "相关同比/环比政策待用户确认，当前暂不计算这些比较")
    elif cfg.get("comparison_policy_status") == "confirmed_withheld":
        lines[-1] = (
            "2018 年 1 月有 31 个有记录日，不能据此证明全部业务记录已收齐。"
            "2017 年 10 月起明细数/订单数与品类结构变化。按用户已确认政策，保留月度金额趋势，"
            "2017-10 及以后月份的同比/环比列为“待核验”，不计算变化率、不作经营升降结论。")
    write_business_case(lines, root)
    write_html(data, kpi, paths, lines, cfg, root)
    powerbi_checks(root, kpi, cfg)

