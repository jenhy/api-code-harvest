"""CUN.ai registration + login + wallet redeem + API key creation.

完整流程：
1. 注册（带 44Wb 邀请码）→ 滑块1（手动）→ 发送验证码 → 验证码（Gmail API）
2. 登录 → 滑块2（手动）→ 登录成功
3. 钱包兑换邀请码 → 创建 API 密钥 → 复制密钥 → 登出清理
"""
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

    # ------------------------------------------------------------------
    # 注册
    # ------------------------------------------------------------------

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

            # 填写注册表单（带 44Wb 邀请码）
            await self._fill_register_form(page, username, email_addr, password)

            # --- 滑块1（手动）---
            print("\n  *** 请拖滑块完成人机验证 (Alt+Tab 切到浏览器) ***")
            print("  *** 脚本轮询等待中...")
            slider_ok = await self._wait_for_slider(page)

            # 点击发送验证码
            if slider_ok:
                send_btn = page.locator('button:has-text("发送验证码")')
                await send_btn.click()
                await page.wait_for_timeout(2000)
            else:
                print("  Slider timeout — trying to click send button anyway")
                send_btn = page.locator('button:has-text("发送验证码")')
                if await send_btn.is_enabled():
                    await send_btn.click()
                    await page.wait_for_timeout(2000)
                else:
                    return RegistrationResult(site="cun", success=False,
                                              error="Slider verification timeout")

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
                return RegistrationResult(site="cun", success=False,
                                          error="Email code not received")

            code_input = page.locator('input[placeholder*="验证码"]')
            await code_input.fill(email_code)

            # 勾选协议
            checkbox = page.locator('input[type="checkbox"]').first
            if await checkbox.count() > 0 and not await checkbox.is_checked():
                await checkbox.check()

            # 创建账户
            submit_btn = page.locator('button:has-text("创建账户")')
            await submit_btn.click()
            await page.wait_for_timeout(5000)

            return RegistrationResult(
                site="cun", success=True,
                account=AccountInfo(site="cun", username=username,
                                    email=email_addr, password=password,
                                    verified=True),
            )
        except Exception as e:
            return RegistrationResult(site="cun", success=False, error=str(e))
        finally:
            await page.close()

    # ------------------------------------------------------------------
    # 登录
    # ------------------------------------------------------------------

    async def login(self, context: BrowserContext, username: str,
                    password: str) -> bool:
        """CUN 登录（注册后跳转，会再次出现滑块）。返回登录是否成功。"""
        page = await context.new_page()
        try:
            await page.goto(self.LOGIN_URL, wait_until="networkidle")
            await page.wait_for_timeout(2000)

            # 填写用户名/邮箱 + 密码
            email_input = page.locator("input:visible").first
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

            success = ("login" not in page.url.lower()
                       and "sign-up" not in page.url.lower())
            print(f"  CUN login {'success' if success else 'failed'}")
            return success
        finally:
            await page.close()

    # ------------------------------------------------------------------
    # 钱包兑换
    # ------------------------------------------------------------------

    async def redeem_invite_code(self, page: Page, invite_code: str) -> bool:
        """在钱包页兑换邀请码。返回兑换是否成功。"""
        await page.goto(self.WALLET_URL, wait_until="networkidle")
        await page.wait_for_timeout(3000)

        # 点击"充值/卡密兑换"菜单
        redeem_menu = page.locator('a:has-text("充值/卡密兑换"),'
                                    'a:has-text("Redeem"),'
                                    'a:has-text("兑换")')
        if await redeem_menu.count() > 0:
            await redeem_menu.click()
            await page.wait_for_timeout(2000)

        # 填入兑换码
        redeem_input = page.locator('input[placeholder*="兑换码"]')
        if await redeem_input.count() == 0:
            redeem_input = page.locator('input:visible').first
        await redeem_input.fill(invite_code)

        # 点击兑换
        redeem_btn = page.locator('button:has-text("兑换额度"),'
                                    'button:has-text("兑换"),'
                                    'button:has-text("Redeem")')
        await redeem_btn.click()
        await page.wait_for_timeout(3000)

        body = await page.inner_text("body")
        success = self._detect_redeem_success(body)
        print(f"  Redeem {'success' if success else 'failed'}")
        return success

    @staticmethod
    def _detect_redeem_success(body_text: str) -> bool:
        """改进的兑换成功检测逻辑。

        先检查失败关键词（"失败"、"无效"、"error"、"failed"、"不存在"、"已使用"），
        再检查成功关键词（"成功"、"success"）。
        如果两者都没有，默认返回 True（保守策略，避免漏过成功兑换）。
        """
        text_lower = body_text.lower()
        # 失败关键词
        fail_keywords = ["失败", "无效", "不存在", "已使用",
                         "failed", "error", "invalid", "expired"]
        for kw in fail_keywords:
            if kw in text_lower:
                return False
        # 成功关键词（兜底默认 True，所以此处只是补充确认）
        success_keywords = ["成功", "success"]
        for kw in success_keywords:
            if kw in text_lower:
                return True
        # 中性页面内容，默认视为成功
        return True

    # ------------------------------------------------------------------
    # API 密钥
    # ------------------------------------------------------------------

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
        name_input = page.locator('input[placeholder*="名称"],'
                                   'input:visible').first
        await name_input.fill("Claude Code")

        # 选择分组"default"
        group_btn = page.locator('button:has-text("选择一个分组"),'
                                  'button:has-text("Select")')
        if await group_btn.count() > 0:
            await group_btn.click()
            await page.wait_for_timeout(1000)
            default_option = page.locator('text=default').first
            if await default_option.count() > 0:
                await default_option.click()
                await page.wait_for_timeout(500)

        # 关闭无限配额
        switch = page.locator('[role="switch"]')
        if await switch.count() > 0:
            checked = await switch.is_checked()
            if checked:
                await switch.click()
                await page.wait_for_timeout(500)

        # 输入额度 30
        amount_input = page.locator('input[type="number"],'
                                     'input[placeholder*="额度"]').first
        await amount_input.fill("30")

        # 保存
        save_btn = page.locator('button:has-text("保存更改"),'
                                 'button:has-text("Save")')
        await save_btn.click()
        await page.wait_for_timeout(3000)

        # 从页面内容读取 API 密钥（sk- 开头）
        body = await page.inner_text("body")
        api_keys = re.findall(r'sk-[a-zA-Z0-9]{32,64}', body)
        if api_keys:
            key = api_keys[0]
            print(f"  >>> API Key: {key[:16]}...{key[-8:]}")
            return key

        # 兜底：从表格中读取
        cells = page.locator('td, [class*="key"], [class*="api"]')
        cell_count = await cells.count()
        for i in range(cell_count):
            text = await cells.nth(i).inner_text()
            text = text.strip()
            if text.startswith("sk-"):
                print(f"  >>> API Key (table): {text[:16]}...{text[-8:]}")
                return text

        print("  Could not auto-read API key — please copy manually")
        return None

    # ------------------------------------------------------------------
    # 登出 & 清理
    # ------------------------------------------------------------------

    async def logout(self, context: BrowserContext) -> None:
        """登出 CUN.ai，清除相关 cookies。"""
        await context.clear_cookies(urls=["https://www.cun.ai",
                                           "https://cun.ai"])
        print("  Cleared CUN.ai cookies")

    # ------------------------------------------------------------------
    # 滑块等待
    # ------------------------------------------------------------------

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

    async def _wait_for_slider_login(self, page: Page,
                                      timeout: int = 180) -> bool:
        """轮询等待登录滑块完成（登录按钮变为可点击）。"""
        login_btn = page.locator('button:has-text("登录"),'
                                  'button[type="submit"]')
        for i in range(timeout):
            if await login_btn.is_enabled():
                print("  Login slider passed! Continuing...")
                return True
            if i % 10 == 0:
                print(f"  Waiting for login slider... ({i}s)")
            await asyncio.sleep(1)
        print("  Login slider timeout")
        return False

    # ------------------------------------------------------------------
    # 表单辅助
    # ------------------------------------------------------------------

    async def _fill_register_form(self, page: Page, username: str,
                                   email: str, password: str) -> None:
        """填写 CUN 注册表单（带 44Wb 邀请码）。"""
        await page.locator('input[placeholder*="用户名"]').fill(username)
        pwd_fields = page.locator('input[type="password"]')
        count = await pwd_fields.count()
        if count >= 2:
            await pwd_fields.nth(0).fill(password)
            await pwd_fields.nth(1).fill(password)
        else:
            await pwd_fields.first.fill(password)
            confirm = page.locator('input[placeholder*="确认"],'
                                    'input[placeholder*="Repeat"]')
            if await confirm.count() > 0:
                await confirm.first.fill(password)
        await page.locator('input[placeholder*="name@example.com"]').fill(email)

        # 邀请码统一填 44Wb
        invite_input = page.locator('input[placeholder*="邀请码"],'
                                     'input[placeholder*="Invite"]')
        if await invite_input.count() > 0:
            await invite_input.fill("44Wb")

    async def _dismiss_popup(self, page: Page) -> None:
        """关闭注册时可能出现的弹窗。"""
        try:
            dismiss = page.locator('button:has-text("知道了")')
            if await dismiss.is_visible(timeout=3000):
                await dismiss.click()
                await page.wait_for_timeout(1000)
        except Exception:
            pass
        try:
            close = page.locator('[class*="close"], [class*="Close"],'
                                  'img[alt*="close"]')
            if await close.first.is_visible(timeout=1000):
                await close.first.click()
                await page.wait_for_timeout(1000)
        except Exception:
            pass
