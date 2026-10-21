"""Build editable Power BI PBIP/PBIR report and import semantic model."""
import csv
import hashlib
import json
from pathlib import Path
import re
import uuid
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "powerbi/DataCoSource"
REPORT = PROJECT / "DataCoSupplyChain.Report"
MODEL = PROJECT / "DataCoSupplyChain.SemanticModel"
WIDTH, HEIGHT = 1280, 720
NAVY, BLUE, TEAL, ORANGE = "#112B46", "#245B9B", "#16877F", "#DF8C35"
VISUAL_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.9.0/schema.json"
PAGES = [
    ("overview", "经营总览"), ("fulfillment", "时效与异常诊断"),
    ("products", "商品与利润分析"), ("customers", "客户与市场分析"),
]
CAPTIONS = {
    "Sales": "记录销售额（折扣后）", "Reported Profit": "记录利润", "Gross Sales": "折扣前金额",
    "Sales Millions": "记录销售额（百万）", "Profit Millions": "记录利润（百万）",
    "Reported Profit Margin": "记录利润率", "Orders": "独立订单数",
    "Canceled Order Rate": "运营取消率", "Over Schedule Order Rate": "超期订单率",
    "Eligible Orders": "有效未取消订单", "Over Schedule Orders": "超期订单数",
    "Average Positive Over Days": "平均正超期天数", "Over Schedule Exposure Millions": "超期整篮金额（百万）",
    "Unknown Timing Orders": "未知时效订单", "Order Items": "订单明细数",
    "Negative Profit Items": "负利润明细数", "Negative Profit Item Rate": "负利润明细比例",
    "Average Order Value": "订单客单价", "Customers": "涉及客户数",
    "Top Category Sales": "销售额", "Top Category Profit": "记录利润",
    "Top Loss Magnitude": "负利润明细绝对额", "Top Loss Cumulative Share": "累计负利润占比",
    "Top Country Sales": "记录销售额", "Negative Profit Magnitude": "负利润明细绝对额",
    "Small Sample Note": "样本提示", "Comparison Policy": "同比/环比状态",
    "Sales MoM": "金额观察值环比", "Sales YoY": "金额观察值同比",
    "Data Loaded UTC Display": "源数据载入时间（UTC）",
}
COLUMN_CAPTIONS = {
    "order_month":"月份", "market":"市场", "region":"地区", "country":"国家",
    "shipping_mode":"运输模式", "planned_days":"计划天数", "category":"品类",
    "department":"部门", "product_name":"商品", "customer_segment":"客户类型", "month_start":"月份",
    "timing_label":"时效分类", "comparison_status":"比较状态",
}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def identity(label):
    return hashlib.sha256(label.encode()).hexdigest()[:20]


def guid(label):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "dataco:" + label))


def lit(value):
    if isinstance(value, bool):
        text = str(value).lower()
    elif isinstance(value, (int, float)):
        text = str(value) + "D"
    else:
        text = "'" + value.replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": text}}}


def fill(color):
    return {"solid": {"color": lit(color)}}


def property_set(props, selector=None):
    result = {"properties": props}
    if selector is not None:
        result["selector"] = selector
    return [result]


def field(table, name, measure=False):
    return {"Measure" if measure else "Column": {
        "Expression": {"SourceRef": {"Entity": table}}, "Property": name}}


def projection(table, name, measure=False):
    return {"field": field(table, name, measure),
            "queryRef": table+"."+name,
            "nativeQueryRef": name,
            "displayName": CAPTIONS.get(name, name) if measure else COLUMN_CAPTIONS.get(name, name)}


def metric(name):
    return projection("KPI", name, True)


def container(title=None, background="#FFFFFF", padding=10):
    result = {
        "background": property_set({"show":lit(True),"color":fill(background),"transparency":lit(0)}),
        "border": property_set({"show":lit(False)}),
        "padding": property_set({k:lit(padding) for k in ("top","bottom","left","right")}),
        "visualHeader": property_set({"show":lit(True)}),
        "subTitle": property_set({"show":lit(False)}),
    }
    result["title"] = property_set({"show":lit(bool(title)), "text":lit(title or ""),
                                   "fontSize":lit(11), "fontColor":fill(NAVY),
                                   "fontFamily":lit("Microsoft YaHei")})
    return result


