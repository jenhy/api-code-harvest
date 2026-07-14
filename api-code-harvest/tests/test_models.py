"""数据模型单元测试 — AccountInfo 新增字段"""
from src.models import AccountInfo, InviteCode, RegistrationResult, BatchResult


class TestAccountInfoNewFields:
    """验证新增的 invite_code 和 api_key 字段"""

    def test_default_empty_invite_code(self):
        info = AccountInfo(site="hvoy", username="u", email="e@t.com", password="p")
        assert info.invite_code == ""

    def test_default_empty_api_key(self):
        info = AccountInfo(site="cun", username="u", email="e@t.com", password="p")
        assert info.api_key == ""

    def test_set_invite_code(self):
        info = AccountInfo(site="hvoy", username="u", email="e@t.com",
                           password="p", invite_code="abc123")
        assert info.invite_code == "abc123"

    def test_set_api_key(self):
        info = AccountInfo(site="cun", username="u", email="e@t.com",
                           password="p", api_key="sk-test123")
        assert info.api_key == "sk-test123"

    def test_both_new_fields(self):
        info = AccountInfo(site="cun", username="u", email="e@t.com",
                           password="p", verified=True,
                           invite_code="invite_xyz", api_key="sk-key456")
        assert info.invite_code == "invite_xyz"
        assert info.api_key == "sk-key456"
        assert info.verified is True

    def test_account_info_to_dict_includes_new_fields(self):
        """确保 dataclasses.asdict() 导出新字段"""
        from dataclasses import asdict
        info = AccountInfo(site="hvoy", username="u", email="e@t.com",
                           password="p", invite_code="ic", api_key="ak")
        d = asdict(info)
        assert "invite_code" in d
        assert "api_key" in d
        assert d["invite_code"] == "ic"
        assert d["api_key"] == "ak"
