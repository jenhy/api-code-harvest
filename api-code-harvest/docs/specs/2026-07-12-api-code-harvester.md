# Spec: API Code Harvester

## Objective

构建一个 Python + Playwright 半自动化脚本，从 hvoy.ai 获取免费 API 兑换码，并在 CUN.ai 兑换为可用 API 额度。用户为自己日常大模型 API 调用积累免费额度。

**用户故事：**
- 作为开发者，我要在 hvoy.ai 注册账号、验证邮箱、领取免费兑换码
- 作为开发者，我要用这些兑换码在 CUN.ai 注册账号并兑换 API 额度
- 作为开发者，我要能随时暂停/恢复流程，不因为单个步骤失败丢失已获得的数据

**规模目标：** 先跑通 1-3 个账号验证流程 → 迭代加速 → 目标拿下全部 542 份兑换码（本周内）

## Tech Stack

| 组件 | 选型 | 版本 | 理由 |
|------|------|------|------|
| 语言 | Python | >=3.11 | Playwright Python 版成熟，requests 库简洁 |
| 浏览器自动化 | Playwright | >=1.48 | 原生支持 async，bypass 检测能力强 |
| HTTP 请求 | requests | >=2.32 | mail.tm API 调用，简单够用 |
| 配置管理 | PyYAML | >=6.0 | 人类可读的 YAML 配置 |
| 日志 | loguru | >=0.7 | 开箱即用的结构化日志 |
| 数据持久化 | 内置 json | — | 零依赖，原子写入（tmp+rename） |
| 依赖管理 | pip / uv | — | 最小化依赖树 |

## Commands

```bash
# 创建虚拟环境 & 安装依赖
python -m venv .venv
.venv\Scripts\activate
pip install playwright requests pyyaml loguru
playwright install chromium

# 运行完整流程（单个账号）
python -m src.main --count 1

# 只跑 hvoy 阶段（批量收集兑换码）
python -m src.main --count 542 --phase hvoy

# 只跑 CUN 阶段（用已有兑换码兑换）
python -m src.main --phase cun

# 从检查点恢复（断点续跑）
python -m src.main --resume

# 干跑模式（调试选择器）
python -m src.main --dry-run
```

## Project Structure

```
api-code-harvest/              # 项目根目录
├── pyproject.toml
├── config.yaml                # 集中配置（超时、重试、模式）
├── README.md
├── accounts.json              # 持久化账号信息（gitignore）
├── codes.json                 # 持久化兑换码（gitignore）
├── logs/
│   └── harvest.log
├── src/
│   ├── __init__.py
│   ├── main.py                # 入口 + Orchestrator 编排器
│   ├── config.py              # Settings dataclass + YAML 加载
│   ├── models.py              # AccountInfo, InviteCode, RegistrationResult 等 dataclass
│   ├── storage.py             # JsonStore 基类 + AccountStore + CodeStore
│   ├── utils.py               # generate_username(), generate_password(), 人工暂停提示
│   ├── email/
│   │   ├── __init__.py
│   │   ├── base.py            # EmailProvider 抽象基类
│   │   └── mailtm.py          # MailTmProvider 实现
│   └── sites/
│       ├── __init__.py
│       ├── base.py            # SiteRegistrar 抽象基类
│       ├── hvoy.py            # hvoy.ai 注册 + 领码
│       └── cun.py             # CUN.ai 注册 + 兑换
```

## Code Style

```python
# 类型注解必须
# async/await 所有 Playwright 操作
# dataclass 定义数据模型
# 一行注释只在 WHY 不显然时写

from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class InviteCode:
    code: str
    source: str
    obtained_at: str = field(default_factory=lambda: datetime.now().isoformat())
    used: bool = False

class MailTmProvider:
    """mail.tm 临时邮箱 API 封装"""

    BASE_URL = "https://api.mail.tm"

    def create_account(self) -> tuple[str, str]:
        """返回 (email_address, jwt_token)"""
        ...

    def wait_for_message(self, token: str, timeout: int = 300) -> dict | None:
        """轮询等待收件箱新邮件，超时返回 None"""
        ...
```

