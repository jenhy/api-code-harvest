# API Code Harvester v2 设计文档

> **目标：** 批量从 hvoy.ai 领取免费兑换码，到 CUN.ai 兑换充值并创建 API 密钥。
> **规模：** 动态数量（约 337 份），每轮独立账号。
> **核心约束：** 唯一邮箱需求（1 账号 = 1 邮箱），全自动收验证邮件。

---

## 避坑记录（排除的方案）

| 方案 | 排除原因 |
|------|---------|
| Gmail IMAP — `imap.gmail.com:993` | 中国大陆被 GFW 封锁，连接 timeout |
| patchright + Chrome Profile 登录 Gmail 网页 | Google 反自动化检测，即使真实 Profile 也被重定向到登录页 |
| patchright `channel="chrome"` | 被 patchright 忽略，仍启动捆绑的旧版 chromium-1228 |
| 捆绑 chromium-1228 + 系统 Chrome User Data | 版本不匹配，浏览器启动后瞬间崩溃 |
| Guerrilla Mail 临时邮箱 | hvoy.ai 有邮箱白名单，临时邮箱域名被拒 |
| 163 / Outlook 等非 Gmail 邮箱 | 不支持 `+` aliasing，1 个邮箱 = 1 个地址，无法批量 |

---

## 技术方案

### 1. Gmail `+` aliasing 解决唯一邮箱问题

```
真实邮箱: ross.chen85.dev@gmail.com
别名:     ross.chen85.dev+hvoy001@gmail.com  → 收件进同一收件箱
          ross.chen85.dev+hvoy002@gmail.com
          ...
          ross.chen85.dev+hvoyNNN@gmail.com
```

所有别名邮件落入同一个 Gmail 收件箱，可通过 Gmail REST API（`gmail.googleapis.com`）搜索查询。

### 2. Gmail API 读取验证邮件

- 协议：HTTPS REST API（非 IMAP）
- 代理：通过 `127.0.0.1:22222` 访问 Google
- 已验证：VPN 开启时 API 可达，OAuth 授权成功，可搜索到 hvoy 验证邮件
- 已验证：邮件 HTML body 包含可提取的 `verify-email?token=` 链接

### 3. Chrome + Chrome Profile 过 Cloudflare Turnstile

- 使用 `executable_path` 显式指定系统 Chrome 路径：`C:\Program Files\Google\Chrome\Application\chrome.exe`
- 加载真实 Chrome Profile（已有登录态 cookie），Cloudflare Turnstile 自动完成
- 不影响 Chrome 自身设置，仅对指定域名（hvoy.ai、cun.ai）操作

---

## 完整循环（每轮 9 步）

### 阶段 A：hvoy.ai 全自动（步骤 1-5）

| 步骤 | 操作 | 自动化方式 |
|------|------|-----------|
| **A1** | 生成别名 `ross.chen85.dev+hvoyNNN@gmail.com` + 随机用户名 + 随机密码 | 脚本内 |
| **A2** | 打开 hvoy 注册页，填写表单（用户名/邮箱/密码/确认密码），Turnstile 自动通过后点"注册" | patchright |
| **A3** | Gmail API 搜索 `from:noreply@hvoy.ai to:别名`，提取 `verify-email?token=` 链接 | Gmail API |
| **A4** | 浏览器打开验证链接 → 点"去登录" → 输入用户名+密码登录 | patchright |
| **A5** | 菜单"免费Token"→"免费兑换码"→点"领取"→弹窗点"确认领取"→获取32位兑换码→保存 | patchright |

### 阶段 B：CUN.ai 手动+自动混合（步骤 6-9）

| 步骤 | 操作 | 自动化方式 |
|------|------|-----------|
| **B6** | 点"前往站点"跳转 CUN → 填写注册表单（用户名/密码/确认密码/邮箱/邀请码`44Wb`） | patchright |
| **B7** | ⚠️ **手动拖滑块1** → 脚本轮询检测"发送验证码"按钮启用 → 点之 | 人工 + 轮询 |
| **B8** | Gmail API 查收 CUN 6位验证码 → 自动填入 → 勾选协议 → 点"创建账户" | Gmail API + patchright |
| **B9** | 可能跳转登录页 → 输入用户名或邮箱 + 密码 + 勾选协议 → ⚠️ **可能手动拖滑块2** → 登录 | patchright + 人工 |
| **B10** | 菜单"充值/卡密兑换"→ 填入 B5 的兑换码 → 点"兑换额度" | patchright |
| **B11** | 菜单"API密钥"→"创建API密钥"→名称"Claude Code"→分组"default"→关闭无限配额→额度`30`→"保存更改" | patchright |
| **B12** | 表格中"API密钥"列点复制按钮 → 完整记录保存到 `accounts.json` | patchright |
| **B13** | 清除 hvoy.ai + cun.ai 的 cookies → 关闭所有页面 | patchright |

