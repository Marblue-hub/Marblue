"""Prepare a data-free, portable GitHub copy; never copy raw/row-level datasets."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT=Path(__file__).resolve().parents[1]
TOP=['README.md','LICENSE','CHANGELOG.md','pyproject.toml','requirements.txt',
     'requirements-lock.txt','run_pipeline.ps1','.env.example','.gitignore']
REPORTS=['analysis_report.html','commercial_summary.csv','cancellation_status_audit.csv',
         'amount_audit.csv','fulfillment_segments.csv','first_class_audit.csv','loss_pareto.csv',
         'monthly_trends.csv','source_control_reconciliation.csv','kpi_snapshot.json',
         'data_quality.json','build_manifest.json','reconciliation.json','reconciliation.csv',
         'verification.json','run_manifest.json','powerbi_schema_validation.json',
         'powerbi_filter_checks.csv','powerbi_expected_kpis.csv','powerbi_build.json',
         'monthly_sales_and_profit.png','fulfillment_by_mode.png','category_sales_profit.png','market_and_loss.png']

def write_json(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def prepare(destination):
    destination=destination.resolve()
    if not destination.is_relative_to(ROOT/'.tmp'):
        raise ValueError('Publish staging must stay inside this project .tmp directory.')
    destination.mkdir(parents=True,exist_ok=False)
    def copy(relative):
        source=ROOT/relative
        target=destination/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
    for name in TOP:
        copy(Path(name))
    for folder in ['src','tests','scripts','sql','config']:
        for file in (ROOT/folder).rglob('*'):
            if file.is_file() and '__pycache__' not in file.parts and file.suffix not in {'.pyc','.pyo'}:
                copy(file.relative_to(ROOT))
    for file in (ROOT/'docs').glob('*.md'):
        copy(file.relative_to(ROOT))
    for name in ['REBUILD.md','ACCEPTANCE.md','measures.dax','queries.pq']:
        copy(Path('powerbi')/name)
    for file in (ROOT/'powerbi/DataCoSource').rglob('*'):
        if file.is_file() and '.pbi' not in file.parts:
            copy(file.relative_to(ROOT))
    for name in REPORTS:
        copy(Path('reports')/name)
    for file in (ROOT/'reports/powerbi').rglob('*'):
        if file.is_file() and file.suffix in {'.json','.png'}:
            copy(file.relative_to(ROOT))
    (destination/'data/raw').mkdir(parents=True)
    (destination/'data/raw/.gitkeep').write_text('',encoding='utf-8')
    config=destination/'config/project.yaml'
    text=config.read_text(encoding='utf-8')
    text=re.sub(r'^input:.*$', 'input: "data/raw/DataCoSupplyChainDataset.csv"',text,flags=re.M)
    text=re.sub(r'^dictionary:.*$', 'dictionary: "data/raw/DescriptionDataCoSupplyChain.csv"',text,flags=re.M)
    config.write_text(text,encoding='utf-8')
    model=destination/'powerbi/DataCoSource/DataCoSupplyChain.SemanticModel/model.bim'
    content=json.loads(model.read_text(encoding='utf-8'))
    parameter=next(x for x in content['model']['expressions'] if x['name']=='DataFolder')
    parameter['expression']='"" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]'
    write_json(model,content)
    # Keep actual validation evidence, replacing machine-specific project roots.
    variants=[str(ROOT),ROOT.as_posix(),json.dumps(str(ROOT))[1:-1]]
    for file in destination.rglob('*'):
        if not file.is_file() or file.suffix.lower() in {'.png'}:
            continue
        text=file.read_text(encoding='utf-8-sig')
        for prefix in variants:
            text=text.replace(prefix,'<PROJECT_ROOT>')
        if file.suffix=='.md':
            text=re.sub(r'\[([^\]]+)\]\(([^)]*\.pbix)\)',r'\1（含明细，仅本地交付）',text,flags=re.I)
            text=text.replace('当前目录没有 Git 元数据，本次没有提交或推送。','当前公开版本按发布清单上传代码、源项目和聚合结果。')
            text=text.replace('当前目录来自下载文件，没有 Git 元数据，本次未执行提交、推送或上传原始数据。','代码改造自下载的原项目，公开版本不包含原始数据或含明细的报表。')
        file.write_text(text,encoding='utf-8')
    ignore=destination/'.gitignore'
    ignore.write_text(ignore.read_text(encoding='utf-8')+'\nconfig/*.local.yaml\n*.pem\n*.key\n',encoding='utf-8')
    (destination/'README.md').write_text(README,encoding='utf-8')
    (destination/'PUBLICATION.md').write_text(PUBLICATION,encoding='utf-8')
    (destination/'.gitattributes').write_text('* text=auto eol=lf\n*.png -text\n',encoding='utf-8')
    files=[f for f in destination.rglob('*') if f.is_file()]
    for file in files:
        if file.suffix!='.png':
            file.write_bytes(file.read_bytes().replace(b'\r\n',b'\n'))
    assert not any(f.suffix.lower() in {'.pbix','.parquet','.db','.sqlite','.abf'} for f in files)
    assert not any((destination/'data/raw').glob('*.csv'))
    # Check the shipped CSVs are aggregate controls, not customer/order rows.
    forbidden={'order_id','order_item_id','customer_id','source_row','Customer Email','Customer Password','Customer Fname','Customer Lname','Customer Street'}
    for file in destination.rglob('*.csv'):
        with file.open(encoding='utf-8-sig',newline='') as stream:
            header=next(csv.reader(stream),[])
        assert not forbidden.intersection(header),(file.name,forbidden.intersection(header))
    secrets=re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----)')
    for file in files:
        if file.suffix!='.png':
            assert not secrets.search(file.read_text(encoding='utf-8')),file.relative_to(destination)
    manifest={'files':len(files),'bytes':sum(f.stat().st_size for f in files),
              'excluded':['raw data','customer/order rows','PBIX with imported data','legacy','local tools and caches'],
              'portable_config':True,'source':'DataCo P0 local verified implementation',
              'sha256':{f.relative_to(destination).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(files)}}
    write_json(destination/'publication_manifest.json',manifest)
    print(json.dumps({k:v for k,v in manifest.items() if k!='sha256'},ensure_ascii=True))

README='''# DataCo Supply Chain Intelligence

使用 Python、SQL 和 Power BI 分析 **180,519 条订单明细、65,752 笔独立订单**，完成数据审计、双粒度建模、统一 KPI、运输时效诊断和四页交互展板。

![经营总览](reports/powerbi/screenshots/经营总览.png)

## 核心结果

| 指标 | 结果 |
|---|---:|
| 折扣后记录销售额 | 33,054,402.38 |
| 记录利润 | 3,966,902.97 |
| 记录利润率 | 12.00% |
| 有效未取消订单 | 62,897 |
| 运输时长超过计划的订单 | 36,048 |
| 超期订单率 | 57.31% |
| 负利润明细比例 | 18.71% |

Standard Class 贡献 41.60% 的超期订单。First Class 的 9,602 笔有效订单全部超过源计划时长，需核验计划规则及字段定义。运输方式的比例与订单规模并列展示，不作因果推断。

金额为源数据单位，币种未核验；记录利润不是财务净利润，超期不是最终签收迟到。2017-10 及以后保留金额趋势，同比/环比列为“待核验”，不输出经营升降结论。

## 项目实现

- 数据治理：主键、订单内属性一致性、金额字段关系和取消状态差异审计；原数据始终只读。
- 分析模型：订单与订单明细双事实表、五个维度、六条单向业务关系；商品筛选通过去重订单集统计运营指标。
- 指标对账：24 项核心指标在 Python/SQL 间独立对账；实际 Desktop 中完成 404 项 DAX 检查，含商品/运输筛选、月度和空样本边界。
- 可视化：46 个测量值，经营总览、时效诊断、商品利润、客户市场四页原生 Power BI 展板；已实际刷新、保存并重开验证。
- 工程：Python 3.12、SQLite、命令行管道、29 项自动化测试、依赖锁文件及输入/产物指纹。

## 查看成果

- [Power BI 源项目（PBIP）](powerbi/DataCoSource/DataCoSupplyChain.pbip)
- [四页截图与实际验收记录](powerbi/ACCEPTANCE.md)
- [中文分析报告（下载后用浏览器打开）](reports/analysis_report.html)
- [业务发现与建议](docs/BUSINESS_CASE.md) · [指标合同](docs/METRIC_CONTRACT.md) · [数据边界](docs/LIMITATIONS.md)

本公开仓库只包含代码、模型/布局定义、聚合结果和截图。原始 CSV、客户/订单行级衍生表及含导入明细的 PBIX 保留本地。PBIP 不内嵌数据，复现时须自行获取源数据并设置 DataFolder 参数。完整发布范围见 [PUBLICATION.md](PUBLICATION.md)。

## 本地复现

1. 从 [Mendeley Data，Version 5](https://data.mendeley.com/datasets/8gx2fvg2k6/5) 获取 DataCoSupplyChainDataset.csv 和 DescriptionDataCoSupplyChain.csv，放入 data/raw。
2. 创建 Python 3.12 环境并安装依赖：

```powershell
python -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install -r requirements-lock.txt
.\\.venv\\Scripts\\python.exe -m pip install --no-build-isolation --no-deps -e .
.\\run_pipeline.ps1
```

3. 打开 PBIP，在 Power BI Desktop 中把 DataFolder 参数设为当前项目 powerbi/data 的绝对路径，应用查询并刷新；需要单文件时另存 PBIX。
4. Desktop 验收可使用 scripts/verify_powerbi_desktop.py；安装与路径说明见 [刷新/重建指南](powerbi/REBUILD.md)。

测试使用合成样本，无需下载原始数据：

```powershell
.\\.venv\\Scripts\\python.exe -m pytest -q --basetemp=.pytest_tmp
```

更换源数据后需重新执行 Python 管道和 Desktop 刷新验收；仓库中的 404 项验收是当前历史快照，不能自动证明新数据也通过。详细说明见 [复现指南](docs/REPRODUCTION.md)。

## 来源与许可

数据：Fabian Constante、Fernando Silva、António Pereira，DataCo SMART SUPPLY CHAIN FOR BIG DATA ANALYSIS，Version 5，DOI 10.17632/8gx2fvg2k6.5。源站许可 CC BY 4.0；本仓库不分发原始数据。

源码改造自 [Mo-210/dataco-supplychain-analytics](https://github.com/Mo-210/dataco-supplychain-analytics)，保留原作者的 [MIT LICENSE](LICENSE)。本项目是非官方派生改造，P1 情景模拟与 P2 预测模型不在本次范围。
'''

PUBLICATION='''# 公开发布范围

公开版本包含 Python/SQL 源码、合成样本测试、指标与分析文档、Power BI PBIP/PBIR/model.bim 定义、聚合结果及原生展板截图。

原始 CSV、订单/客户行级衍生表、SQLite/Parquet、导入明细的 PBIX、原项目旧输出、安装包、虚拟环境、令牌及本地缓存不进入仓库。保留原 MIT LICENSE 和数据来源署名。

发布副本将默认输入改为 data/raw，并清空 PBIP 的机器专属 DataFolder 参数；运行代码与指标公式保留。查看 PBIP 前需自行取得源数据、运行管道并填写 DataFolder。本地已经验收的 PBIX 保留在原工作区。

reports 中的 DAX 对账、刷新元数据、产物 SHA256 和验收记录是原本地快照的历史证据；它们不会因发布副本路径变化而重新代表一次分析或 Desktop 验收。报告中的 PROJECT_ROOT 标记替代本机绝对路径。publication_manifest.json 记录本次实际公开文件及 SHA256。
'''

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('destination',type=Path)
    prepare(parser.parse_args().destination)
