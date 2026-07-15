# API Code Harvester v2 实现方案

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标：** 实现一个 Python 脚本，从 hvoy.ai 批量领取免费邀请码，在 CUN.ai 兑换为 API 密钥，保存到本地 JSON。

**架构：** Patchright 驱动 Chrome Profile（真实浏览器，过 Cloudflare Turnstile）完成网页交互；Gmail REST API（走 HTTP 代理）读取收件箱验证邮件；Gmail `+` aliasing 提供无限唯一邮箱地址。

**Tech Stack:** Python 3.11+, patchright, Gmail REST API (google-api-python-client), google-auth-oauthlib

---

## 文件变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `src/email/gmail_api.py` | Gmail REST API 封装 |
| 修改 | `src/models.py` | 增加 `invite_code`/`api_key` 字段 |
| 修改 | `src/config.py` | 增加代理配置 |
| 修改 | `config.yaml` | 增加代理/credentials 路径 |
| 修改 | `pyproject.toml` | 增加 Gmail API 依赖 |
| 修改 | `src/sites/hvoy.py` | 重写领码交互（点击式） |
| 修改 | `src/sites/cun.py` | 重写完整流程 |
| 修改 | `src/main.py` | 重写主循环 + 修复 Chrome 启动 |
| 删除 | `src/email/gmail_inbox.py` | IMAP 方案废弃 |
| 删除 | `src/email/guerrilla.py` | 临时邮箱被拒收 |
| 删除 | `src/email/manual.py` | 不再需要 |
| 保留 | `src/utils.py`, `src/storage.py`, `src/sites/base.py` | 逻辑未变 |

---

### Task 1: 更新依赖和配置

**Files:**
- Modify: `pyproject.toml:4-8`
- Modify: `src/config.py:8-36`
- Modify: `config.yaml:1-35`

- [ ] **Step 1: 在 `pyproject.toml` 中增加 Gmail API 依赖**

```toml
dependencies = [
    "playwright>=1.48.0",
    "patchright>=1.48.0",
    "requests>=2.32.0",
    "pyyaml>=6.0",
    "loguru>=0.7.0",
    "google-api-python-client>=2.120.0",
    "google-auth-oauthlib>=1.2.0",
]
```

- [ ] **Step 2: 在 `src/config.py` 中增加代理和 Gmail 凭据配置**

在 `StorageConfig` 之后添加：

```python
@dataclass
class GmailConfig:
    credentials_file: str = "credentials.json"
    token_pickle: str = "token.pickle"
    email_address: str = ""
    proxy_host: str = "127.0.0.1"
    proxy_port: int = 22222
```

在 `Settings` 中添加字段：

```python
@dataclass
class Settings:
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    timeouts: TimeoutConfig = field(default_factory=TimeoutConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    mode: ModeConfig = field(default_factory=ModeConfig)
    batch: BatchConfig = field(default_factory=BatchConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    gmail: GmailConfig = field(default_factory=GmailConfig)   # 新增

    @classmethod
    def from_yaml(cls, path: str) -> "Settings":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls(
            browser=BrowserConfig(**data.get("browser", {})),
            timeouts=TimeoutConfig(**data.get("timeouts", {})),
            retry=RetryConfig(**data.get("retry", {})),
            mode=ModeConfig(**data.get("mode", {})),
            batch=BatchConfig(**data.get("batch", {})),
            storage=StorageConfig(**data.get("storage", {})),
            gmail=GmailConfig(**data.get("gmail", {})),        # 新增
        )
```

- [ ] **Step 3: 在 `config.yaml` 中增加 Gmail 配置**

```yaml
# Gmail API 配置（用于读取验证邮件）
gmail:
  credentials_file: "credentials.json"
  token_pickle: "token.pickle"
  email_address: "ross.chen85.dev@gmail.com"
  proxy_host: "127.0.0.1"
  proxy_port: 22222
```

- [ ] **Step 4: 安装新依赖**

```bash
pip install google-api-python-client google-auth-oauthlib
```

- [ ] **Step 5: 提交**

```bash
git add pyproject.toml src/config.py config.yaml
git commit -m "chore: add Gmail API dependencies and proxy/gmail config"
```

---

### Task 2: 创建 GmailApi 类

**Files:**
- Create: `src/email/gmail_api.py`

- [ ] **Step 1: 实现 `GmailApi` 类**

这个类封装 Gmail REST API 的 OAuth 认证、邮件搜索、正文提取、验证链接/验证码提取。

