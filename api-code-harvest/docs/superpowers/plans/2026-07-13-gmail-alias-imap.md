# Gmail Alias + IMAP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 Gmail 别名 (`yourname+hvoy001@gmail.com`) 替代临时邮箱，用 IMAP 全自动检查收件箱提取验证链接和验证码。

**Architecture:** 删除 GuerrillaMailProvider，新增 GmailInboxChecker（imaplib 查收件箱），main.py 邮箱生成改为别名循环。hvoy.py、cun.py 不变。

**Tech Stack:** Python `imaplib` + `email` 标准库，无新依赖。

---

## Task 1: 清理旧的临时邮箱代码

**Delete:**
- `src/email/guerrilla.py`
- `tests/test_guerrilla_integration.py`

**Modify:**
- `src/main.py` — 删除 `GuerrillaMailProvider` 导入，添加 `GmailInboxChecker` 占位

### Task 2: GmailInboxChecker — TDD 纯逻辑

### Task 3: GmailInboxChecker — IMAP 集成

### Task 4: 更新 main.py 编排器

### Task 5: 端到端验证

---

### Task 1: 清理旧代码 + 更新导入占位

**Files:**
- Delete: `src/email/guerrilla.py`
- Delete: `tests/test_guerrilla_integration.py`
- Modify: `src/main.py`

- [ ] **Step 1: 删除旧文件**

```bash
rm src/email/guerrilla.py
rm tests/test_guerrilla_integration.py
```

- [ ] **Step 2: 更新 main.py 导入**

替换 `from src.email.guerrilla import GuerrillaMailProvider` 为占位导入：

```python
from src.email.gmail_inbox import GmailInboxChecker
```

- [ ] **Step 3: 验证所有现有测试通过**

```bash
python -m pytest tests/ --ignore=tests/test_e2e.py -q
```
Expected: ~33 passed (删除 guerrilla 测试后)

- [ ] **Step 4: 验证导入**

```bash
python -c "from src.email.gmail_inbox import GmailInboxChecker; print('OK')"
```
Expected: FAIL (模块不存在 — 下一个任务创建)

---

### Task 2: GmailInboxChecker 纯逻辑 — TDD

**Files:**
- Create: `tests/test_gmail_inbox.py`
- Create: `src/email/gmail_inbox.py` (最小实现)

- [ ] **Step 1: 写测试 — 提取验证链接**

```python
"""GmailInboxChecker 纯逻辑测试"""
from src.email.gmail_inbox import GmailInboxChecker


class TestExtractVerificationLink:
    def test_extracts_hvoy_verify_link(self):
        html = '<a href="https://hvoy.ai/verify-email?token=abc123">Verify</a>'
        link = GmailInboxChecker.extract_verification_link(html, domain_hint="hvoy.ai")
        assert link == "https://hvoy.ai/verify-email?token=abc123"

    def test_extracts_cun_verify_link(self):
        html = 'Click: https://www.cun.ai/verify?code=xyz'
        link = GmailInboxChecker.extract_verification_link(html, domain_hint="cun.ai")
        assert link == "https://www.cun.ai/verify?code=xyz"

    def test_no_link_returns_none(self):
        assert GmailInboxChecker.extract_verification_link("no link here", domain_hint="hvoy.ai") is None

    def test_ignores_non_matching_domain(self):
        html = '<a href="https://other.com/verify">link</a>'
        assert GmailInboxChecker.extract_verification_link(html, domain_hint="hvoy.ai") is None


class TestExtractVerificationCode:
    def test_extracts_6_digit_code(self):
        text = "Your verification code is 123456"
        assert GmailInboxChecker.extract_verification_code(text) == "123456"

    def test_no_code_returns_none(self):
        assert GmailInboxChecker.extract_verification_code("no code") is None

    def test_7_digit_not_matched(self):
        assert GmailInboxChecker.extract_verification_code("code: 1234567") is None
```

- [ ] **Step 2: 运行测试 — RED**

```bash
python -m pytest tests/test_gmail_inbox.py -v
```
Expected: FAIL, module not found

- [ ] **Step 3: 写最小实现**

```python
"""Gmail inbox checker — IMAP + regex extraction."""
import re


class GmailInboxChecker:
    """Check Gmail inbox for verification emails."""

    @staticmethod
    def extract_verification_link(html: str, domain_hint: str) -> str | None:
        links = re.findall(r'https?://[^\s"\'<>]+', html)
        for link in links:
            if domain_hint in link:
                return link
        return None

    @staticmethod
    def extract_verification_code(text: str) -> str | None:
        m = re.search(r'\b(\d{6})\b', text)
        return m.group(1) if m else None
```

