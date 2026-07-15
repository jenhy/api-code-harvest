"""Yahoo 邮箱读取器 — 通过 Playwright 检查收件箱

使用 Chrome Profile 中已登录的 Yahoo 会话读取验证邮件。
无需 Gmail 转发或 IMAP 配置。
"""
import asyncio
import re
import time

from patchright.async_api import BrowserContext, Page


class YahooMailReader:
    """通过 Playwright 读取 Yahoo 收件箱中的验证邮件。"""

    YAHOO_INBOX_URL = "https://mail.yahoo.com/n/folders/1"

    # ------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------

    async def wait_for_verification_link(
        self, context: BrowserContext, *, timeout: int = 120,
        poll_interval: int = 5,
    ) -> str | None:
        """等待来自 hvoy 的验证邮件，提取验证链接。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            page = await context.new_page()
            try:
                emails = await self._fetch_inbox(page)
                for email in emails:
                    if self._is_from_hvoy(email):
                        link = await self._extract_verification_link(page, email)
                        if link:
                            return link
            except Exception as e:
                print(f"  Yahoo inbox error: {e}")
            finally:
                await page.close()
            remaining = int(deadline - time.time())
            print(f"  Waiting for hvoy verification email... ({remaining}s left)")
            await asyncio.sleep(poll_interval)
        return None

    async def wait_for_verification_code(
        self, context: BrowserContext, *, timeout: int = 120,
        poll_interval: int = 5,
    ) -> str | None:
        """等待 CUN 验证码邮件，提取 6 位验证码。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            page = await context.new_page()
            try:
                emails = await self._fetch_inbox(page)
                for email in emails:
                    if "CUN" in email.get("subject", "") or "cun" in email.get("subject", "").lower():
                        code = await self._pick_verification_code(page, email)
                        if code:
                            return code
            except Exception as e:
                print(f"  Yahoo inbox error: {e}")
            finally:
                await page.close()
            remaining = int(deadline - time.time())
            print(f"  Waiting for CUN verification code... ({remaining}s left)")
            await asyncio.sleep(poll_interval)
        return None

    # ------------------------------------------------------------------
    # 收件箱扫描
    # ------------------------------------------------------------------

    async def _fetch_inbox(self, page: Page) -> list[dict]:
        """打开 Yahoo 收件箱，返回最近邮件列表。"""
        await page.goto(self.YAHOO_INBOX_URL, wait_until="domcontentloaded",
                        timeout=30000)
        await page.wait_for_timeout(3000)

        # 关闭 Yahoo Plus 弹窗（如果有）
        try:
            dismiss = page.locator('button:has-text("以后再说"), button:has-text("关闭")').first
            if await dismiss.is_visible(timeout=2000):
                await dismiss.click()
                await page.wait_for_timeout(1000)
        except Exception:
            pass

        # 读取邮件列表
        emails = []
        items = page.locator('a[href*="/n/folders/1/"], [role="link"]')
        count = await items.count()
        for i in range(min(count, 30)):
            try:
                href = await items.nth(i).get_attribute("href") or ""
                if "/n/folders/1/" not in href:
                    continue
                text = (await items.nth(i).inner_text()) or ""
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                sender = ""
                subject = ""
                for line in lines:
                    if "@" in line:
                        sender = line
                    elif not sender:
                        sender = line
                    else:
                        subject = line
                        break
                emails.append({"href": href, "sender": sender, "subject": subject, "text": text})
            except Exception:
                continue

        return emails

    # ------------------------------------------------------------------
    # 邮件筛选
    # ------------------------------------------------------------------

    @staticmethod
    def _is_from_hvoy(email: dict) -> bool:
        text = (email.get("text", "") + email.get("sender", "")).lower()
        return "hvoy" in text or "noreply@hvoy" in text

    # ------------------------------------------------------------------
    # 链接 & 验证码提取
    # ------------------------------------------------------------------

    async def _extract_verification_link(self, page: Page, email: dict) -> str | None:
        """点击邮件，从正文提取验证链接。"""
        try:
            email_link = page.locator(f'a[href="{email["href"]}"]').first
            if await email_link.count() == 0:
                email_link = page.locator(f'text="{email["subject"][:30]}"').first
            await email_link.click()
            await page.wait_for_timeout(3000)

            # 切换到 iframe（Yahoo 邮件内容在 iframe 中）
            try:
                body_frame = page.frame_locator("iframe").first
                body_text = await body_frame.locator("body").inner_text(timeout=5000)
            except Exception:
                body_text = await page.inner_text("body")

            # 提取链接
            links = re.findall(r'https://[^\s"\'<>]*verify-email[^\s"\'<>]*', body_text)
            for link in links:
                if "hvoy" in link.lower():
                    return link
            # 兜底：任何包含 hvoy 的链接
            all_links = re.findall(r'https?://[^\s"\'<>]+', body_text)
            for link in all_links:
                if "hvoy" in link.lower() and "verify" in link.lower():
                    return link
        except Exception as e:
            print(f"  Error extracting link: {e}")
        return None

    async def _pick_verification_code(self, page: Page, email: dict) -> str | None:
        """点击邮件，从正文提取 6 位验证码。"""
        try:
            email_link = page.locator(f'a[href="{email["href"]}"]').first
            if await email_link.count() == 0:
                email_link = page.locator(f'text="{email["subject"][:30]}"').first
            await email_link.click()
            await page.wait_for_timeout(3000)

            try:
                body_frame = page.frame_locator("iframe").first
                body_text = await body_frame.locator("body").inner_text(timeout=5000)
            except Exception:
                body_text = await page.inner_text("body")

            m = re.search(r'\b(\d{6})\b', body_text)
            return m.group(1) if m else None
        except Exception:
            return None
