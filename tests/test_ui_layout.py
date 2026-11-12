import time

import pytest

tk = pytest.importorskip("tkinter")

from appcore.ui import MIN_SIZE, BibleApp  # noqa: E402


@pytest.fixture(scope="module")
def interpreter():
    # One Tk interpreter per module: repeatedly creating Tk() on Windows can
    # intermittently fail to re-source tk.tcl.
    try:
        master = tk.Tk()
    except tk.TclError as error:  # Linux CI has no display; Windows CI and local runs do.
        pytest.skip(f"Tk display unavailable: {error}")
    master.withdraw()
    yield master
    master.destroy()


@pytest.fixture
def make_root(interpreter):
    def make(scale):
        interpreter.tk.call("tk", "scaling", 96 * scale / 72)
        root = tk.Toplevel(interpreter)
        # Mapped but transparent: geometry and ismapped are real without flashing a window.
        root.attributes("-alpha", 0.0)
        root.maxsize(10000, 10000)
        return root
    return make


def wait_for_result(app):
    deadline = time.monotonic() + 10
    while app.result is None and time.monotonic() < deadline:
        app.root.update()
        time.sleep(0.02)
    assert app.result is not None


def frame_in_root(widget, root):
    """Widget rectangle in root coordinates, asserting each ancestor fully contains it."""
    x, y, width, height = 0, 0, widget.winfo_width(), widget.winfo_height()
    current = widget
    while current is not root:
        parent = current.master
        x, y = x + current.winfo_x(), y + current.winfo_y()
        assert current.winfo_x() >= 0 and current.winfo_y() >= 0, widget
        assert current.winfo_x() + current.winfo_width() <= parent.winfo_width(), widget
        assert current.winfo_y() + current.winfo_height() <= parent.winfo_height(), widget
        current = parent
    return x, y, width, height


def assert_layout(app):
    app.root.update()
    root_w, root_h = app.root.winfo_width(), app.root.winfo_height()
    essentials = [app.copy_button, app.bookmark_button, app.context_button, app.font_down, app.font_up,
                  app.previous_button, app.next_button, app.version_box]
    if app.mode == "search":
        essentials += [app.query_entry, app.search_button, app.scope_box]
    if app.mode == "chapter":
        essentials += [app.book_box, app.chapter_box]
    for widget in essentials:
        assert widget.winfo_ismapped(), widget
        assert widget.winfo_width() >= widget.winfo_reqwidth() - 1, widget
        assert widget.winfo_height() >= widget.winfo_reqheight() - 1, widget
        x, y, width, height = frame_in_root(widget, app.root)
        assert x + width <= root_w and y + height <= root_h, widget
    line = app.detail_text.tk.call("font", "metrics", app.detail_text.cget("font"), "-linespace")
    if app.compact or app.preferences.font_size > 14:
        assert app.detail_text.winfo_height() >= line
    else:
        assert app.detail_text.winfo_height() >= 3 * line
        assert app.results_text.winfo_height() >= 0.45 * app.content.winfo_height()


def exercise_modes(app):
    app.query.set("先知")
    app.search()
    wait_for_result(app)
    assert_layout(app)
    app.read_selected()
    assert app.mode == "chapter"
    assert_layout(app)
    app.show_bookmarks()
    assert_layout(app)


@pytest.mark.parametrize("scale", [1.0, 1.25, 1.5, 2.0])
def test_minimum_window_keeps_every_control_visible(tmp_path, scale, make_root):
    root = make_root(scale)
    app = BibleApp(root, tmp_path)
    try:
        assert all(actual <= design for actual, design in zip(root.minsize(), app.design_size(MIN_SIZE)))
        root.geometry("%dx%d" % app.design_size(MIN_SIZE))
        wait_for_result(app)
        exercise_modes(app)
        assert not app.compact
    finally:
        app.close()