def visual(page, key, kind, x, y, width, height, roles=None, title=None, objects=None, background="#FFFFFF"):
    name = identity(page["name"]+":"+key)
    data = {"$schema":VISUAL_SCHEMA, "name":name,
            "position":{"x":x,"y":y,"z":page["z"],"height":height,"width":width,"tabOrder":page["z"]},
            "visual":{"visualType":kind,"visualContainerObjects":container(title,background)}}
    page["z"] += 1000
    if roles:
        data["visual"]["query"] = {"queryState":{role:{"projections":projections} for role,projections in roles.items()}}
    if objects:
        data["visual"]["objects"] = objects
    page["visuals"].append(data)
    return data


def textbox(page, key, text, x, y, width, height, size=12, color=NAVY, background="#F0F4F8"):
    paragraphs = []
    for n,line in enumerate(text.split("\n")):
        paragraphs.append({"textRuns":[{"value":line,"textStyle":{
            "fontFamily":"Microsoft YaHei","fontSize":str(size if n==0 else max(size-8,10))+"px",
            "color":color}}],"horizontalTextAlignment":"left"})
    v = visual(page,key,"textbox",x,y,width,height,background=background,
               objects={"general":property_set({"paragraphs":paragraphs})})
    v["visual"]["visualContainerObjects"]["padding"] = property_set({k:lit(0) for k in ("top","bottom","left","right")})
    v["visual"]["visualContainerObjects"]["visualHeader"] = property_set({"show":lit(False)})
    return v


def card(page, name, x, width, y=84, height=None, header=False):
    h = height or round(HEIGHT*.135)
    font = 11 if header else round(HEIGHT*.031)
    label_size = 8 if header else 10
    objects = {
        "value":property_set({"fontSize":lit(font),"fontFamily":lit("Microsoft YaHei"),
                             "fontColor":fill("#FFFFFF" if header else NAVY),
                             "labelDisplayUnits":lit(1),"bold":lit(not header)}, {"id":"default"}),
        "label":property_set({"fontSize":lit(label_size),"fontFamily":lit("Microsoft YaHei"),
                             "fontColor":fill("#C7D8E8" if header else "#476075")},{"id":"default"}),
        "padding":property_set({"paddingUniform":lit(2 if header else 8)},{"id":"default"}),
        "layout":property_set({"paddingUniform":lit(0)},{"id":"default"}),
        "fillCustom":property_set({"show":lit(True),"fillColor":fill(NAVY if header else "#FFFFFF"),
                                   "transparency":lit(0)},{"id":"default"}),
    }
    v = visual(page, "card:"+name, "cardVisual", x,y,width,h,{"Data":[metric(name)]},
               objects=objects, background=NAVY if header else "#FFFFFF")
    v["visual"]["visualContainerObjects"]["visualHeader"] = property_set({"show":lit(False)})
    if header:
        v["visual"]["visualContainerObjects"]["padding"]=property_set({k:lit(0) for k in ("top","bottom","left","right")})
    return v


def slicer(page, table, column, x, width=300):
    textbox(page,"slicer-label:"+column,COLUMN_CAPTIONS.get(column,column),x,183,width,18,10,"#476075")
    v=visual(page, "slicer:"+column,"slicer",x,202,width,48,
                  {"Values":[projection(table,column)]},
                  objects={"data":property_set({"mode":lit("Dropdown")}),
                           "header":property_set({"show":lit(False)})})
    v["visual"]["visualContainerObjects"]["padding"]=property_set({k:lit(5) for k in ("top","bottom","left","right")})
    return v


def chart(page, key, kind, table, category, measures, x,y,width,height,title,
          second=None, sort_desc=True):
    roles = {"Category":[projection(table,category)], "Y":[metric(m) for m in measures]}
    if second:
        roles["Y2"] = [metric(second)]
    v = visual(page,key,kind,x,y,width,height,roles,title,
               objects={"legend":property_set({"show":lit(len(measures)>1 or bool(second)),
                                              "fontSize":lit(9)}),
                        "categoryAxis":property_set({"fontSize":lit(9),"showAxisTitle":lit(False)}),
                        "valueAxis":property_set({"fontSize":lit(9),"showAxisTitle":lit(False)})})
    v["visual"]["query"]["sortDefinition"] = {
        "sort":[{"field":field("KPI",measures[0],True) if sort_desc else field(table,category),
                 "direction":"Descending" if sort_desc else "Ascending"}], "isDefaultSort":True}
    if kind=="lineChart" and category=="month_start":
        v["visual"]["objects"]["categoryAxis"][0]["properties"]["axisType"]=lit("Scalar")
    if second=="Top Loss Cumulative Share":
        v["visual"]["objects"]["valueAxis"][0]["properties"].update({
            "secStart":lit(0),"secEnd":lit(1),"secShow":lit(True)})
    return v


