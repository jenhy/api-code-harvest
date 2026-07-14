"""E2E 测试 — 真实浏览器 + 页面选择器验证"""
import pytest
from patchright.sync_api import sync_playwright


@pytest.mark.e2e
class TestBrowserLaunch:
    """验证 Playwright 驱动正常"""

    def test_can_launch_browser(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            assert browser.is_connected()
            browser.close()


@pytest.mark.e2e
class TestCunAIRegistrationPage:
    """验证 CUN.ai 注册页选择器"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.p = sync_playwright().start()
        self.browser = self.p.chromium.launch(headless=True)
        self.page = self.browser.new_page()
        self.page.goto("https://www.cun.ai/sign-up", wait_until="networkidle")
        self.page.wait_for_timeout(3000)
        # Dismiss popup if present
        try:
            dismiss = self.page.locator('button:has-text("知道了")')
            if dismiss.is_visible(timeout=3000):
                dismiss.click()
                self.page.wait_for_timeout(1000)
        except Exception:
            pass
        yield
        self.page.close()
        self.browser.close()
        self.p.stop()

    def test_username_input_exists(self):
        el = self.page.locator('input[placeholder*="用户名"]')
        assert el.is_visible()

    def test_email_input_exists(self):
        el = self.page.locator('input[type="email"]')
        assert el.is_visible()

    def test_password_inputs_exist(self):
        pwd_inputs = self.page.locator('input[type="password"]')
        assert pwd_inputs.count() >= 2

    def test_submit_button_exists(self):
        btn = self.page.locator('button:has-text("创建账户")')
        assert btn.is_visible()


@pytest.mark.e2e
class TestHvoyAIRegistrationPage:
    """验证 hvoy.ai 注册页选择器（依赖 Cloudflare 通过）"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.p = sync_playwright().start()
        self.browser = self.p.chromium.launch(headless=True)
        self.page = self.browser.new_page()
        self.page.goto("https://hvoy.ai/user/register", wait_until="domcontentloaded")
        self.page.wait_for_timeout(5000)
        yield
        self.page.close()
        self.browser.close()
        self.p.stop()

    def test_page_loads(self):
        """页面至少能加载（可能有 Cloudflare challenge）"""
        title = self.page.title()
        assert len(title) > 0  # 不管标题是什么，页面必须返回

    def test_if_form_visible_check_inputs(self):
        """如果 Cloudflare 通过了，表单应该可见"""
        body = self.page.inner_text("body")
        if "用户名" in body and "注册账号" in body:
            inputs = self.page.locator("input:visible")
            assert inputs.count() >= 4
        else:
            pytest.skip("Cloudflare challenge active — can't verify form")
