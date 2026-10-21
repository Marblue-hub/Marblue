"""Reconcile real Desktop DAX results with independent Python/SQL controls."""
import argparse
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import subprocess
import psutil
import re

ROOT = Path(__file__).resolve().parents[1]
METRICS = dict(zip(
    'orders canceled_orders eligible_orders over_schedule_orders within_schedule_orders conflict_orders avg_positive_over_days order_items sales gross_sales reported_profit recorded_discount negative_profit_items eligible_items over_schedule_items canceled_sales_exposure over_schedule_sales_exposure unknown_timing_orders reported_profit_margin average_order_value canceled_order_rate over_schedule_order_rate over_schedule_item_rate negative_profit_item_rate'.split(),
    ['Orders','Canceled Orders','Eligible Orders','Over Schedule Orders','Within Schedule Orders','Conflict Orders','Average Positive Over Days','Order Items','Sales','Gross Sales','Reported Profit','Recorded Discount','Negative Profit Items','Eligible Items','Over Schedule Items','Canceled Sales Exposure','Over Schedule Order Sales Exposure','Unknown Timing Orders','Reported Profit Margin','Average Order Value','Canceled Order Rate','Over Schedule Order Rate','Over Schedule Item Rate','Negative Profit Item Rate']))

def csv_rows(name):
    with (ROOT/'reports'/name).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))

def row_query(metrics):
    return 'ROW('+','.join(f'"{key}",[{METRICS[key]}]' for key in metrics)+')'

def number(value):
    return None if value is None or value=='' else float(value)

def verify(pid):
    connections=[]
    for child in psutil.Process(pid).children(recursive=True):
        if child.name().lower()=='msmdsrv.exe':
            args=child.cmdline()
            folder=Path(args[args.index('-s')+1])
            for file in folder.parent.rglob('msmdsrv.port.txt'):
                raw=file.read_bytes()
                port=int(re.search(r'\d+',raw.decode('utf-16') if b'\0' in raw else raw.decode()).group())
                connections.append(port)
    if len(connections)!=1:
        raise RuntimeError(f'Expected one local engine, found {connections}')
    queries=[]
    expectations={}
    base=csv_rows('powerbi_expected_kpis.csv')
    expectations['full']={r['metric']:number(r['expected_value']) for r in base}
    queries.append({'id':'full','dax':'EVALUATE '+row_query(expectations['full'])})
    groups={}
    for row in csv_rows('powerbi_filter_checks.csv'):
        key=(row['filter_kind'],row['filter_value'])
        groups.setdefault(key,{})[row['metric']]=number(row['expected_value'])
    for (kind,value),expected in groups.items():
        key=kind+':'+value
        literal=json.dumps(value) if kind=='shipping_mode' else str(int(float(value)))
        column='dim_shipping[shipping_mode]' if kind=='shipping_mode' else 'dim_product[product_id]'
        queries.append({'id':key,'dax':f'EVALUATE CALCULATETABLE({row_query(expected)},TREATAS({{{literal}}},{column}))'})
        expectations[key]=expected
    edge_metrics=['orders','eligible_orders','over_schedule_orders','within_schedule_orders','over_schedule_order_rate','order_items','negative_profit_item_rate']
    queries.append({'id':'canceled_only','dax':'EVALUATE CALCULATETABLE('+row_query(edge_metrics)+',fact_orders[is_canceled]=1)'})
    expectations['canceled_only']={'orders':2855,'eligible_orders':0,'over_schedule_orders':0,'within_schedule_orders':0,'over_schedule_order_rate':None}
    queries.append({'id':'empty_selection','dax':'EVALUATE CALCULATETABLE('+row_query(edge_metrics)+',TREATAS({-999999},dim_product[product_id]))'})
    expectations['empty_selection']={k:None if k.endswith('rate') else 0 for k in edge_metrics}
    queries.append({'id':'months','dax':'EVALUATE SUMMARIZECOLUMNS(dim_date[order_month],"sales",[Sales],"profit",[Reported Profit],"mom",[Sales MoM],"yoy",[Sales YoY],"policy",[Comparison Policy]) ORDER BY dim_date[order_month]'})
    tables=['fact_orders','fact_order_items','dim_product','dim_customer','dim_date','dim_geography','dim_shipping','build_metadata','KPI']
    queries.append({'id':'rowcounts','dax':'EVALUATE ROW('+','.join(f'"{t}",COUNTROWS(\'{t}\')' for t in tables)+')'})
    expectations['rowcounts']=dict(zip(tables,[65752,180519,118,20652,1127,1117,4,1,1]))
    folder=ROOT/'.tmp/powerbi-acceptance'
    folder.mkdir(parents=True,exist_ok=True)
    input_file=folder/'queries.json'
    output_file=ROOT/'reports/powerbi/desktop_dax_results.json'
    output_file.parent.mkdir(parents=True,exist_ok=True)
    input_file.write_text(json.dumps(queries,ensure_ascii=False),encoding='utf-8')
    subprocess.run(['powershell.exe','-NoProfile','-File',str(ROOT/'scripts/query_powerbi_desktop.ps1'),'-InputFile',str(input_file),'-OutputFile',str(output_file),'-Port',str(connections[0])],check=True,cwd=ROOT)
    actual=json.loads(output_file.read_text(encoding='utf-8-sig'))
    checks=[]
    def compare(case,metric,expected,observed):
        passed=(expected is None and observed is None) or (expected is not None and observed is not None and math.isclose(expected,observed,rel_tol=1e-10,abs_tol=1e-7))
        checks.append({'case':case,'metric':metric,'expected':expected,'actual':observed,'passed':passed})
    for result in actual['queries']:
        case=result['id']
        if case in expectations:
            for metric,expected in expectations[case].items():
                compare(case,metric,expected,result['rows'][0].get(metric))
        if case=='months':
            months={r['order_month']:r for r in csv_rows('monthly_trends.csv')}
            for row in result['rows']:
                month=row['dim_date[order_month]']
                for key,source in [('sales','sales'),('profit','reported_profit'),('mom','sales_mom_change'),('yoy','sales_yoy_change')]:
                    compare(month,key,number(months[month][source]),row.get(key))
                if month>='2017-10':
                    checks.append({'case':month,'metric':'comparison_policy','expected':'待核验','actual':row.get('policy'),'passed':row.get('policy')=='待核验'})
    summary={'verified_at_utc':datetime.now(timezone.utc).isoformat(),'engine':'Power BI Desktop Analysis Services / actual DAX','desktop_pid':pid,'catalog':actual['catalog'],'checks':len(checks),'passed':sum(r['passed'] for r in checks),'failed':sum(not r['passed'] for r in checks),'full_kpis':len(base),'filter_checks':sum(len(v) for v in groups.values()),'checks_detail':checks}
    (ROOT/'reports/powerbi/desktop_acceptance.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='checks_detail'},ensure_ascii=True))
    for check in checks:
        if not check['passed']:
            print(json.dumps(check,ensure_ascii=True))
    if summary['failed']:
        raise SystemExit(1)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--pid',type=int,required=True)
    verify(parser.parse_args().pid)