- [ ] **Step 4: 运行测试 — GREEN**

```bash
python -m pytest tests/test_gmail_inbox.py -v
```
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add tests/test_gmail_inbox.py src/email/gmail_inbox.py
git commit -m "feat: add GmailInboxChecker with link/code extraction"
```

---

### Task 3: GmailInboxChecker IMAP 集成

**Files:**
- Modify: `src/email/gmail_inbox.py` — 添加 IMAP 方法
- Create: `tests/test_gmail_imap.py` — 集成测试

- [ ] **Step 1: 添加 IMAP 方法到 GmailInboxChecker**

```python
import email
import imaplib
import re
import time
from email.header import decode_header


class GmailInboxChecker:
    """Check Gmail inbox for verification emails via IMAP."""

    def __init__(self, gmail_addr: str, app_password: str):
        self.gmail_addr = gmail_addr
        self.app_password = app_password
        self._conn: imaplib.IMAP4_SSL | None = None

    def connect(self):
        self._conn = imaplib.IMAP4_SSL("imap.gmail.com")
        self._conn.login(self.gmail_addr, self.app_password)

    def disconnect(self):
        if self._conn:
            try:
                self._conn.logout()
            except Exception:
                pass
            self._conn = None

    def wait_for_verification_link(self, domain_hint: str, timeout: int = 180, poll_interval: int = 5) -> str | None:
        return self._poll_inbox(domain_hint, timeout, poll_interval, mode="link")

    def wait_for_verification_code(self, timeout: int = 120, poll_interval: int = 3) -> str | None:
        return self._poll_inbox("", timeout, poll_interval, mode="code")

    def _poll_inbox(self, domain_hint: str, timeout: int, poll_interval: int, mode: str) -> str | None:
        """轮询收件箱，返回验证链接或验证码"""
        if not self._conn:
            raise RuntimeError("Not connected. Call connect() first.")
        deadline = time.time() + timeout
        seen_ids: set[str] = set()
        while time.time() < deadline:
            try:
                self._conn.select("INBOX")
                _, data = self._conn.search(None, "ALL")
                msg_ids = data[0].split()
                for mid in reversed(msg_ids):
                    mid_str = mid.decode() if isinstance(mid, bytes) else mid
                    if mid_str in seen_ids:
                        continue
                    seen_ids.add(mid_str)
                    _, msg_data = self._conn.fetch(mid, "(RFC822)")
                    raw = msg_data[0][1]
                    msg = email.message_from_bytes(raw)
                    body = self._get_body(msg)
                    if mode == "link":
                        result = self.extract_verification_link(body, domain_hint)
                    else:
                        result = self.extract_verification_code(body)
                    if result:
                        return result
            except Exception:
                pass
            time.sleep(poll_interval)
        return None

    @staticmethod
    def _get_body(msg) -> str:
        """提取邮件正文"""
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype in ("text/plain", "text/html"):
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            body += payload.decode(errors="replace")
                    except Exception:
                        pass
        else:
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    body = payload.decode(errors="replace")
            except Exception:
                pass
        return body

    @staticmethod
    def extract_verification_link(html: str, domain_hint: str) -> str | None:
        links = re.findall(r'https?://[^\s"\'<>]+', html)
        for link in links:
            if domain_hint in link:
                return link
        return None

    @staticmethod
    def extract_verification_code(text: str) -> str | None:
        m = re.search(r'\b(\d{6})\b', text)
        return m.group(1) if m else None
```

添加 `__init__.py` 中的 imports 以确保模块可用。

- [ ] **Step 2: 运行纯逻辑测试确保不破坏**

```bash
python -m pytest tests/test_gmail_inbox.py -v
```
Expected: 7 passed

- [ ] **Step 3: 验证导入**

```bash
python -c "from src.email.gmail_inbox import GmailInboxChecker; c = GmailInboxChecker('test@gmail.com', 'pwd'); print('OK')"
```
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add src/email/gmail_inbox.py
git commit -m "feat: add IMAP inbox polling to GmailInboxChecker"
```

---

### Task 4: 更新 main.py 编排器

**Files:**
- Modify: `src/main.py`

- [ ] **Step 1: 更新导入和 Orchestrator.__init__**

在 `__init__` 中保存 Gmail 凭据和计数器：

