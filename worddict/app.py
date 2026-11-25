# -*- coding: utf-8 -*-
"""随取词典 - 总调度。

后台线程负责全局鼠标钩子 + 托盘；主线程跑 tkinter 界面。
"""
import os
import queue
import threading
import datetime

import tkinter as tk

import win32api
import win32con
import win32event

from . import config
from . import database
from . import translator
from . import daily
from . import icon
from . import system_tray
from .popup import SelectionPopup, DefinitionCard
from .dictionary_window import DictionaryWindow


def _enable_dpi_awareness():
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


_MUTEX = None


def acquire_single_instance():
    """用命名互斥量防止多开（多开会叠加钩子与托盘，导致弹窗异常）。"""
    global _MUTEX
    try:
        _MUTEX = win32event.CreateMutex(None, False, "WordDict_SingleInstance_v1")
        return win32api.GetLastError() != 183  # 183 = ERROR_ALREADY_EXISTS
    except Exception:
        return True


def _notify_already_running():
    """唤起已有实例；等待托盘窗口就绪以支持启动时连续双击。"""
    import time
    import ctypes
    import win32gui
    import win32process
    for _ in range(50):
        hwnd = win32gui.FindWindow("WordDictTrayClass", None)
        if hwnd:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            ctypes.windll.user32.AllowSetForegroundWindow(pid)
            win32gui.PostMessage(hwnd, system_tray.WM_SHOW_MAIN, 0, 0)
            return
        time.sleep(0.1)


class App:
    def __init__(self):
        database.init()
        self.icon_path = icon.ensure_icon(
            os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "assets", "icon.ico"))
        self.q = queue.Queue()

        self.root = tk.Tk()
        self.root.withdraw()
        self.root.iconbitmap(self.icon_path)

        self.dict_win = DictionaryWindow(self.root, on_quit=self._quit)
        self.sys = system_tray.SystemThread(self.q, self.icon_path)
        self._popup = None
        self._card = None
        self.dict_win.daily_callback = self._show_daily

    # ---------------- 消息轮询 ----------------

    def run(self):
        self.sys.start()
        self.dict_win.show()
        self.root.after(80, self._poll)
        self.root.after(40, self._watch_click_away)
        self.root.after(1500, self._startup_notice)
        self.root.after(6000, self._maybe_daily)   # 首次稍等托盘就绪
        self.root.after(30000, self._hourly)
        self.root.mainloop()

    def _startup_notice(self):
        """启动提示：告诉用户图标在哪、如何退出。"""
        self.sys.show_balloon("随取词典已启动", "图标已驻留系统托盘，右键图标可退出")

    def _watch_click_away(self):
        """轮询：左键按下且落在弹窗外部时，关闭弹窗（不抢键盘焦点）。"""
        try:
            popup = self._popup
            if popup is not None and not popup._closed:
                if win32api.GetAsyncKeyState(win32con.VK_LBUTTON) & 0x8000:
                    x, y = win32api.GetCursorPos()
                    if not popup.contains(x, y):
                        self._close_popup()
        except Exception:
            pass
        self.root.after(40, self._watch_click_away)

    def _poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                self._handle(msg)
        except queue.Empty:
            pass
        self.root.after(80, self._poll)

    def _handle(self, msg):
        kind = msg[0]
        if kind == "selection":
            _, word, pos = msg
            self._on_selection(word, pos)
        elif kind == "action":
            act = msg[1]
            if act == "open":
                self.dict_win.show()
            elif act == "daily":
                self._show_daily()
            elif act == "quit":
                self._quit()
        elif kind == "error":
            print("[随取词典] 系统线程错误:", msg[1])

    # ---------------- 选词处理 ----------------

    def _on_selection(self, word, pos):
        self._close_popup()
        self._popup = SelectionPopup(
            self.root, word, pos,
            on_translate=self._translate_and_show,
            on_add=self._add_word,
        )
        threading.Thread(target=self._prefetch, args=(word, self._popup),
                         daemon=True).start()

    def _prefetch(self, word, popup):
        try:
            res = translator.lookup(word)
        except Exception:
            res = None
        if popup is self._popup:
            popup.push_result(res)

    def _close_popup(self):
        if self._popup:
            try:
                self._popup.close()
            except Exception:
                pass
            self._popup = None

    def _translate_and_show(self, word, result):
        if result:
            database.add_history(word, result.get("word", word),
                                 result.get("translation", ""))
            self._close_popup()
            self._card = DefinitionCard(self.root, result, on_add=self._add_word)
        else:
            self._close_popup()
            self._card = DefinitionCard(
                self.root,
                {"word": word, "phonetic": "", "translation": "未找到释义",
                 "definitions": [], "source": "none"},
                on_add=self._add_word,
            )

    def _add_word(self, word, result):
        if result:
            database.upsert_word(
                word, display=result.get("word", word),
                phonetic=result.get("phonetic", ""),
                translation=result.get("translation", ""),
                definition=result.get("definitions", []),
                source=result.get("source", "user"),
            )
            database.add_history(word, result.get("word", word),
                                 result.get("translation", ""))
        else:
            database.upsert_word(word, display=word, source="user")
            database.add_history(word, word, "")
            threading.Thread(target=self._fill_meaning, args=(word,),
                             daemon=True).start()
        self.dict_win.refresh()

    def _fill_meaning(self, word):
        try:
            res = translator.lookup(word)
        except Exception:
            res = None
        if res:
            database.upsert_word(
                word, display=res.get("word", word),
                phonetic=res.get("phonetic", ""),
                translation=res.get("translation", ""),
                definition=res.get("definitions", []),
                source=res.get("source", "user"),
            )
            self.root.after(0, self.dict_win.refresh)

    # ---------------- 每日一词 ----------------

    def _hourly(self):
        self._maybe_daily()
        self.root.after(30000, self._hourly)

    def _maybe_daily(self):
        if not config.get()["daily_word"].get("enabled", True):
            return
        if daily.shown_today():
            return
        hour = config.get()["daily_word"].get("hour", 9)
        if 0 <= hour <= 23 and datetime.datetime.now().hour >= hour:
            self._show_daily()

    def _show_daily(self):
        result = daily.pick()
        if result is None:
            from tkinter import messagebox
            messagebox.showinfo("每日一词", "每日词库中的单词已全部收藏，暂无新词。", parent=self.root)
            daily.mark_shown()
            return
        w, t = result
        if self._card:
            self._card.close()
        self._card = DefinitionCard(self.root,
            {"word": w, "translation": t, "phonetic": "", "definitions": [], "source": "daily"},
            on_add=self._add_word)
        self.sys.show_balloon("每日一词", "%s  %s" % (w, t) if t else w)
        daily.mark_shown()

    # ---------------- 退出 ----------------

    def _quit(self):
        self._close_popup()
        if self._card:
            try:
                self._card.close()
            except Exception:
                pass
        self.sys.request_stop()
        self.root.destroy()


def main():
    if not acquire_single_instance():
        _notify_already_running()
        return
    _enable_dpi_awareness()
    app = App()
    try:
        app.run()
    except KeyboardInterrupt:
        # 终端 Ctrl+C / 关闭控制台时，尽量干净退出（移除托盘与钩子）
        try:
            app._quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
