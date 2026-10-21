import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from appcore.books import ALIASES, BOOKS
from appcore.engine import Bible, DATA_PATH, PAGE_SIZE, VERSIONS, parse_reference
from appcore.preferences import Preferences
from appcore.profile_lock import ProfileLock


@pytest.fixture(scope="module")
def bible():
    return Bible()


@pytest.mark.parametrize("query", ["约3:16", "約 3:16", "约翰福音3章16节", "約翰福音３：１６", "John 3:16", "JOHN3:16", "Jn.3:16"])
def test_reference_aliases(bible, query):
    result = bible.search(query)
    assert result.total == 1
    verse = result.verses[0]
    assert (verse.book, verse.chapter, verse.verse) == (43, 3, 16)
    assert "神爱世人" in verse.text


@pytest.mark.parametrize("query,book", [("约一 1:1", 62), ("1 John 1:1", 62), ("2Tim 1:1", 55), ("撒上1:1", 9), ("Song of Solomon 1:1", 22)])
def test_numbered_books(bible, query, book):
    assert bible.search(query).verses[0].book == book


def test_all_aliases_point_to_actual_book(bible):
    assert len(BOOKS) == 66
    for alias, book in ALIASES.items():
        assert bible.search(f"{alias} 1:1").verses[0].book == book


def test_ranges_and_whole_chapter(bible):
    assert [v.verse for v in bible.search("John3:16-18").verses] == [16, 17, 18]
    assert bible.search("约3:36-4:2").total == 3
    assert bible.search("诗篇23章").total == 6
    assert bible.search("诗篇119").total == 176
    assert bible.search("约3:16", scope="old").total == 1


@pytest.mark.parametrize("query", ["", " ", "x" * 201, "约0:1", "约22:1", "约3:999", "约3:0", "约3:18-16", "约3:16-2:20", "约3:16junk", "约3:16-", "Unknown 3:16", "约3:16;4:1"])
def test_invalid_references_provide_errors(bible, query):
    with pytest.raises(ValueError):
        bible.search(query)


def test_keywords_scope_and_literal_punctuation(bible):
    result = bible.search("先知")
    assert result.total > 400 and all("先知" in v.text for v in result.verses)
    old = bible.search("先知", scope="old")
    new = bible.search("先知", scope="new")
    assert old.total + new.total == result.total
    assert all(v.book <= 39 for v in old.verses)
    assert all(v.book >= 40 for v in new.verses)
    assert all(v.book == 43 for v in bible.search("耶稣", scope=43).verses)
    for query in ("%", "_", "\\", "' OR 1=1 --", "无此经文zzzz"):
        assert bible.search(query).total == 0


def test_pagination_has_no_duplicate_or_missing_rows(bible):
    first = bible.search("先知")
    rows = []
    for page in range(1, first.pages + 1):
        result = bible.search("先知", page=page)
        assert len(result.verses) <= PAGE_SIZE and result.page == page
        rows.extend(v.key for v in result.verses)
    assert len(set(rows)) == len(rows) == first.total
    assert bible.search("先知", page=9999).page == first.pages
    with pytest.raises(ValueError):
        bible.search("先知", page=0)


def test_english_and_traditional(bible):
    assert "神愛世人" in bible.search("約3:16", "cut").verses[0].text
    assert bible.search("神 愛 世人", "cut").total >= 1
    assert bible.search("GOD SO LOVED", "web").total == bible.search("God so loved", "web").total > 0
    assert "God so loved" in bible.search("John3:16", "web").verses[0].text


def test_context_and_book_boundaries(bible):
    assert len(bible.chapter("cus", 43, 3)) == 36
    assert bible.adjacent_chapter("cus", 1, 1, -1) is None
    assert bible.adjacent_chapter("cus", 66, 22, 1) is None
    assert bible.adjacent_chapter("cus", 1, 50, 1) == (2, 1)
    assert bible.adjacent_chapter("cus", 2, 1, -1) == (1, 50)
    with pytest.raises(ValueError):
        bible.chapter("cus", 43, 22)


def test_complete_data_integrity_and_provenance(bible):
    manifest = json.loads(DATA_PATH.with_name("sources.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(DATA_PATH.read_bytes()).hexdigest() == manifest["database_sha256"]
    assert bible.query("PRAGMA integrity_check")[0][0] == "ok"
    for version in VERSIONS:
        info = manifest["translations"][version]
        assert info["metadata"]["distribution_license"] == "Public Domain"
        rows = bible.query("SELECT book,COUNT(DISTINCT chapter) AS chapters,COUNT(*) AS verses FROM verses WHERE version=? GROUP BY book", (version,))
        assert [r["book"] for r in rows] == list(range(1, 67))
        assert sum(r["verses"] for r in rows) == info["verse_count"]
        assert sum(r["chapters"] for r in rows) == 1189
        assert bible.get_verse(version, 66, 22, 21)
        assert bible.query("SELECT COUNT(*) FROM verses WHERE version=? AND text=''", (version,))[0][0] == 0


def test_read_only_and_concurrent_queries(bible):
    connection = bible.connect()
    try:
        with pytest.raises(Exception, match="readonly"):
            connection.execute("DELETE FROM verses")
    finally:
        connection.close()
    with ThreadPoolExecutor(max_workers=4) as executor:
        assert all(r.total == 1 for r in executor.map(bible.search, ["约3:16"] * 12))


def test_bookmark_roundtrip(tmp_path):
    path = tmp_path / "profile/settings.json"
    preferences = Preferences(path)
    assert preferences.toggle_bookmark("cus:43:3:16")
    preferences.version = "web"
    preferences.font_size = 16
    preferences.save()
    restored = Preferences(path)
    assert restored.bookmarks == ["cus:43:3:16"]
    assert (restored.version, restored.font_size) == ("web", 16)
    assert not restored.toggle_bookmark("cus:43:3:16")
    assert Preferences(path).bookmarks == []


def test_corrupt_preferences_are_preserved(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{broken", encoding="utf-8")
    preferences = Preferences(path)
    assert preferences.warning
    with pytest.raises(OSError):
        preferences.toggle_bookmark("cus:43:3:16")
    assert preferences.bookmarks == []
    assert path.read_text() == "{broken"


def test_save_failure_does_not_claim_bookmark_success(tmp_path, monkeypatch):
    preferences = Preferences(tmp_path / "settings.json")
    def fail():
        raise PermissionError("read-only")
    monkeypatch.setattr(preferences, "save", fail)
    with pytest.raises(PermissionError):
        preferences.toggle_bookmark("cus:43:3:16")
    assert not preferences.bookmarks


def test_invalid_settings_are_filtered(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"bookmarks": [None, "bad", "cus:99:1:1", "cus:43:3:16", "cus:43:3:16"], "font_size": 900}), encoding="utf-8")
    preferences = Preferences(path)
    assert preferences.bookmarks == ["cus:43:3:16"]
    assert preferences.font_size == 12


def test_missing_database_and_bad_options(tmp_path, bible):
    with pytest.raises(FileNotFoundError):
        Bible(tmp_path / "missing.sqlite3")
    with pytest.raises(ValueError):
        bible.search("test", version="no")
    with pytest.raises(ValueError):
        bible.search("test", scope="no")
    assert parse_reference("耶稣") is None


def test_profile_lock_prevents_stale_window_writes(tmp_path):
    with ProfileLock(tmp_path):
        with pytest.raises(OSError, match="已有一个寻经窗口"):
            with ProfileLock(tmp_path):
                pytest.fail("Second instance must not open the same profile")
        with ProfileLock(tmp_path / "different-profile"):
            pass
    with ProfileLock(tmp_path):
        pass