```python
"""Gmail REST API client — search & read verification emails via OAuth."""
import base64
import os
import pickle
import re
import time

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class GmailApi:
    """Gmail API client, proxied for GFW bypass."""

    def __init__(self, credentials_file: str, token_pickle: str,
                 proxy_host: str = "127.0.0.1", proxy_port: int = 22222):
        self.credentials_file = credentials_file
        self.token_pickle = token_pickle
        self.proxy = f"http://{proxy_host}:{proxy_port}"
        self._service = None

    def _auth(self):
        """Authenticate with Gmail API via OAuth. Caches token.pickle."""
        os.environ["HTTPS_PROXY"] = self.proxy
        os.environ["HTTP_PROXY"] = self.proxy

        creds = None
        if os.path.exists(self.token_pickle):
            with open(self.token_pickle, "rb") as f:
                creds = pickle.load(f)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES
                )
                creds = flow.run_local_server(port=0)
            with open(self.token_pickle, "wb") as f:
                pickle.dump(creds, f)
        return creds

    @property
    def service(self):
        if self._service is None:
            creds = self._auth()
            self._service = build("gmail", "v1", credentials=creds)
        return self._service

    def search_messages(self, query: str, max_results: int = 5) -> list[dict]:
        """Search messages by query. Returns [{id, from, subject, snippet}]."""
        result = self.service.users().messages().list(
            userId="me", q=query, maxResults=max_results
        ).execute()
        messages = result.get("messages", [])
        out = []
        for msg in messages:
            detail = self.service.users().messages().get(
                userId="me", id=msg["id"], format="metadata",
                metadataHeaders=["From", "Subject", "To"]
            ).execute()
            headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
            out.append({
                "id": msg["id"],
                "from": headers.get("From", ""),
                "subject": headers.get("Subject", ""),
                "to": headers.get("To", ""),
                "snippet": detail.get("snippet", ""),
            })
        return out

    def get_email_body(self, msg_id: str) -> str:
        """Get full HTML body of a message."""
        detail = self.service.users().messages().get(
            userId="me", id=msg_id, format="full"
        ).execute()
        return self._extract_body(detail["payload"])

    def _extract_body(self, payload: dict) -> str:
        """Recursively extract body text from MIME parts."""
        if payload.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
        for part in payload.get("parts", []):
            result = self._extract_body(part)
            if result:
                return result
        return ""

    def wait_for_verification_link(self, query: str, domain: str,
                                    timeout: int = 120, poll_interval: int = 5) -> str | None:
        """Poll for email matching query, extract verification link containing domain."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            msgs = self.search_messages(query, max_results=3)
            for msg in msgs:
                body = self.get_email_body(msg["id"])
                link = self._extract_link(body, domain)
                if link:
                    return link
            time.sleep(poll_interval)
        return None

    def wait_for_verification_code(self, query: str,
                                    timeout: int = 120, poll_interval: int = 5) -> str | None:
        """Poll for email matching query, extract 6-digit verification code."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            msgs = self.search_messages(query, max_results=3)
            for msg in msgs:
                body = self.get_email_body(msg["id"])
                code = self._extract_code(body)
                if code:
                    return code
            time.sleep(poll_interval)
        return None

    @staticmethod
    def _extract_link(html: str, domain_hint: str) -> str | None:
        """Extract verification link: href with verify-email?token= and domain_hint."""
        pattern = r'https://[^\s"\'<>]*verify-email\?token=[a-f0-9]+[^\s"\'<>]*'
        links = re.findall(pattern, html)
        for link in links:
            if domain_hint in link:
                return link
        # Fallback: any link containing domain_hint
        all_links = re.findall(r'https?://[^\s"\'<>]+', html)
        for link in all_links:
            if domain_hint in link:
                return link
        return None

    @staticmethod
    def _extract_code(html: str) -> str | None:
        """Extract 6-digit code from email body."""
        m = re.search(r'\b(\d{6})\b', html)
        return m.group(1) if m else None
```

- [ ] **Step 2: 提交**

```bash
git add src/email/gmail_api.py
git commit -m "feat: add GmailApi class for REST API email verification"
```

---

### Task 3: 更新数据模型

**Files:**
- Modify: `src/models.py`

- [ ] **Step 1: 修改 `AccountInfo`，增加 `invite_code` 和 `api_key` 字段**

```python
@dataclass
class AccountInfo:
    site: str
    username: str
    email: str
    password: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    verified: bool = False
    invite_code: str = ""           # 新增：从 hvoy 领取的兑换码
    api_key: str = ""               # 新增：CUN 生成的 API 密钥
```

- [ ] **Step 2: 提交**

```bash
git add src/models.py
git commit -m "feat: add invite_code and api_key fields to AccountInfo"
```

---

### Task 4: 重写 HvoyRegistrar（登录 + 领码 + 登出）

**Files:**
- Modify: `src/sites/hvoy.py`

- [ ] **Step 1: 重写 `HvoyRegistrar` 类**

主要变更：
1. 注册逻辑基本不变（已有代码可用）
2. **新增 `login()` 方法**：注册后或验证后登录
3. **重写 `extract_invite_code()`**：不再爬页面源码正则匹配，而是模拟用户点击交互
4. **新增 `logout()` 方法**：清除 hvoy.ai cookies

