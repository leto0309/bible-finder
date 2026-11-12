from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import queue
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, ttk

from . import __version__
from .books import BOOKS, book_name
from .engine import Bible, PAGE_SIZE, VERSIONS, normalize_keyword
from .preferences import Preferences

BG = "#F6F5F0"
INK = "#243C32"
GREEN = "#183E32"
GREEN_HOVER = "#2B5644"
MUTED = "#6F7D72"
LINE = "#D9E0D4"
PAPER = "#FFFFFF"
SOFT = "#F1F5EE"
PANEL = "#EAF0E5"
GOLD = "#DABC79"
ACCENT = "#3E7353"
SELECTED = "#E6F0E1"
MATCH = "#F6E3AE"
DISABLED = "#A7B2A9"
FONT = "Microsoft YaHei UI"

# Layout sizes in 96-DPI pixels; scaled by the actual display DPI at runtime.
DEFAULT_SIZE = (1180, 780)
MIN_SIZE = (900, 620)

MODES = {
    "search": ("经文查询", "输入出处（约 3:16、John 3:16-18、诗篇 23）或关键词"),
    "chapter": ("整章阅读", "按书卷与章节通读，可跨书卷翻章"),
    "bookmarks": ("我的收藏", "全部译本的收藏，仅保存在本机"),
}


