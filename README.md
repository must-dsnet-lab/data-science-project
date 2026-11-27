# Analyzing Historical Video Game Sales and Regional Market Patterns

澳门科技大学 Data Science 小组项目。我们比较历史游戏销量分布和地区结构，并评估游戏元数据能在多大程度上估计未见过标题的历史累计销量。

全量 Raw 用于覆盖率和质量审查。三个主研究问题使用 2000–2018 年发行的游戏–平台条目，销量单位均为**百万份**。按发行年份分组得到各批次游戏的累计销量。

## 当前交接版本

数据准备 **v1** 已在本机从 Raw 验证，待两位队友独立复现。课程进度按 [课程要求与提交核对](docs/course_requirements.md) 跟踪。

| 验收项 | 实测数量 |
| --- | ---: |
| Raw 审查记录 | 64,016 |
| 有总销量 | 18,922 |
| 兼有发行日期与总销量 | 18,832 |
| 2000–2018 主数据 | 17,102 |
| 地区可比记录，主数据子集 | 2,049 |
| 有原始评分，主数据子集 | 3,866 |

完整口径和覆盖图见 [数据质量报告](docs/data_quality_report.md) 与 [数据字典](docs/data_dictionary.md)。

## 复现数据准备

从 Kaggle 获取 **Video Games Sales (1980-2024) - Raw.csv**，原样放在仓库根目录的 `data/raw/`。也可以通过 `--raw` 传入任意本地路径。准备程序会验证 Raw 快照的 SHA-256。[Kaggle 数据集](https://www.kaggle.com/datasets/bhushandivekar/video-game-sales-and-industry-data-1980-2024) · [来源与文件指纹](docs/data_source.md)

在仓库根目录运行以下命令。Windows PowerShell 可以直接使用 `.venv` 中的解释器。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m src.prepare_data --raw "data/raw/Video Games Sales (1980-2024) - Raw.csv"
```

macOS / Linux 使用 `python3.12 -m venv .venv` 创建环境，后续命令使用 `./.venv/bin/python`。已有 `.venv` 的成员可以直接使用其中的解释器。

| 默认产物 | 用途 |
| --- | --- |
| `data/processed/dataset_manifest.json` | 数据版本、输入及输出指纹、主范围与样本数 |
| `data/processed/games_audited.csv` | 全量审查、来源索引和入样状态 |
| `data/processed/games_main.csv` | 分析与建模统一输入，可通过 `record_id` 回查 Raw |
| `data/processed/audit/` | 字段缺失、年度与平台覆盖、清洗台账、冲突候选与无效值 |

用同一文件重跑会比对已有产物。要保留两份结果用于复核，可指定 `--output-dir data/processed-check`。默认输出及 `data/processed-*` 下的文件由 Git 忽略。

如需复查参考文件中重复的 7.3，可将 Cleaned CSV 放到 `data/raw/` 后运行以下命令。核心流程只读取 Raw。

```text
python -m src.audit_score_reference --raw "data/raw/Video Games Sales (1980-2024) - Raw.csv" --cleaned-reference "data/raw/Video_Games_Sales_Cleaned.csv"
```

[数据审查 Notebook](notebooks/01_data_audit.ipynb) 从已生成的汇总表重现报告数字和覆盖图。重绘时在项目环境运行 `python -m pip install matplotlib==3.11.2 ipykernel`，在 VS Code 选择对应的 `.venv` 内核。核心数据准备只需 `requirements.txt`。

## 小组任务

### Xu Yanxi · 数据准备与交接

- [x] 固定 Raw 输入和 SHA-256，完成数据字典、全量质量审查、清洗台账和评分对照。
- [x] 生成 v1 并核对行数、地区一致性、记录来源及重复运行的文件指纹。
- [ ] 收集 B、C 的独立复现结果，确认交接版本并复核后续图表与建模口径。

### Feng Sunzhou · 全局和地区销量分析

- [ ] 先复现 v1，确认 `games_main.csv` 有 17,102 行，地区可比子集有 2,049 行。记录清单中的输出指纹。
- [ ] 完成 `notebooks/02_sales_eda.ipynb` 的全局分析。比较发行批次、平台、类型的销量分布与集中度，使用样本量、中位数和分位数支持解释。
- [ ] 从 `regional_status == "comparable"` 的记录比较地区结构，写清分母。以四区和为分母时，区分逐条占比的平均值和直接汇总销量后的占比。报告子集覆盖及选择偏差。
- [ ] 将关键图表和汇总表放入 `reports/`，注明样本、单位和口径。核对排除同标题同平台冲突候选后，重点比较是否改变。

### Yu Cuiyu · 销量回归与评估

- [ ] 复现 v1，使用 `record_id` 和 `title_group` 固定切分，记录数据指纹、种子、每组样本数并验证组间无重叠。
- [ ] 完成 `notebooks/03_sales_modeling.ipynb`。以 `total_sales` 为目标，先做训练内中位数基线，再比较正则化线性回归与一个树模型。
- [ ] 主模型候选特征用 `console`、`genre`、`release_year`、`publisher`、`developer`。编码、填补和参数选择在对应训练折内拟合。地区销量、占比、地区匹配状态、目标派生字段、ID 和分组键只用于审查或切分。
- [ ] 冻结方案后在同一测试集报告 MAE、RMSE 和 R²，按平台和销量段核对误差。评分对比如开展，只使用同一个有原始评分的子集和相同拆分。

### 全员

- [ ] 交叉复核样本口径、图表与模型指标，并将各自的材料汇总到报告和展示。
- [ ] 确认老师正式截止、提交入口与交付格式，从干净环境复现并归档最终版本。

分支、提交、评审及数据使用约定见 [开发规范](CONTRIBUTING.md) 与 [仓库协作指令](AGENTS.md)。