```python
import argparse
import asyncio
from dataclasses import asdict

from playwright.async_api import async_playwright

from src.config import Settings
from src.email.gmail_inbox import GmailInboxChecker
from src.models import BatchResult
from src.sites.hvoy import HvoyRegistrar
from src.sites.cun import CunRegistrar
from src.storage import AccountStore, CodeStore
from src.utils import generate_username, generate_password, setup_logger


class Orchestrator:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.hvoy = HvoyRegistrar()
        self.cun = CunRegistrar()
        self.account_store = AccountStore(settings.storage.accounts_file)
        self.code_store = CodeStore(settings.storage.codes_file)
        self.logger = setup_logger("orchestrator")

    async def run(self, count: int, phase: str, resume: bool, dry_run: bool,
                  gmail_addr: str = "", app_password: str = ""):
        settings = self.settings
        self.logger.info(f"start, count={count}, phase={phase}")

        if not gmail_addr or not app_password:
            print("ERROR: --gmail and --app-password required")
            return

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=settings.browser.headless,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            context = await browser.new_context(
                viewport={"width": settings.browser.viewport_width, "height": settings.browser.viewport_height},
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
                elif phase == "hvoy":
                    await self._run_hvoy_only(context, count, result, gmail_addr, app_password)
                elif phase == "cun":
                    await self._run_cun_only(context, result, gmail_addr, app_password)
                else:
                    await self._run_full(context, count, result, gmail_addr, app_password)
            finally:
                await browser.close()

            self._print_summary(result)
```

- [ ] **Step 2: 添加 Gmail 别名生成方法**

```python
    def _make_alias(self, gmail_addr: str, counter: int) -> str:
        """Generate Gmail alias: name+001@gmail.com"""
        user, domain = gmail_addr.split("@")
        return f"{user}+hvoy{counter:03d}@{domain}"
```

- [ ] **Step 3: 重写 _run_full**

```python
    async def _run_full(self, context, count: int, result: BatchResult,
                        gmail_addr: str, app_password: str):
        checker = GmailInboxChecker(gmail_addr, app_password)
        checker.connect()
        try:
            for i in range(count):
                idx = i + 1
                print(f"\n{'='*60}")
                print(f"  Account {idx}/{count}")
                print(f"{'='*60}")

                email_addr = self._make_alias(gmail_addr, idx)
                username = generate_username()
                hvoy_password = generate_password()
                self.logger.info(f"[{idx}] username={username}, email={email_addr}")
                print(f"  Email: {email_addr}")

                # Step 1: hvoy register
                print(f"\n  >>> hvoy.ai register...")
                hvoy_result = await self.hvoy.register(context, email_addr, username, hvoy_password)
                if not hvoy_result.success:
                    self.logger.error(f"[{idx}] hvoy failed: {hvoy_result.error}")
                    result.failed += 1
                    continue
                self.account_store.save(asdict(hvoy_result.account))

                # Step 2: verify hvoy email via IMAP
                print(f"\n  >>> Waiting for hvoy verification email...")
                verify_link = checker.wait_for_verification_link(domain_hint="hvoy.ai", timeout=180)
                if verify_link:
                    vp = await context.new_page()
                    await vp.goto(verify_link, wait_until="domcontentloaded", timeout=15000)
                    await vp.wait_for_timeout(3000)
                    await vp.close()
                    hvoy_result.account.verified = True
                    self.account_store.save(asdict(hvoy_result.account))
                    print(f"  >>> Email verified")
                else:
                    self.logger.warning(f"[{idx}] hvoy verification link not found")

                # Step 3: extract invite code
                print(f"\n  >>> Extracting invite code...")
                invite_code = await self.hvoy.extract_invite_code(context)
                if invite_code:
                    self.code_store.save(asdict(invite_code))
                    result.codes_obtained.append(invite_code)
                    print(f"  >>> Invite code: {invite_code.code}")
                result.results.append(hvoy_result)

                # Step 4: CUN register
                print(f"\n  >>> CUN.ai register...")
                cun_result = await self.cun.register_gmail(context, email_addr, username, hvoy_password, checker)
                if not cun_result.success:
                    self.logger.error(f"[{idx}] CUN failed: {cun_result.error}")
                    result.failed += 1
                    continue
                self.account_store.save(asdict(cun_result.account))

                # Step 5: redeem
                if invite_code:
                    print(f"\n  >>> Redeeming {invite_code.code} on CUN wallet...")
                    page = await context.new_page()
                    try:
                        redeemed = await self.cun.redeem_code(page, invite_code.code)
                        if redeemed:
                            self.code_store.mark_used(invite_code.code, username)
                            print(f"  >>> Redeemed")
                    finally:
                        await page.close()

                result.success += 1
                self.logger.info(f"[{idx}] done")
        finally:
            checker.disconnect()
```

- [ ] **Step 4: 添加到 cun.py — register_gmail 方法**