```python
"""hvoy.ai registration + login + invite code extraction via UI clicks."""
import asyncio
import re

from patchright.async_api import BrowserContext, Page

from src.models import AccountInfo, InviteCode, RegistrationResult
from src.sites.base import HumanVerification


class HvoyRegistrar(HumanVerification):
    """hvoy.ai register + login + extract invite code + logout"""

    REGISTER_URL = "https://hvoy.ai/user/register"
    LOGIN_URL = "https://hvoy.ai/user/login"
    INVITE_CODES_URL = "https://hvoy.ai/free-tokens/invite-codes"

    async def register(
        self, context: BrowserContext, email_addr: str,
        username: str, password: str,
    ) -> RegistrationResult:
        page = await context.new_page()
        try:
            await page.goto(self.REGISTER_URL, wait_until="domcontentloaded")
            await self._wait_for_page_ready(page)

            print("  Waiting for Cloudflare & Turnstile...")
            if not await self._wait_for_turnstile(page, timeout=120):
                return RegistrationResult(site="hvoy", success=False, error="Turnstile timeout")

            await self._fill_form(page, username, email_addr, password)
            await page.locator('button[type="submit"]').click()
            await page.wait_for_timeout(3000)

            return RegistrationResult(
                site="hvoy", success=True,
                account=AccountInfo(site="hvoy", username=username,
                                    email=email_addr, password=password, verified=False),
            )
        except Exception as e:
            return RegistrationResult(site="hvoy", success=False, error=str(e))
        finally:
            await page.close()

    async def login(self, context: BrowserContext, username: str, password: str) -> bool:
        """登录 hvoy.ai。返回 True 表示登录成功。"""
        page = await context.new_page()
        try:
            await page.goto(self.LOGIN_URL, wait_until="domcontentloaded")
            # 等待 Turnstile 自动完成
            print("  Waiting for Turnstile on login page...")
            await self._wait_for_turnstile(page, timeout=60)

            inputs = page.locator("input:visible")
            count = await inputs.count()
            if count >= 2:
                await inputs.nth(0).fill(username)
                await inputs.nth(1).fill(password)
            else:
                # 单个输入框（用户名或电子邮件）
                await inputs.first.fill(username)
                pwd = page.locator('input[type="password"]')
                await pwd.fill(password)

            await page.locator('button[type="submit"]').click()
            await page.wait_for_timeout(3000)

            # 检查是否成功登录（URL 不再包含 /login）
            success = "login" not in page.url.lower()
            print(f"  Login {'success' if success else 'failed'}")
            return success
        finally:
            await page.close()

    async def extract_invite_code(self, context: BrowserContext) -> InviteCode | None:
        """通过点击 UI 交互领取邀请码并提取 32 位兑换码。"""
        page = await context.new_page()
        try:
            await page.goto(self.INVITE_CODES_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

            # 点击"领取"按钮
            claim_btn = page.locator('button:has-text("领取")')
            if await claim_btn.count() == 0:
                claim_btn = page.locator('text=领取').first
            await claim_btn.click()
            await page.wait_for_timeout(1000)

            # 确认弹窗显示兑换码
            confirm_btn = page.locator('button:has-text("确认领取")')
            if await confirm_btn.count() == 0:
                confirm_btn = page.locator('text=确认领取').first
            await confirm_btn.click()
            await page.wait_for_timeout(1000)

            # 弹窗中显示的兑换码（32 位十六进制）
            # 可能在某个 div/span 中显示
            body = await page.inner_text("body")
            codes = re.findall(r'[a-f0-9]{32}', body)
            if codes:
                code_str = codes[0]
                print(f"  >>> Invite code: {code_str}")
                return InviteCode(code=code_str, source="hvoy_free_token")

            # 尝试用其他方式提取
            content = await page.content()
            codes = re.findall(r'[A-Za-z0-9]{16,32}', content)
            if codes:
                print(f"  >>> Invite code (fallback): {codes[0]}")
                return InviteCode(code=codes[0], source="hvoy_free_token")

            return None
        finally:
            await page.close()

    async def click_go_to_site(self, context: BrowserContext) -> None:
        """在确认领取弹窗中点击"前往站点"按钮，跳转 CUN。"""
        page = await context.new_page()
        try:
            go_btn = page.locator('button:has-text("前往站点")')
            if await go_btn.count() == 0:
                go_btn = page.locator('text=前往站点').first
            await go_btn.click()
            await page.wait_for_timeout(3000)
        finally:
            await page.close()

    async def logout(self, context: BrowserContext) -> None:
        """登出 hvoy.ai，清除相关 cookies。"""
        await context.clear_cookies(urls=["https://hvoy.ai", "https://www.hvoy.ai"])
        print("  Cleared hvoy.ai cookies")

    # ---- 以下为内部辅助方法，与当前版本相同 ----

    async def _wait_for_turnstile(self, page: Page, timeout: int = 120) -> bool:
        import time
        deadline = time.time() + timeout
        while time.time() < deadline:
            if await self._detect_turnstile_token(page):
                print("  Turnstile completed!")
                return True
            await asyncio.sleep(2)
        return False

    async def _wait_for_page_ready(self, page: Page, max_wait: int = 120) -> None:
        for _ in range(max_wait // 2):
            body = await page.inner_text("body")
            if "注册账号" in body or "用户名" in body:
                return
            await asyncio.sleep(2)
        raise TimeoutError("Cloudflare challenge timeout")

    async def _detect_turnstile_token(self, page: Page) -> bool:
        return await page.evaluate("""() => {
            const el = document.querySelector('[name="cf-turnstile-response"]');
            return el && el.value && el.value.length > 10;
        }""")

    async def _fill_form(self, page: Page, username: str, email: str, password: str) -> None:
        await page.wait_for_selector("input:visible", timeout=15000)
        inputs = page.locator("input:visible")
        await inputs.nth(0).fill(username)
        await inputs.nth(1).fill(email)
        await inputs.nth(2).fill(password)
        await inputs.nth(3).fill(password)
```

