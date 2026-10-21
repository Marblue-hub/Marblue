# 公开发布范围

公开版本包含 Python/SQL 源码、合成样本测试、指标与分析文档、Power BI PBIP/PBIR/model.bim 定义、聚合结果及原生展板截图。

原始 CSV、订单/客户行级衍生表、SQLite/Parquet、导入明细的 PBIX、原项目旧输出、安装包、虚拟环境、令牌及本地缓存不进入仓库。保留原 MIT LICENSE 和数据来源署名。

发布副本将默认输入改为 data/raw，并清空 PBIP 的机器专属 DataFolder 参数；运行代码与指标公式保留。查看 PBIP 前需自行取得源数据、运行管道并填写 DataFolder。本地已经验收的 PBIX 保留在原工作区。

reports 中的 DAX 对账、刷新元数据、产物 SHA256 和验收记录是原本地快照的历史证据；它们不会因发布副本路径变化而重新代表一次分析或 Desktop 验收。报告中的 PROJECT_ROOT 标记替代本机绝对路径。publication_manifest.json 记录本次实际公开文件及 SHA256。