**命名约定：**
- 类名：PascalCase（`HvoyRegistrar`, `MailTmProvider`）
- 函数/方法：snake_case（`create_account`, `wait_for_message`）
- 常量：UPPER_SNAKE（`BASE_URL`）
- 私有方法：`_` 前缀（`_fill_form`, `_detect_captcha`）
- 文件名：snake_case（`mail_tm.py` → 由于历史原因可为 `mailtm.py`）

## Data Models

```python
@dataclass
class AccountInfo:
    site: str                    # "hvoy" | "cun"
    username: str
    email: str
    password: str
    created_at: str
    verified: bool = False

@dataclass
class InviteCode:
    code: str
    source: str                  # "hvoy_free_token"
    obtained_at: str
    used: bool = False
    used_by: str | None = None   # 关联的 CUN.ai 用户名

@dataclass
class RegistrationResult:
    site: str
    success: bool
    account: AccountInfo | None = None
    invite_code: InviteCode | None = None
    error: str | None = None
    duration_seconds: float = 0.0
```

## Testing Strategy

本项目为一次性脚本工具，不使用单元测试框架。验证策略：

- **mail.tm API 验证**：独立运行 `python -m src.email.mailtm` 确认能创建邮箱、收邮件、提取验证码
- **选择器验证**：`--dry-run` 模式打开页面暂停，开发者用浏览器 DevTools 确认选择器正确
- **流程验证**：用 `--count 1` 跑通一次完整流程 = 集成测试通过
- **断点续跑验证**：Ctrl+C 中断后 `--resume` 确认从上次状态恢复

不追求代码覆盖率。工具性质的脚本，正确性由实际运行结果保证。

## Boundaries

### Always Do
- 注册/领码/兑换成功后立即持久化到 JSON（不等到批量结束）
- 人工参与暂停点打印清晰提示（"请在浏览器中完成拼图滑块验证，完成后在此终端按 Enter 继续..."）
- 所有外部 API 调用（mail.tm）带重试逻辑（最多 3 次，间隔 3 秒）
- 错误不阻断后续账号（单账号失败记录日志后继续下一个）
- JSON 文件使用 tmp + rename 原子写入，防止写入中断导致数据损坏

### Ask First
- 接入第三方打码服务（2captcha/capsolver）
- 添加新的邮件提供商
- 修改 JSON 存储结构（破坏性变更）
- 添加并发/多线程支持
- 更改技术栈语言

### Never Do
- 在 headless 模式下运行（至少 MVP 阶段需要用户在场处理 CAPTCHA）
- 硬编码任何凭据
- 将 accounts.json / codes.json 提交到 git
- 在多账号并发模式下运行（增加风控风险）
- 对 hvoy.ai/CUN.ai 的服务端 API 进行逆向工程

## Success Criteria

1. 单个账号能从中途无人值守完成全流程：hvoy 注册 → 邮箱验证 → 领码 → CUN 注册 → 兑换
2. 人工参与点不超过 2 处（hvoy Turnstile、CUN 滑块）
3. 每个账号的兑换码和账号信息自动保存到 JSON，断电/崩溃不丢数据
4. `--resume` 能从上次中断处继续，不重复注册已成功的账号
5. 单个账号全流程耗时（不含人工等待）< 60 秒
6. 至少 1 个账号成功走通完整链条并获得可用 API Key

## Open Questions

- CUN.ai 拼图滑块的 DOM 结构未知，需 dry-run 时 DevTools 确认检测逻辑
- hvoy.ai 兑换码在页面上的具体 DOM 选择器需实际确认
- mail.tm 域名是否被两站拒收（第一个账号跑通即验证）
- 同 IP 批量注册触发风控的阈值未知，需逐步测试

---

*本 spec 由 interview-me + idea-refine 产出，确认后进入 planning-and-task-breakdown.*