def table(page,key,columns,measures,x,y,width,height,title, matrix=False):
    roles = {}
    if matrix:
        roles["Rows"] = [projection(t,c) for t,c in columns]
        roles["Values"] = [metric(m) for m in measures]
    else:
        roles["Values"] = [projection(t,c) for t,c in columns]+[metric(m) for m in measures]
    v=visual(page,key,"pivotTable" if matrix else "tableEx",x,y,width,height,roles,title,
             objects={"grid":property_set({"rowPadding":lit(1),"textSize":lit(9)}),
                      "values":property_set({"fontSize":lit(8),"wordWrap":lit(False)}),
                      "columnHeaders":property_set({"fontSize":lit(8),"wordWrap":lit(False)})})
    if key=="months":
        v["visual"]["objects"]["total"]=property_set({"totals":lit(False)})
    if key in {"regions","planned"}:
        short={"Eligible Orders":"有效订单","Over Schedule Orders":"超期订单", "Over Schedule Order Rate":"超期率", "Small Sample Note":"样本"}
        for group in roles.values():
            for item in group:
                name=item.get("nativeQueryRef")
                if name in short:
                    item["displayName"]=short[name]
    if key=="planned":
        v["filterConfig"]={"filters":[{
            "name":identity("planned:nonempty"),"field":field("KPI","Orders",True),
            "type":"Advanced","howCreated":"User",
            "filter":{"Version":2,"From":[{"Name":"k","Entity":"KPI","Type":0}],
                      "Where":[{"Condition":{"Comparison":{"ComparisonKind":1,
                        "Left":{"Measure":{"Expression":{"SourceRef":{"Source":"k"}},"Property":"Orders"}},
                        "Right":{"Literal":{"Value":"0L"}}}}}]}}]}
    if key in {"months","sku","market-detail"}:
        sort_field=field("dim_date","order_month") if key=="months" else field("KPI","Sales",True)
        v["visual"]["query"]["sortDefinition"]={"sort":[{"field":sort_field,"direction":"Descending"}],"isDefaultSort":True}
    return v


