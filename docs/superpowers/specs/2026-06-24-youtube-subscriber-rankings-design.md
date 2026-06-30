# YouTube 订阅者排行榜 — 设计文档

> 日期：2026-06-24
> 状态：已批准

## 概述

爬取 SocialBlade Top 1000 YouTube 频道订阅者排名，生成可搜索排序的静态排行榜网页和 CSV 数据文件，支持手动触发的数据更新。

## 需求摘要

| 维度 | 规格 |
|------|------|
| 目的 | 个人兴趣/好奇 |
| 范围 | Top 100 频道（SocialBlade 限制，URL 标注 1000 但实际仅返回 100） |
| 字段 | 频道名、订阅数、总观看量、总视频数、链接 |
| 输出 | CSV（可 Excel 打开） + 静态 HTML 网页 |
| 更新 | 手动运行脚本触发 |
| 准确度 | 灵活（第三方数据源） |

## 架构

```
youtube-rank/
├── config.py          # 配置
├── scraper.py         # cloudscraper + BeautifulSoup 爬虫
├── parser.py          # 数据清洗 & 结构化
├── exporter.py        # CSV + HTML 生成
├── run.bat            # 一键运行脚本
├── requirements.txt   # 依赖（cloudscraper, bs4, lxml）
├── data/              # 历史数据快照
│   ├── raw_YYYY-MM-DD.json
│   ├── parsed_YYYY-MM-DD.json
│   └── top1000_YYYY-MM-DD.csv
└── web/               # 排行榜网页
    └── index.html
```

**数据流**：
- 流水线模式：手动执行 `run.bat` → `scraper.py` → `data/raw_*.json` → `parser.py` → `data/parsed_*.json` → `exporter.py` → `data/top1000_*.csv` + `web/index.html`
- 独立模式：`python exporter.py [parsed_*.json]` → 读取已有 parsed JSON → `data/top1000_*.csv`

## 模块设计

### 1. scraper.py — 爬虫模块

- **目标 URL**：`https://socialblade.com/youtube/lists/top/1000/subscribers/all/global`
- **工具**：cloudscraper + BeautifulSoup（Playwright 被 Cloudflare 阻挡）
- **策略**：单页抓取（实际仅 100 条），保留翻页逻辑兼容未来变化
- **每项提取**：排名、频道名、订阅数、总观看量、总视频数（不含国家/分类——列表页无此数据）
- **反爬**：cloudscraper 自动处理 Cloudflare 指纹，请求间隔 2-3 秒/页，失败重试 3 次
- **输出**：`data/raw_YYYY-MM-DD.json`（原始抓取数据）

### 2. parser.py — 数据处理模块

- 数字清洗：`504M` → `504000000`，保留原始字符串用于显示（`subscribers_display`）
- 去重校验（基于 channel_url）、缺失值标记
- 输出：`data/parsed_YYYY-MM-DD.json`（结构化数据，含数值和展示字段）

### 3. exporter.py — 导出模块

**运行方式**：
- 可作为流水线一环（`run.bat` 串联调用）
- 也可独立运行：`python exporter.py [parsed_json_path]`
- 不传参数时自动查找 `data/` 下最新的 `parsed_*.json`
- 传参时使用指定文件：`python exporter.py data/parsed_2026-06-30.json`

**CSV 输出**：
- 字段：`rank, channel_name, channel_url, subscribers, subscribers_display, total_views, total_videos, total_views_display, total_videos_display`
- 使用 `csv.DictWriter`，UTF-8 BOM 编码，Excel 直接兼容
- 文件名取当前日期：`data/top1000_YYYY-MM-DD.csv`
- 若 `data/` 目录不存在则自动创建

**错误处理**：

| 情况 | 行为 |
|------|------|
| 无参数且 data/ 下无 parsed_*.json | 报错退出，提示先运行 scraper + parser |
| 指定文件不存在 | 报错退出："文件不存在" |
| JSON 中某行缺少必要字段 | 跳过该行，stderr 输出警告，继续导出 |
| JSON 为空数组 `[]` | 生成仅含表头的空 CSV，打印警告 |
| data/ 目录不存在 | 自动创建（`os.makedirs(exist_ok=True)`） |

**HTML 输出**：
- 纯静态单页 `web/index.html`
- 表格：5 列（#、频道、订阅数、总观看量、视频数）
- 极简表格布局（用户选中的方案 A）
- Vanilla JS 实现列排序 + 搜索框实时过滤
- 显示更新时间和频道总数
- 支持深色/浅色模式切换
- 浏览器端 CSV 导出按钮
- 响应式设计（移动端隐藏次要列）

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
┌─────────────────────────────────────────────────┐
│  YouTube 订阅者 Top 100                         │
│  更新时间: 2026-06-24  |  共 100 个频道          │
│  ┌─────────────────────────────────────────────┐│
│  │ 🔍 搜索频道...      [深色/浅色] [导出 CSV] ││
│  ├────┬──────────┬──────────┬──────────┬───────┤│
│  │ #  │ 频道     │ 订阅数 ▼│ 总观看量 │ 视频数││
│  ├────┼──────────┼──────────┼──────────┼───────┤│
│  │ 1  │ MrBeast  │   504M  │ 130.57B  │   987 ││
│  │ 2  │ T-Series │   313M  │ 345.82B  │ 26.5K ││
│  │ ...│          │          │          │       ││
│  │100 │ Shakira  │  51.3M  │  36.61B  │   409 ││
│  └────┴──────────┴──────────┴──────────┴───────┘│
└─────────────────────────────────────────────────┘
```

## 验证方式

1. 运行 `run.bat`，确认爬取正常完成（日志无报错）
2. 检查 `data/` 下 CSV 文件数据完整性（行数 ≈ 100，字段完整）
3. 打开 `web/index.html` 在浏览器中确认排名、排序、搜索功能正常
4. 第二次运行检查历史数据是否增量保存

## 非目标

- 不爬取 YouTube 直接（使用 SocialBlade 作为数据源）
- 非实时更新（手动触发）
- 不包含视频内容、评论等额外数据
- 不做数据分析/可视化图表（纯数据表）