@pytest.mark.parametrize("scale", [1.0, 1.25, 1.5, 2.0])
@pytest.mark.parametrize("font_size", [12, 20])
def test_screen_limited_window_on_1080p_keeps_actions_visible(tmp_path, scale, font_size, make_root):
    # A 1920x1080 screen caps the minimum window below the design size at high
    # scaling; the compact layout must still keep every action on screen.
    root = make_root(scale)
    app = BibleApp(root, tmp_path)
    try:
        (min_w, min_h), _ = app.window_sizes(1920, 1080)
        root.geometry(f"{min_w}x{min_h}")
        wait_for_result(app)
        app.preferences.font_size = font_size
        app._apply_text_fonts()
        exercise_modes(app)
        assert app.compact == (min_h < app.design_size(MIN_SIZE)[1] - 1)
    finally:
        app.close()


def test_compact_layout_restores_full_layout(tmp_path, make_root):
    root = make_root(1.0)
    app = BibleApp(root, tmp_path)
    try:
        wait_for_result(app)
        width, height = app.design_size(MIN_SIZE)
        root.minsize(1, 1)  # As if a small screen had capped the minimum size.
        root.geometry(f"{width}x{height - 120}")
        root.update()
        assert app.compact and not app.detail_hint.winfo_ismapped()
        assert app.context_button.winfo_manager() == "grid" and str(app.context_button.grid_info()["in"]) == str(app.actions)
        root.geometry(f"{width}x{height}")
        root.update()
        assert not app.compact and app.detail_hint.winfo_ismapped() and app.page_subtitle.winfo_ismapped()
        assert str(app.context_button.grid_info()["in"]) == str(app.detail)
        assert_layout(app)
    finally:
        app.close()


def test_modes_switch_header_and_toolbars(tmp_path, make_root):
    root = make_root(1.0)
    app = BibleApp(root, tmp_path)
    try:
        wait_for_result(app)
        root.update()
        assert app.page_title.cget("text") == "经文查询"
        assert app.search_bar.winfo_ismapped() and not app.reader_bar.winfo_ismapped()
        app.read_selected()
        root.update()
        assert app.page_title.cget("text") == "整章阅读"
        assert app.reader_bar.winfo_ismapped() and not app.search_bar.winfo_ismapped()
        assert str(app.context_button["state"]) == "disabled"
        app.show_bookmarks()
        root.update()
        assert app.page_title.cget("text") == "我的收藏"
        assert not app.reader_bar.winfo_ismapped() and not app.search_bar.winfo_ismapped()
        app.focus_search()
        wait_for_result(app)
        assert app.mode == "search" and app.search_bar.winfo_ismapped()
    finally:
        app.close()


def test_arrow_keys_move_selection_but_not_inside_inputs(tmp_path, make_root):
    root = make_root(1.0)
    app = BibleApp(root, tmp_path)
    try:
        app.run_example("John 3:16-18")
        wait_for_result(app)
        assert app.selected.verse == 16
        app.move_selection(1)
        app.move_selection(1)
        app.move_selection(1)
        assert app.selected.verse == 18
        app.move_selection(-5)
        assert app.selected.verse == 16

        class Event:
            widget = app.query_entry

        assert app._arrow(Event, 1) is None and app.selected.verse == 16
        Event.widget = app.results_text
        assert app._arrow(Event, 1) == "break" and app.selected.verse == 17
    finally:
        app.close()


def test_bookmark_button_reflects_saved_state_and_font_limits(tmp_path, make_root):
    root = make_root(1.0)
    app = BibleApp(root, tmp_path)
    try:
        wait_for_result(app)
        assert "收藏" in app.bookmark_button.cget("text") and "已" not in app.bookmark_button.cget("text")
        app.toggle_bookmark()
        assert app.bookmark_button.cget("text").endswith("已收藏")
        app.toggle_bookmark()
        assert not app.bookmark_button.cget("text").endswith("已收藏")
        for _ in range(15):
            app.resize_font(1)
        assert app.preferences.font_size == 20 and str(app.font_up["state"]) == "disabled"
        assert str(app.font_down["state"]) == "normal"
    finally:
        app.close()
