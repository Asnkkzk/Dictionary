# -*- coding: utf-8 -*-
"""主词典窗口：字母序词表 + 搜索 + 释义详情 + 历史记录。"""
import tkinter as tk
from tkinter import ttk

from . import appearance
from . import database
from . import translator
from . import config as cfg

BG = "#2b2b2e"
FG = "#f0f0f0"
DIM = "#9e9ea7"
LIST_BG = "#232327"


def _parse_definitions(raw):
    if not raw:
        return []
    if isinstance(raw, list):
        data = raw
    else:
        data = translator.json_loads(raw)
    out = []
    for d in data:
        if isinstance(d, dict):
            out.append({
                "pos": d.get("pos", ""),
                "def": d.get("def", ""),
                "example": d.get("example", ""),
            })
    return out


class DictionaryWindow:
    def __init__(self, root, on_quit=None):
        self.root = root
        self.on_quit = on_quit
        self._view = "dict"  # dict | history
        self._items = []
        self._current = None

        root.title(cfg.APP_NAME)
        root.geometry("860x560")
        root.minsize(680, 440)
        root.configure(bg=BG)
        root.protocol("WM_DELETE_WINDOW", self.hide)

        self._build()

    # ---------------- 界面 ----------------

    def _build(self):
        # 菜单栏（明确的退出入口）
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="退出", command=self._quit_app)
        menubar.add_cascade(label="文件", menu=file_menu)
        daily_menu = tk.Menu(menubar, tearoff=0)
        daily_menu.add_command(label="查看今日单词", command=lambda: self.daily_callback())
        self.daily_enabled = tk.BooleanVar(value=cfg.get()["daily_word"].get("enabled", True))
        daily_menu.add_checkbutton(label="每日自动提醒", variable=self.daily_enabled,
            command=lambda: cfg.set_value("daily_word.enabled", self.daily_enabled.get()))
        hours = tk.Menu(daily_menu, tearoff=0)
        self.daily_hour = tk.IntVar(value=cfg.get()["daily_word"].get("hour", 9))
        for hour in range(24):
            hours.add_radiobutton(label="%02d:00" % hour, value=hour, variable=self.daily_hour,
                command=lambda selected=hour: self._toggle_daily_hour(selected))
        daily_menu.add_cascade(label="提醒时间（电脑本地时间）", menu=hours)
        menubar.add_cascade(label="每日一词", menu=daily_menu)
        looks = tk.Menu(menubar, tearoff=0)
        self.theme_mode = tk.StringVar(value=cfg.get().get("appearance", {}).get("mode", "dark"))
        for label, value in [("昼间 · 浅色", "light"), ("夜间 · 深色", "dark")]:
            looks.add_radiobutton(label=label, variable=self.theme_mode, value=value,
                                 command=self._change_theme)
        looks.add_separator()
        looks.add_command(label="自定义背景颜色…", command=self._choose_background)
        looks.add_command(label="恢复默认背景", command=self._reset_background)
        menubar.add_cascade(label="外观", menu=looks)
        self.root.config(menu=menubar)

        # 顶部工具栏
        bar = tk.Frame(self.root, bg=BG)
        bar.pack(fill="x", padx=10, pady=(10, 4))

        tk.Label(bar, text="搜索", bg=BG, fg=FG,
                 font=("Microsoft YaHei", 10)).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._reload())
        e = tk.Entry(bar, textvariable=self.search_var, bg=LIST_BG, fg=FG,
                     insertbackground=FG, relief="flat", font=("Microsoft YaHei", 10))
        e.pack(side="left", padx=(6, 12), ipady=3, fill="x", expand=True)

        self.letter_var = tk.StringVar(value="全部")
        self.dict_btn = tk.Button(bar, text="词典", command=self._set_dict,
                                  bg="#3b82f6", fg="#fff",
                                  relief="flat", font=("Microsoft YaHei", 10),
                                  padx=10, pady=3, cursor="hand2")
        self.dict_btn.pack(side="left", padx=2)
        self.hist_btn = tk.Button(bar, text="历史", command=self._set_history,
                                  bg="#3a3a3f", fg=FG, relief="flat",
                                  font=("Microsoft YaHei", 10), padx=10, pady=3,
                                  cursor="hand2")
        self.hist_btn.pack(side="left", padx=2)

        self.count_lbl = tk.Label(bar, text="", bg=BG, fg=DIM,
                                  font=("Microsoft YaHei", 9))
        self.count_lbl.pack(side="right")

        alphabet = tk.Frame(self.root, bg=BG)
        alphabet.pack(fill="x", padx=10, pady=4)
        self.letter_buttons = {}
        for i, letter in enumerate(["全部"] + list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")):
            button = tk.Button(alphabet, text=letter, width=3,
                               command=lambda value=letter: self._filter_letter(value),
                               bg=LIST_BG, fg=FG, relief="flat", cursor="hand2")
            button.grid(row=i // 14, column=i % 14, sticky="ew", padx=2, pady=2)
            alphabet.columnconfigure(i % 14, weight=1)
            self.letter_buttons[letter] = button

        # 主体：左列表 + 右详情
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        left = tk.Frame(body, bg=BG)
        left.pack(side="left", fill="y")
        self.listbox = tk.Listbox(left, bg=LIST_BG, fg=FG, selectbackground="#3b82f6",
                                  selectforeground="#ffffff", relief="flat",
                                  font=("Microsoft YaHei", 11), width=26,
                                  activestyle="none", highlightthickness=0)
        sb = tk.Scrollbar(left, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.listbox.pack(side="left", fill="both", expand=True)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)

        right = tk.Frame(body, bg="#232327")
        right.pack(side="left", fill="both", expand=True, padx=(10, 0))

        self.detail_text = tk.Text(right, bg="#232327", fg=FG, relief="flat",
                                   wrap="word", font=("Microsoft YaHei", 11),
                                   padx=14, pady=12, state="disabled")
        self.detail_text.pack(fill="both", expand=True)
        self.detail_text.tag_configure("title", foreground="#ffffff",
                                       font=("Segoe UI", 18, "bold"))
        self.detail_text.tag_configure("phonetic", foreground=DIM,
                                       font=("Segoe UI", 12))
        self.detail_text.tag_configure("translation", foreground="#7cc6fe",
                                       font=("Microsoft YaHei", 14))
        self.detail_text.tag_configure("pos", foreground="#f8b26a",
                                       font=("Microsoft YaHei", 11, "bold"))
        self.detail_text.tag_configure("def", foreground=FG)
        self.detail_text.tag_configure("example", foreground=DIM,
                                       font=("Microsoft YaHei", 10))
        self.detail_text.tag_configure("meta", foreground=DIM,
                                       font=("Microsoft YaHei", 9))

        # 详情底部操作按钮
        acts = tk.Frame(right, bg="#232327")
        acts.pack(side="bottom", fill="x", pady=(0, 8), before=self.detail_text)
        self.del_btn = tk.Button(acts, text="删除选中单词", command=self._delete_word,
                                 bg="#5a2a2a", fg="#ffb3b3", relief="flat",
                                 font=("Microsoft YaHei", 10), padx=10, pady=3,
                                 cursor="hand2")
        self.relookup_btn = tk.Button(acts, text="重新查询", command=self._relookup,
                                      bg="#3b82f6", fg="#fff", relief="flat",
                                      font=("Microsoft YaHei", 10), padx=10, pady=3,
                                      cursor="hand2")
        self.clear_hist_btn = tk.Button(acts, text="清空历史", command=self._clear_history,
                                        bg="#5a2a2a", fg="#ffb3b3", relief="flat",
                                        font=("Microsoft YaHei", 10), padx=10, pady=3,
                                        cursor="hand2")

        self._reload()

    def _change_theme(self):
        cfg.set_value("appearance.mode", self.theme_mode.get())
        appearance.apply(self.root)

    def _choose_background(self):
        from tkinter import colorchooser
        color = colorchooser.askcolor(color=appearance.palette()["#2b2b2e"],
                                     title="选择背景板颜色", parent=self.root)[1]
        if color:
            cfg.set_value("appearance.background", color)
            appearance.apply(self.root)

    def _reset_background(self):
        cfg.set_value("appearance.background", "")
        appearance.apply(self.root)

    def _toggle_daily_hour(self, hour):
        previous = cfg.get()["daily_word"].get("hour", 9)
        selected = -1 if previous == hour else hour
        cfg.set_value("daily_word.hour", selected)
        self.daily_hour.set(selected)

    def _quit_app(self):
        if self.on_quit:
            self.on_quit()

    def _set_view_buttons(self):
        if self._view == "dict":
            self.dict_btn.config(bg="#3b82f6", fg="#fff")
            self.hist_btn.config(bg="#3a3a3f", fg=FG)
        else:
            self.dict_btn.config(bg="#3a3a3f", fg=FG)
            self.hist_btn.config(bg="#3b82f6", fg="#fff")

    # ---------------- 视图切换 ----------------

    def _set_dict(self):
        self._view = "dict"
        self._set_view_buttons()
        self._reload()

    def _set_history(self):
        self._view = "history"
        self._set_view_buttons()
        self._reload()

    # ---------------- 数据加载 ----------------

    def _reload(self):
        self.listbox.delete(0, "end")
        if self._view == "dict":
            q = self.search_var.get().strip()
            if q:
                items = database.search_words(q)
            else:
                letter = self.letter_var.get()
                items = database.list_words(None if letter == "全部" else letter)
            letter = self.letter_var.get()
            if letter != "全部":
                items = [it for it in items if it["word"].lower().startswith(letter.lower())]
            self._items = items
            for it in items:
                self.listbox.insert("end", it["display"])
            self.count_lbl.config(text="共 %d 词" % len(items))
            self.del_btn.pack(side="right", padx=(6, 14))
            self.relookup_btn.pack_forget()
            self.clear_hist_btn.pack_forget()
        else:
            items = database.list_history()
            self._items = items
            for it in items:
                t = (it.get("looked_at") or "")[5:16]
                self.listbox.insert("end", "  %s" % it.get("display", ""))
            self.count_lbl.config(text="共 %d 条" % len(items))
            self.del_btn.pack_forget()
            self.relookup_btn.pack(side="right", padx=6)
            self.clear_hist_btn.pack(side="right", padx=(0, 14))
        self._current = None
        self.del_btn.config(state="disabled")
        self._render("", "", "请选择左侧单词", [])
        for letter, button in self.letter_buttons.items():
            button.config(bg="#3b82f6" if letter == self.letter_var.get() else LIST_BG)

        appearance.apply(self.root)

    def _filter_letter(self, letter):
        self.letter_var.set(letter)
        self._set_dict()

    def _on_select(self, evt):
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx >= len(self._items):
            return
        self._current = self._items[idx]
        if self._view == "dict":
            self.del_btn.config(state="normal")
            self._render_dict_detail(self._current)
        else:
            self._render_history_detail(self._current)

    def _render_dict_detail(self, rec):
        defs = _parse_definitions(rec.get("definition"))
        self._render(rec.get("display", ""), rec.get("phonetic", ""),
                     rec.get("translation", ""), defs,
                     meta="来源：%s   添加于 %s" % (rec.get("source", ""),
                                                  rec.get("created_at", "")))

    def _render_history_detail(self, rec):
        self._render(rec.get("display", ""), "",
                     rec.get("translation", ""), [],
                     meta="查询于 " + (rec.get("looked_at") or ""))

    def _render(self, title, phonetic, translation, definitions, meta=""):
        txt = self.detail_text
        txt.config(state="normal")
        txt.delete("1.0", "end")
        txt.insert("end", title + "\n", "title")
        if phonetic:
            txt.insert("end", phonetic + "\n", "phonetic")
        if translation:
            txt.insert("end", "\n" + translation + "\n", "translation")
        if definitions:
            txt.insert("end", "\n", "translation")
            for d in definitions:
                pos = d.get("pos", "")
                line = ("[" + pos + "] " if pos else "") + d.get("def", "")
                txt.insert("end", line + "\n", "pos" if pos else "def")
                if d.get("example"):
                    txt.insert("end", "    例：" + d["example"] + "\n", "example")
        if meta:
            txt.insert("end", "\n" + meta + "\n", "meta")
        txt.config(state="disabled")

    # ---------------- 操作 ----------------

    def _delete_word(self):
        if self._view != "dict" or not self._current:
            return
        word = self._current.get("word")
        if word:
            database.delete_word(word)
        self._current = None
        self._reload()

    def _clear_history(self):
        database.clear_history()
        self._current = None
        self._reload()

    def _relookup(self):
        if not self._current:
            return
        word = self._current.get("word") or self._current.get("display")
        self.detail_text.config(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("end", word + "\n", "title")
        self.detail_text.insert("end", "\n查询中…\n", "meta")
        self.detail_text.config(state="disabled")

        def worker():
            res = translator.lookup(word)
            self.root.after(0, lambda: self._finish_relookup(word, res))

        import threading
        threading.Thread(target=worker, daemon=True).start()

    def _finish_relookup(self, word, res):
        if not res:
            self._render(word, "", "未找到释义", [], "")
            return
        self._render(res.get("word", word), res.get("phonetic", ""),
                     res.get("translation", ""), res.get("definitions", []),
                     meta="来源：" + res.get("source", ""))

    # ---------------- 显示/隐藏 ----------------

    def show(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self._reload()

    def hide(self):
        self.root.withdraw()

    def refresh(self):
        self._reload()
