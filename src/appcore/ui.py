from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import queue
import tkinter as tk
from tkinter import messagebox, ttk

from . import __version__
from .books import BOOKS, book_name
from .engine import Bible, PAGE_SIZE, VERSIONS, normalize_keyword
from .preferences import Preferences

BG = "#F6F5F0"
INK = "#243C32"
GREEN = "#183E32"
MUTED = "#758278"
LINE = "#DDE3D9"
PAPER = "#FFFFFF"
GOLD = "#DABC79"
FONT = "Microsoft YaHei UI"


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
        self.version = tk.StringVar(value=VERSIONS[self.preferences.version])
        self.query = tk.StringVar(value="约 3:16")
        self.scope = tk.StringVar(value="整本圣经")
        self.read_book = tk.StringVar(value="约翰福音")
        self.read_chapter = tk.StringVar(value="3")
        self.status = tk.StringVar(value="准备就绪 · 经文在本机离线查询")
        self.root.title(f"寻经 Bible Finder · {__version__}")
        self.root.geometry("1240x810")
        self.root.minsize(1000, 690)
        self.root.configure(bg=BG)
        self.root.option_add("*Font", (FONT, 10))
        self.root.option_add("*TCombobox*Listbox.font", (FONT, 10))
        self._styles()
        self._layout()
        self.root.bind("<Control-f>", self.focus_search)
        self.root.bind("<Control-d>", lambda _: self.toggle_bookmark())
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._poll_id = self.root.after(40, self._poll)
        self.search()
        if self.preferences.warning:
            self.root.after(200, lambda: messagebox.showwarning("收藏文件", self.preferences.warning, parent=root))

    def _styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TCombobox", fieldbackground=PAPER, background=PAPER, foreground=INK, arrowcolor=GREEN, bordercolor=LINE, lightcolor=LINE, darkcolor=LINE, padding=7)
        style.map("TCombobox", fieldbackground=[("readonly", PAPER)], foreground=[("readonly", INK)], selectbackground=[("readonly", PAPER)], selectforeground=[("readonly", INK)])
        style.configure("Vertical.TScrollbar", gripcount=0, background="#CAD5CB", troughcolor=PAPER, bordercolor=PAPER, arrowcolor=MUTED, width=11)

    def label(self, parent, text="", size=10, color=INK, bold=False, bg=None, **kwargs):
        return tk.Label(parent, text=text, bg=bg or parent.cget("bg"), fg=color, font=(FONT, size, "bold" if bold else "normal"), **kwargs)

    def button(self, parent, text, command, primary=False, **kwargs):
        return tk.Button(parent, text=text, command=command, relief="flat", bd=0, bg=GREEN if primary else "#EAF0E7", fg="white" if primary else GREEN, activebackground="#2B5644" if primary else "#D9E5D5", activeforeground="white" if primary else GREEN, cursor="hand2", padx=14, pady=9, font=(FONT, 10), disabledforeground="#9CA89E", **kwargs)

    def _layout(self):
        rail = tk.Frame(self.root, bg=GREEN, width=170)
        rail.pack(side="left", fill="y")
        rail.pack_propagate(False)
        self.label(rail, "寻经", 30, "#F3EAD3", True).pack(anchor="w", padx=25, pady=(34, 0))
        self.label(rail, "B I B L E  F I N D E R", 8, "#ACC4B3").pack(anchor="w", padx=25, pady=(3, 32))
        tk.Frame(rail, bg="#3A5D4C", height=1).pack(fill="x", padx=24, pady=(0, 22))
        self.nav_buttons = {}
        for mode, label, action in [("search", "经文查询", self.return_search), ("chapter", "整章阅读", self.open_reader), ("bookmarks", "我的收藏", self.show_bookmarks)]:
            button = tk.Button(rail, text=label, command=action, anchor="w", bg=GREEN, fg="#CEDDCF", activebackground="#335B47", activeforeground="white", bd=0, padx=22, pady=14, cursor="hand2", font=(FONT, 11))
            button.pack(fill="x", padx=12, pady=4)
            self.nav_buttons[mode] = button
        self.label(rail, "66 卷 · 3 个译本\n完整经文，随时查找", 9, "#B1C7B7", justify="left").pack(side="bottom", anchor="w", padx=24, pady=(0, 25))
        about = tk.Button(rail, text="使用说明与数据来源", command=self.about, bg=GREEN, fg="#DABC79", activebackground=GREEN, activeforeground="white", bd=0, cursor="hand2", font=(FONT, 9))
        about.pack(side="bottom", anchor="w", padx=21, pady=(0, 15))

        main = tk.Frame(self.root, bg=BG)
        main.pack(side="left", fill="both", expand=True, padx=30, pady=22)
        top = tk.Frame(main, bg=BG)
        top.pack(fill="x")
        self.label(top, "SCRIPTURE / 圣经工具", 9, MUTED).pack(side="left")
        self.label(top, "●  离线可用", 9, "#427354").pack(side="right")
        self.label(main, "查找圣经经文", 24, bold=True).pack(anchor="w", pady=(15, 4))
        self.label(main, "从一个关键词，到完整的上下文。", 10, MUTED).pack(anchor="w", pady=(0, 18))

        search_box = tk.Frame(main, bg=PAPER, highlightbackground=LINE, highlightthickness=1)
        search_box.pack(fill="x")
        self.query_entry = tk.Entry(search_box, textvariable=self.query, font=(FONT, 14), fg=INK, bg=PAPER, insertbackground=GREEN, relief="flat", bd=0)
        self.query_entry.pack(side="left", fill="x", expand=True, padx=16, pady=15)
        self.query_entry.bind("<Return>", lambda _: self.search())
        self.search_button = self.button(search_box, "查找经文  →", self.search, True)
        self.search_button.pack(side="right", padx=7, pady=7)
        filters = tk.Frame(main, bg=BG)
        filters.pack(fill="x", pady=(12, 0))
        self.label(filters, "译本", 9, MUTED).pack(side="left", padx=(0, 7))
        version_box = ttk.Combobox(filters, textvariable=self.version, values=list(VERSIONS.values()), state="readonly", width=23)
        version_box.pack(side="left", padx=(0, 20))
        version_box.bind("<<ComboboxSelected>>", self.change_version)
        self.label(filters, "关键词范围", 9, MUTED).pack(side="left", padx=(0, 7))
        self.scope_box = ttk.Combobox(filters, textvariable=self.scope, values=["整本圣经", "旧约", "新约", *[b[1] for b in BOOKS]], state="readonly", width=17)
        self.scope_box.pack(side="left")
        self.scope_box.bind("<<ComboboxSelected>>", lambda _: self.search())
        examples = tk.Frame(main, bg=BG)
        examples.pack(fill="x", pady=(8, 15))
        self.label(examples, "试试", 9, MUTED).pack(side="left", padx=(0, 6))
        for example in ("约 3:16", "John 3:16-18", "诗篇 23", "先知"):
            tk.Button(examples, text=example, command=lambda q=example: self.run_example(q), bg=BG, fg="#52725D", activebackground=BG, activeforeground=GREEN, bd=0, cursor="hand2", font=(FONT, 9), padx=8).pack(side="left")

        self.reader_bar = tk.Frame(main, bg=BG)
        self.label(self.reader_bar, "前往", 9, MUTED).pack(side="left", padx=(0, 8))
        self.book_box = ttk.Combobox(self.reader_bar, textvariable=self.read_book, values=[b[1] for b in BOOKS], width=16, state="readonly")
        self.book_box.pack(side="left", padx=(0, 8))
        self.book_box.bind("<<ComboboxSelected>>", self.reader_book_changed)
        self.chapter_box = ttk.Combobox(self.reader_bar, textvariable=self.read_chapter, values=list(range(1, 22)), width=5, state="readonly")
        self.chapter_box.pack(side="left", padx=(0, 8))
        self.chapter_box.bind("<<ComboboxSelected>>", lambda _: self.read_chosen())
        self.label(self.reader_bar, "章", 10).pack(side="left")
        self.button(self.reader_bar, "阅读", self.read_chosen).pack(side="left", padx=10)

        self.content = tk.Frame(main, bg=BG)
        self.content.pack(fill="both", expand=True)
        self.content.columnconfigure(0, weight=3)
        self.content.columnconfigure(1, weight=2, minsize=280)
        self.content.rowconfigure(0, weight=1)
        left = tk.Frame(self.content, bg=PAPER, highlightbackground=LINE, highlightthickness=1)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        heading = tk.Frame(left, bg=PAPER)
        heading.pack(fill="x", padx=18, pady=(14, 8))
        self.result_title = self.label(heading, "查询结果", 12, bold=True)
        self.result_title.pack(side="left")
        self.result_meta = self.label(heading, "", 9, MUTED)
        self.result_meta.pack(side="right")
        tk.Frame(left, bg=LINE, height=1).pack(fill="x", padx=18)
        text_frame = tk.Frame(left, bg=PAPER)
        text_frame.pack(fill="both", expand=True, padx=(18, 3), pady=(8, 0))
        self.results_text = tk.Text(text_frame, wrap="word", bg=PAPER, fg=INK, font=(FONT, self.preferences.font_size), relief="flat", bd=0, padx=0, pady=5, spacing1=3, spacing3=7, cursor="arrow", state="disabled", width=26, height=8, exportselection=False)
        self.results_text.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(text_frame, command=self.results_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.results_text.configure(yscrollcommand=scrollbar.set)
        self.results_text.tag_configure("reference", foreground="#417356", font=(FONT, 10, "bold"), spacing1=12, spacing3=5)
        self.results_text.tag_configure("muted", foreground=MUTED)
        self.results_text.tag_configure("match", background="#F3E5BC", foreground=INK)
        self.results_text.tag_configure("selected", background="#EAF2E7")
        paging = tk.Frame(left, bg="#FBFCF9")
        paging.pack(fill="x", side="bottom", padx=1, pady=1)
        self.previous_button = self.button(paging, "← 上一页", lambda: self.navigate(-1))
        self.previous_button.pack(side="left", padx=10, pady=8)
        self.page_label = self.label(paging, "1 / 1", 9, MUTED)
        self.page_label.pack(side="left", expand=True)
        self.next_button = self.button(paging, "下一页 →", lambda: self.navigate(1))
        self.next_button.pack(side="right", padx=10, pady=8)
        # Reserve the pager before giving the remaining space to the text viewport.
        text_frame.pack_forget()
        text_frame.pack(fill="both", expand=True, padx=(18, 3), pady=(8, 0))

        detail = tk.Frame(self.content, bg="#EAF0E5", padx=22, pady=19)
        detail.grid(row=0, column=1, sticky="nsew")
        self.label(detail, "选 中 经 文", 9, "#78866C").pack(anchor="w")
        self.detail_title = self.label(detail, "点击左侧经文", 16, bold=True, anchor="w", justify="left")
        self.detail_title.pack(fill="x", pady=(17, 4))
        self.detail_version = self.label(detail, "", 9, MUTED)
        self.detail_version.pack(anchor="w", pady=(0, 14))
        tk.Frame(detail, bg="#CEDBC6", height=1).pack(fill="x", pady=(0, 15))
        self.detail_text = tk.Text(detail, wrap="word", bg="#EAF0E5", fg=GREEN, font=(FONT, self.preferences.font_size + 1), relief="flat", bd=0, spacing3=8, height=5, width=20, state="disabled", exportselection=False)
        self.detail_text.pack(fill="both", expand=True)
        self.detail_text.bind("<MouseWheel>", lambda e: self.detail_text.yview_scroll(int(-e.delta / 120), "units"))
        actions = tk.Frame(detail, bg="#EAF0E5")
        actions.pack(fill="x", pady=(16, 8))
        self.copy_button = self.button(actions, "复制经文", self.copy_verse)
        self.copy_button.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.bookmark_button = self.button(actions, "☆ 收藏", self.toggle_bookmark)
        self.bookmark_button.pack(side="left", fill="x", expand=True)
        self.context_button = self.button(detail, "阅读整章，查看上下文  →", self.read_selected, True)
        self.context_button.pack(fill="x")
        font_bar = tk.Frame(detail, bg="#EAF0E5")
        font_bar.pack(fill="x", pady=(12, 0))
        self.label(font_bar, "阅读字号", 9, MUTED).pack(side="left")
        self.button(font_bar, "A−", lambda: self.resize_font(-1)).pack(side="left", padx=(12, 4))
        self.button(font_bar, "A+", lambda: self.resize_font(1)).pack(side="left")
        # Pack persistent actions first so high DPI / short windows shrink the
        # scrollable text area, never push essential controls out of view.
        self.detail_text.pack_forget()
        actions.pack_forget()
        self.context_button.pack_forget()
        font_bar.pack_forget()
        font_bar.pack(side="bottom", fill="x", pady=(12, 0))
        self.context_button.pack(side="bottom", fill="x")
        actions.pack(side="bottom", fill="x", pady=(12, 8))
        self.detail_text.pack(fill="both", expand=True)
        detail.bind("<Configure>", lambda event: self.detail_title.configure(wraplength=max(180, event.width - 44)))
        footer = tk.Frame(main, bg=BG)
        footer.pack(side="bottom", fill="x", pady=(13, 0))
        tk.Label(footer, textvariable=self.status, bg=BG, fg=MUTED, font=(FONT, 9), anchor="w").pack(side="left", fill="x", expand=True)
        self.label(footer, f"v{__version__}", 9, MUTED).pack(side="right", padx=(12, 0))
        self.content.pack_forget()
        self.content.pack(fill="both", expand=True)
        self._select(None)

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
            button.configure(bg="#355D48" if key == mode else GREEN, fg="white" if key == mode else "#CEDDCF")
        if mode == "chapter":
            self.reader_bar.pack(fill="x", pady=(0, 12), before=self.content)
        else:
            self.reader_bar.pack_forget()

    def focus_search(self, _=None):
        self.query_entry.focus_set()
        self.query_entry.selection_range(0, "end")
        return "break"

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
        self.previous_button.configure(state="disabled", text="← 上一页")
        self.next_button.configure(state="disabled", text="下一页 →")
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
                self._render((), str(error))
                self.page_label.configure(text="—")
                self.status.set("查询未完成 · 请检查输入后重试")
                continue
            result = self.result
            self.result_title.configure(text=f"找到 {result.total:,} 节经文")
            self.result_meta.configure(text=f"{result.elapsed_ms:.0f} 毫秒")
            self._render(result.verses, "没有找到匹配经文。\n\n请缩短关键词，检查简体 / 繁体是否与译本一致，或调整查询范围。", "" if result.reference else self.result_query)
            self.page_label.configure(text=f"{result.page} / {result.pages} 页")
            self.previous_button.configure(state="normal" if result.page > 1 else "disabled")
            self.next_button.configure(state="normal" if result.page < result.pages else "disabled")
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
            text.insert("end", verse.reference + "\n", (tag, "reference"))
            text.insert("end", verse.text + "\n\n", (tag,))
            text.tag_bind(tag, "<Button-1>", lambda _, v=verse: self._select(v))
            text.tag_bind(tag, "<Double-Button-1>", lambda _, v=verse: self.read_chapter_at(v.book, v.chapter, v.verse, v.version))
            text.tag_bind(tag, "<Enter>", lambda _: text.configure(cursor="hand2"))
            text.tag_bind(tag, "<Leave>", lambda _: text.configure(cursor="arrow"))
        if not self.rows:
            text.insert("end", "\n" + empty_message, ("muted",))
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
        self.detail_text.configure(state="disabled")
        for button in (self.copy_button, self.bookmark_button, self.context_button):
            button.configure(state="normal" if verse else "disabled")
        self.bookmark_button.configure(text="★ 已收藏" if verse and verse.key in self.preferences.bookmarks else "☆ 收藏")

    def _see_selected(self):
        if self.selected in self.rows:
            ranges = self.results_text.tag_ranges(f"row_{self.rows.index(self.selected)}")
            if ranges:
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
        self.previous_button.configure(text="← 上一章", state="normal" if self.bible.adjacent_chapter(version, book, chapter, -1) else "disabled")
        self.next_button.configure(text="下一章 →", state="normal" if self.bible.adjacent_chapter(version, book, chapter, 1) else "disabled")
        self.page_label.configure(text=f"第 {chapter} 章")
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
        self._render(rows[start:start + PAGE_SIZE], "还没有收藏经文。\n\n查找经文后，点击右侧「☆ 收藏」，即可保存在本机。")
        self.previous_button.configure(text="← 上一页", state="normal" if self.bookmark_page > 1 else "disabled")
        self.next_button.configure(text="下一页 →", state="normal" if self.bookmark_page < self.bookmark_pages else "disabled")
        self.page_label.configure(text=f"{self.bookmark_page} / {self.bookmark_pages} 页")
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
        self.bookmark_button.configure(text="★ 已收藏" if added else "☆ 收藏")
        if self.mode == "bookmarks":
            self.show_bookmarks(self.bookmark_page)
        self.status.set("已收藏到本机" if added else "已取消收藏")

    def resize_font(self, direction):
        self.preferences.font_size = max(10, min(20, self.preferences.font_size + direction))
        self.results_text.configure(font=(FONT, self.preferences.font_size))
        self.detail_text.configure(font=(FONT, self.preferences.font_size + 1))
        self._save_preferences()

    def _save_preferences(self):
        self.preferences.version = self.version_id()
        try:
            self.preferences.save()
        except OSError:
            self.status.set("当前偏好未保存 · 数据文件夹不可写或已有文件损坏")

    def about(self):
        messagebox.showinfo("关于寻经", f"寻经 Bible Finder {__version__}\n\n查询示例：约 3:16 / 約3:16 / John 3:16-18\n整章：诗篇23；跨章：约3:36-4:2\n中文章、节编号使用阿拉伯数字。\n关键词按所选译本的字面文本匹配，区分简体与繁体。\n英文搜索忽略大小写。经文出处优先于关键词范围。\n\nCtrl+F 聚焦查询；Enter 搜索；Ctrl+D 收藏当前经文。\n双击结果打开整章。点击 A− / A+ 调整字号。\n\n数据：GetBible v2 / CrossWire；中文和合本简繁体、\nWorld English Bible 均标注 Public Domain。\n仅整理排版空白，译本差异与节数以原数据为准。\n\n收藏位置：{self.preferences.path}\n\n本软件独立开发，与参考网站无隶属关系。", parent=self.root)

    def close(self):
        self.closed = True
        self.generation += 1
        self.root.after_cancel(self._poll_id)
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()
