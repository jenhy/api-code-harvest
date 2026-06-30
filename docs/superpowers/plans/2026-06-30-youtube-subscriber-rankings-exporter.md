# YouTube 订阅者排行榜 — 实施计划（修订版）

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建 SocialBlade Top 100 YouTube 频道爬虫流水线，生成 CSV 数据文件和静态排行榜网页。exporter.py 支持流水线模式和独立运行模式。

**Architecture:** 五模块结构：config → scraper → parser → exporter → run.bat。手动触发，全流水线依次执行。scraper 用 cloudscraper + BeautifulSoup（Playwright 被 Cloudflare 阻挡），parser 输出 JSON，exporter 支持独立运行。

**Tech Stack:** Python 3.10+, cloudscraper, BeautifulSoup4, lxml

---

## 文件结构

```
C:\Users\Jenhy\youtube-rank\
├── config.py          # 全局配置（已存在）
├── requirements.txt   # 依赖声明
├── scraper.py         # cloudscraper + BeautifulSoup 爬虫
├── parser.py          # 数据清洗 & 结构化
├── exporter.py        # CSV 导出（可独立运行）
├── run.bat            # 一键运行流水线
├── data/              # 数据存放目录
│   ├── raw_YYYY-MM-DD.json
│   ├── parsed_YYYY-MM-DD.json
│   └── top1000_YYYY-MM-DD.csv
└── web/               # 排行榜网页（本次不做）
    └── index.html
```

---

### Task 1: 添加 requirements.txt

**文件：**
- Create: `C:\Users\Jenhy\youtube-rank\requirements.txt`

- [ ] **Step 1: 编写 requirements.txt**

```txt
cloudscraper>=1.2.71
beautifulsoup4>=4.12.0
lxml>=5.0.0
```

- [ ] **Step 2: 安装依赖**

```bash
pip install -r "C:\Users\Jenhy\youtube-rank\requirements.txt"
```

- [ ] **Step 3: 提交**

```bash
git add "C:/Users/Jenhy/youtube-rank/requirements.txt"
git commit -m "feat: add project dependencies (cloudscraper, bs4, lxml)"
```

---

### Task 2: 实现 scraper.py

**文件：**
- Create: `C:\Users\Jenhy\youtube-rank\scraper.py`

- [ ] **Step 1: 编写 scraper.py**

