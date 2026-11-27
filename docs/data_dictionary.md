# 数据字典与审查报表

每条记录对应一个游戏在某个平台上的登记条目。同名跨平台发行可以是不同记录，同标题和平台也可能有多个版本。销量单位为**百万份**，是数据集记录的累计销量。按发行年份分组后，统计量描述同年发行的游戏条目。

## 源字段

输出保留 Raw 的 14 个字段名。文本去除首尾空白，空白字段保留为缺失，`NA`、`Unknown` 等非空文本保留原有含义。数值和日期转换失败时留空，并在 `invalid_values.csv` 记录原值。缺失销量与实际零销量分别保留。

| 字段 | 输出类型 | 含义与检查 |
| --- | --- | --- |
| `img` | 字符串 | 封面图片引用，保留源字符串 |
| `title` | 字符串 | 游戏标题，原始字符串可通过 `source_row` 回查 |
| `console` | 字符串 | 平台标签，如 `PS3`，规范化键另见 `console_key` |
| `genre` | 字符串 | 来源标注的游戏类型 |
| `publisher` | 字符串 | 发行商，疑似格式误转换的标签额外标记 |
| `developer` | 字符串 | 开发商，保留来源标注方式 |
| `critic_score` | 数值 | 媒体评分，范围为 0–10（含端点）。保留有效的 `7.3` 观测与原始缺失 |
| `total_sales` | 数值 | 累计总销量，有限且非负，单位为百万份 |
| `na_sales` | 数值 | 北美累计销量，有限且非负，单位为百万份 |
| `jp_sales` | 数值 | 日本累计销量，有限且非负，单位为百万份 |
| `pal_sales` | 数值 | 来源标为 PAL 的地区累计销量，有限且非负，单位为百万份 |
| `other_sales` | 数值 | 来源标为其他地区的累计销量，有限且非负，单位为百万份 |
| `release_date` | 日期 | 发行日期，输入按 `dd-mm-yyyy` 解析，CSV 输出为 `YYYY-MM-DD` |
| `last_update` | 日期 | 来源记录更新日期，输入和输出格式同 `release_date` |

## 派生字段

| 字段 | 类型 | 含义与使用方式 |
| --- | --- | --- |
| `record_id` | 字符串 | 当前输入版本中的唯一记录标识。与清单中的 Raw SHA-256 一起核对，跨版本先确认映射 |
| `source_row` | 整数 | Raw 第几条数据记录，从 1 开始，不含表头。CSV 内嵌换行时以解析后的记录顺序定位 |
| `title_group` | 字符串 | 对标题执行 Unicode NFC、首尾去空白、连续内部空白折叠与 `casefold`。建模切分以它分组，同一标题的多平台记录留在同一折或同一侧 |
| `console_key` | 字符串 | 按标题相同规则规范化的平台键，用于分组汇总及检查同标题同平台记录 |
| `release_year` | 可空整数 | 从有效的 `release_date` 提取的发行年份 |
| `critic_score_observed` | 布尔 | Raw 评分通过解析及范围检查时为真。评分未做填补 |
| `publisher_suspect` | 布尔 | `publisher` 为 `08-Apr` 时标记，保留原标签供复核 |
| `exact_duplicate` | 布尔 | 标记与前序记录完全一致的 Raw 记录，原始覆盖审查仍计入这些记录 |
| `title_console_conflict` | 布尔 | 在全量数据中标记需要复核的同标题同平台候选。可能涉及不同版本，继续按入样条件判断每条记录 |
| `in_main_window` | 布尔 | 有效发行年份在 2000–2018 年之间，含两端 |
| `main_exclusion` | 枚举 | 主样本决策。每条记录分配一个类别，`included` 为保留。其他取值见清洗台账 |
| `region_total_delta` | 数值 | 四地区销量之和减总销量，单位为百万份。任一分量缺失时留空 |
| `regional_status` | 枚举 | 地区样本可比性。`comparable` 表示总量与四地区均有效、总量与地区合计均为正且绝对差不超过 0.025 百万份。其他状态为 `missing_or_invalid_sales`、`nonpositive_total`、`nonpositive_regional_sum`、`regional_total_mismatch` |

`games_audited.csv` 覆盖全量 Raw 数据记录，包括缺失和重复。`games_main.csv` 保留 `main_exclusion == "included"` 的记录。地区比较还需在主样本中筛选 `regional_status == "comparable"`，并在图表中说明涉及的样本数和占比分母。

## 读取输出

CSV 用空字段表示缺失。显式关闭 pandas 的默认缺失词表以保留 `NA` 等来源标签。从仓库根目录运行时可按以下方式读取和恢复日期类型。

```python
import pandas as pd

games = pd.read_csv(
    "data/processed/games_main.csv",
    keep_default_na=False,
    na_values=[""],
    dtype={"record_id": "string", "release_year": "Int64"},
    parse_dates=["release_date", "last_update"],
)
```

## 审查报表

默认输出目录为 `data/processed/audit/`。分组覆盖表中的比例为 0–1，分母是分组内的 `records`，包括缺失和重复的 Raw 记录。分母为 0 时比例留空。

| 文件 | 使用方式 |
| --- | --- |
| `field_missingness.csv` | 每个 Raw 字段的缺失审查。`raw_missing` 统计原始空字段和纯空白字段。`audited_missing` 额外计入失效的非空值，差值为 `invalid_nonblank`。两个比例均用全量输入行数作分母 |
| `coverage_by_year.csv` | 按有效发行年份统计，空白年份表示发行日期缺失或无效 |
| `coverage_by_platform.csv` | 按 `console_key` 汇总，空白键表示平台缺失。原始平台拼写参见主表 |
| `coverage_by_period.csv` | 按 `<2000`、`2000–2018`、`2019–2020`、`2021+` 和缺失日期五段汇总。`main_candidates` 统计日期和总销量有效且发行年份在主区间的清洗前候选，`main_included` 统计清洗后入样记录 |
| `cleaning_ledger.csv` | 汇总 `included`、`exact_duplicate`、`missing_or_invalid_release_date`、`outside_main_window`、`missing_or_invalid_total_sales`、`missing_title_or_console`。类别互斥，合计等于输入行数，`share_of_input` 以全量输入行数作分母 |
| `title_platform_conflicts.csv` | 罗列已标记的同标题同平台候选，带 `source_row`、`record_id`、主样本决策和相关原始字段以便追溯。标记本身无需删行 |
| `invalid_values.csv` | 每条记录的每个失效字段单列一行，给出 `record_id`、`source_row`、`field`、`raw_value` |

覆盖表的 `date_and_total_sales_available` 是有效日期和总销量的交集。`total_and_four_regions_available` 只要求五项销量均有效。`regionally_comparable` 还要求可用的正分母及通过地区一致性检查。`main_regionally_comparable` 再限于主样本，适合核对地区分析的入样数。