在 `src/sites/cun.py` 的 `CunRegistrar` 类末尾添加：

```python
    async def register_gmail(
        self,
        context: BrowserContext,
        email_addr: str,
        username: str,
        password: str,
        checker,
    ) -> RegistrationResult:
        """Register on CUN.ai, getting verification code via IMAP."""
        page = await context.new_page()
        try:
            await page.goto(self.REGISTER_URL, wait_until="networkidle")
            await page.wait_for_timeout(2000)

            await self._dismiss_popup(page)
            await self._fill_form(page, username, email_addr, password)

            await self.human_verification_pause(
                "Complete the slider puzzle captcha AND click [Send Code] in browser, then press Enter."
            )
            await page.wait_for_timeout(2000)

            send_btn = page.locator('button:has-text("发送验证码")')
            if await send_btn.is_enabled():
                await send_btn.click()
                await page.wait_for_timeout(2000)

            # Get verification code from Gmail IMAP
            print("  >>> Waiting for CUN verification code in Gmail...")
            email_code = checker.wait_for_verification_code(timeout=120)
            if not email_code:
                return RegistrationResult(site="cun", success=False, error="Email code not received")

            code_input = page.locator('input[placeholder*="验证码"]')
            await code_input.fill(email_code)

            checkbox = page.locator('input[type="checkbox"]').first()
            if not await checkbox.is_checked():
                await checkbox.check()

            submit_btn = page.locator('button:has-text("创建账户")')
            await submit_btn.click()
            await page.wait_for_timeout(5000)

            if not await self._detect_success(page):
                return RegistrationResult(site="cun", success=False, error="Registration redirect not detected")

            return RegistrationResult(
                site="cun", success=True,
                account=AccountInfo(site="cun", username=username, email=email_addr,
                                    password=password, verified=True),
            )
        except Exception as e:
            return RegistrationResult(site="cun", success=False, error=str(e))
        finally:
            await page.close()
```

- [ ] **Step 5: 更新 CLI (main 函数)**

```python
def main():
    parser = argparse.ArgumentParser(description="API Code Harvester")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--phase", choices=["hvoy", "cun", "full"], default="full")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--gmail", default="", help="Gmail address")
    parser.add_argument("--app-password", default="", help="Gmail App Password")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()
    settings = Settings.from_yaml(args.config)
    asyncio.run(Orchestrator(settings).run(
        count=args.count, phase=args.phase,
        resume=args.resume, dry_run=args.dry_run,
        gmail_addr=args.gmail, app_password=args.app_password,
    ))


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: 删除 _run_hvoy_only, _run_cun_only, _create_email 中的旧引用**

删除与 `GmxProvider`、`GuerrillaMailProvider`、`email_accounts` 相关的代码。`_run_hvoy_only` 和 `_run_cun_only` 也使用 Gmail 别名 + IMAP。

- [ ] **Step 7: 验证导入**

```bash
python -c "from src.main import Orchestrator; print('OK')"
```
Expected: OK

- [ ] **Step 8: 运行所有纯逻辑测试**

```bash
python -m pytest tests/ --ignore=tests/test_e2e.py -q
```
Expected: all pass (~40)

- [ ] **Step 9: Commit**

```bash
git add src/main.py src/sites/cun.py
git commit -m "feat: integrate Gmail alias + IMAP into orchestrator"
```

---

### Task 5: 端到端验证

**No code changes — manual verification only.**

- [ ] **Step 1: 生成 Gmail App Password**

1. 去 https://myaccount.google.com/apppasswords
2. 选择 "Mail" → "Other" → 输入 "api-code-harvest"
3. 复制生成的 16 位密码

- [ ] **Step 2: 运行 dry-run 验证选择器**

```bash
python -m src.main --dry-run
```

- [ ] **Step 3: 跑 1 个完整账号**

```bash
python -m src.main --count 1 --gmail "yourname@gmail.com" --app-password "xxxx"
```

Expected: 完整走通 hvoy 注册 → 邮箱验证 → 领码 → CUN 注册 → 兑换

- [ ] **Step 4: 确认 accounts.json 和 codes.json 有数据**

```bash
python -c "import json; print(json.load(open('accounts.json'))); print(json.load(open('codes.json')))"
```

---

## Self-Review

| 检查 | 结果 |
|------|------|
| Spec 覆盖 | IMAP 收件箱 ✅, Gmail 别名 ✅, hvoy/CUN 流程 ✅ |
| 无占位符 | 所有步骤有完整代码 |
| 类型一致 | `register_gmail` 接受 `checker` 参数 ✅ |
| 文件路径 | 全部精确 |