```python
"""爬取 SocialBlade Top 1000 YouTube 订阅者排名

输出: data/raw_YYYY-MM-DD.json
"""

import json
import os
import random
import time
from datetime import datetime

import cloudscraper
from bs4 import BeautifulSoup

import config


def fetch_page(url, retries=0):
    """抓取单个页面，返回 BeautifulSoup 对象"""
    scraper = cloudscraper.create_scraper()
    try:
        resp = scraper.get(url, timeout=30)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        if retries < config.MAX_RETRIES:
            delay = random.uniform(config.DELAY_MIN, config.DELAY_MAX)
            time.sleep(delay)
            return fetch_page(url, retries + 1)
        raise RuntimeError(f"抓取失败（已重试 {config.MAX_RETRIES} 次）: {e}")


def parse_rows(soup):
    """从页面提取频道数据"""
    rows = []
    table = soup.select_one("table")
    if not table:
        return rows

    trs = table.select("tbody tr")
    for tr in trs:
        cells = tr.select("td")
        if len(cells) < 5:
            continue

        rank_text = cells[0].get_text(strip=True)
        rank = "".join(ch for ch in rank_text if ch.isdigit())

        name_link = cells[1].select_one("a")
        channel_name = name_link.get_text(strip=True) if name_link else cells[1].get_text(strip=True)

        channel_url = ""
        if name_link:
            href = name_link.get("href", "")
            if href:
                channel_url = f"https://socialblade.com{href}"

        sub_link = cells[2].select_one("a")
        subscribers_display = sub_link.get_text(strip=True) if sub_link else cells[2].get_text(strip=True)

        views_link = cells[3].select_one("a")
        views_display = views_link.get_text(strip=True) if views_link else cells[3].get_text(strip=True)

        videos_link = cells[4].select_one("a")
        videos_display = videos_link.get_text(strip=True) if videos_link else cells[4].get_text(strip=True)

        rows.append({
            "rank": rank,
            "channel_name": channel_name,
            "channel_url": channel_url,
            "subscribers_display": subscribers_display,
            "total_views_display": views_display,
            "total_videos_display": videos_display,
        })

    return rows


def scrape_all():
    """爬取所有页面（单页模式下仅抓首页，保留翻页逻辑兼容未来变化）"""
    all_rows = []
    page_num = 1
    url = config.TARGET_URL

    while True:
        print(f"正在爬取第 {page_num} 页...")
        soup = fetch_page(url)
        rows = parse_rows(soup)
        print(f"  获取到 {len(rows)} 条数据")
        all_rows.extend(rows)

        if page_num >= config.PAGE_COUNT:
            break

        # 查找下一页
        next_link = soup.select_one('a:-soup-contains("Next")') or soup.select_one('a:-soup-contains("›")')
        if not next_link:
            print("  未找到翻页按钮，停止")
            break

        href = next_link.get("href", "")
        if href:
            url = f"https://socialblade.com{href}" if href.startswith("/") else href
        else:
            break

        delay = random.uniform(config.DELAY_MIN, config.DELAY_MAX)
        time.sleep(delay)
        page_num += 1

    return all_rows


def save_raw(data):
    """保存原始抓取数据"""
    os.makedirs(config.DATA_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(config.DATA_DIR, f"raw_{today}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"原始数据已保存: {path}")
    return path


def main():
    print("=" * 50)
    print("开始爬取 SocialBlade Top 1000")
    print(f"目标: {config.TARGET_URL}")
    print("=" * 50)

    rows = scrape_all()
    print(f"\n总计获取: {len(rows)} 条记录")

    save_raw(rows)
    print("爬取完成!")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 试运行爬虫**

```bash
cd "C:\Users\Jenhy\youtube-rank" && python scraper.py
```
预期：控制台输出翻页日志，`data/raw_YYYY-MM-DD.json` 生成，包含约 100 条记录。

- [ ] **Step 3: 提交**

```bash
git add "C:/Users/Jenhy/youtube-rank/scraper.py"
git commit -m "feat: implement cloudscraper-based scraper for SocialBlade"
```

---

### Task 3: 实现 parser.py

**文件：**
- Create: `C:\Users\Jenhy\youtube-rank\parser.py`

- [ ] **Step 1: 编写 parser.py**

```python
"""数据清洗与结构化

输入: data/raw_YYYY-MM-DD.json（scraper.py 输出）
输出: data/parsed_YYYY-MM-DD.json
"""

import json
import os
import re
from datetime import datetime

import config


def parse_number(display_str):
    """将 "504M" -> 504000000, "130.57B" -> 130570000000, "26.46K" -> 26460"""
    s = display_str.strip().replace(",", "").replace(" ", "")
    if not s or s in ("N/A", "-"):
        return 0
    m = re.match(r"^([\d.]+)([BKM])?$", s, re.IGNORECASE)
    if not m:
        return 0
    value = float(m.group(1))
    suffix = (m.group(2) or "").upper()
    multipliers = {"B": 1_000_000_000, "M": 1_000_000, "K": 1_000}
    return int(value * multipliers.get(suffix, 1))


def parse_rows(raw_rows):
    """清洗并结构化原始数据（去重、数字转换、按订阅数降序重排）"""
    parsed = []
    seen_urls = set()

    for row in raw_rows:
        name = row.get("channel_name", "").strip()
        url = row.get("channel_url", "")
        if not name:
            continue
        if url and url in seen_urls:
            continue

        seen_urls.add(url or name)
        parsed.append({
            "rank": int(row["rank"]) if row.get("rank", "").isdigit() else 0,
            "channel_name": name,
            "channel_url": url,
            "subscribers": parse_number(row.get("subscribers_display", "0")),
            "subscribers_display": row.get("subscribers_display", ""),
            "total_views": parse_number(row.get("total_views_display", "0")),
            "total_views_display": row.get("total_views_display", ""),
            "total_videos": parse_number(row.get("total_videos_display", "0")),
            "total_videos_display": row.get("total_videos_display", ""),
        })

    parsed.sort(key=lambda x: x["subscribers"], reverse=True)
    for i, row in enumerate(parsed, 1):
        row["rank"] = i

    return parsed


