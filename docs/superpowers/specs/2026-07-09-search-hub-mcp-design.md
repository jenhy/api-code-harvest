# Search Hub MCP Server 设计文档

**日期**: 2026-07-09
**状态**: 已批准

---

## 1. 概述

Search Hub 是一个 MCP Server，为 AI 客户端（Claude Code、CodeX 等）提供统一的搜索能力。核心特性：

- **多供应商聚合**: 支持 Firecrawl、Tavily，通过配置文件可扩展
- **多 Key 自动轮换**: 每个供应商可配多个 API Key，触发 429/402/403 时自动切下一个
- **供应商降级**: 按优先级链依次尝试，支持终极兜底
- **统一工具接口**: web_search / web_fetch / web_map，统一响应格式

## 2. 项目结构

```
C:\Users\Jenhy\.claude\tools\search-hub\
├── main.py                    # MCP Server 入口，注册 tools
├── config.yaml                # 供应商配置（Key 池、优先级、兜底）
├── providers/
│   ├── __init__.py
│   ├── base.py                # 抽象基类 ProviderBase
│   ├── firecrawl.py           # Firecrawl 实现
│   └── tavily.py              # Tavily 实现
├── core/
│   ├── __init__.py
│   ├── key_rotator.py         # Key 池管理、轮换策略
│   └── router.py              # 供应商选择、降级路由
├── requirements.txt
└── README.md
```

## 3. 组件设计

### 3.1 Provider 抽象基类 (`providers/base.py`)

```python
class ProviderBase(ABC):
    """所有搜索供应商必须实现此接口"""

    @abstractmethod
    async def search(self, query: str, **kwargs) -> SearchResult:
        """网页搜索"""
        ...

    @abstractmethod
    async def fetch(self, url: str, **kwargs) -> FetchResult:
        """抓取页面内容"""
        ...

    @abstractmethod
    async def map(self, url: str, **kwargs) -> MapResult:
        """发现站点 URL"""
        ...

    @abstractmethod
    async def health(self) -> bool:
        """检查供应商连通性"""
        ...
```

### 3.2 KeyRotator (`core/key_rotator.py`)

```
Key 池管理:
  - 每个供应商拥有独立的 Key 列表
  - 轮换策略: round_robin（循环，v1 唯一策略）
  - 错误计数: 跟踪每个 Key 的连续失败次数
  - 故障切换: 429/402/403/5xx 时自动切到本供应商的下一个 Key
  - 供应商耗尽: 当供应商所有 Key 都失败，标记该供应商不可用
```

### 3.3 Router (`core/router.py`)

```
路由逻辑:
  1. 取出 provider_priority 列表 + fallback 供应商
  2. 遍历 priority 列表，对每个供应商:
     a. 从 KeyRotator 取下一个可用 Key
     b. 调用供应商 API
     c. 成功 → 返回
     d. 失败(配额耗尽) → 继续遍历
  3. priority 全部耗尽 → 走 fallback 供应商（同上 Key 轮换逻辑）
  4. fallback 也耗尽 → 抛出错误
```

### 3.4 MCP 工具定义 (`main.py`)

| 工具 | 描述 | 参数 |
|------|------|------|
| `web_search` | 搜索网页 | `query: string` (必填), `count: number` (可选, 默认5) |
| `web_fetch` | 抓取页面内容 | `url: string` (必填) |
| `web_map` | 发现站点 URL | `url: string` (必填), `max_depth: number` (可选) |
| `doctor` | 诊断各供应商连通性 | 无参数 |

响应格式统一为:

```python
# search 响应
{
  "results": [
    {
      "title": "...",
      "url": "...",
      "content": "...",       # 摘要或全文
      "source": "firecrawl"   # 来自哪个供应商
    }
  ]
}
```

## 4. 配置方案 (`config.yaml`)

```yaml
# 搜索供应商优先级（前面的先用）
provider_priority:
  - firecrawl

# 终极兜底：所有 priority 供应商都挂了以后，降级到这里
fallback:
  provider: tavily

# Key 轮换策略: round_robin
rotation_strategy: round_robin

providers:
  firecrawl:
    type: firecrawl
    base_url: https://api.firecrawl.dev
    api_keys:
      - fc-key-xxx-1
      - fc-key-xxx-2
    timeout: 60

  tavily:
    type: tavily
    base_url: https://api.tavily.com
    api_keys:
      - tvly-key-xxx-1
    timeout: 30
```

> **扩展方式**: 新增供应商时，只需在 `providers/` 下新建一个文件实现 `ProviderBase`，在 `config.yaml` 中添加配置，注册到 `providers/__init__.py` 即可，不需要修改核心逻辑。

## 5. 集成方案

替换现有 MCP 配置（`settings.local.json` 中的 `firecrawl` 和 `web-search`），改为:

```json
"search-hub": {
  "command": "D:\\Program Files\\Python\\Python311\\python.exe",
  "args": ["C:\\Users\\Jenhy\\.claude\\tools\\search-hub\\main.py"],
  "env": {}
}
```

## 6. 错误处理

| 场景 | 行为 |
|------|------|
| 单个 Key 返回 429 | 切换本供应商下一个 Key，继续重试 |
| 单个 Key 返回 402/403 | 永久标记此 Key 不可用 |
| 供应商所有 Key 失效 | 标记供应商不可用，降级到下个供应商 |
| 供应商网络超时 | 当前 Key 标记暂时不可用（冷却 60s），切下一个 Key |
| 所有供应商（含兜底）均不可用 | 返回清晰错误信息 |

## 7. 非功能性需求

- **Python 3.11+**，仅依赖 `mcp`, `httpx`, `pyyaml`
- **无状态**: 无数据库，配置即状态
- **轻量**: 单文件入口，快速启动
