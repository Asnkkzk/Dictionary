# -*- coding: utf-8 -*-
"""系统后台线程：全局鼠标钩子 + 系统托盘图标 + 每日一词气球。

通过 queue.Queue 与主线程（tkinter）通信：
  ('selection', word, (x, y))  选中了一个单词，请求弹出菜单
  ('action', 'open'|'quit'|'daily'|'pause'|'autostart')
"""
import os
import time
import queue
import threading
import winreg
import ctypes

import win32api
import win32con
import win32gui
import win32process
import win32clipboard

from . import config as cfg

# ---- 底层鼠标钩子（该 pywin32 版本无 SetWindowsHookEx，改用 ctypes）----
_user32 = ctypes.windll.user32
WH_MOUSE_LL = 14

_MouseProc = ctypes.WINFUNCTYPE(
    ctypes.c_long,          # LRESULT
    ctypes.c_int,           # nCode
    ctypes.c_uint,          # wParam
    ctypes.c_void_p,        # lParam
)

_user32.SetWindowsHookExW.restype = ctypes.c_void_p
_user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int, _MouseProc, ctypes.c_void_p, ctypes.c_uint]
_user32.CallNextHookEx.restype = ctypes.c_long
_user32.CallNextHookEx.argtypes = [
    ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_void_p]
_user32.UnhookWindowsHookEx.restype = ctypes.c_int
_user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]

WM_TRAYICON = win32con.WM_USER + 20
WM_SHOW_MAIN = win32con.WM_USER + 21

# 菜单命令
CMD_OPEN = 1
CMD_DAILY = 2
CMD_PAUSE = 3
CMD_AUTOSTART = 4
CMD_EXIT = 5

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def autostart_command():
    """计算开机自启要注册的命令行（pythonw 无窗口运行 main.py）。"""
    import sys
    if getattr(sys, "frozen", False):
        return chr(34) + sys.executable + chr(34)
    exe = sys_executable_pythonw()
    pkg_dir = os.path.dirname(os.path.abspath(__file__))     # worddict/
    main_py = os.path.join(os.path.dirname(pkg_dir), "main.py")  # 上级 main.py
    return '"%s" "%s"' % (exe, main_py)


def sys_executable_pythonw():
    import sys
    base = os.path.dirname(sys.executable)
    pw = os.path.join(base, "pythonw.exe")
    if os.path.exists(pw):
        return pw
    return sys.executable


def get_autostart():
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(k, cfg.APP_ID)
            return True
        except OSError:
            return False
        finally:
            winreg.CloseKey(k)
    except OSError:
        return False


