"""主控入口 + CLI + Orchestrator (v2 — Gmail API + 完整 9 步流程)

修复：
- chrome launch: channel="chrome" → executable_path
- Gmail API 替代 GuerrillaMail / IMAP
- 新增 --proxy / --email CLI 参数
- 移除 --phase / --gmail / --app-password
- 每轮清理 cookies
"""
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
        name, domain = self.base_email.split("@")
        return f"{name}+hvoy{counter:03d}@{domain}"

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
                    args=["--disable-blink-features=AutomationControlled",
                          "--no-sandbox"],
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

    # ------------------------------------------------------------------
    # 干跑模式
    # ------------------------------------------------------------------

    async def _dry_run(self, context):
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

    # ------------------------------------------------------------------
    # 完整 9 步循环
    # ------------------------------------------------------------------

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
            hvoy_result = await self.hvoy.register(
                context, email_addr, username, password)
            if not hvoy_result.success:
                self.logger.error(
                    f"[{idx}] hvoy register failed: {hvoy_result.error}")
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
            await vp.goto(verify_link, wait_until="domcontentloaded",
                          timeout=20000)
            await vp.wait_for_timeout(3000)
            # 点击"去登录"按钮确认邮箱验证
            go_login = vp.locator('button:has-text("去登录"), a:has-text("去登录")')
            if await go_login.count() > 0:
                await go_login.click()
                await vp.wait_for_timeout(2000)
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
            result.codes_obtained.append(invite_code)

            # === Step 6-7: CUN 注册 + 滑块1 ===
            print(f"\n  >>> [5/9] CUN.ai register (invite: 44Wb)...")
            cun_result = await self.cun.register(
                context, email_addr, username, password, gmail_api=self.gmail,
            )
            if not cun_result.success:
                self.logger.error(
                    f"[{idx}] CUN register failed: {cun_result.error}")
                result.failed += 1
                continue

            # === Step 8: CUN 登录 + 滑块2 ===
            print(f"\n  >>> [6/9] CUN.ai login...")
            cun_login_ok = await self.cun.login(context, username, password)
            if not cun_login_ok:
                self.logger.error(f"[{idx}] CUN login failed")
                result.failed += 1
                continue

            # === Step 9: 兑换 + API 密钥 ===
            page = await context.new_page()
            try:
                print(f"\n  >>> [7/9] Redeeming {invite_code.code}...")
                redeemed = await self.cun.redeem_invite_code(
                    page, invite_code.code)
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
            print(f"\n  >>> [9/9] Cleanup...")
            await self.hvoy.logout(context)
            await self.cun.logout(context)

            result.success += 1
            self.logger.info(f"[{idx}] done")

    # ------------------------------------------------------------------
    # 断点续跑
    # ------------------------------------------------------------------

    async def _run_resume(self, context, count: int, result: BatchResult):
        existing = self.account_store.list_all()
        used_emails = {r.get("email") for r in existing}
        self.logger.info(f"Found {len(used_emails)} existing records, "
                         f"skipping them")
        self.logger.info(f"Starting fresh rounds from next index")

        for idx in range(1, count + 1):
            email_addr = self._make_alias(idx)
            if email_addr in used_emails:
                self.logger.info(f"  Skipping {email_addr} (already done)")
                continue

            print(f"\n{'='*60}")
            print(f"  Account {idx}/{count}")
            print(f"{'='*60}")

            username = generate_username()
            password = generate_password()
            print(f"  Email: {email_addr}")

            # 复用 _run_full 的单轮逻辑（与完整流程一致）
            await self._run_one_cycle(
                context, idx, count, email_addr, username, password, result)

    async def _run_one_cycle(self, context, idx: int, count: int,
                              email_addr: str, username: str,
                              password: str, result: BatchResult):
        """单轮完整流程，供 resume 复用。"""
        print(f"\n  >>> [1/9] hvoy.ai register...")
        hvoy_result = await self.hvoy.register(
            context, email_addr, username, password)
        if not hvoy_result.success:
            self.logger.error(f"[{idx}] hvoy register failed: "
                              f"{hvoy_result.error}")
            result.failed += 1
            return

        print(f"\n  >>> [2/9] Waiting for hvoy verification email...")
        verify_link = await self.gmail.wait_for_verification_link(
            query=f"from:noreply@hvoy.ai to:{email_addr}",
            domain="hvoy.ai", timeout=120)
        if not verify_link:
            self.logger.error(f"[{idx}] hvoy verification email not found")
            result.failed += 1
            return

        vp = await context.new_page()
        await vp.goto(verify_link, wait_until="domcontentloaded", timeout=20000)
        await vp.wait_for_timeout(3000)
        # 点击"去登录"按钮确认邮箱验证
        go_login = vp.locator('button:has-text("去登录"), a:has-text("去登录")')
        if await go_login.count() > 0:
            await go_login.click()
            await vp.wait_for_timeout(2000)
        await vp.close()

        print(f"\n  >>> [3/9] hvoy.ai login...")
        login_ok = await self.hvoy.login(context, username, password)
        if not login_ok:
            self.logger.error(f"[{idx}] hvoy login failed")
            result.failed += 1
            return

        print(f"\n  >>> [4/9] Extracting invite code...")
        invite_code = await self.hvoy.extract_invite_code(context)
        if not invite_code:
            self.logger.error(f"[{idx}] invite code not found")
            result.failed += 1
            return
        self.code_store.save(asdict(invite_code))
        result.codes_obtained.append(invite_code)

        print(f"\n  >>> [5/9] CUN.ai register (invite: 44Wb)...")
        cun_result = await self.cun.register(
            context, email_addr, username, password, gmail_api=self.gmail)
        if not cun_result.success:
            self.logger.error(f"[{idx}] CUN register failed: "
                              f"{cun_result.error}")
            result.failed += 1
            return

        print(f"\n  >>> [6/9] CUN.ai login...")
        cun_login_ok = await self.cun.login(context, username, password)
        if not cun_login_ok:
            self.logger.error(f"[{idx}] CUN login failed")
            result.failed += 1
            return

        page = await context.new_page()
        try:
            print(f"\n  >>> [7/9] Redeeming {invite_code.code}...")
            redeemed = await self.cun.redeem_invite_code(
                page, invite_code.code)
            if redeemed:
                self.code_store.mark_used(invite_code.code, username)

            print(f"\n  >>> [8/9] Creating API key...")
            api_key = await self.cun.create_api_key(page)

            account = asdict(cun_result.account)
            account["invite_code"] = invite_code.code
            account["api_key"] = api_key or ""
            self.account_store.save(account)
        finally:
            await page.close()

        print(f"\n  >>> [9/9] Cleanup...")
        await self.hvoy.logout(context)
        await self.cun.logout(context)

        result.success += 1
        self.logger.info(f"[{idx}] done")

    # ------------------------------------------------------------------
    # 摘要
    # ------------------------------------------------------------------

    def _print_summary(self, result: BatchResult):
        if result.total == 0 and result.success == 0 and result.failed == 0:
            print("\n  DRY RUN complete: no registration performed.")
            return
        print(f"\n{'='*60}")
        print(f"  Done | Total: {result.total} | Success: {result.success} "
              f"| Failed: {result.failed}")
        print(f"  Codes: {len(result.codes_obtained)}")
        print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="API Code Harvester v2")
    parser.add_argument("--count", type=int, default=1,
                        help="Number of cycles to run")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from last completed cycle")
    parser.add_argument("--dry-run", action="store_true",
                        help="Open pages for selector debugging")
    parser.add_argument("--chrome-profile", default="",
                        help="Chrome user data dir")
    parser.add_argument("--email", default="",
                        help="Gmail address (default: from config)")
    parser.add_argument("--proxy", default="",
                        help="Proxy for Gmail API (default: from config)")
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