def load_measures():
    text=(ROOT/"powerbi/measures.dax").read_text(encoding="utf-8")
    lines=[line for line in text.splitlines() if not line.lstrip().startswith("//")]
    joined="\n".join(lines)
    # Patterns are plain regex, kept separate for readability.
    starts=list(re.finditer(r"^(?!VAR\b|RETURN\b)([A-Za-z][A-Za-z0-9 ]*?)[ \t]*=[ \t]*",joined,re.M|re.I))
    measures={}
    for idx,match in enumerate(starts):
        end=starts[idx+1].start() if idx+1<len(starts) else len(joined)
        measures[match.group(1).strip()] = joined[match.end():end].strip()
    measures.update({
        "Sales Millions":"DIVIDE([Sales],1000000)",
        "Profit Millions":"DIVIDE([Reported Profit],1000000)",
        "Over Schedule Exposure Millions":"DIVIDE([Over Schedule Order Sales Exposure],1000000)",
        "Customers":"""VAR SelectedOrderIds=VALUES(fact_order_items[order_id])
RETURN CALCULATE(DISTINCTCOUNT(fact_orders[customer_id]),TREATAS(SelectedOrderIds,fact_orders[order_id]))""",
        "Data Loaded UTC Display":"""VAR Stamp=[Data Refresh UTC]
RETURN LEFT(SUBSTITUTE(Stamp,"T"," "),19)&" UTC" """,
        "Negative Profit Magnitude":"-CALCULATE([Reported Profit],KEEPFILTERS(fact_order_items[reported_profit]<0))",
        "Category Sales Rank":"RANKX(ALLSELECTED(dim_product[category]),[Sales],,DESC,DENSE)",
        "Top Category Sales":"IF([Category Sales Rank]<=10,[Sales])",
        "Top Category Profit":"IF([Category Sales Rank]<=10,[Reported Profit])",
        "Loss Category Rank":"RANKX(ALLSELECTED(dim_product[category]),[Negative Profit Magnitude],,DESC,DENSE)",
        "Top Loss Magnitude":"IF([Loss Category Rank]<=10,[Negative Profit Magnitude])",
        "Top Loss Cumulative Share":"""VAR CurrentLoss=[Negative Profit Magnitude]
VAR TotalLoss=CALCULATE([Negative Profit Magnitude],ALLSELECTED(dim_product[category]))
VAR CumulativeLoss=SUMX(FILTER(ALLSELECTED(dim_product[category]),[Negative Profit Magnitude]>=CurrentLoss),[Negative Profit Magnitude])
RETURN IF([Loss Category Rank]<=10,DIVIDE(CumulativeLoss,TotalLoss))""",
        "Top Country Sales":"IF(RANKX(ALLSELECTED(dim_geography[country]),[Sales],,DESC,DENSE)<=10,[Sales])",
        "Comparison Policy":"""VAR CurrentMonth=SELECTEDVALUE(dim_date[order_month])
RETURN IF(NOT HASONEVALUE(dim_date[order_month]),"请按月查看",
IF(CurrentMonth>="2017-10","待核验",IF(SELECTEDVALUE(dim_date[is_comparable],0)=1,"观察值比较","不适用")))""",
    })
    for name, offset in [("Sales MoM",-1),("Sales YoY",-12)]:
        measures[name]=f"""VAR CurrentMonth=SELECTEDVALUE(dim_date[order_month])
VAR StartDate=IF(NOT ISBLANK(CurrentMonth),DATE(VALUE(LEFT(CurrentMonth,4)),VALUE(RIGHT(CurrentMonth,2)),1))
VAR PriorMonth=IF(NOT ISBLANK(StartDate),FORMAT(EDATE(StartDate,{offset}),"yyyy-MM"))
VAR PriorAllowed=CALCULATE(MAX(dim_date[is_comparable]),REMOVEFILTERS(dim_date),dim_date[order_month]=PriorMonth)
VAR PriorSales=CALCULATE([Sales],REMOVEFILTERS(dim_date),dim_date[order_month]=PriorMonth)
RETURN IF(NOT ISBLANK(CurrentMonth)&&CurrentMonth<"2017-10"&&SELECTEDVALUE(dim_date[is_comparable],0)=1&&PriorAllowed=1,
DIVIDE([Sales]-PriorSales,PriorSales))"""
    return measures


