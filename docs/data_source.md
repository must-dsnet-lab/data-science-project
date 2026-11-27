# 数据来源与版本

项目使用 Kaggle 发布账号 `bhushandivekar` 的 *Video Game Sales & Industry Data (1980–2024)*。发布者的 Notebook 输入页列出了当前项目对应的两份 CSV。原始下载日期、Kaggle 数据集版本及数据再分发许可仍待核实。项目用文件字节数和 SHA-256 固定实际输入。[Kaggle 数据集](https://www.kaggle.com/datasets/bhushandivekar/video-game-sales-and-industry-data-1980-2024) · [Notebook 输入页](https://www.kaggle.com/code/bhushandivekar/video-games-sales-eda/input)

| 文件 | 数据行 × 字段 | 字节数 | 项目用途 |
| --- | ---: | ---: | --- |
| `Video Games Sales (1980-2024) - Raw.csv` | 64,016 × 14 | 8,255,648 | 数据准备的唯一输入 |
| `Video_Games_Sales_Cleaned.csv` | 18,832 × 8 | 1,513,500 | 仅用于评分填补核查 |

- Raw SHA-256 `33780cc77d2395d82628c6f9120cc0905355a4804d5616dee06bdae414aff0d1`
- Cleaned SHA-256 `4a792d2b2a2f049025546f0accfa1872288d1c675b80a835db11637276ffdd3b`

下载并解压到本地后，应先比对文件名、字节数和指纹。Windows PowerShell 可用 `Get-FileHash -Algorithm SHA256 -LiteralPath "<CSV 路径>"`，macOS 可用 `shasum -a 256 "<CSV 路径>"`，Linux 可用 `sha256sum "<CSV 路径>"`。如果指纹不同，先核查下载版本或文件是否被表格软件重新保存。

## 上游对照与适用范围

将 Raw 与本地保存的 `vgchartz-2024.csv` 逐行对照，64,016 条记录顺序一致。将 `release_date` 和 `last_update` 转成同一日期格式后，仅有三条记录的 `publisher` 不同，Raw 为 `08-Apr`，对照文件为 `8-4`。这与表格自动日期转换的现象一致，转换过程尚待核实。项目保留 Raw 原值，并将对照文件只用于追溯来源。[Kaggle 上游数据集](https://www.kaggle.com/datasets/asaniczka/video-game-sales-2024)

VGChartz 说明其在 2018 年底停止生成软件销量估算，随后仅在发行商或开发商提供官方出货或销量时记录这些数据。主分析聚焦 2000–2018 年有有效总销量的发行记录。缺失销量代表缺少该记录的观测，发行年用于区分游戏发行批次。[VGChartz 数据方法](https://www.vgchartz.com/methodology.php)

公开仓库保留来源、校验值及复现代码。原始 CSV、对照 CSV 和逐条记录的生成产物保存在本地。公开分发数据副本前须确认对应数据许可。
