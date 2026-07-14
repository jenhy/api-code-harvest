"""Task 4: 工具函数测试"""
import re

from src.utils import generate_username, generate_password, setup_logger


class TestGenerateUsername:
    def test_length_in_range(self):
        for _ in range(100):
            u = generate_username()
            assert 3 <= len(u) <= 32, f"username '{u}' length {len(u)} out of range"

    def test_only_valid_characters(self):
        for _ in range(100):
            u = generate_username()
            assert re.match(r'^[a-zA-Z0-9_-]+$', u), f"username '{u}' has invalid chars"

    def test_no_leading_hyphen(self):
        for _ in range(100):
            u = generate_username()
            assert not u.startswith("-"), f"username '{u}' starts with hyphen"

    def test_default_length_is_12(self):
        for _ in range(50):
            u = generate_username()
            assert len(u) == 12

    def test_custom_length(self):
        for length in [3, 8, 16, 32]:
            u = generate_username(length=length)
            assert len(u) == length

    def test_custom_length_too_short_raises(self):
        import pytest
        with pytest.raises(ValueError):
            generate_username(length=2)

    def test_custom_length_too_long_raises(self):
        import pytest
        with pytest.raises(ValueError):
            generate_username(length=33)


class TestGeneratePassword:
    def test_minimum_length(self):
        for _ in range(100):
            p = generate_password()
            assert len(p) >= 9, f"password '{p}' is too short ({len(p)})"

    def test_has_uppercase(self):
        for _ in range(100):
            p = generate_password()
            assert re.search(r'[A-Z]', p), f"password '{p}' missing uppercase"

    def test_has_lowercase(self):
        for _ in range(100):
            p = generate_password()
            assert re.search(r'[a-z]', p), f"password '{p}' missing lowercase"

    def test_has_digit(self):
        for _ in range(100):
            p = generate_password()
            assert re.search(r'\d', p), f"password '{p}' missing digit"

    def test_has_special_char(self):
        specials = set("!@#$%^&*()_+-=[]{}|;:,.<>?")
        for _ in range(100):
            p = generate_password()
            assert any(c in specials for c in p), f"password '{p}' missing special char"

    def test_default_length_is_16(self):
        for _ in range(50):
            p = generate_password()
            assert len(p) == 16

    def test_custom_length(self):
        for length in [9, 12, 20, 32]:
            p = generate_password(length=length)
            assert len(p) == length

    def test_custom_length_too_short_raises(self):
        import pytest
        with pytest.raises(ValueError):
            generate_password(length=8)


class TestSetupLogger:
    def test_returns_logger(self):
        logger = setup_logger("test_module")
        assert logger is not None

    def test_logger_can_info(self):
        logger = setup_logger("test_module")
        logger.info("test message")  # 不抛异常即通过

    def test_different_names_get_different_loggers(self):
        a = setup_logger("mod_a")
        b = setup_logger("mod_b")
        assert a is not b