def set_autostart(enable):
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE)
    except OSError:
        return False
    try:
        if enable:
            winreg.SetValueEx(k, cfg.APP_ID, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(k, cfg.APP_ID)
            except OSError:
                pass
        return True
    finally:
        winreg.CloseKey(k)


def _send_ctrl_c():
    """向当前前台窗口发送 Ctrl+C，复制选中文本（保证 Ctrl 一定被释放）。"""
    try:
        win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
        time.sleep(0.03)
        win32api.keybd_event(ord("C"), 0, 0, 0)
        time.sleep(0.03)
        win32api.keybd_event(ord("C"), 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(0.03)
    finally:
        win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)


def _read_clipboard():
    try:
        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                return win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()
    except Exception:
        pass
    return None


def _is_own_window():
    """判断当前前台窗口是否属于本进程（避免在词典界面内取词）。"""
    try:
        hwnd = win32gui.GetForegroundWindow()
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return pid == os.getpid()
    except Exception:
        return False


class SystemThread(threading.Thread):
    """负责托盘、鼠标钩子、复制读取，跑在自己的消息循环里。"""

    def __init__(self, out_queue, icon_path):
        super().__init__(daemon=True, name="WordDictSystem")
        self.out_queue = out_queue
        self.icon_path = icon_path
        self._stop_event = threading.Event()
        self._sel_event = threading.Event()
        self._paused = not cfg.get()["popup"].get("enabled", True)
        self._last_trigger = 0.0
        self._down_pos = None
        self._hook = None
        self._hicon = None
        self._hwnd = None
        self._taskbar_created = win32gui.RegisterWindowMessage("TaskbarCreated")
        self._class_atom = None
        self._last_selection = None
        self._worker = None

    # ---------- 生命周期 ----------

    def run(self):
        try:
            self._create_window()
            self._add_tray_icon()
            try:
                self._install_hook()
            except Exception as exc:
                self.out_queue.put(("error", str(exc)))
            self._worker = threading.Thread(target=self._selection_worker,
                                            daemon=True, name="WordDictSel")
            self._worker.start()
            win32gui.PumpMessages()
        except Exception as e:  # noqa: BLE001
            self.out_queue.put(("error", str(e)))
        finally:
            self._cleanup()

    def request_stop(self):
        self._stop_event.set()
        self._sel_event.set()
        if self._hwnd:
            try:
                win32api.PostThreadMessage(self.ident, win32con.WM_QUIT, 0, 0)
            except Exception:
                pass

    def _cleanup(self):
        if self._hook:
            try:
                _user32.UnhookWindowsHookEx(self._hook)
            except Exception:
                pass
            self._hook = None
        self._remove_tray_icon()
        if self._hwnd:
            try:
                win32gui.DestroyWindow(self._hwnd)
            except Exception:
                pass
            self._hwnd = None

    # ---------- 窗口与托盘 ----------

    def _create_window(self):
        hinst = win32api.GetModuleHandle(None)
        wc = win32gui.WNDCLASS()
        wc.hInstance = hinst
        wc.lpszClassName = "WordDictTrayClass"
        wc.lpfnWndProc = self._wndproc
        self._class_atom = win32gui.RegisterClass(wc)
        self._hwnd = win32gui.CreateWindow(
            self._class_atom, cfg.APP_NAME, 0, 0, 0, 0, 0,
            0, 0, hinst, None,
        )

    def _add_tray_icon(self):
        self._hicon = self._hicon or win32gui.LoadImage(
            0, self.icon_path, win32con.IMAGE_ICON, 0, 0,
            win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE,
        )
        nid = (self._hwnd, 0,
               win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP,
               WM_TRAYICON, self._hicon, cfg.APP_NAME)
        win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, nid)

    def _remove_tray_icon(self):
        if self._hwnd:
            try:
                win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, (self._hwnd, 0))
            except Exception:
                pass

    def show_balloon(self, title, text):
        if not self._hwnd:
            return
        try:
            nid = (self._hwnd, 0,
                   win32gui.NIF_INFO, WM_TRAYICON, self._hicon, cfg.APP_NAME,
                   text, 0, 0, title, win32gui.NIIF_INFO, 0)
            win32gui.Shell_NotifyIcon(win32gui.NIM_MODIFY, nid)
        except Exception:
            # 兜底：某些环境 NIF_INFO 元组不兼容，忽略即可
            pass

    def _wndproc(self, hwnd, msg, wParam, lParam):
        if msg == WM_SHOW_MAIN:
            self.out_queue.put(("action", "open"))
            return 0
        if msg == self._taskbar_created:
            self._add_tray_icon()
            return 0
        if msg == WM_TRAYICON:
            if lParam in (win32con.WM_RBUTTONUP, win32con.WM_CONTEXTMENU):
                self._show_menu()
            elif lParam == win32con.WM_LBUTTONDBLCLK:
                self.out_queue.put(("action", "open"))
            return 0
        if msg == win32con.WM_COMMAND:
            cmd = win32api.LOWORD(wParam)
            self._on_command(cmd)
            return 0
        if msg == win32con.WM_DESTROY:
            win32api.PostQuitMessage(0)
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wParam, lParam)

    def _on_command(self, cmd):
        if cmd == CMD_OPEN:
            self.out_queue.put(("action", "open"))
        elif cmd == CMD_DAILY:
            self.out_queue.put(("action", "daily"))
        elif cmd == CMD_PAUSE:
            self._paused = not self._paused
            cfg.set_value("popup.enabled", not self._paused)
        elif cmd == CMD_AUTOSTART:
            new_state = not get_autostart()
            set_autostart(new_state)
            cfg.set_value("autostart", new_state)
        elif cmd == CMD_EXIT:
            self.out_queue.put(("action", "quit"))

    def _show_menu(self):
        menu = win32gui.CreatePopupMenu()
        flags = win32con.MF_STRING
        win32gui.AppendMenu(menu, flags, CMD_OPEN, "打开词典")
        win32gui.AppendMenu(menu, flags, CMD_DAILY, "今日单词")
        win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, "")
        pause_flag = flags | (win32con.MF_CHECKED if self._paused else 0)
        win32gui.AppendMenu(menu, pause_flag, CMD_PAUSE, "暂停取词")
        auto_flag = flags | (win32con.MF_CHECKED if get_autostart() else 0)
        win32gui.AppendMenu(menu, auto_flag, CMD_AUTOSTART, "开机自启")
        win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, "")
        win32gui.AppendMenu(menu, flags, CMD_EXIT, "退出")
        pos = win32gui.GetCursorPos()
        win32gui.SetForegroundWindow(self._hwnd)
        win32gui.TrackPopupMenu(
            menu, win32con.TPM_LEFTALIGN | win32con.TPM_RIGHTBUTTON,
            pos[0], pos[1], 0, self._hwnd, None,
        )
        win32gui.PostMessage(self._hwnd, win32con.WM_NULL, 0, 0)
        win32gui.DestroyMenu(menu)

    # ---------- 鼠标钩子 ----------

    def _install_hook(self):
        # 保存回调引用防止被回收
        self._mouse_proc_cb = _MouseProc(self._mouse_proc)
        self._hook = _user32.SetWindowsHookExW(
            WH_MOUSE_LL, self._mouse_proc_cb, None, 0)
        if not self._hook:
            raise RuntimeError("无法安装全局鼠标钩子")

    def _mouse_proc(self, nCode, wParam, lParam):
        if nCode >= 0 and not self._paused:
            if wParam == win32con.WM_LBUTTONDOWN:
                self._down_pos = win32api.GetCursorPos()
            elif wParam == win32con.WM_LBUTTONUP:
                if self._down_pos is not None:
                    up = win32api.GetCursorPos()
                    dist = cfg.get()["popup"].get("drag_min_distance", 15)
                    if (abs(up[0] - self._down_pos[0]) > dist
                            or abs(up[1] - self._down_pos[1]) > dist):
                        self._trigger()
                self._down_pos = None
            elif wParam == win32con.WM_LBUTTONDBLCLK:
                self._trigger()
        return _user32.CallNextHookEx(self._hook, nCode, wParam, lParam)

    def _trigger(self):
        now = time.time()
        if now - self._last_trigger < 1.5:
            return
        self._last_trigger = now
        self._sel_event.set()

    def _selection_worker(self):
        while not self._stop_event.is_set():
            if not self._sel_event.wait(0.2):
                continue
            if self._stop_event.is_set():
                break
            self._sel_event.clear()
            if self._paused:
                continue
            try:
                delay = cfg.get()["popup"].get("copy_delay_ms", 120) / 1000.0
                time.sleep(delay)
                if _is_own_window():
                    continue
                old = _read_clipboard()
                _send_ctrl_c()
                time.sleep(0.05)
                text = _read_clipboard()
                if not text or text == old:
                    # 剪贴板没变化 → 没有真正选中新内容（误触发的普通点击）
                    continue
                word = _clean_word(text)
                if not word:
                    continue
                x, y = win32api.GetCursorPos()
                self.out_queue.put(("selection", word, (x, y)))
            except Exception:
                continue


def _clean_word(text):
    # 延迟导入，避免循环
    from .translator import _clean_word as _f
    return _f(text)
