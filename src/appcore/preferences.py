import json
import os
from pathlib import Path
import tempfile

from .engine import VERSIONS


class Preferences:
    """Portable, atomic saves; preserve unreadable files instead of replacing them."""

    def __init__(self, path):
        self.path = Path(path)
        self.bookmarks = []
        self.version = "cus"
        self.font_size = 12
        self.warning = ""
        self.block_save = False
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("bookmarks", []), list):
                raise ValueError("invalid preferences")
            for key in data.get("bookmarks", []):
                parts = key.split(":") if isinstance(key, str) else []
                if len(parts) == 4 and parts[0] in VERSIONS and all(p.isdigit() and 1 <= int(p) <= 176 for p in parts[1:]) and int(parts[1]) <= 66:
                    if key not in self.bookmarks:
                        self.bookmarks.append(key)
            if data.get("version") in VERSIONS:
                self.version = data["version"]
            if type(data.get("font_size")) is int and 10 <= data["font_size"] <= 20:
                self.font_size = data["font_size"]
        except (OSError, ValueError, TypeError):
            self.warning = "收藏文件无法读取，已保留原文件。请备份后移走该文件，再重启软件。"
            self.block_save = True

    def save(self):
        if self.block_save:
            raise OSError(self.warning)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps({"bookmarks": self.bookmarks, "version": self.version, "font_size": self.font_size}, ensure_ascii=False, indent=2)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent, prefix=".settings-", suffix=".tmp", delete=False) as output:
                temporary = Path(output.name)
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def toggle_bookmark(self, key):
        previous = self.bookmarks.copy()
        if key in self.bookmarks:
            self.bookmarks.remove(key)
        else:
            self.bookmarks.append(key)
        try:
            self.save()
        except OSError:
            self.bookmarks = previous
            raise
        return key in self.bookmarks
