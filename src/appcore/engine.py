from dataclasses import dataclass
from pathlib import Path
import re
import sqlite3
import time
import unicodedata

from .books import ALIASES, book_name

VERSIONS = {"cus": "和合本 · 简体", "cut": "和合本 · 繁體", "web": "World English Bible"}
PAGE_SIZE = 20
DATA_PATH = Path(__file__).with_name("data") / "bible.sqlite3"


@dataclass(frozen=True)
class Reference:
    book: int
    chapter: int
    verse: int | None = None
    end_chapter: int | None = None
    end_verse: int | None = None


@dataclass(frozen=True)
class Verse:
    version: str
    book: int
    chapter: int
    verse: int
    text: str

    @property
    def reference(self):
        return f"{book_name(self.book, self.version)} {self.chapter}:{self.verse}"

    @property
    def key(self):
        return f"{self.version}:{self.book}:{self.chapter}:{self.verse}"

    @property
    def citation(self):
        return f"{self.reference}（{VERSIONS[self.version]}）\n{self.text}"


@dataclass(frozen=True)
class SearchResult:
    verses: tuple[Verse, ...]
    total: int
    page: int
    pages: int
    elapsed_ms: float
    reference: Reference | None = None


def parse_reference(query: str) -> Reference | None:
    compact = re.sub(r"\s+", "", unicodedata.normalize("NFKC", query)).casefold()
    compact = compact.replace("–", "-").replace("—", "-").replace("至", "-")
    for alias in sorted(ALIASES, key=len, reverse=True):
        if not compact.startswith(alias):
            continue
        suffix = compact[len(alias):].lstrip(".")
        if not suffix or not suffix[0].isdigit():
            continue
        suffix = suffix.replace("章", ":").replace("节", "").replace("節", "")
        if suffix.endswith(":"):
            suffix = suffix[:-1]
        match = re.fullmatch(r"(\d+)(?::(\d+)(?:-(?:(\d+):)?(\d+))?)?", suffix)
        if not match:
            raise ValueError("经文格式有误。请使用 约 3:16、John 3:16-18 或 诗篇 23。")
        chapter, verse, end_chapter, end_verse = (int(n) if n else None for n in match.groups())
        if any(n is not None and (n < 1 or n > 176) for n in (chapter, verse, end_chapter, end_verse)):
            raise ValueError("章、节编号必须是有效的正整数。")
        end_chapter = end_chapter or chapter
        end_verse = end_verse or verse
        if verse is not None and (end_chapter, end_verse) < (chapter, verse):
            raise ValueError("经文范围的结束位置不能早于开始位置。")
        return Reference(ALIASES[alias], chapter, verse, end_chapter, end_verse)
    if re.search(r"\d+[:章]\d+", compact):
        raise ValueError("未识别书卷名称。请使用中文书名、简称或英文书名，例如 约 3:16。")
    return None


def normalize_keyword(text: str, version: str) -> str:
    text = unicodedata.normalize("NFKC", text).strip()
    return "".join(text.split()) if version in ("cus", "cut") else " ".join(text.split())


class Bible:
    def __init__(self, path=DATA_PATH):
        self.path = Path(path).resolve()
        if not self.path.is_file():
            raise FileNotFoundError("找不到离线经文库，请重新下载完整的发布包。")

    def connect(self):
        connection = sqlite3.connect(f"{self.path.as_uri()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        return connection

    def query(self, sql, parameters=()):
        connection = self.connect()
        try:
            return connection.execute(sql, parameters).fetchall()
        finally:
            connection.close()

    @staticmethod
    def validate_version(version):
        if version not in VERSIONS:
            raise ValueError("不支持这个译本。")

    def chapter_count(self, version, book):
        self.validate_version(version)
        rows = self.query("SELECT MAX(chapter) AS n FROM verses WHERE version=? AND book=?", (version, book))
        return rows[0]["n"] or 0

    def get_verse(self, version, book, chapter, verse):
        self.validate_version(version)
        rows = self.query("SELECT version,book,chapter,verse,text FROM verses WHERE version=? AND book=? AND chapter=? AND verse=?", (version, book, chapter, verse))
        return Verse(**dict(rows[0])) if rows else None

    def search(self, query, version="cus", scope="all", page=1):
        start = time.perf_counter()
        self.validate_version(version)
        query = query.strip()
        if not query:
            raise ValueError("请输入关键词或经文出处。")
        if len(query) > 200:
            raise ValueError("查询内容请控制在 200 个字符以内。")
        if not isinstance(page, int) or page < 1:
            raise ValueError("页码必须是正整数。")
        where, parameters = ["version=?"], [version]
        reference = parse_reference(query)
        if reference:
            max_chapter = self.chapter_count(version, reference.book)
            if not 1 <= reference.chapter <= reference.end_chapter <= max_chapter:
                raise ValueError(f"{book_name(reference.book)}只有 {max_chapter} 章。")
            where.append("book=?")
            parameters.append(reference.book)
            if reference.verse is None:
                where.append("chapter=?")
                parameters.append(reference.chapter)
            else:
                for chapter, verse in [(reference.chapter, reference.verse), (reference.end_chapter, reference.end_verse)]:
                    if not self.get_verse(version, reference.book, chapter, verse):
                        raise ValueError(f"{book_name(reference.book)} {chapter} 章不存在第 {verse} 节。")
                where.append("(chapter * 1000 + verse) BETWEEN ? AND ?")
                parameters += [reference.chapter * 1000 + reference.verse, reference.end_chapter * 1000 + reference.end_verse]
        else:
            if scope == "old":
                where.append("book <= 39")
            elif scope == "new":
                where.append("book >= 40")
            elif isinstance(scope, int) and 1 <= scope <= 66:
                where.append("book=?")
                parameters.append(scope)
            elif scope != "all":
                raise ValueError("查询范围无效。")
            literal = normalize_keyword(query, version).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            where.append("search_text LIKE ? ESCAPE '\\'")
            parameters.append(f"%{literal}%")
        clause = " AND ".join(where)
        total = self.query(f"SELECT COUNT(*) AS n FROM verses WHERE {clause}", parameters)[0]["n"]
        pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        page = min(page, pages)
        rows = self.query(f"SELECT version,book,chapter,verse,text FROM verses WHERE {clause} ORDER BY book,chapter,verse LIMIT ? OFFSET ?", [*parameters, PAGE_SIZE, (page - 1) * PAGE_SIZE])
        return SearchResult(tuple(Verse(**dict(row)) for row in rows), total, page, pages, (time.perf_counter() - start) * 1000, reference)

    def chapter(self, version, book, chapter):
        self.validate_version(version)
        rows = self.query("SELECT version,book,chapter,verse,text FROM verses WHERE version=? AND book=? AND chapter=? ORDER BY verse", (version, book, chapter))
        if not rows:
            raise ValueError("该章节不存在。")
        return tuple(Verse(**dict(row)) for row in rows)

    def adjacent_chapter(self, version, book, chapter, direction):
        if direction not in (-1, 1):
            raise ValueError("章节方向必须为 -1 或 1。")
        target = chapter + direction
        if target < 1:
            return (book - 1, self.chapter_count(version, book - 1)) if book > 1 else None
        if target > self.chapter_count(version, book):
            return (book + 1, 1) if book < 66 else None
        return book, target