class BibleApp:
    def __init__(self, root, profile_dir: Path):
        self.root = root
        self.bible = Bible()
        self.preferences = Preferences(profile_dir / "settings.json")
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bible-search")
        self.events = queue.Queue()
        self.generation = 0
        self.closed = False
        self.mode = "search"
        self.result = None
        self.rows = ()
        self.selected = None
        self.chapter_location = (43, 3)
        self.last_search = ("约 3:16", self.preferences.version, "all")
        self.result_query = ""
        self.bookmark_page = 1
        self.bookmark_pages = 1
        self._base_bg = {}
        self.version = tk.StringVar(value=VERSIONS[self.preferences.version])
        self.query = tk.StringVar(value="约 3:16")
        self.scope = tk.StringVar(value="整本圣经")
        self.read_book = tk.StringVar(value="约翰福音")
        self.read_chapter = tk.StringVar(value="3")
        self.status = tk.StringVar(value="准备就绪 · 经文在本机离线查询")
        self.root.title(f"寻经 Bible Finder · {__version__}")
        self.scale = max(1.0, self.root.winfo_fpixels("1i") / 96)
        self._place_window()
        self.root.configure(bg=BG)
        self.root.option_add("*Font", (FONT, 10))
        self.root.option_add("*TCombobox*Listbox.font", (FONT, 10))
        self._styles()
        self._layout()
        self.root.bind("<Control-f>", self.focus_search)
        self.root.bind("<Control-d>", lambda _: self.toggle_bookmark())
        self.root.bind("<Up>", lambda event: self._arrow(event, -1))
        self.root.bind("<Down>", lambda event: self._arrow(event, 1))
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._poll_id = self.root.after(40, self._poll)
        self.search()
        if self.preferences.warning:
            self.root.after(200, lambda: messagebox.showwarning("收藏文件", self.preferences.warning, parent=root))

    # ----- window, styles and widget helpers -----

    def design_size(self, size):
        """A 96-DPI size scaled to the display, before fitting it on the screen."""
        return round(size[0] * self.scale), round(size[1] * self.scale)

    def _place_window(self):
        screen_w, screen_h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        min_w, min_h = self.design_size(MIN_SIZE)
        width, height = self.design_size(DEFAULT_SIZE)
        # Leave room for the title bar and taskbar, which the screen size includes.
        min_w, min_h = min(min_w, int(screen_w * 0.9)), min(min_h, int(screen_h * 0.8))
        width, height = max(min_w, min(width, int(screen_w * 0.92))), max(min_h, min(height, int(screen_h * 0.8)))
        self.root.minsize(min_w, min_h)
        x, y = max(0, (screen_w - width) // 2), max(0, (screen_h - height) // 2 - round(20 * self.scale))
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _px(self, value):
        return round(value * self.scale)

    def _styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TCombobox", fieldbackground=PAPER, background=PAPER, foreground=INK, arrowcolor=GREEN,
                        bordercolor=LINE, lightcolor=PAPER, darkcolor=PAPER, padding=(8, 5), arrowsize=self._px(13))
        style.map("TCombobox",
                  fieldbackground=[("readonly", PAPER)], foreground=[("readonly", INK)],
                  selectbackground=[("readonly", PAPER)], selectforeground=[("readonly", INK)],
                  bordercolor=[("focus", ACCENT), ("hover", "#B9C8BA")],
                  background=[("active", SOFT), ("readonly", PAPER)])
        style.configure("Vertical.TScrollbar", gripcount=0, background="#CAD5CB", troughcolor=PAPER,
                        bordercolor=PAPER, lightcolor="#CAD5CB", darkcolor="#CAD5CB", arrowcolor=MUTED,
                        width=self._px(10), arrowsize=self._px(10))
        style.map("Vertical.TScrollbar", background=[("active", "#AFC0B1")])
        style.configure("Panel.Vertical.TScrollbar", troughcolor=PANEL, bordercolor=PANEL)

    def label(self, parent, text="", size=10, color=INK, bold=False, bg=None, **kwargs):
        return tk.Label(parent, text=text, bg=bg or parent.cget("bg"), fg=color, font=(FONT, size, "bold" if bold else "normal"), **kwargs)

    def _hover(self, widget, normal, hover):
        self._base_bg[widget] = normal

        def enter(_):
            if str(widget["state"]) != "disabled":
                widget.configure(bg=hover)

        widget.bind("<Enter>", enter, add="+")
        widget.bind("<Leave>", lambda _: widget.configure(bg=self._base_bg[widget]), add="+")

    def _set_base(self, widget, bg, **kwargs):
        self._base_bg[widget] = bg
        widget.configure(bg=bg, **kwargs)

    def button(self, parent, text, command, kind="secondary", size=10, padx=14, pady=7, **kwargs):
        """kind: primary (filled), secondary (outlined), ghost (text only)."""
        colors = {
            "primary": (GREEN, "white", GREEN_HOVER, GREEN),
            "secondary": (PAPER, GREEN, SOFT, LINE),
            "ghost": (parent.cget("bg"), GREEN, SOFT, parent.cget("bg")),
        }[kind]
        bg, fg, hover, border = colors
        widget = tk.Button(parent, text=text, command=command, relief="flat", bd=0, bg=bg, fg=fg,
                           activebackground=hover, activeforeground=fg, cursor="hand2", padx=padx, pady=pady,
                           font=(FONT, size), disabledforeground=DISABLED, highlightthickness=1,
                           highlightbackground=border, highlightcolor=ACCENT, **kwargs)
        widget.kind = kind
        self._hover(widget, bg, hover)
        return widget

    def _enable(self, button, enabled):
        button.configure(state="normal" if enabled else "disabled", cursor="hand2" if enabled else "arrow")
        if getattr(button, "kind", "") == "primary":
            # Windows draws disabled text in grey, so a pale fill keeps it legible.
            self._set_base(button, GREEN if enabled else "#DCE5DA", highlightbackground=GREEN if enabled else "#DCE5DA")

    # ----- layout -----

    def _layout(self):
        self._rail()
        main = tk.Frame(self.root, bg=BG)
        main.pack(side="left", fill="both", expand=True, padx=self._px(26), pady=(self._px(16), self._px(10)))
        self.main = main

        header = tk.Frame(main, bg=BG)
        header.pack(fill="x", pady=(0, self._px(12)))
        titles = tk.Frame(header, bg=BG)
        titles.pack(side="left", fill="x", expand=True)
        self.page_title = self.label(titles, MODES["search"][0], 18, bold=True, anchor="w")
        self.page_title.pack(anchor="w")
        self.page_subtitle = self.label(titles, MODES["search"][1], 9, MUTED, anchor="w")
        self.page_subtitle.pack(anchor="w", pady=(self._px(1), 0))
        version_group = tk.Frame(header, bg=BG)
        version_group.pack(side="right", anchor="s")
        self.label(version_group, "译本", 9, MUTED).pack(side="left", padx=(0, self._px(7)))
        self.version_box = ttk.Combobox(version_group, textvariable=self.version, values=list(VERSIONS.values()),
                                        state="readonly", width=20, font=(FONT, 10))
        self.version_box.pack(side="left")
        self.version_box.bind("<<ComboboxSelected>>", self.change_version)

        footer = tk.Frame(main, bg=BG)
        footer.pack(side="bottom", fill="x", pady=(self._px(9), 0))
        tk.Label(footer, textvariable=self.status, bg=BG, fg=MUTED, font=(FONT, 9), anchor="w").pack(side="left", fill="x", expand=True)
        self.label(footer, f"●  离线可用 · v{__version__}", 9, "#4E7A5E").pack(side="right", padx=(self._px(12), 0))

        self._search_bar(main)
        self._reader_bar(main)

        self.content = tk.Frame(main, bg=BG)
        self.content.pack(fill="both", expand=True)
        self.content.columnconfigure(0, weight=3)
        self.content.columnconfigure(1, weight=2, minsize=self._px(270))
        self.content.rowconfigure(0, weight=1)
        self._results_card()
        self._detail_panel()
        self._set_mode("search")
        self._select(None)

    def _rail(self):
        rail = tk.Frame(self.root, bg=GREEN, width=170)
        rail.pack(side="left", fill="y")
        rail.pack_propagate(False)
        self.label(rail, "寻经", 30, "#F3EAD3", True).pack(anchor="w", padx=25, pady=(34, 0))
        self.label(rail, "B I B L E  F I N D E R", 8, "#ACC4B3").pack(anchor="w", padx=25, pady=(3, 32))
        tk.Frame(rail, bg="#3A5D4C", height=1).pack(fill="x", padx=24, pady=(0, 22))
        self.nav_buttons = {}
        for mode, label, action in [("search", "⌕  经文查询", self.return_search), ("chapter", "▤  整章阅读", self.open_reader), ("bookmarks", "☆  我的收藏", self.show_bookmarks)]:
            button = tk.Button(rail, text=label, command=action, anchor="w", bg=GREEN, fg="#CEDDCF", activebackground="#335B47",
                               activeforeground="white", bd=0, relief="flat", padx=18, pady=12, cursor="hand2", font=(FONT, 11))
            button.pack(fill="x", padx=12, pady=3)
            self._hover(button, GREEN, "#244D3D")
            self.nav_buttons[mode] = button
        self.label(rail, "66 卷 · 3 个译本\n完整经文，随时查找", 9, "#B1C7B7", justify="left").pack(side="bottom", anchor="w", padx=24, pady=(0, 25))
        about = tk.Button(rail, text="使用说明与数据来源", command=self.about, bg=GREEN, fg=GOLD, activebackground=GREEN,
                          activeforeground="white", bd=0, relief="flat", cursor="hand2", font=(FONT, 9, "underline"))
        about.pack(side="bottom", anchor="w", padx=21, pady=(0, 15))

        # Point-sized fonts grow with Windows DPI; pixel-sized frames do not.
        # Reserve every child's requested width plus its horizontal margins.
        rail.configure(width=max(
            170,
            *(child.winfo_reqwidth() + 2 * int(child.pack_info()["padx"])
              for child in rail.winfo_children()),
        ))

    def _search_bar(self, main):
        self.search_bar = tk.Frame(main, bg=BG)
        search_box = tk.Frame(self.search_bar, bg=PAPER, highlightbackground=LINE, highlightcolor=ACCENT, highlightthickness=1)
        search_box.pack(fill="x")
        self.label(search_box, "⌕", 15, MUTED).pack(side="left", padx=(self._px(14), 0))
        self.query_entry = tk.Entry(search_box, textvariable=self.query, font=(FONT, 13), fg=INK, bg=PAPER,
                                    insertbackground=GREEN, relief="flat", bd=0)
        self.query_entry.pack(side="left", fill="x", expand=True, padx=(self._px(8), self._px(12)), pady=self._px(9))
        self.query_entry.bind("<Return>", lambda _: self.search())
        self.query_entry.bind("<FocusIn>", lambda _: search_box.configure(highlightbackground=ACCENT))
        self.query_entry.bind("<FocusOut>", lambda _: search_box.configure(highlightbackground=LINE))
        self.search_button = self.button(search_box, "查找  →", self.search, "primary", padx=18)
        self.search_button.pack(side="right", padx=self._px(5), pady=self._px(5))

        filters = tk.Frame(self.search_bar, bg=BG)
        filters.pack(fill="x", pady=(self._px(9), 0))
        self.label(filters, "关键词范围", 9, MUTED).pack(side="left", padx=(0, self._px(7)))
        self.scope_box = ttk.Combobox(filters, textvariable=self.scope, values=["整本圣经", "旧约", "新约", *[b[1] for b in BOOKS]],
                                      state="readonly", width=12, font=(FONT, 10))
        self.scope_box.pack(side="left", padx=(0, self._px(18)))
        self.scope_box.bind("<<ComboboxSelected>>", lambda _: self.search())
        self.label(filters, "试试", 9, MUTED).pack(side="left", padx=(0, self._px(4)))
        for example in ("约 3:16", "John 3:16-18", "诗篇 23", "先知"):
            chip = self.button(filters, example, lambda q=example: self.run_example(q), "secondary", size=9, padx=10, pady=3)
            chip.configure(fg="#45694F")
            chip.pack(side="left", padx=(self._px(4), 0))

    def _reader_bar(self, main):
        self.reader_bar = tk.Frame(main, bg=BG)
        self.label(self.reader_bar, "书卷", 9, MUTED).pack(side="left", padx=(0, self._px(7)))
        self.book_box = ttk.Combobox(self.reader_bar, textvariable=self.read_book, values=[b[1] for b in BOOKS],
                                     width=14, state="readonly", font=(FONT, 10))
        self.book_box.pack(side="left", padx=(0, self._px(14)))
        self.book_box.bind("<<ComboboxSelected>>", self.reader_book_changed)
        self.label(self.reader_bar, "第", 10).pack(side="left", padx=(0, self._px(6)))
        self.chapter_box = ttk.Combobox(self.reader_bar, textvariable=self.read_chapter, values=list(range(1, 22)),
                                        width=4, state="readonly", font=(FONT, 10))
        self.chapter_box.pack(side="left", padx=(0, self._px(6)))
        self.chapter_box.bind("<<ComboboxSelected>>", lambda _: self.read_chosen())
        self.label(self.reader_bar, "章", 10).pack(side="left")
        self.button(self.reader_bar, "阅读", self.read_chosen, "primary", padx=16, pady=5).pack(side="left", padx=self._px(14))

    def _results_card(self):
        card = tk.Frame(self.content, bg=PAPER, highlightbackground=LINE, highlightthickness=1)
        card.grid(row=0, column=0, sticky="nsew", padx=(0, self._px(14)))
        card.columnconfigure(0, weight=1)
        card.rowconfigure(2, weight=1)
        heading = tk.Frame(card, bg=PAPER)
        heading.grid(row=0, column=0, sticky="ew", padx=self._px(16), pady=(self._px(10), self._px(8)))
        self.result_title = self.label(heading, "查询结果", 12, bold=True)
        self.result_title.pack(side="left")
        self.result_meta = self.label(heading, "", 9, MUTED)
        self.result_meta.pack(side="left", padx=(self._px(10), 0), pady=(self._px(3), 0))
        self.font_up = self.button(heading, "A+", lambda: self.resize_font(1), "ghost", size=10, padx=7, pady=1)
        self.font_up.pack(side="right")
        self.font_down = self.button(heading, "A−", lambda: self.resize_font(-1), "ghost", size=9, padx=7, pady=2)
        self.font_down.pack(side="right", padx=(0, self._px(2)))
        self.label(heading, "字号", 9, MUTED).pack(side="right", padx=(0, self._px(4)))
        tk.Frame(card, bg=LINE, height=1).grid(row=1, column=0, sticky="ew", padx=self._px(16))

        text_frame = tk.Frame(card, bg=PAPER)
        text_frame.grid(row=2, column=0, sticky="nsew", padx=(self._px(6), self._px(3)), pady=(self._px(4), 0))
        size = self.preferences.font_size
        self.results_text = tk.Text(text_frame, wrap="word", bg=PAPER, fg=INK, font=(FONT, size), relief="flat", bd=0,
                                    padx=0, pady=self._px(4), spacing1=0, spacing2=self._px(3), spacing3=0, cursor="arrow",
                                    state="disabled", width=26, height=4, exportselection=False, takefocus=1,
                                    highlightthickness=0)
        self.results_text.pack(side="left", fill="both", expand=True)
        self.results_text.bind("<Button-1>", lambda _: self.results_text.focus_set(), add="+")
        scrollbar = ttk.Scrollbar(text_frame, command=self.results_text.yview)
        self.results_text.configure(yscrollcommand=lambda first, last: self._autoscroll(scrollbar, self.results_text, first, last))
        margin = self._px(12)
        self.results_text.tag_configure("row", lmargin1=margin, lmargin2=margin, rmargin=margin)
        self.results_text.tag_configure("reference", foreground=ACCENT, spacing1=self._px(12), spacing3=self._px(3))
        self.results_text.tag_configure("body", spacing3=self._px(12))
        self.results_text.tag_configure("muted", foreground=MUTED, lmargin1=margin, lmargin2=margin, rmargin=margin, spacing1=self._px(4))
        self.results_text.tag_configure("match", background=MATCH, foreground=INK)
        self.results_text.tag_configure("selected", background=SELECTED, lmargincolor=SELECTED, rmargincolor=SELECTED)

        pager = tk.Frame(card, bg="#F3F6F0")
        pager.grid(row=3, column=0, sticky="ew", padx=1, pady=1)
        tk.Frame(pager, bg=LINE, height=1).pack(side="top", fill="x")
        self.previous_button = self.button(pager, "← 上一页", lambda: self.navigate(-1), padx=12, pady=5)
        self.previous_button.pack(side="left", padx=self._px(10), pady=self._px(7))
        self.page_label = self.label(pager, "1 / 1", 9, MUTED)
        self.page_label.pack(side="left", expand=True)
        self.next_button = self.button(pager, "下一页 →", lambda: self.navigate(1), padx=12, pady=5)
        self.next_button.pack(side="right", padx=self._px(10), pady=self._px(7))

    def _detail_panel(self):
        pad = self._px(18)
        detail = tk.Frame(self.content, bg=PANEL, padx=pad, pady=self._px(14))
        detail.grid(row=0, column=1, sticky="nsew")
        detail.columnconfigure(0, weight=1)
        self.detail = detail
        self.label(detail, "选中经文", 9, "#6E7F67").grid(row=0, column=0, sticky="w")
        self.detail_title = self.label(detail, "点击左侧经文", 15, bold=True, anchor="w", justify="left")
        self.detail_title.grid(row=1, column=0, sticky="ew", pady=(self._px(6), 0))
        self.detail_version = self.label(detail, "", 9, MUTED, anchor="w")
        self.detail_version.grid(row=2, column=0, sticky="ew", pady=(self._px(2), self._px(10)))
        tk.Frame(detail, bg="#CEDBC6", height=1).grid(row=3, column=0, sticky="ew", pady=(0, self._px(10)))

        text_frame = tk.Frame(detail, bg=PANEL)
        text_frame.grid(row=4, column=0, sticky="nsew")
        self.detail_text = tk.Text(text_frame, wrap="word", bg=PANEL, fg=GREEN, relief="flat", bd=0, spacing2=self._px(4),
                                   spacing3=self._px(6), height=3, width=20, state="disabled", exportselection=False,
                                   highlightthickness=0, cursor="arrow")
        detail_scroll = ttk.Scrollbar(text_frame, command=self.detail_text.yview, style="Panel.Vertical.TScrollbar")
        self.detail_text.configure(yscrollcommand=lambda first, last: self._autoscroll(detail_scroll, self.detail_text, first, last))
        self.detail_text.pack(side="left", fill="both", expand=True)
        self.detail_scroll = detail_scroll

        actions = tk.Frame(detail, bg=PANEL)
        actions.grid(row=5, column=0, sticky="ew", pady=(self._px(12), self._px(8)))
        actions.columnconfigure((0, 1), weight=1, uniform="actions")
        self.copy_button = self.button(actions, "⧉  复制经文", self.copy_verse)
        self.copy_button.grid(row=0, column=0, sticky="ew", padx=(0, self._px(4)))
        self.bookmark_button = self.button(actions, "☆  收藏", self.toggle_bookmark)
        self.bookmark_button.grid(row=0, column=1, sticky="ew", padx=(self._px(4), 0))
        self.context_button = self.button(detail, "阅读整章，查看上下文  →", self.read_selected, "primary", pady=8)
        self.context_button.grid(row=6, column=0, sticky="ew")
        self.label(detail, "↑ ↓ 切换经文 · 双击打开整章", 8, "#7F8D80").grid(row=7, column=0, sticky="w", pady=(self._px(8), 0))
        # The text row absorbs any shortage, but never below three lines, so the
        # actions below it always stay inside the panel.
        detail.rowconfigure(4, weight=1)
        self._apply_text_fonts()
        detail.bind("<Configure>", lambda event: self.detail_title.configure(wraplength=max(160, event.width - 2 * pad)))

    def _autoscroll(self, scrollbar, target, first, last):
        # Stable: hiding the bar only widens the text, so it can never start overflowing again.
        scrollbar.set(first, last)
        if float(first) <= 0 and float(last) >= 1:
            scrollbar.pack_forget()
        elif not scrollbar.winfo_manager():
            scrollbar.pack(side="right", fill="y", before=target)

    def _apply_text_fonts(self):
        size = self.preferences.font_size
        self.results_text.configure(font=(FONT, size))
        self.results_text.tag_configure("reference", font=(FONT, max(9, size - 2), "bold"))
        self.detail_text.configure(font=(FONT, size + 1))
        line = tkfont.Font(root=self.root, family=FONT, size=size + 1).metrics("linespace") + self._px(4)
        self.detail.rowconfigure(4, minsize=3 * line + self._px(6))
        self._enable(self.font_down, size > 10)
        self._enable(self.font_up, size < 20)

    # ----- state -----

    def version_id(self):
        return next(k for k, v in VERSIONS.items() if v == self.version.get())

    def scope_id(self):
        value = self.scope.get()
        if value in ("整本圣经", "旧约", "新约"):
            return {"整本圣经": "all", "旧约": "old", "新约": "new"}[value]
        return next(b[0] for b in BOOKS if b[1] == value)

    def _set_mode(self, mode):
        self.mode = mode
        for key, button in self.nav_buttons.items():
            active = key == mode
            self._set_base(button, "#355D48" if active else GREEN, fg="white" if active else "#CEDDCF")
        title, subtitle = MODES[mode]
        self.page_title.configure(text=title)
        self.page_subtitle.configure(text=subtitle)
        for bar, bar_mode in ((self.search_bar, "search"), (self.reader_bar, "chapter")):
            if mode == bar_mode:
                bar.pack(fill="x", pady=(0, self._px(12)), before=self.content)
            else:
                bar.pack_forget()

    def focus_search(self, _=None):
        if self.mode != "search":
            self.return_search()
        self.query_entry.focus_set()
        self.query_entry.selection_range(0, "end")
        return "break"

    def _arrow(self, event, direction):
        if isinstance(event.widget, (tk.Entry, ttk.Entry, ttk.Combobox, tk.Listbox)):
            return None
        self.move_selection(direction)
        return "break"

    def move_selection(self, direction):
        if not self.rows:
            return
        index = self.rows.index(self.selected) + direction if self.selected in self.rows else 0
        self._select(self.rows[max(0, min(len(self.rows) - 1, index))])
        self._see_selected()

    def run_example(self, query):
        self.query.set(query)
        self.scope.set("整本圣经")
        self.search()

    def search(self, page=1, use_last=False):
        self.generation += 1
        generation = self.generation
        self._set_mode("search")
        self.result = None
        self._render(())
        self.previous_button.configure(text="← 上一页")
        self.next_button.configure(text="下一页 →")
        self._enable(self.previous_button, False)
        self._enable(self.next_button, False)
        self.page_label.configure(text="查询中…")
        self.result_title.configure(text="正在查找…")
        self.result_meta.configure(text="")
        if not use_last:
            self.last_search = (self.query.get(), self.version_id(), self.scope_id())
        query, version, scope = self.last_search
        self.result_query = query
        self.status.set("正在查询本机经文库…")
        future = self.executor.submit(self.bible.search, query, version, scope, page)
        future.add_done_callback(lambda f: self.events.put((generation, f)))

    def _poll(self):
        while True:
            try:
                generation, future = self.events.get_nowait()
            except queue.Empty:
                break
            if generation != self.generation:
                continue
            try:
                self.result = future.result()
            except Exception as error:
                self.result = None
                self.result_title.configure(text="请调整查询")
                self._render((), f"⚠  {error}\n\n示例：约 3:16 · John 3:16-18 · 约3:36-4:2 · 诗篇 23 · 先知")
                self.page_label.configure(text="—")
                self.status.set("查询未完成 · 请检查输入后重试")
                continue
            result = self.result
            self.result_title.configure(text=f"找到 {result.total:,} 节经文")
            self.result_meta.configure(text=f"{result.elapsed_ms:.0f} 毫秒")
            self._render(result.verses, "没有找到匹配经文。\n\n请缩短关键词，检查简体 / 繁体是否与译本一致，或调整查询范围。", "" if result.reference else self.result_query)
            self.page_label.configure(text=f"第 {result.page} / {result.pages} 页")
            self._enable(self.previous_button, result.page > 1)
            self._enable(self.next_button, result.page < result.pages)
            hint = "经文出处查询 · 已按指定书卷定位" if result.reference else "关键词查询 · 按书卷顺序排列"
            self.status.set(f"{hint} · {VERSIONS[self.last_search[1]]}")
        if not self.closed:
            self._poll_id = self.root.after(40, self._poll)

    def _render(self, verses, empty_message="", highlight="", selected_key=None):
        self.rows = tuple(verses)
        text = self.results_text
        text.configure(state="normal")
        text.delete("1.0", "end")
        for tag in text.tag_names():
            if tag.startswith("row_"):
                text.tag_delete(tag)
        for index, verse in enumerate(self.rows):
            tag = f"row_{index}"
            text.insert("end", verse.reference + "\n", (tag, "row", "reference"))
            text.insert("end", verse.text + "\n", (tag, "row", "body"))
            text.tag_bind(tag, "<Button-1>", lambda _, v=verse: self._select(v))
            text.tag_bind(tag, "<Double-Button-1>", lambda _, v=verse: self.read_chapter_at(v.book, v.chapter, v.verse, v.version))
            text.tag_bind(tag, "<Enter>", lambda _: text.configure(cursor="hand2"))
            text.tag_bind(tag, "<Leave>", lambda _: text.configure(cursor="arrow"))
        if not self.rows and empty_message:
            text.insert("end", empty_message, ("muted",))
        if highlight and self.rows:
            # Highlight original display text. Normalized punctuation may match without a highlight.
            word = normalize_keyword(highlight, self.rows[0].version)
            index = "1.0"
            while word:
                found = text.search(word, index, stopindex="end", nocase=True, exact=True)
                if not found:
                    break
                end = f"{found}+{len(word)}c"
                text.tag_add("match", found, end)
                index = end
        text.configure(state="disabled")
        text.yview_moveto(0)
        chosen = next((v for v in self.rows if v.key == selected_key), self.rows[0] if self.rows else None)
        self._select(chosen)
        if selected_key and chosen:
            self._see_selected()

    def _select(self, verse):
        self.selected = verse
        self.results_text.tag_remove("selected", "1.0", "end")
        if verse and verse in self.rows:
            ranges = self.results_text.tag_ranges(f"row_{self.rows.index(verse)}")
            if ranges:
                self.results_text.tag_add("selected", ranges[0], ranges[-1])
                self.results_text.tag_lower("selected", "match")
        self.detail_title.configure(text=verse.reference if verse else "选择一节经文")
        self.detail_version.configure(text=VERSIONS[verse.version] if verse else "在左侧点击查询结果")
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0", verse.text if verse else "这里可以复制、收藏经文，或打开整章阅读上下文。")
        self.detail_text.configure(state="disabled", fg=GREEN if verse else MUTED)
        self.detail_text.yview_moveto(0)
        self._enable(self.copy_button, bool(verse))
        self._enable(self.bookmark_button, bool(verse))
        self._enable(self.context_button, bool(verse) and self.mode != "chapter")
        self.context_button.configure(text="正在阅读整章" if self.mode == "chapter" else "阅读整章，查看上下文  →")
        self._show_bookmark_state(bool(verse) and verse.key in self.preferences.bookmarks)

    def _show_bookmark_state(self, saved):
        if saved:
            self._set_base(self.bookmark_button, "#FBF3DF", text="★  已收藏", fg="#8A6516", highlightbackground=GOLD, activebackground="#F6E9C6", activeforeground="#8A6516")
        else:
            self._set_base(self.bookmark_button, PAPER, text="☆  收藏", fg=GREEN, highlightbackground=LINE, activebackground=SOFT, activeforeground=GREEN)

    def _see_selected(self):
        if self.selected in self.rows:
            ranges = self.results_text.tag_ranges(f"row_{self.rows.index(self.selected)}")
            if ranges:
                self.results_text.see(ranges[-1])
                self.results_text.see(ranges[0])

    def navigate(self, direction):
        if self.mode == "search" and self.result:
            self.search(self.result.page + direction, True)
        elif self.mode == "chapter":
            target = self.bible.adjacent_chapter(self.version_id(), *self.chapter_location, direction)
            if target:
                self.read_chapter_at(*target)
        elif self.mode == "bookmarks":
            self.show_bookmarks(self.bookmark_page + direction)

    def return_search(self):
        query, version, scope = self.last_search
        self.query.set(query)
        self.version.set(VERSIONS[version])
        self.scope.set({"all": "整本圣经", "old": "旧约", "new": "新约"}.get(scope, book_name(scope) if isinstance(scope, int) else "整本圣经"))
        self.search(use_last=True)

    def open_reader(self):
        if self.selected:
            self.read_selected()
        else:
            self.read_chapter_at(*self.chapter_location)

    def reader_book_changed(self, _=None):
        self.read_chapter.set("1")
        self.read_chosen()

    def read_chosen(self):
        book = next(b[0] for b in BOOKS if b[1] == self.read_book.get())
        self.read_chapter_at(book, int(self.read_chapter.get()))

    def read_selected(self):
        if self.selected:
            v = self.selected
            self.read_chapter_at(v.book, v.chapter, v.verse, v.version)

    def read_chapter_at(self, book, chapter, verse=1, version=None):
        version = version or self.version_id()
        try:
            rows = self.bible.chapter(version, book, chapter)
        except ValueError as error:
            self.status.set(str(error))
            return
        self.generation += 1
        self.version.set(VERSIONS[version])
        self._set_mode("chapter")
        self.chapter_location = (book, chapter)
        self.read_book.set(book_name(book))
        self.read_chapter.set(str(chapter))
        self.chapter_box.configure(values=list(range(1, self.bible.chapter_count(version, book) + 1)))
        self.result_title.configure(text=f"{book_name(book, version)} 第 {chapter} 章")
        self.result_meta.configure(text=f"{len(rows)} 节")
        self._render(rows, selected_key=f"{version}:{book}:{chapter}:{verse}")
        self.previous_button.configure(text="← 上一章")
        self.next_button.configure(text="下一章 →")
        self._enable(self.previous_button, bool(self.bible.adjacent_chapter(version, book, chapter, -1)))
        self._enable(self.next_button, bool(self.bible.adjacent_chapter(version, book, chapter, 1)))
        self.page_label.configure(text=f"{book_name(book, version)} · 第 {chapter} 章")
        self.status.set(f"整章阅读 · {VERSIONS[version]} · 点击经文可复制或收藏")

    def change_version(self, _=None):
        if self.mode == "chapter":
            self.read_chapter_at(*self.chapter_location, self.selected.verse if self.selected else 1)
        elif self.mode == "bookmarks":
            self.show_bookmarks()
        else:
            self.search()
        self._save_preferences()

    def show_bookmarks(self, page=1):
        self.generation += 1
        self._set_mode("bookmarks")
        rows = []
        for key in reversed(self.preferences.bookmarks):
            version, book, chapter, verse = key.split(":")
            item = self.bible.get_verse(version, int(book), int(chapter), int(verse))
            if item:
                rows.append(item)
        self.bookmark_pages = max(1, (len(rows) + PAGE_SIZE - 1) // PAGE_SIZE)
        self.bookmark_page = max(1, min(page, self.bookmark_pages))
        start = (self.bookmark_page - 1) * PAGE_SIZE
        self.result_title.configure(text=f"我的收藏 · {len(rows)} 节")
        self.result_meta.configure(text="最近收藏优先")
        self._render(rows[start:start + PAGE_SIZE], "还没有收藏经文。\n\n查找经文后，点击右侧「☆ 收藏」或按 Ctrl+D，即可保存在本机。")
        self.previous_button.configure(text="← 上一页")
        self.next_button.configure(text="下一页 →")
        self._enable(self.previous_button, self.bookmark_page > 1)
        self._enable(self.next_button, self.bookmark_page < self.bookmark_pages)
        self.page_label.configure(text=f"第 {self.bookmark_page} / {self.bookmark_pages} 页")
        self.status.set("收藏包含全部译本 · 仅保存在本机，随软件数据文件夹迁移")

    def copy_verse(self):
        if self.selected:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.selected.citation)
            self.root.update_idletasks()
            self.status.set(f"已复制 {self.selected.reference}，包含译本与出处")

    def toggle_bookmark(self):
        if not self.selected:
            return
        try:
            added = self.preferences.toggle_bookmark(self.selected.key)
        except OSError as error:
            messagebox.showerror("未能保存收藏", f"{error}\n\n请将软件放到可写入的文件夹后重试。", parent=self.root)
            return
        self._show_bookmark_state(added)
        if self.mode == "bookmarks":
            self.show_bookmarks(self.bookmark_page)
        self.status.set("已收藏到本机" if added else "已取消收藏")

    def resize_font(self, direction):
        self.preferences.font_size = max(10, min(20, self.preferences.font_size + direction))
        self._apply_text_fonts()
        self._save_preferences()

    def _save_preferences(self):
        self.preferences.version = self.version_id()
        try:
            self.preferences.save()
        except OSError:
            self.status.set("当前偏好未保存 · 数据文件夹不可写或已有文件损坏")

    def about(self):
        messagebox.showinfo("关于寻经", f"寻经 Bible Finder {__version__}\n\n查询示例：约 3:16 / 約3:16 / John 3:16-18\n整章：诗篇23；跨章：约3:36-4:2\n中文章、节编号使用阿拉伯数字。\n关键词按所选译本的字面文本匹配，区分简体与繁体。\n英文搜索忽略大小写。经文出处优先于关键词范围。\n\nCtrl+F 回到查询并聚焦；Enter 搜索；Ctrl+D 收藏当前经文。\n↑ / ↓ 切换选中经文；双击结果打开整章。字号 A− / A+ 调整阅读字号。\n\n数据：GetBible v2 / CrossWire；中文和合本简繁体、\nWorld English Bible 均标注 Public Domain。\n仅整理排版空白，译本差异与节数以原数据为准。\n\n收藏位置：{self.preferences.path}\n\n本软件独立开发，与参考网站无隶属关系。", parent=self.root)

    def close(self):
        self.closed = True
        self.generation += 1
        self.root.after_cancel(self._poll_id)
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()
