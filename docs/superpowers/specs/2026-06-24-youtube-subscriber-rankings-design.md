# YouTube 订阅者排行榜 — 设计文档

> 日期：2026-06-24
> 状态：已批准

## 概述

爬取 SocialBlade Top 1000 YouTube 频道订阅者排名，生成可搜索排序的静态排行榜网页和 CSV 数据文件，支持手动触发的数据更新。

## 需求摘要

| 维度 | 规格 |
|------|------|
| 目的 | 个人兴趣/好奇 |
| 范围 | Top 1000 频道 |
| 字段 | 频道名、订阅数、总观看量、总视频数、国家、分类、链接 |
| 输出 | CSV（可 Excel 打开） + 静态 HTML 网页 |
| 更新 | 手动运行脚本触发 |
| 准确度 | 灵活（第三方数据源） |

## 架构

```
youtube-rank/
├── scraper.py         # Playwright 爬虫
├── parser.py          # 数据清洗 & 结构化
├── exporter.py        # CSV + HTML 生成
├── config.py          # 配置
├── data/              # 历史数据快照
│   └── top1000_YYYY-MM-DD.csv
├── web/               # 排行榜网页
│   └── index.html
└── run.bat            # 一键运行脚本
```

**数据流**：手动执行 `run.bat` → `scraper.py` → `parser.py` → `exporter.py` → `data/*.csv` + `web/index.html`

## 模块设计

### 1. scraper.py — 爬虫模块

- **目标 URL**：`https://socialblade.com/youtube/top/1000/mostsubscribed`
- **工具**：Playwright 无头浏览器
- **策略**：分页抓取，每页 50 条，共 20 页
- **每项提取**：排名、频道名、订阅数、总观看量、总视频数、国家
- **反爬**：请求间隔 2-3 秒/页，失败重试 3 次
- **输出**：`data/raw_YYYY-MM-DD.json`（原始抓取数据）

### 2. parser.py — 数据处理模块

- 数字清洗：`2.85亿` → `285000000`，保留原始字符串用于显示
- 国家代码推断（从国旗图标/文本）
- 去重校验、缺失值标记
- 输出结构化数据

### 3. exporter.py — 导出模块

**CSV 输出**：
- 字段：`rank, channel_name, channel_url, subscribers, subscribers_display, total_views, total_videos, country, category`
- UTF-8 BOM 编码，Excel 直接兼容
- 文件：`data/top1000_YYYY-MM-DD.csv`

**HTML 输出**：
- 纯静态单页 `web/index.html`
- 极简表格布局（用户选中的方案 A）
- Vanilla JS 实现列排序 + 搜索框实时过滤
- 显示更新时间和频道总数
- 支持深色/浅色模式
- 单文件，无需任何依赖

### 4. config.py — 配置模块

- `TARGET_URL`：SocialBlade Top 1000 URL
- `PAGE_COUNT`：分页数（默认 20）
- `DELAY_BETWEEN_PAGES`：翻页间隔（默认 2-3 秒）
- `OUTPUT_DIR`：数据输出目录
- `WEB_DIR`：网页输出目录
- `MAX_RETRIES`：最大重试次数（默认 3）

### 5. run.bat — 一键运行

```bat
python scraper.py
python parser.py
python exporter.py
```

手动双击或命令行执行即可整条流水线跑完。

## 输出网页预览

```
┌─────────────────────────────────────────────────────┐
│  🏆 YouTube 订阅者 Top 1000                        │
│  更新时间: 2026-06-24  |  共 1000 个频道            │
│  ┌─────────────────────────────────────────────────┐│
│  │ 🔍 搜索频道...          [深色/浅色] [导出 CSV] ││
│  ├────┬──────────┬──────────┬──────┬──────┬───────┤│
│  │ #  │ 频道     │ 订阅数 ▼│ 分类 │ 国家 │ 总观看││
│  ├────┼──────────┼──────────┼──────┼──────┼───────┤│
│  │ 1  │ T-Series │ 2.85亿  │ 音乐 │  IN  │ 2600亿││
│  │ 2  │ MrBeast  │ 2.70亿  │ 娱乐 │  US  │  570亿││
│  │ 3  │ Cocomelon│ 1.79亿  │ 教育 │  US  │ 1800亿││
│  │ ...│          │          │      │      │       ││
│  │1000│ ...      │ ...      │ ...  │ ...  │ ...   ││
│  └────┴──────────┴──────────┴──────┴──────┴───────┘│
└─────────────────────────────────────────────────────┘
```

## 验证方式

1. 运行 `run.bat`，确认爬取正常完成（日志无报错）
2. 检查 `data/` 下 CSV 文件数据完整性（行数 ≈ 1000，字段完整）
3. 打开 `web/index.html` 在浏览器中确认排名、排序、搜索功能正常
4. 第二次运行检查历史数据是否增量保存

## 非目标

- 不爬取 YouTube 直接（使用 SocialBlade 作为数据源）
- 非实时更新（手动触发）
- 不包含视频内容、评论等额外数据
- 不做数据分析/可视化图表（纯数据表）
