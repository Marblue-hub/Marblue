# 复现指南

## 环境

验证环境：Windows，Python 3.12.14。运行依赖和测试依赖锁定在 requirements-lock.txt。默认系统 python 为 3.7，不能用来运行该重构项目。项目内已建 .venv，当前通过打包运行时安装依赖；没有修改全局 Python。

新的电脑：安装 Python 3.12，创建虚拟环境并从锁文件安装：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip install --no-build-isolation --no-deps -e .
```

## 数据入口

编辑 config/project.yaml 的 input、dictionary。当前指向工作区已有 data/8gx2fvg2k6-5/ 的源文件，路径从项目根解析，不复制、不移动、不改写源数据。任意工作目录下调用已安装 CLI 均以项目根和配置解析相对路径。

如果 input 文件更换，先 validate，再 build；旧建模结果不能混用。源数据版本和 SHA256 写入 reports/data_quality.json，建模及配置指纹写入 build_manifest.json。

## 执行

在项目根 PowerShell：

```powershell
.\run_pipeline.ps1
```

分步入口（已安装项目后）：

```powershell
.\.venv\Scripts\python.exe -m dataco.cli validate
.\.venv\Scripts\python.exe -m dataco.cli build
.\.venv\Scripts\python.exe -m dataco.cli reconcile
.\.venv\Scripts\python.exe -m dataco.cli analyze
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest_tmp
```

也可 python -m dataco.cli build --input data/raw/DataCoSupplyChainDataset.csv；相对输入路径从项目根解析，源 CSV 始终只读。build 完成审计、建模和 SQLite 视图；analyze 必须先通过当前数据对账。

## 返回码与产物

- 0 成功，非 0 失败。SCHEMA_MISSING 包含缺失字段名；QUALITY_BLOCKED 对应 issues CSV 的行标识、规则和动作。
- reports/data_quality.json 与 data_quality_issues.csv：质量统计及逐项问题。
- data/processed/*.parquet、data/db/dataco.sqlite：7 张分析表；powerbi/data/*.csv：同一模型的 BI 输入。
- reports/kpi_snapshot.json、reconciliation.csv/json：24 指标对账及分市场经营金额对账。
- reports/*summary.csv、monthly_trends.csv、fulfillment_segments.csv、first_class_audit.csv、loss_pareto.csv：描述性分析。
- reports/analysis_report.html：可直接打开的中文四页报告，图像内嵌；相关 CSV 在同目录。
- docs/BUSINESS_CASE.md：由运行结果生成的文字证据。
- powerbi/REBUILD.md：Power BI 实现和 Desktop 验收步骤。
- powerbi/DataCoSupplyChain_P0.pbix：含已刷新数据的四页实际 Power BI 报表。
- powerbi/DataCoSource/DataCoSupplyChain.pbip：可编辑源项目；scripts/build_powerbi_project.py 生成模型和布局。
- powerbi/ACCEPTANCE.md、reports/powerbi/：真实 Desktop 验收、404 项 DAX 结果、刷新元数据和四页画布截图。
- reports/run_manifest.json：执行时间、源指纹、分析文件指纹及已完成门槛。

## 常见情况

- 默认 Python 3.7：改用项目 .venv/Scripts/python.exe，或安装 Python 3.12。
- bundled Python 的 ensurepip 失败：本次以 --without-pip 建 venv，再用可用 Python 的 pip --python 指定该虚拟环境安装；未修改运行时依赖目录。
- 网络/代理权限：依赖安装需要可访问配置的 Python 包索引；分析阶段无需联网。
- pytest 临时目录权限：显式使用 --basetemp=.pytest_tmp，临时文件全部在项目内。
- SOURCE_CHANGED / CONFIG_CHANGED / MART_CHANGED：按当前输入重新 build 再 reconcile，不改报表数字去迎合旧参考值。
- 数据库被 Power BI/其他程序锁住：关闭相关连接后重跑 build；异常不删除源数据。
- 图表有结构断点：先检查月份覆盖、每单明细数和品类，不能直接解释为经营下滑。

## 验收范围

Gate 0 口径确认；Gate 1 数据与对账；Gate 2 经营/时效分析；Gate 3 已完成实际 Power BI 四页、刷新、DAX 与 PBIX 重开验收。29 项项目测试通过；404 项真实引擎检查见 reports/powerbi/desktop_acceptance.json。P1、P2 不在本次范围。

Python 分析管道不启动 Desktop，也不自动改写正式 PBIX。每次更换数据或重跑 build 后，在 Desktop 刷新 PBIX，再运行 scripts/verify_powerbi_desktop.py --pid <当前 Desktop 进程号>，重新验收和保存。run_manifest 的分析阶段会将 Power BI 门槛重置为待执行，防止将旧 PBIX 当作新数据结果。

代码改造自下载的原项目，公开版本不包含原始数据或含明细的报表。后续初始化仓库时保持 .gitignore，并审核任何历史 Notebook 输出。

