import argparse
import json
from pathlib import Path
import sys
import time
import traceback

from . import __version__
from .engine import Bible, VERSIONS
from .profile_lock import ProfileLock


def self_test():
    bible = Bible()
    counts = {}
    for version in VERSIONS:
        result = bible.search("John 3:16-18", version)
        assert result.total == 3 and result.verses[0].verse == 16
        counts[version] = bible.query("SELECT COUNT(*) AS n FROM verses WHERE version=?", (version,))[0]["n"]
        assert counts[version] > 30000
    assert bible.query("PRAGMA integrity_check")[0][0] == "ok"
    assert bible.search("先知").total > 400
    return {"version": __version__, "status": "passed", "verse_counts": counts}


def smoke_test(app):
    def wait_search():
        deadline = time.monotonic() + 10
        while app.result is None and time.monotonic() < deadline:
            app.root.update()
            time.sleep(0.02)
        assert app.result is not None, "GUI search did not complete"
    wait_search()
    app.query.set("先知")
    app.search()
    wait_search()
    assert app.result.total > 400 and len(app.rows) == 20
    app.navigate(1)
    wait_search()
    assert app.result.page == 2
    app.run_example("John 3:16-18")
    wait_search()
    assert len(app.rows) == 3
    app.read_selected()
    assert app.mode == "chapter" and len(app.rows) == 36 and app.selected.verse == 16
    app.copy_verse()
    assert "3:16" in app.root.clipboard_get()
    if app.selected.key not in app.preferences.bookmarks:
        app.toggle_bookmark()
    app.show_bookmarks()
    assert len(app.rows) >= 1
    app.read_chapter_at(66, 22)
    assert str(app.next_button["state"]) == "disabled"
    app.read_chapter_at(1, 1)
    assert str(app.previous_button["state"]) == "disabled"
    app.version.set(VERSIONS["web"])
    app.run_example("John 3:16")
    wait_search()
    assert "God so loved" in app.rows[0].text
    app.close()
    return {"status": "passed", "gui": "search, pagination, context, copy, bookmarks, chapter boundaries, version switch"}


def main(argv=None):
    parser = argparse.ArgumentParser(description="寻经 Bible Finder — 离线圣经查询")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--profile-dir", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.self_test:
            result = self_test()
        else:
            if sys.platform == "win32":
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            import tkinter as tk
            from .ui import BibleApp
            profile = args.profile_dir
            if profile is None:
                base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2] / "work"
                profile = base / "BibleFinder-data"
            with ProfileLock(profile):
                root = tk.Tk()
                if args.smoke_test:
                    root.withdraw()
                app = BibleApp(root, profile)
                if args.smoke_test:
                    result = smoke_test(app)
                else:
                    root.mainloop()
                    result = {"status": "closed"}
        exit_code = 0
    except Exception as error:
        result = {"status": "failed", "error": str(error), "traceback": traceback.format_exc()}
        exit_code = 1
        if not args.self_test and not args.smoke_test:
            from tkinter import messagebox
            messagebox.showerror("寻经无法启动", str(error))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if sys.stdout:
        print(json.dumps(result, ensure_ascii=False))
    return exit_code