def model():
    MODEL.mkdir(parents=True,exist_ok=True)
    data_tables=["dim_product","dim_customer","dim_date","dim_geography","dim_shipping",
                 "fact_orders","fact_order_items","build_metadata"]
    pq=(ROOT/"powerbi/queries.pq").read_text(encoding="utf-8")
    function=pq.split("(name as text) as table =>",1)[1].split("// Create eight separate",1)[0].strip()
    expression="(name as text) as table =>\n"+function
    tables=[]
    for name in data_tables:
        frame=pd.read_csv(ROOT/"powerbi/data"/(name+".csv"),nrows=5) if name=="build_metadata" else pd.read_parquet(ROOT/"data/processed"/(name+".parquet"))
        columns=[]
        for col in frame:
            if col in {"date","date_key","order_date","shipping_date"}:
                kind="dateTime"
            elif pd.api.types.is_integer_dtype(frame[col].dtype):
                kind="int64"
            elif pd.api.types.is_numeric_dtype(frame[col].dtype):
                kind="double"
            else:
                kind="string"
            column={"name":col,"dataType":kind,"sourceColumn":col,"lineageTag":guid(name+"."+col),"summarizeBy":"none"}
            if kind=="dateTime":
                column["formatString"]="yyyy-MM-dd" if col in {"date","date_key"} else "yyyy-MM-dd HH:mm"
                if col in {"date","date_key"}:
                    column["annotations"]=[{"name":"UnderlyingDateTimeDataType","value":"Date"}]
            if col in {"order_id","order_item_id","customer_id","product_id","geo_key","shipping_mode_key",
                       "source_row","category_id","department_id"}:
                column["isHidden"]=True
            if kind=="double":
                column["formatString"]="#,0.00"
            elif kind=="int64":
                column["formatString"]="#,0"
            columns.append(column)
        if name=="fact_orders":
            columns.append({"name":"timing_label","type":"calculated","dataType":"string",
                "expression":"""SWITCH(fact_orders[timing_state],"over_schedule","实际时长超过计划","within_schedule","未超过计划","not_applicable_canceled","已取消","未知或属性冲突")""",
                "lineageTag":guid("fact_orders.timing_label"),"summarizeBy":"none"})
        if name=="dim_date":
            columns.append({"name":"month_start","type":"calculated","dataType":"dateTime",
                "expression":"DATE(YEAR(dim_date[date_key]),MONTH(dim_date[date_key]),1)",
                "formatString":"yyyy-MM","lineageTag":guid("dim_date.month_start"),"summarizeBy":"none"})
        table_model={"name":name,"lineageTag":guid(name),"columns":columns,
                     "partitions":[{"name":name,"mode":"import","source":{"type":"m","expression":f'LoadData("{name}")'}}]}
        if name=="dim_date":
            table_model["dataCategory"]="Time"
            next(c for c in columns if c["name"]=="date_key")["isKey"]=True
        if name=="build_metadata":
            table_model["isHidden"]=True
        tables.append(table_model)
    measures=[]
    for name, expr in load_measures().items():
        m={"name":name,"expression":expr,"lineageTag":guid("KPI."+name),
           "displayFolder":"业务指标","description":CAPTIONS.get(name,name)}
        if any(p in name for p in ("Rate","Margin","Share","MoM","YoY")):
            m["formatString"]="0.00%"
        elif name not in {"Data Refresh UTC","Data Loaded UTC Display","Small Sample Note","First Class Audit Note",
                           "Timing Definition","Money Definition","Comparison Policy"}:
            m["formatString"]="#,0.00" if any(p in name for p in ("Sales","Profit","Value","Days","Millions","Exposure","Magnitude")) and not name.endswith("Items") else "#,0"
        measures.append(m)
    tables.append({"name":"KPI","lineageTag":guid("KPI"),
                   "columns":[{"name":"Dummy","dataType":"int64","sourceColumn":"Dummy","isHidden":True,"summarizeBy":"none"}],
                   "measures":measures,
                   "partitions":[{"name":"KPI","mode":"import","source":{"type":"m",
                       "expression":"#table(type table [Dummy=Int64.Type], {{1}})"}}]})
    relations=[]
    for ft,fc,dt,dc in [
        ("fact_orders","customer_id","dim_customer","customer_id"),
        ("fact_orders","date_key","dim_date","date_key"),
        ("fact_orders","geo_key","dim_geography","geo_key"),
        ("fact_orders","shipping_mode_key","dim_shipping","shipping_mode_key"),
        ("fact_order_items","order_id","fact_orders","order_id"),
        ("fact_order_items","product_id","dim_product","product_id"),
    ]:
        relations.append({"name":guid(ft+"."+fc),"fromTable":ft,"fromColumn":fc,
                          "toTable":dt,"toColumn":dc,"crossFilteringBehavior":"oneDirection",
                          "fromCardinality":"many","toCardinality":"one","isActive":True})
    data={"name":"DataCoSupplyChain","compatibilityLevel":1601,"model":{
        "culture":"en-US","defaultPowerBIDataSourceVersion":"powerBI_V3",
        "dataAccessOptions":{"legacyRedirects":True,"returnErrorValuesAsNull":True},
        "tables":tables,"relationships":relations,
        "expressions":[
            {"name":"DataFolder","kind":"m","expression":json.dumps((ROOT/"powerbi/data").as_posix())+' meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]'},
            {"name":"LoadData","kind":"m","expression":expression}],
        "annotations":[{"name":"PBI_QueryOrder","value":json.dumps(["DataFolder","LoadData"]+data_tables)}]}}
    write(MODEL/"model.bim",data)
    write(MODEL/"definition.pbism",{"$schema":"https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json","version":"4.0","settings":{}})
    write(MODEL/".platform",{"$schema":"https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json","metadata":{"type":"SemanticModel","displayName":"DataCoSupplyChain"},"config":{"version":"2.0","logicalId":guid("semantic-model")}})
    return len(measures)


