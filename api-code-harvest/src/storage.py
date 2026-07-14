import json
import os


class JsonStore:
    """JSON 文件存储基类，原子写入"""

    def __init__(self, filepath: str):
        self.filepath = filepath
        if not os.path.exists(self.filepath):
            self._write([])

    def _read(self) -> list:
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                content = f.read()
                if not content.strip():
                    return []
                return json.loads(content)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _write(self, data: list) -> None:
        tmp = self.filepath + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.filepath)

    def append(self, item: dict) -> None:
        data = self._read()
        data.append(item)
        self._write(data)

    def list_all(self) -> list:
        return self._read()

    def update(self, predicate, updater) -> bool:
        data = self._read()
        for i, item in enumerate(data):
            if predicate(item):
                data[i] = updater(item)
                self._write(data)
                return True
        return False


class AccountStore(JsonStore):
    """账号存储"""

    def save(self, account: dict) -> None:
        self.append(account)

    def find_by_username(self, site: str, username: str) -> dict | None:
        for item in self.list_all():
            if item.get("site") == site and item.get("username") == username:
                return item
        return None


class CodeStore(JsonStore):
    """兑换码存储"""

    def save(self, code: dict) -> None:
        self.append(code)

    def get_unused(self) -> list[dict]:
        return [c for c in self.list_all() if not c.get("used")]

    def mark_used(self, code_str: str, used_by: str) -> bool:
        from datetime import datetime

        return self.update(
            lambda c: c.get("code") == code_str,
            lambda c: {**c, "used": True, "used_by": used_by, "used_at": datetime.now().isoformat()},
        )