def find_latest_raw():
    """查找 data/ 下最新的 raw_*.json"""
    files = [f for f in os.listdir(config.DATA_DIR) if f.startswith("raw_") and f.endswith(".json")]
    if not files:
        raise FileNotFoundError(f"未找到 raw_*.json，请先运行 scraper.py")
    files.sort(reverse=True)
    return os.path.join(config.DATA_DIR, files[0])


def main():
    print("=" * 50)
    print("开始解析原始数据")
    print("=" * 50)

    raw_path = find_latest_raw()
    print(f"输入: {raw_path}")
    with open(raw_path, "r", encoding="utf-8") as f:
        raw_rows = json.load(f)
    print(f"原始数据: {len(raw_rows)} 条")

    parsed = parse_rows(raw_rows)
    print(f"清洗后: {len(parsed)} 条（去重后）")
    if parsed:
        print(f"排名 #1: {parsed[0]['channel_name']} ({parsed[0]['subscribers_display']})")
        print(f"排名 #{len(parsed)}: {parsed[-1]['channel_name']} ({parsed[-1]['subscribers_display']})")

    today = datetime.now().strftime("%Y-%m-%d")
    out_path = os.path.join(config.DATA_DIR, f"parsed_{today}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)
    print(f"解析数据已保存: {out_path}")
    print("解析完成!")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 测试解析器**

```bash
cd "C:\Users\Jenhy\youtube-rank" && python parser.py
```
预期：显示清洗后数据统计（去重后 100 条左右），`data/parsed_YYYY-MM-DD.json` 生成。

- [ ] **Step 3: 提交**

```bash
git add "C:/Users/Jenhy/youtube-rank/parser.py"
git commit -m "feat: implement data parser with B/M/K number normalization"
```

---

### Task 4: 实现 exporter.py

**文件：**
- Create: `C:\Users\Jenhy\youtube-rank\exporter.py`

- [ ] **Step 1: 编写 exporter.py**

```python
"""导出 CSV 文件

用法:
  python exporter.py                           # 默认：找 data/ 下最新的 parsed_*.json
  python exporter.py data/parsed_2026-06-30.json  # 指定文件
"""

import csv
import json
import os
import sys
from datetime import datetime
from glob import glob

import config


def find_latest_parsed():
    """找 data/ 下最新的 parsed_*.json"""
    pattern = os.path.join(config.DATA_DIR, "parsed_*.json")
    files = glob(pattern)
    if not files:
        sys.exit(f"错误: 未找到 parsed_*.json，请先运行 scraper.py + parser.py")
    files.sort(reverse=True)
    return files[0]


def read_channels(path):
    """读取 parsed JSON，返回频道列表。若某行缺少必要字段则跳过并警告。"""
    if not os.path.exists(path):
        sys.exit(f"错误: 文件不存在: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not data:
        print(f"警告: {path} 为空数组，将生成仅含表头的空 CSV")

    channels = []
    required = {"rank", "channel_name", "channel_url",
                "subscribers", "subscribers_display",
                "total_views", "total_views_display",
                "total_videos", "total_videos_display"}

    for row in data:
        missing = required - set(row.keys())
        if missing:
            print(f"警告: 跳过第 {row.get('rank', '?')} 行，缺少字段: {', '.join(sorted(missing))}",
                  file=sys.stderr)
            continue
        channels.append(row)

    return channels


def export_csv(channels, output_path):
    """用 csv.DictWriter 写入 CSV，UTF-8 BOM，Excel 兼容"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=config.CSV_FIELDS)
        writer.writeheader()
        for row in channels:
            writer.writerow({field: row.get(field, "") for field in config.CSV_FIELDS})

    print(f"已导出: {output_path} ({len(channels)} 条)")


def main():
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        path = find_latest_parsed()

    print(f"输入: {path}")
    channels = read_channels(path)
    today = datetime.now().strftime("%Y-%m-%d")
    output = os.path.join(config.DATA_DIR, f"top1000_{today}.csv")
    export_csv(channels, output)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 测试——流水线模式（无参数）**

```bash
cd "C:\Users\Jenhy\youtube-rank" && python exporter.py
```
预期：自动找到最新 parsed_*.json，输出 `data/top1000_YYYY-MM-DD.csv (100 条)`。

- [ ] **Step 3: 测试——独立模式（指定文件）**

```bash
cd "C:\Users\Jenhy\youtube-rank" && python exporter.py "data/parsed_2026-06-30.json"
```
预期：读取指定文件，输出 CSV。

- [ ] **Step 4: 测试——文件不存在**

```bash
cd "C:\Users\Jenhy\youtube-rank" && python exporter.py "data/nonexistent.json"
```
预期：`错误: 文件不存在: data/nonexistent.json`

- [ ] **Step 5: 测试——无 parsed 文件**

先清空 parsed 文件，然后运行：
```bash
cd "C:\Users\Jenhy\youtube-rank" && python exporter.py
```
预期：`错误: 未找到 parsed_*.json，请先运行 scraper.py + parser.py`

- [ ] **Step 6: 在 Excel 中打开 CSV，确认中文不乱码**

- [ ] **Step 7: 提交**

```bash
git add "C:/Users/Jenhy/youtube-rank/exporter.py"
git commit -m "feat: implement CSV exporter with standalone mode and error handling"
```

---

### Task 5: 实现 run.bat 一键运行

**文件：**
- Create: `C:\Users\Jenhy\youtube-rank\run.bat`

- [ ] **Step 1: 编写 run.bat**

```bat
@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================
echo   YouTube 订阅者排行榜 - 全自动流水线
echo ========================================
echo.
echo [1/3] 爬取 SocialBlade 数据...
call python scraper.py
if %errorlevel% neq 0 (
    echo 爬取失败，终止运行
    pause
    exit /b 1
)
echo.
echo [2/3] 解析数据...
call python parser.py
if %errorlevel% neq 0 (
    echo 解析失败，终止运行
    pause
    exit /b 1
)
echo.
echo [3/3] 导出 CSV...
call python exporter.py
if %errorlevel% neq 0 (
    echo 导出失败，终止运行
    pause
    exit /b 1
)
echo.
echo ========================================
echo   全部完成!
echo   数据: data\ 目录
echo ========================================
pause
```

- [ ] **Step 2: 测试 run.bat**

双击或命令行运行 `C:\Users\Jenhy\youtube-rank\run.bat`，确认三步依次执行无报错。

- [ ] **Step 3: 提交**

```bash
git add "C:/Users/Jenhy/youtube-rank/run.bat"
git commit -m "feat: add run.bat one-click pipeline"
```

---

### Task 6: 端到端验证

- [ ] **Step 1: 清空旧数据后全流程运行**

```bash
rm -f "C:\Users\Jenhy\youtube-rank\data\raw_*.json"
rm -f "C:\Users\Jenhy\youtube-rank\data\parsed_*.json"
rm -f "C:\Users\Jenhy\youtube-rank\data\top1000_*.csv"
cd "C:\Users\Jenhy\youtube-rank" && python scraper.py && python parser.py && python exporter.py
```
预期：三步全部成功，生成 raw_、parsed_、top1000_ 三个文件。

- [ ] **Step 2: 验证 CSV 行数**

```bash
python -c "
import csv
with open('C:/Users/Jenhy/youtube-rank/data/top1000_$(python -c \"from datetime import datetime; print(datetime.now().strftime('%Y-%m-%d'))\").csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    print(f'行数: {len(rows)}')
    print(f'字段: {reader.fieldnames}')
    print(f'第1行: {rows[0][\"channel_name\"]} - {rows[0][\"subscribers_display\"]}')
"
```
预期：约 100 行，字段完整，第 1 行是排名最高的频道。

- [ ] **Step 3: 测试 exporter 独立模式**

```bash
cd "C:\Users\Jenhy\youtube-rank" && python exporter.py
```
预期：找到已有的 parsed_*.json，重新生成 CSV（无需跑完整流水线）。

- [ ] **Step 4: 在 Excel 中打开 CSV**

双击 `data/top1000_YYYY-MM-DD.csv`，确认在 Excel 中中文显示正常，列对齐正确。

---

## 验证清单

1. `run.bat` 全流程无报错完成
2. `data/raw_YYYY-MM-DD.json` 包含约 100 条原始数据
3. `data/parsed_YYYY-MM-DD.json` 包含清洗后数据（去重、数值正确转换）
4. `data/top1000_YYYY-MM-DD.csv` UTF-8 BOM 编码，Excel 直接打开不乱码
5. `python exporter.py` 无参数可独立运行
6. `python exporter.py data/parsed_xxx.json` 可指定文件
7. 文件不存在或无 parsed 文件时给出明确错误提示
8. 第二次运行不会覆盖历史快照（带日期文件名）
