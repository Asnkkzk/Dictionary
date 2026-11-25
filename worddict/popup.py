# -*- coding: utf-8 -*-
"""选词弹出菜单 + 释义卡片（均为置顶无边框小窗）。"""
import tkinter as tk
from . import appearance

BG = "#2b2b2e"
FG = "#f0f0f0"
DIM = "#9e9ea7"
ACCENT = "#3b82f6"
GOOD = "#7ee787"


def _clamp_pos(root, x, y, w=260, h=80):
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    if x + w > sw - 8:
        x = sw - w - 8
    if y + h > sh - 8:
        y = y - h - 24
    if x < 8:
        x = 8
    if y < 8:
        y = 8
    return x, y


class SelectionPopup:
    """选中单词后出现在鼠标附近的迷你菜单。"""

    def __init__(self, root, word, pos, on_translate, on_add):
        self.root = root
        self.word = word
        self.on_translate = on_translate
        self.on_add = on_add
        self.result = None
        self._want_translate = False
        self._closed = False

        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=BG)

        f = tk.Frame(self.win, bg=BG, padx=10, pady=8)
        f.pack()

        self.word_lbl = tk.Label(f, text=word, bg=BG, fg=FG,
                                 font=("Segoe UI", 12, "bold"))
        self.word_lbl.pack(side="left", padx=(0, 10))

        self.preview_lbl = tk.Label(f, text="", bg=BG, fg=DIM,
                                    font=("Segoe UI", 9))
        self.preview_lbl.pack(side="left", padx=(0, 10))

        for text, cmd, accent in (("翻译", self._translate, ACCENT),
                                  ("添加", self._add, None)):
            b = tk.Button(f, text=text, command=cmd, bg=accent if accent else "#3a3a3f",
                          fg=FG, activebackground=ACCENT, activeforeground="#ffffff",
                          relief="flat", font=("Segoe UI", 9),
                          padx=12, pady=3, cursor="hand2")
            b.pack(side="left", padx=3)

        # 关闭按钮
        tk.Button(f, text="✕", command=self.close, bg="#3a3a3f", fg=DIM,
                  activebackground="#5a2a2a", activeforeground="#ffffff",
                  relief="flat", font=("Segoe UI", 9, "bold"),
                  padx=7, pady=2, cursor="hand2").pack(side="left", padx=(6, 0))

        appearance.apply(self.win)
        self.win.update_idletasks()
        w = self.win.winfo_reqwidth()
        h = self.win.winfo_reqheight()
        x, y = _clamp_pos(root, pos[0] + 12, pos[1] + 14, w, h)
        self.win.geometry("+%d+%d" % (x, y))

        # 不抢键盘焦点，避免影响用户正常打字；点击外部/超时由外部逻辑关闭
        self._timer = self.win.after(5000, self.close)

    def contains(self, x, y):
        """判断屏幕坐标 (x, y) 是否落在弹窗范围内。"""
        try:
            gx = self.win.winfo_rootx()
            gy = self.win.winfo_rooty()
            w = self.win.winfo_width()
            h = self.win.winfo_height()
            return gx <= x <= gx + w and gy <= y <= gy + h
        except Exception:
            return False

    def push_result(self, result):
        """后台查词结果回填（线程安全）。"""
        try:
            self.root.after(0, lambda: self._on_result(result))
        except Exception:
            pass

    def _on_result(self, result):
        if self._closed:
            return
        self.result = result
        if result and result.get("translation"):
            t = result["translation"]
            self.preview_lbl.config(text="· " + (t[:30] + "…" if len(t) > 30 else t))
        if self._want_translate:
            self._want_translate = False
            self.close()
            self.on_translate(self.word, result)

    def _translate(self):
        if self.result is not None:
            self.close()
            self.on_translate(self.word, self.result)
        else:
            self._want_translate = True
            self.preview_lbl.config(text="· 查询中…")

    def _add(self):
        self.on_add(self.word, self.result)
        if self._closed:
            return
        self.win.after_cancel(self._timer)
        self.word_lbl.config(text="已添加 ✓", fg=GOOD)
        self.win.after(800, self.close)

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self.win.after_cancel(self._timer)
            self.win.destroy()
        except Exception:
            pass