- [ ] **Step 2: 提交**

```bash
git add src/sites/hvoy.py
git commit -m "refactor: rewrite hvoy registrar with click-based invite code extraction"
```

---

### Task 5: 重写 CunRegistrar（完整流程）

**Files:**
- Modify: `src/sites/cun.py`

- [ ] **Step 1: 重写 `CunRegistrar` 类**

完整流程：注册(填44Wb) → 滑块轮询 → 发验证码 → 验证码验证 → 创建账户 → 登录 → 滑块轮询 → 登录成功 → 钱包兑换 → 创建API密钥 → 复制密钥

```python
"""CUN.ai registration + login + wallet redeem + API key creation."""
import asyncio
import re

from patchright.async_api import BrowserContext, Page

from src.models import AccountInfo, RegistrationResult
from src.sites.base import HumanVerification


class CunRegistrar(HumanVerification):
    """CUN.ai full flow: register → verify → login → redeem → create API key"""

    REGISTER_URL = "https://www.cun.ai/sign-up"
    LOGIN_URL = "https://www.cun.ai/login"
    WALLET_URL = "https://www.cun.ai/wallet"

    async def register(
        self, context: BrowserContext, email_addr: str,
        username: str, password: str, gmail_api=None,
    ) -> RegistrationResult:
        """注册 CUN 账号。gmail_api 用于自动获取验证码。"""
        page = await context.new_page()
        try:
            await page.goto(self.REGISTER_URL, wait_until="networkidle")
            await page.wait_for_timeout(2000)
            await self._dismiss_popup(page)

            # 填写注册表单
            await self._fill_register_form(page, username, email_addr, password)

            # --- 滑块1（手动）---
            print("\n  *** 请拖滑块完成人机验证 (Alt+Tab 切到浏览器) ***")
            print("  *** 脚本轮询等待中...")
            await self._wait_for_slider(page)

            # 点击发送验证码
            send_btn = page.locator('button:has-text("发送验证码")')
            if await send_btn.is_enabled():
                await send_btn.click()
                await page.wait_for_timeout(2000)
            else:
                await send_btn.click(force=True)
                await page.wait_for_timeout(2000)

            # 从 Gmail API 获取验证码
            email_code = None
            if gmail_api:
                to_addr = email_addr
                print(f"  Waiting for verification code to {to_addr}...")
                email_code = gmail_api.wait_for_verification_code(
                    query=f"to:{to_addr}",
                    timeout=120,
                    poll_interval=5,
                )
            if not email_code:
                email_code = input("  >>> Enter verification code manually: ").strip()
            if not email_code:
                return RegistrationResult(site="cun", success=False, error="Email code not received")

            code_input = page.locator('input[placeholder*="验证码"]')
            await code_input.fill(email_code)

            # 勾选协议
            checkbox = page.locator('input[type="checkbox"]').first
            if not await checkbox.is_checked():
                await checkbox.check()

            # 创建账户
            submit_btn = page.locator('button:has-text("创建账户")')
            await submit_btn.click()
            await page.wait_for_timeout(5000)

            # 返回成功（此时页面会跳转到登录页）
            return RegistrationResult(
                site="cun", success=True,
                account=AccountInfo(site="cun", username=username,
                                    email=email_addr, password=password, verified=True),
            )
        except Exception as e:
            return RegistrationResult(site="cun", success=False, error=str(e))
        finally:
            await page.close()

    async def login(self, context: BrowserContext, username: str, password: str) -> bool:
        """CUN 登录（注册后跳转，会再次出现滑块）。返回登录是否成功。"""
        page = await context.new_page()
        try:
            await page.goto(self.LOGIN_URL, wait_until="networkidle")
            await page.wait_for_timeout(2000)

            # 填写用户名/邮箱 + 密码
            email_input = page.locator('input:visible').first
            await email_input.fill(username)

            pwd_input = page.locator('input[type="password"]')
            await pwd_input.fill(password)

            # 勾选协议
            checkbox = page.locator('input[type="checkbox"]').first
            if await checkbox.count() > 0 and not await checkbox.is_checked():
                await checkbox.check()

            # --- 滑块2（手动）---
            print("\n  *** 请拖滑块完成登录人机验证 ***")
            print("  *** 脚本轮询等待中...")
            await self._wait_for_slider_login(page)

            # 登录
            login_btn = page.locator('button:has-text("登录")')
            if await login_btn.count() == 0:
                login_btn = page.locator('button[type="submit"]')
            await login_btn.click()
            await page.wait_for_timeout(5000)

            success = "login" not in page.url.lower() and "sign-up" not in page.url.lower()
            print(f"  CUN login {'success' if success else 'failed'}")
            return success
        finally:
            await page.close()

    async def redeem_invite_code(self, page: Page, invite_code: str) -> bool:
        """在钱包页兑换邀请码。"""
        await page.goto(self.WALLET_URL, wait_until="networkidle")
        await page.wait_for_timeout(3000)

        # 点击"充值/卡密兑换"菜单
        redeem_menu = page.locator('a:has-text("充值/卡密兑换"), a:has-text("Redeem")')
        if await redeem_menu.count() > 0:
            await redeem_menu.click()
            await page.wait_for_timeout(2000)

        # 填入兑换码
        redeem_input = page.locator('input[placeholder*="兑换码"]')
        if await redeem_input.count() == 0:
            redeem_input = page.locator('input:visible').first
        await redeem_input.fill(invite_code)

        # 点击兑换
        redeem_btn = page.locator('button:has-text("兑换额度"), button:has-text("兑换")')
        await redeem_btn.click()
        await page.wait_for_timeout(3000)

        body = await page.inner_text("body")
        success = "成功" in body or "success" in body.lower()
        print(f"  Redeem {'success' if success else 'failed'}")
        return success

    async def create_api_key(self, page: Page) -> str | None:
        """创建 API 密钥并复制。返回密钥字符串。"""
        # 点击"API密钥"菜单
        api_menu = page.locator('a:has-text("API密钥")')
        if await api_menu.count() > 0:
            await api_menu.click()
            await page.wait_for_timeout(2000)

        # 点击"创建API密钥"按钮
        create_btn = page.locator('button:has-text("创建API密钥")')
        await create_btn.click()
        await page.wait_for_timeout(2000)

        # 名称输入：Claude Code
        name_input = page.locator('input[placeholder*="名称"], input:visible').first
        await name_input.fill("Claude Code")

        # 选择分组"default"
        group_btn = page.locator('button:has-text("选择一个分组"), button:has-text("Select")')
        if await group_btn.count() > 0:
            await group_btn.click()
            await page.wait_for_timeout(1000)
            default_option = page.locator('text=default').first
            if await default_option.count() > 0:
                await default_option.click()
                await page.wait_for_timeout(500)

        # 关闭无限配额（switch 默认为开 → 关闭）
        switch = page.locator('[role="switch"]')
        if await switch.count() > 0:
            checked = await switch.is_checked()
            if checked:
                await switch.click()
                await page.wait_for_timeout(500)

        # 输入额度 30
        amount_input = page.locator('input[type="number"], input[placeholder*="额度"]').first
        await amount_input.fill("30")

        # 保存
        save_btn = page.locator('button:has-text("保存更改"), button:has-text("Save")')
        await save_btn.click()
        await page.wait_for_timeout(3000)

        # 读取 API 密钥
        body = await page.inner_text("body")
        api_keys = re.findall(r'sk-[a-zA-Z0-9]{32,64}', body)
        if api_keys:
            return api_keys[0]

        # 尝试从表格中读取
        cells = page.locator('td, [class*="key"], [class*="api"]')
        cell_count = await cells.count()
        for i in range(cell_count):
            text = await cells.nth(i).inner_text()
            if text.startswith("sk-"):
                return text

        print("  Could not auto-read API key — please copy manually")
        return None

    async def logout(self, context: BrowserContext) -> None:
        """登出 CUN.ai，清除相关 cookies。"""
        await context.clear_cookies(urls=["https://www.cun.ai", "https://cun.ai"])
        print("  Cleared CUN.ai cookies")

    async def _wait_for_slider(self, page: Page, timeout: int = 180) -> bool:
        """轮询等待滑块完成（注册页"发送验证码"按钮变为可用）。"""
        send_btn = page.locator('button:has-text("发送验证码")')
        for i in range(timeout):
            if await send_btn.is_enabled():
                print("  Slider passed! Continuing...")
                return True
            if i % 10 == 0:
                print(f"  Waiting for slider... ({i}s)")
            await asyncio.sleep(1)
        print("  Slider timeout — you can still try to complete it")
        return False

    async def _wait_for_slider_login(self, page: Page, timeout: int = 180) -> bool:
        """轮询等待登录滑块完成（登录按钮变为可点击）。"""
        login_btn = page.locator('button:has-text("登录"), button[type="submit"]')
        for i in range(timeout):
            if await login_btn.is_enabled():
                print("  Login slider passed! Continuing...")
                return True
            if i % 10 == 0:
                print(f"  Waiting for login slider... ({i}s)")
            await asyncio.sleep(1)
        print("  Login slider timeout")
        return False

    async def _fill_register_form(self, page: Page, username: str, email: str, password: str) -> None:
        """填写 CUN 注册表单。"""
        await page.locator('input[placeholder*="用户名"]').fill(username)
        pwd_fields = page.locator('input[type="password"]')
        count = await pwd_fields.count()
        if count >= 2:
            await pwd_fields.nth(0).fill(password)
            await pwd_fields.nth(1).fill(password)
        else:
            await pwd_fields.first.fill(password)
            confirm = page.locator('input[placeholder*="确认"], input[placeholder*="Repeat"]')
            if await confirm.count() > 0:
                await confirm.first.fill(password)
        await page.locator('input[placeholder*="name@example.com"]').fill(email)

        # 邀请码统一填 44Wb
        invite_input = page.locator('input[placeholder*="邀请码"], input[placeholder*="Invite"]')
        if await invite_input.count() > 0:
            await invite_input.fill("44Wb")

    async def _dismiss_popup(self, page: Page) -> None:
        try:
            dismiss = page.locator('button:has-text("知道了")')
            if await dismiss.is_visible(timeout=3000):
                await dismiss.click()
                await page.wait_for_timeout(1000)
        except Exception:
            pass
        try:
            close = page.locator('[class*="close"], [class*="Close"], img[alt*="close"]')
            if await close.first.is_visible(timeout=1000):
                await close.first.click()
                await page.wait_for_timeout(1000)
        except Exception:
            pass
```