---

## 数据模型

`accounts.json` 中每条记录的格式：

```json
{
  "site": "cun",
  "username": "随机用户名",
  "email": "ross.chen85.dev+hvoy001@gmail.com",
  "password": "随机密码",
  "invite_code": "1011fd381fc445acaaf61f930d335a45",
  "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}
```

---

## 组件变更

### 新增文件

**`src/email/gmail_api.py`** — Gmail REST API 封装

```python
class GmailApi:
    def __init__(self, credentials_json: str, token_pickle: str, proxy: str):
        # OAuth 认证 + 代理配置

    def search_emails(self, query: str, max_results: int = 10) -> list[dict]:
        """搜索邮件，返回 {id, from, subject, snippet}"""

    def get_email_body(self, msg_id: str) -> str:
        """获取邮件完整 HTML body"""

    def extract_verification_link(self, html_body: str, domain: str) -> str | None:
        """从 HTML 中提取 verify-email?token= 链接"""

    def extract_code(self, html_body: str) -> str | None:
        """从 HTML 中提取 6 位数字验证码"""
```

### 修改文件

**`src/main.py`** — 主入口重写
- 浏览器启动：`channel="chrome"` → `executable_path="C:\Program Files\Google\Chrome\Application\chrome.exe"`
- CLI 参数：删除 `--gmail` / `--app-password`，新增 `--proxy`
- 主循环：9 步完整流程

**`src/sites/hvoy.py`** — 重构领码逻辑
- `extract_invite_code()` 从爬页面改为模拟点击交互：菜单导航 → 领取 → 确认领取 → 提取

**`src/sites/cun.py`** — 完整重写
- 集成 Gmail API（替代 IMAP/Guerrilla）
- 新增钱包兑换 + API 密钥创建 + 复制
- 滑块轮询等待逻辑保持

**`src/config.py`** — 新增代理配置字段

### 删除文件

- `src/email/gmail_inbox.py`（IMAP 方案废弃）
- `src/email/guerrilla.py`（临时邮箱被 hvoy 拒收）
- `src/email/manual.py`（不再需要手动邮箱操作）

### 保留不变

- `src/models.py` — 可能需要增加 `api_key` 字段
- `src/storage.py` — 足够满足需求
- `src/utils.py` — 用户名/密码生成器
- `config.yaml` — 微调

---

## CLI 用法

```bash
python -m src.main --count 337 --proxy 127.0.0.1:22222
```

| 参数 | 说明 |
|------|------|
| `--count N` | 目标轮数 |
| `--proxy host:port` | Gmail API HTTP 代理（默认 `127.0.0.1:22222`） |
| `--chrome-profile PATH` | Chrome 用户数据目录（默认当前 Chrome 路径） |
| `--resume` | 断点续跑，跳过已成功的轮次 |
| `--dry-run` | 打开页面暂停，供测试 DOM 选择器 |

---

## 错误处理

| 场景 | 策略 |
|------|------|
| Gmail API 暂时不可用 | 重试 3 次（间隔 5 秒） |
| hvoy Turnstile 超时（>2 分钟） | 标记失败，继续下一轮 |
| CUN 滑块超时（>3 分钟无操作） | 暂停等待，确认后继续 |
| 验证邮件未到达（>2 分钟） | 跳过当前账号，继续下一轮 |
| 邀请码提取失败 | 记录日志，继续下一轮 |
| 单轮任何步骤失败 | 不阻塞后续轮，失败计入计数 |

---

## 人工参与点

每轮中，脚本会在 B7（注册滑块1）和 B9（登录滑块2）处暂停等待。

- 脚本轮询检测后续按钮状态（"发送验证码"、"登录"）
- 按钮变为可用 → 脚本自动继续
- 超时无操作 → 打印提示
- 建议你听到 Chrome 窗口打开的声音后切过去拖滑块

---

## 待 dry-run 确认项

1. hvoy 菜单"免费兑换码"的 DOM 定位（文本匹配）
2. "领取"/"确认领取"/"前往站点"按钮的定位
3. CUN 注册表单各输入框的定位
4. CUN 滑块容器检测
5. "允许跳转到第三方网站"中间页的按钮定位
6. "创建API密钥"弹窗中分组选择器的定位
7. 复制按钮的定位 + API 密钥值读取方式
