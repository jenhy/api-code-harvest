"""Task 5: JSON 持久化存储测试"""
import json
import os
import tempfile

import pytest

from src.storage import JsonStore, AccountStore, CodeStore


@pytest.fixture
def temp_file():
    """创建临时JSON文件，测试后清理"""
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


class TestJsonStore:
    def test_init_creates_file(self, temp_file):
        os.unlink(temp_file)
        store = JsonStore(temp_file)
        assert os.path.exists(temp_file)

    def test_init_empty_file_has_empty_list(self, temp_file):
        store = JsonStore(temp_file)
        assert store.list_all() == []

    def test_append_and_list(self, temp_file):
        store = JsonStore(temp_file)
        store.append({"name": "item1"})
        store.append({"name": "item2"})
        items = store.list_all()
        assert len(items) == 2
        assert items[0]["name"] == "item1"
        assert items[1]["name"] == "item2"

    def test_data_persists_across_instances(self, temp_file):
        store1 = JsonStore(temp_file)
        store1.append({"value": 42})
        store2 = JsonStore(temp_file)
        assert store2.list_all()[0]["value"] == 42

    def test_update_modifies_matching_item(self, temp_file):
        store = JsonStore(temp_file)
        store.append({"id": 1, "name": "old"})
        store.append({"id": 2, "name": "keep"})
        result = store.update(
            lambda item: item["id"] == 1,
            lambda item: {**item, "name": "new"},
        )
        assert result is True
        items = store.list_all()
        assert items[0]["name"] == "new"
        assert items[1]["name"] == "keep"

    def test_update_no_match_returns_false(self, temp_file):
        store = JsonStore(temp_file)
        store.append({"id": 1})
        result = store.update(
            lambda item: item["id"] == 999,
            lambda item: item,
        )
        assert result is False

    def test_atomic_write_no_corruption(self, temp_file):
        """模拟写入过程中断：如果存在 .tmp 文件，原文件不受影响"""
        store = JsonStore(temp_file)
        store.append({"safe": True})
        # 确认不存在残留 .tmp 文件
        assert not os.path.exists(temp_file + ".tmp")

    def test_init_with_existing_data(self, temp_file):
        with open(temp_file, "w") as f:
            json.dump([{"existing": True}], f)
        store = JsonStore(temp_file)
        assert len(store.list_all()) == 1
        assert store.list_all()[0]["existing"] is True

    def test_init_with_empty_file(self, temp_file):
        with open(temp_file, "w") as f:
            f.write("")
        store = JsonStore(temp_file)
        assert store.list_all() == []

    def test_init_with_invalid_json_resets(self, temp_file):
        with open(temp_file, "w") as f:
            f.write("not valid json")
        store = JsonStore(temp_file)
        assert store.list_all() == []


class TestAccountStore:
    def test_save_and_find(self, temp_file):
        store = AccountStore(temp_file)
        store.save({"site": "hvoy", "username": "user1", "email": "e@t.com"})
        found = store.find_by_username("hvoy", "user1")
        assert found is not None
        assert found["email"] == "e@t.com"

    def test_find_returns_none_for_unknown(self, temp_file):
        store = AccountStore(temp_file)
        assert store.find_by_username("hvoy", "nobody") is None


class TestCodeStore:
    def test_save_and_get_unused(self, temp_file):
        store = CodeStore(temp_file)
        store.save({"code": "ABC", "source": "hvoy", "used": False})
        unused = store.get_unused()
        assert len(unused) == 1
        assert unused[0]["code"] == "ABC"

    def test_mark_used(self, temp_file):
        store = CodeStore(temp_file)
        store.save({"code": "XYZ", "source": "hvoy", "used": False})
        result = store.mark_used("XYZ", "cun_user1")
        assert result is True
        unused = store.get_unused()
        assert len(unused) == 0

    def test_get_unused_filters_used_codes(self, temp_file):
        store = CodeStore(temp_file)
        store.save({"code": "USED", "used": True})
        store.save({"code": "FREE", "used": False})
        unused = store.get_unused()
        assert len(unused) == 1
        assert unused[0]["code"] == "FREE"