- [ ] **Step 2: 提交**

```bash
git add src/sites/cun.py
git commit -m "refactor: rewrite CUN registrar with full flow (register, login, redeem, create API key)"
```

---

### Task 6: 重写主入口 Orchestrator + CLI

**Files:**
- Modify: `src/main.py`

- [ ] **Step 1: 重写 `main.py`**

主要变更：
1. 修复 Chrome 启动：`channel="chrome"` → `executable_path`
2. 集成 `GmailApi` 替代 `GuerrillaMailChecker`
3. 9 步完整循环
4. 新增 `--proxy` CLI 参数，删除 `--gmail` / `--app-password`
5. 每轮清除 cookies + 关闭页面

```python
"""主控入口 + CLI + Orchestrator (v2 — Gmail API + 完整 9 步流程)"""
import argparse
import asyncio
from dataclasses import asdict

from patchright.async_api import async_playwright

from src.config import Settings
from src.email.gmail_api import GmailApi
from src.models import BatchResult
from src.sites.hvoy import HvoyRegistrar
from src.sites.cun import CunRegistrar
from src.storage import AccountStore, CodeStore
from src.utils import generate_username, generate_password, setup_logger


CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"


class Orchestrator:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.hvoy = HvoyRegistrar()
        self.cun = CunRegistrar()
        self.account_store = AccountStore(settings.storage.accounts_file)
        self.code_store = CodeStore(settings.storage.codes_file)
        self.logger = setup_logger("orchestrator")
        self.gmail = GmailApi(
            credentials_file=settings.gmail.credentials_file,
            token_pickle=settings.gmail.token_pickle,
            proxy_host=settings.gmail.proxy_host,
            proxy_port=settings.gmail.proxy_port,
        )
        self.base_email = settings.gmail.email_address

    def _make_alias(self, counter: int) -> str:
        user, domain = self.base_email.split("@")
        return f"{user}+hvoy{counter:03d}@{domain}"

    async def run(self, count: int, resume: bool, dry_run: bool,
                  chrome_profile: str = ""):
        settings = self.settings
        self.logger.info(f"start v2, count={count}")

        async with async_playwright() as p:
            if chrome_profile:
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=chrome_profile,
                    executable_path=CHROME_PATH,
                    headless=False,
                    viewport={
                        "width": settings.browser.viewport_width,
                        "height": settings.browser.viewport_height,
                    },
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-extensions",
                        "--disable-sync",
                        "--disable-dev-shm-usage",
                        "--max_old_space_size=512",
                    ],
                )
            else:
                browser = await p.chromium.launch(
                    executable_path=CHROME_PATH,
                    headless=False,
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
                )
                context = await browser.new_context(
                    viewport={
                        "width": settings.browser.viewport_width,
                        "height": settings.browser.viewport_height,
                    },
                    user_agent=settings.browser.user_agent,
                )
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => false });
                window.chrome = { runtime: {} };
            """)

            result = BatchResult(total=count, success=0, failed=0)

            try:
                if dry_run:
                    await self._dry_run(context)
                elif resume:
                    await self._run_resume(context, count, result)
                else:
                    await self._run_full(context, count, result)
            finally:
                if not chrome_profile:
                    await browser.close()
                else:
                    await context.close()

            self._print_summary(result)

    async def _dry_run(self, context):
        """干跑模式：打开各页面暂停，供调试 DOM 选择器。"""
        pages_to_check = [
            ("hvoy 注册页", "https://hvoy.ai/user/register"),
            ("hvoy 兑换码页 (需登录)", "https://hvoy.ai/free-tokens/invite-codes"),
            ("CUN 注册页", "https://www.cun.ai/sign-up"),
            ("CUN 登录页", "https://www.cun.ai/login"),
            ("CUN 钱包页 (需登录)", "https://www.cun.ai/wallet"),
        ]
        for name, url in pages_to_check:
            print(f"\n  >>> Opening {name}...")
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            input(f"\n  Check selectors for '{name}' then press Enter to close...")
            await page.close()

    async def _run_full(self, context, count: int, result: BatchResult):
        for i in range(count):
            idx = i + 1
            print(f"\n{'='*60}")
            print(f"  Account {idx}/{count}")
            print(f"{'='*60}")

            email_addr = self._make_alias(idx)
            username = generate_username()
            password = generate_password()
            self.logger.info(f"[{idx}] email={email_addr}, username={username}")
            print(f"  Email: {email_addr}")

            # === Step 1-2: hvoy 注册 ===
            print(f"\n  >>> [1/9] hvoy.ai register...")
            hvoy_result = await self.hvoy.register(context, email_addr, username, password)
            if not hvoy_result.success:
                self.logger.error(f"[{idx}] hvoy register failed: {hvoy_result.error}")
                result.failed += 1
                continue

            # === Step 3: Gmail API 收验证邮件 ===
            print(f"\n  >>> [2/9] Waiting for hvoy verification email...")
            verify_link = await self.gmail.wait_for_verification_link(
                query=f"from:noreply@hvoy.ai to:{email_addr}",
                domain="hvoy.ai",
                timeout=120,
            )
            if not verify_link:
                self.logger.error(f"[{idx}] hvoy verification email not found")
                result.failed += 1
                continue

            vp = await context.new_page()
            await vp.goto(verify_link, wait_until="domcontentloaded", timeout=20000)
            await vp.wait_for_timeout(3000)
            await vp.close()
            hvoy_result.account.verified = True
            print("  >>> hvoy email verified!")

            # === Step 4: hvoy 登录 ===
            print(f"\n  >>> [3/9] hvoy.ai login...")
            login_ok = await self.hvoy.login(context, username, password)
            if not login_ok:
                self.logger.error(f"[{idx}] hvoy login failed")
                result.failed += 1
                continue

            # === Step 5: hvoy 提取兑换码 ===
            print(f"\n  >>> [4/9] Extracting invite code...")
            invite_code = await self.hvoy.extract_invite_code(context)
            if not invite_code:
                self.logger.error(f"[{idx}] invite code not found")
                result.failed += 1
                continue
            self.code_store.save(asdict(invite_code))

            # === Step 6-7: CUN 注册 + 滑块1 ===
            print(f"\n  >>> [5/9] CUN.ai register (inviting code: 44Wb)...")
            cun_result = await self.cun.register(
                context, email_addr, username, password, gmail_api=self.gmail,
            )
            if not cun_result.success:
                self.logger.error(f"[{idx}] CUN register failed: {cun_result.error}")
                result.failed += 1
                continue

            # === Step 8: CUN 登录 + 滑块2 ===
            print(f"\n  >>> [6/9] CUN.ai login...")
            cun_login_ok = await self.cun.login(context, username, password)
            if not cun_login_ok:
                self.logger.error(f"[{idx}] CUN login failed")
                result.failed += 1
                continue

            # === Step 9: 兑换 + API密钥 ===
            page = await context.new_page()
            try:
                print(f"\n  >>> [7/9] Redeeming {invite_code.code}...")
                redeemed = await self.cun.redeem_invite_code(page, invite_code.code)
                if redeemed:
                    self.code_store.mark_used(invite_code.code, username)

                print(f"\n  >>> [8/9] Creating API key...")
                api_key = await self.cun.create_api_key(page)

                # 保存完整记录
                account = asdict(cun_result.account)
                account["invite_code"] = invite_code.code
                account["api_key"] = api_key or ""
                self.account_store.save(account)
            finally:
                await page.close()

            # === 清理 ===
            print(f"\n  >>> [9/9] Cleanup (logout + close pages)...")
            await self.hvoy.logout(context)
            await self.cun.logout(context)

            result.success += 1
            self.logger.info(f"[{idx}] done")

    async def _run_resume(self, context, count: int, result: BatchResult):
        """断点续跑：跳过已有 records 的 alias，从下一轮继续。"""
        existing = self.account_store.list_all()
        used_emails = {r.get("email") for r in existing}
        self.logger.info(f"Found {len(used_emails)} existing records, skipping them")
        starting_idx = len(used_emails) + 1
        self.logger.info(f"Starting from idx {starting_idx}")

        for i in range(starting_idx, count + 1):
            idx = i
            print(f"\n{'='*60}")
            print(f"  Account {idx}/{count}")
            print(f"{'='*60}")

            email_addr = self._make_alias(idx)
            if email_addr in used_emails:
                self.logger.info(f"  Skipping {email_addr} (already done)")
                continue

            username = generate_username()
            password = generate_password()
            print(f"  Email: {email_addr}")

            # 后续流程与 _run_full 一致
            # ...（为简洁起见，此处直接复用 _run_full 的单轮逻辑）
            # 实际实现时可将单轮抽象为 _run_one_cycle()
            print("  Resume mode running one cycle...")
            # TODO: 抽离单轮逻辑

    def _print_summary(self, result: BatchResult):
        if result.total == 0 and result.success == 0 and result.failed == 0:
            print("\n  DRY RUN complete: no registration performed.")
            return
        print(f"\n{'='*60}")
        print(f"  Done | Total: {result.total} | Success: {result.success} | Failed: {result.failed}")
        print(f"  Codes: {len(result.codes_obtained)}")
        print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="API Code Harvester v2")
    parser.add_argument("--count", type=int, default=1, help="Number of cycles to run")
    parser.add_argument("--resume", action="store_true", help="Resume from last completed cycle")
    parser.add_argument("--dry-run", action="store_true", help="Open pages for selector debugging")
    parser.add_argument("--chrome-profile", default="", help="Chrome user data dir")
    parser.add_argument("--email", default="", help="Gmail address (default: from config)")
    parser.add_argument("--proxy", default="", help="Proxy for Gmail API (default: from config)")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    settings = Settings.from_yaml(args.config)

    # CLI 覆盖配置
    if args.email:
        settings.gmail.email_address = args.email
    if args.proxy:
        host, _, port = args.proxy.partition(":")
        settings.gmail.proxy_host = host
        if port:
            settings.gmail.proxy_port = int(port)

    asyncio.run(Orchestrator(settings).run(
        count=args.count,
        resume=args.resume,
        dry_run=args.dry_run,
        chrome_profile=args.chrome_profile,
    ))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 提交**

```bash
git add src/main.py
git commit -m "refactor: rewrite orchestrator with Gmail API, Chrome fix, and 9-step loop"
```

---

### Task 7: 删除废弃文件

**Files:**
- Delete: `src/email/gmail_inbox.py`
- Delete: `src/email/guerrilla.py`
- Delete: `src/email/manual.py`

- [ ] **Step 1: 删除废弃文件**

```bash
git rm src/email/gmail_inbox.py src/email/guerrilla.py src/email/manual.py
git commit -m "chore: remove abandoned email modules (IMAP, Guerrilla, manual)"
```

---

### Task 8: 干跑验证选择器 + 端到端测试

**无代码变更，纯操作。**

- [ ] **Step 1: 运行 dry-run 模式通过浏览器验证所有 DOM 定位器**

```bash
D:\miniconda3\python.exe -m src.main --dry-run --chrome-profile "C:\Users\Jenhy\AppData\Local\Google\Chrome\User Data"
```

在每个页面检查：
- hvoy 注册表单输入框 → Turnstile → 提交按钮
- hvoy 登录页输入框 → Turnstile → 提交按钮
- hvoy 免费Token菜单 → 免费兑换码 → 领取按钮 → 确认领取弹窗
- CUN 注册表单 → "点击完成人机验证"按钮 → 发送验证码 → 验证码输入框 → 创建账户
- CUN 登录页 → 协议勾选框 → 登录按钮
- CUN 钱包页 → 兑换码输入框 → 兑换额度按钮
- CUN 创建API密钥弹窗 → 名称 → 分组选择 → 无限配额开关 → 额度输入 → 保存

如果定位器不准确，修改 `hvoy.py` 和 `cun.py` 中的选择器后重新 dry-run。

- [ ] **Step 2: 运行第一轮完整流程**

```bash
D:\miniconda3\python.exe -m src.main --count 1 --chrome-profile "C:\Users\Jenhy\AppData\Local\Google\Chrome\User Data"
```

观察脚本行为：
1. Chrome 成功启动（不再崩溃）
2. hvoy 注册成功 + Turnstile 自动过
3. Gmail API 成功获取验证链接
4. 浏览器打开验证链接成功
5. hvoy 登录成功
6. 提取邀请码成功
7. CUN 注册滑块出现 → 手动拖一下
8. Gmail API 获取验证码成功
9. 验证码自动填入 → CUN 注册成功
10. CUN 登录滑块出现 → 手动拖一下
11. CUN 登录成功 → 兑换成功 → API 密钥创建成功
12. `accounts.json` 中有完整记录

- [ ] **Step 3: 如果第一轮成功，运行少量轮次（如 3-5 轮）确认稳定性**

```bash
D:\miniconda3\python.exe -m src.main --count 5 --chrome-profile "C:\Users\Jenhy\AppData\Local\Google\Chrome\User Data"
```

- [ ] **Step 4: 验证 `accounts.json` 输出完整**

检查 `accounts.json`，每条记录应包含：username / email / password / invite_code / api_key。