class DefinitionCard:
    """展示单词完整释义的卡片，含“添加到词典”。"""

    def __init__(self, root, result, on_add):
        self.root = root
        self.result = result
        self.on_add = on_add
        self._added = False

        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=BG)

        head = tk.Frame(self.win, bg=BG, padx=14, pady=10)
        head.pack(fill="x")

        self.title_lbl = tk.Label(head, text=result.get("word", ""), bg=BG, fg=FG,
                                  font=("Segoe UI", 16, "bold"))
        self.title_lbl.pack(side="left")

        phonetic = result.get("phonetic", "")
        if phonetic:
            tk.Label(head, text=phonetic, bg=BG, fg=DIM,
                     font=("Segoe UI", 11)).pack(side="left", padx=(10, 0))

        if result.get("translation"):
            tk.Label(self.win, text=result["translation"], bg=BG, fg="#7cc6fe",
                     font=("Microsoft YaHei", 13), justify="left",
                     padx=14, pady=4, wraplength=420, anchor="w").pack(fill="x")

        defs = result.get("definitions") or []
        body = tk.Frame(self.win, bg=BG, padx=14, pady=4)
        body.pack(fill="both", expand=True)
        if defs:
            txt = tk.Text(body, bg="#232327", fg=FG, font=("Segoe UI", 10),
                          relief="flat", height=10, wrap="word",
                          padx=10, pady=8)
            txt.pack(fill="both", expand=True)
            txt.tag_configure("pos", foreground="#f8b26a", font=("Segoe UI", 10, "bold"))
            txt.tag_configure("example", foreground=DIM)
            for d in defs[:8]:
                pos = d.get("pos", "")
                line = (("[" + pos + "] ") if pos else "")
                line += d.get("def", "")
                txt.insert("end", line + "\n", ("pos",) if pos else ())
                if d.get("example"):
                    txt.insert("end", "   例：" + d["example"] + "\n", "example")
                txt.insert("end", "\n")
            txt.config(state="disabled")
        else:
            tk.Label(body, text="（无更多释义）", bg=BG, fg=DIM,
                     font=("Microsoft YaHei", 10)).pack(anchor="w")

        foot = tk.Frame(self.win, bg=BG, padx=14, pady=10)
        foot.pack(fill="x")
        self.add_btn = tk.Button(foot, text="添加到词典", command=self._do_add,
                                 bg=ACCENT, fg="#ffffff", activebackground="#2563eb",
                                 activeforeground="#ffffff", relief="flat",
                                 font=("Microsoft YaHei", 10), padx=14, pady=4,
                                 cursor="hand2")
        self.add_btn.pack(side="left")
        tk.Button(foot, text="关闭", command=self.close, bg="#3a3a3f", fg=FG,
                  activebackground="#4a4a50", relief="flat",
                  font=("Microsoft YaHei", 10), padx=14, pady=4,
                  cursor="hand2").pack(side="left", padx=(8, 0))

        appearance.apply(self.win)
        self.win.update_idletasks()
        w = self.win.winfo_reqwidth()
        h = self.win.winfo_reqheight()
        px = self.root.winfo_pointerx() + 14
        py = self.root.winfo_pointery() + 14
        x, y = _clamp_pos(root, px, py, w, h)
        self.win.geometry("+%d+%d" % (x, y))

    def _do_add(self):
        if self._added:
            return
        self._added = True
        self.on_add(self.result.get("word", ""), self.result)
        self.add_btn.config(text="已添加 ✓", bg=GOOD, fg="#0d1117", state="disabled")

    def close(self):
        try:
            self.win.destroy()
        except Exception:
            pass