def build_report():
    pages_file=REPORT/"definition/pages/pages.json"
    meta=json.loads(pages_file.read_text(encoding="utf-8"))
    first=meta["pageOrder"][0]
    ids=[first]+[identity("page:"+key) for key,_ in PAGES[1:]]
    page_template=json.loads((REPORT/"definition/pages"/first/"page.json").read_text(encoding="utf-8"))
    all_visuals=[]
    for (key,title),page_id in zip(PAGES,ids):
        p={"name":page_id,"z":0,"visuals":[]}
        textbox(p,"header",title+"\nDataCo Supply Chain Intelligence  |  订单与明细统一口径",20,12,800,53,25,"#FFFFFF",NAVY)
        # Full-width header background is a native textbox, with lower z-order.
        header=p["visuals"][0]
        header["position"].update(x=0,y=0,width=WIDTH,height=68)
        header["visual"]["visualContainerObjects"]["padding"]=property_set({"left":lit(20),"top":lit(8),"right":lit(10),"bottom":lit(0)})
        card(p,"Data Loaded UTC Display",920,340,6,56,True)
        kpis={
            "overview":["Sales Millions","Profit Millions","Reported Profit Margin","Orders","Canceled Order Rate","Over Schedule Order Rate"],
            "fulfillment":["Eligible Orders","Over Schedule Orders","Over Schedule Order Rate","Average Positive Over Days","Over Schedule Exposure Millions","Unknown Timing Orders"],
            "products":["Sales Millions","Profit Millions","Reported Profit Margin","Order Items","Negative Profit Items","Negative Profit Item Rate"],
            "customers":["Sales Millions","Profit Millions","Orders","Average Order Value","Reported Profit Margin","Customers"],
        }[key]
        gap=10
        card_width=(WIDTH-40-gap*5)/6
        for n,m in enumerate(kpis):
            card(p,m,20+n*(card_width+gap),card_width)
        slicer(p,"dim_date","order_month",20)
        slicer(p,"dim_geography","market",336)
        third={"overview":("dim_customer","customer_segment"),"fulfillment":("dim_shipping","shipping_mode"),
               "products":("dim_product","category"),"customers":("dim_customer","customer_segment")}[key]
        slicer(p,*third,652)
        textbox(p,"filter-note","切片器影响本页全部指标\n订单指标按去重订单集计算",970,198,290,42,11)
        if key=="overview":
            chart(p,"trend","lineChart","dim_date","month_start",["Sales","Reported Profit"],20,254,820,200,
                  "月度记录销售额与记录利润（源数据金额单位）",sort_desc=False)
            chart(p,"market","clusteredBarChart","dim_geography","market",["Sales"],856,254,404,200,"市场销售贡献")
            table(p,"months",[("dim_date","order_month")],["Sales","Reported Profit","Comparison Policy","Sales MoM","Sales YoY"],
                  20,470,820,180,"月度金额与比较状态")
            chart(p,"timing","clusteredBarChart","fact_orders","timing_label",["Orders"],856,470,404,180,"订单状态：取消与未知分开")
            note="保留全部月度金额趋势；2017-10 及以后同比/环比为“待核验”，不作经营升降结论。"
        elif key=="fulfillment":
            chart(p,"mode-rate","clusteredBarChart","dim_shipping","shipping_mode",["Over Schedule Order Rate"],20,254,399,200,"运输方式：超期订单率")
            chart(p,"mode-volume","clusteredBarChart","dim_shipping","shipping_mode",["Over Schedule Orders"],435,254,400,200,"运输方式：超期订单量")
            table(p,"regions",[("dim_geography","region")],["Eligible Orders","Over Schedule Orders","Over Schedule Order Rate","Small Sample Note"],
                  851,254,409,396,"地区涉及规模与样本提示")
            table(p,"planned",[("dim_shipping","shipping_mode"),("fact_orders","planned_days")],
                  ["Eligible Orders","Over Schedule Order Rate","Over Schedule Orders"],20,470,815,180,"运输模式与计划天数分层")
            note="First Class 结果需验证计划规则与源字段定义。小样本：少于 100 笔有效订单；没有最终签收时间。"
        elif key=="products":
            chart(p,"category-sales","clusteredBarChart","dim_product","category",["Top Category Sales","Top Category Profit"],
                  20,254,612,245,"销售规模前十品类：金额与记录利润")
            chart(p,"loss-pareto","lineClusteredColumnComboChart","dim_product","category",["Top Loss Magnitude"],
                  648,254,612,245,"负利润明细 Pareto（前十品类）",second="Top Loss Cumulative Share")
            table(p,"sku",[("dim_product","product_name")],["Sales","Reported Profit","Reported Profit Margin","Orders","Negative Profit Items"],
                  20,515,1240,135,"SKU 金额、记录利润与涉及独立订单")
            note="商品切片后，运营指标使用涉及该商品的去重订单集。负利润明细比例不等于亏损订单率。"
        else:
            chart(p,"segments","clusteredColumnChart","dim_customer","customer_segment",["Sales","Reported Profit"],
                  20,254,399,200,"客户类型：销售与记录利润")
            chart(p,"markets","clusteredColumnChart","dim_geography","market",["Sales","Reported Profit"],
                  435,254,400,200,"市场：销售与记录利润")
            chart(p,"countries","clusteredBarChart","dim_geography","country",["Top Country Sales"],
                  851,254,409,396,"销售规模前十目的国家")
            table(p,"market-detail",[("dim_geography","market")],
                  ["Orders","Sales","Reported Profit","Reported Profit Margin","Average Order Value"],
                  20,470,815,180,"市场经营指标（订单数与金额粒度分开）")
            note="仅展示客户类型与地区聚合。取消金额为销售暴露额，不等于实际损失；现有数据不支持物流成本推断。"
        textbox(p,"notice",note,20,659,1240,30,11,"#76501B","#FFF2DD")
        textbox(p,"footer","金额：源数据单位（币种未核验）  |  记录利润不是财务净利润  |  超期：有效未取消订单的实际运输时长超过计划时长",
                20,697,1240,18,10,"#52687C")
        page={k:v for k,v in page_template.items() if k in {"$schema"}}
        page.update({"name":page_id,"displayName":title,"displayOption":"FitToPage","width":WIDTH,"height":HEIGHT,
                     "objects":{"background":property_set({"color":fill("#F0F4F8"),"transparency":lit(0)})}})
        write(REPORT/"definition/pages"/page_id/"page.json",page)
        for v in p["visuals"]:
            write(REPORT/"definition/pages"/page_id/"visuals"/v["name"]/"visual.json",v)
        all_visuals.extend(p["visuals"])
    meta["pageOrder"]=ids
    meta["activePageName"]=ids[0]
    write(pages_file,meta)
    report_path=REPORT/"definition/report.json"
    report=json.loads(report_path.read_text(encoding="utf-8"))
    theme_name="DataCoTheme.json"
    theme={"name":theme_name,"dataColors":[BLUE,TEAL,ORANGE,"#7D8FB3","#71B7AE","#D9B57A"],
           "background":"#F0F4F8","foreground":NAVY,"tableAccent":TEAL,
           "textClasses":{"label":{"fontFace":"Microsoft YaHei","fontSize":10,"color":NAVY},
                          "title":{"fontFace":"Microsoft YaHei","fontSize":12,"color":NAVY},
                          "callout":{"fontFace":"Microsoft YaHei","fontSize":24,"color":NAVY}}}
    write(REPORT/"StaticResources/RegisteredResources/DataCoTheme.json",theme)
    report["themeCollection"]["customTheme"]={
        "name":theme_name,"reportVersionAtImport":report["themeCollection"]["baseTheme"]["reportVersionAtImport"],
        "type":"RegisteredResources"}
    report["resourcePackages"]=[p for p in report["resourcePackages"] if p["name"]!="RegisteredResources"]+[
        {"name":"RegisteredResources","type":"RegisteredResources",
         "items":[{"name":theme_name,"path":"DataCoTheme.json","type":"CustomTheme"}]}]
    write(report_path,report)
    return [{"page":title,"id":pid,"visuals":sum(v["name"] in {p.name for p in (REPORT/"definition/pages"/pid/"visuals").iterdir()} for v in all_visuals)}
            for (_,title),pid in zip(PAGES,ids)]


if __name__=="__main__":
    measures=model()
    pages=build_report()
    result={"project":str(PROJECT/"DataCoSupplyChain.pbip"),"pages":pages,"measures":measures,
            "desktop_verified":False}
    write(ROOT/"reports/powerbi_build.json",result)
    print(json.dumps(result,ensure_ascii=False,indent=2))

