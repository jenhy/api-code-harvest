"""GmailApi 单元测试 — 纯逻辑方法（无需网络）"""
import pytest

from src.email.gmail_api import GmailApi


class TestExtractLink:
    """验证 `_extract_link` 从 HTML 正文提取验证链接"""

    def test_extracts_hvoy_verify_link(self):
        html = '<a href="https://hvoy.ai/verify-email?token=abc123def456">Verify</a>'
        link = GmailApi._extract_link(html, domain_hint="hvoy.ai")
        assert link == "https://hvoy.ai/verify-email?token=abc123def456"

    def test_extracts_link_with_long_token(self):
        html = (
            '<a href="https://hvoy.ai/free-tokens/verify-email?'
            'token=7fcfa50bab609ec4a32750c626cb59998512b97d4afcf975a2dec912a94b3d00'
            '">验证邮箱</a>'
        )
        link = GmailApi._extract_link(html, domain_hint="hvoy.ai")
        assert "verify-email" in link
        assert "token=" in link

    def test_no_link_returns_none(self):
        assert GmailApi._extract_link("no link here", domain_hint="hvoy.ai") is None

    def test_ignores_non_matching_domain(self):
        html = '<a href="https://other.com/verify?token=x">link</a>'
        assert GmailApi._extract_link(html, domain_hint="hvoy.ai") is None

    def test_fallback_to_any_domain_link(self):
        """如果 verify-email?token= 模式没匹配，但 URL 包含 domain_hint，应返回"""
        html = 'Click: https://www.cun.ai/verify?code=xyz'
        link = GmailApi._extract_link(html, domain_hint="cun.ai")
        assert link == "https://www.cun.ai/verify?code=xyz"

    def test_multiple_links_returns_first_matching(self):
        html = (
            '<a href="https://other.com/verify">bad</a>'
            '<a href="https://hvoy.ai/verify-email?token=abc">good</a>'
        )
        link = GmailApi._extract_link(html, domain_hint="hvoy.ai")
        assert "hvoy.ai" in link
        assert "token=abc" in link


class TestExtractCode:
    """验证 `_extract_code` 从邮件正文提取 6 位验证码"""

    def test_extracts_6_digit_code(self):
        text = "Your verification code is 123456"
        assert GmailApi._extract_code(text) == "123456"

    def test_no_code_returns_none(self):
        assert GmailApi._extract_code("no code here") is None

    def test_7_digit_not_matched(self):
        """刚好 7 位数字的序列不应匹配"""
        assert GmailApi._extract_code("code: 1234567") is None

    def test_code_in_html(self):
        html = '<div>验证码：<strong>654321</strong>，5分钟内有效</div>'
        assert GmailApi._extract_code(html) == "654321"

    def test_first_6_digit_in_long_text(self):
        text = "some text 999999 more text 111111 more"
        assert GmailApi._extract_code(text) == "999999"


class TestConfigValidation:
    """验证 GmailApi 初始化参数"""

    def test_default_values(self):
        api = GmailApi("creds.json", "token.pkl")
        assert api.credentials_file == "creds.json"
        assert api.token_pickle == "token.pkl"
        assert api.proxy == "http://127.0.0.1:22222"

    def test_custom_proxy(self):
        api = GmailApi("c.json", "t.pkl", proxy_host="10.0.0.1", proxy_port=8888)
        assert api.proxy == "http://10.0.0.1:8888"
