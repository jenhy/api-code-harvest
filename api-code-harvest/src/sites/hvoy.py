"""hvoy.ai registration + login + invite code extraction + logout.

使用 Chrome Profile 自然过 Cloudflare Turnstile。
invite code 提取改为点击式 UI 交互（领取→确认领取→提取）。
"""
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

    # ------------------------------------------------------------------
    # 注册
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # 登录
    # ------------------------------------------------------------------

    async def login(self, context: BrowserContext, username: str, password: str) -> bool:
        """登录 hvoy.ai。返回 True 表示登录成功。"""
        page = await context.new_page()
        try:
            await page.goto(self.LOGIN_URL, wait_until="domcontentloaded")
            print("  Waiting for Turnstile on login page...")
            await self._wait_for_turnstile(page, timeout=60)

            # 填写表单
            inputs = page.locator("input:visible")
            count = await inputs.count()
            if count >= 2:
                await inputs.nth(0).fill(username)
                await inputs.nth(1).fill(password)
            else:
                await inputs.first.fill(username)
                pwd = page.locator('input[type="password"]')
                await pwd.fill(password)

            await page.locator('button[type="submit"]').click()
            await page.wait_for_timeout(3000)

            success = "login" not in page.url.lower()
            print(f"  Login {'success' if success else 'failed'}")
            return success
        finally:
            await page.close()

    # ------------------------------------------------------------------
    # 提取兑换码（点击式 UI 交互）
    # ------------------------------------------------------------------

    async def extract_invite_code(self, context: BrowserContext) -> InviteCode | None:
        """通过点击 UI 交互领取邀请码并提取 32 位兑换码。

        流程：打开兑换码页 → 点击"领取" → 点击"确认领取" → 提取弹窗中的兑换码。
        """
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

            # 点击"确认领取"
            confirm_btn = page.locator('button:has-text("确认领取")')
            if await confirm_btn.count() == 0:
                confirm_btn = page.locator('text=确认领取').first
            await confirm_btn.click()
            await page.wait_for_timeout(1000)

            # 从页面提取 32 位十六进制兑换码
            body = await page.inner_text("body")
            codes = re.findall(r'[a-f0-9]{32}', body)
            if codes:
                code_str = codes[0]
                print(f"  >>> Invite code: {code_str}")
                return InviteCode(code=code_str, source="hvoy_free_token")

            # 兜底：提取任意 16-32 位字母数字
            content = await page.content()
            codes = re.findall(r'[A-Za-z0-9]{16,32}', content)
            if codes:
                print(f"  >>> Invite code (fallback): {codes[0]}")
                return InviteCode(code=codes[0], source="hvoy_free_token")

            return None
        finally:
            await page.close()

    # ------------------------------------------------------------------
    # 跳转到 CUN
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # 登出 & 清理
    # ------------------------------------------------------------------

    async def logout(self, context: BrowserContext) -> None:
        """登出 hvoy.ai，清除相关 cookies。"""
        await context.clear_cookies(urls=["https://hvoy.ai", "https://www.hvoy.ai"])
        print("  Cleared hvoy.ai cookies")

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    async def _wait_for_turnstile(self, page: Page, timeout: int = 120) -> bool:
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
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

    @staticmethod
    async def _detect_turnstile_token(page: Page) -> bool:
        return await page.evaluate("""() => {
            const el = document.querySelector('[name="cf-turnstile-response"]');
            return el && el.value && el.value.length > 10;
        }""")

    @staticmethod
    async def _fill_form(page: Page, username: str, email: str, password: str) -> None:
        await page.wait_for_selector("input:visible", timeout=15000)
        inputs = page.locator("input:visible")
        await inputs.nth(0).fill(username)
        await inputs.nth(1).fill(email)
        await inputs.nth(2).fill(password)
        await inputs.nth(3).fill(password)
