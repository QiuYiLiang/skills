#!/usr/bin/env python3
"""Windows backend: ctypes against user32/dwmapi, Pillow for capture,
PowerShell 7 + UIAutomation for the accessibility tree."""
import ctypes
import ctypes.wintypes as wt
import os
import shutil
import subprocess
import tempfile
import time

NAME = "windows"
HERE = os.path.dirname(os.path.abspath(__file__))

user32 = ctypes.WinDLL("user32", use_last_error=True)

DPI_MODE = "none"
try:
    ctypes.WinDLL("shcore").SetProcessDpiAwareness(2)
    DPI_MODE = "per-monitor"
except Exception:
    try:
        user32.SetProcessDPIAware()
        DPI_MODE = "system"
    except Exception:
        pass

MOUSEEVENTF = {"left": (0x0002, 0x0004), "right": (0x0008, 0x0010),
               "middle": (0x0020, 0x0040)}
MOUSEEVENTF_WHEEL = 0x0800
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wt.POINT)]
user32.mouse_event.argtypes = [wt.DWORD, wt.DWORD, wt.DWORD, wt.DWORD, ctypes.c_void_p]
user32.keybd_event.argtypes = [wt.BYTE, wt.BYTE, wt.DWORD, ctypes.c_void_p]
user32.GetForegroundWindow.restype = wt.HWND
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.AttachThreadInput.argtypes = [wt.DWORD, wt.DWORD, wt.BOOL]
user32.BringWindowToTop.argtypes = [wt.HWND]
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD),
                ("dwFlags", wt.DWORD), ("time", wt.DWORD),
                ("dwExtraInfo", ctypes.c_void_p)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_void_p)]


class _INPUTUNION(ctypes.Union):
    # MOUSEINPUT is the largest member; leaving it out makes sizeof(INPUT)
    # too small on x64 and SendInput silently drops the event.
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("u", _INPUTUNION)]


user32.SendInput.argtypes = [wt.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wt.UINT

DWMWA_EXTENDED_FRAME_BOUNDS = 9
_dwm = ctypes.WinDLL("dwmapi")


class _DRECT(ctypes.Structure):
    _fields_ = [("left", wt.LONG), ("top", wt.LONG),
                ("right", wt.LONG), ("bottom", wt.LONG)]


VK = {
    "CTRL": 0x11, "CONTROL": 0x11, "SHIFT": 0x10, "ALT": 0x12, "WIN": 0x5B,
    "META": 0x5B, "ENTER": 0x0D, "RETURN": 0x0D, "TAB": 0x09, "ESC": 0x1B,
    "ESCAPE": 0x1B, "SPACE": 0x20, "BACKSPACE": 0x08, "DELETE": 0x2E,
    "DEL": 0x2E, "INSERT": 0x2D, "HOME": 0x24, "END": 0x23,
    "PAGEUP": 0x21, "PAGEDOWN": 0x22, "UP": 0x26, "DOWN": 0x28,
    "LEFT": 0x25, "RIGHT": 0x27, "PRINTSCREEN": 0x2C, "CAPSLOCK": 0x14,
}
VK.update({"F%d" % i: 0x6F + i for i in range(1, 25)})


def ps_exe():
    return shutil.which("pwsh") or shutil.which("powershell") or "powershell.exe"


def vk_of(name):
    key = name.strip().upper()
    if key in VK:
        return VK[key]
    if len(key) == 1:
        return ord(key)
    raise SystemExit("unknown key: %s" % name)


def window_rect(hwnd):
    """DWM bounds exclude the invisible resize border that GetWindowRect
    includes on Win11, which otherwise leaks the desktop into screenshots."""
    r = _DRECT()
    try:
        if _dwm.DwmGetWindowAttribute(wt.HWND(hwnd), DWMWA_EXTENDED_FRAME_BOUNDS,
                                      ctypes.byref(r), ctypes.sizeof(r)) == 0:
            return r.left, r.top, r.right, r.bottom
    except Exception:
        pass
    import win32gui
    return win32gui.GetWindowRect(hwnd)


def cursor():
    p = wt.POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def move_to(x, y):
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.06)


def _monitors():
    import win32api
    out = []
    for m in win32api.EnumDisplayMonitors():
        info = win32api.GetMonitorInfo(m[0])
        left, top, right, bottom = info["Monitor"]
        out.append({"rect": (left, top, right - left, bottom - top),
                    "primary": bool(info.get("Flags", 0) & 1)})
    return out


def screen_info():
    import win32api
    lines = []
    for i, m in enumerate(_monitors()):
        left, top, width, height = m["rect"]
        lines.append("monitor %d  primary=%s  %d,%d %dx%d"
                     % (i, m["primary"], left, top, width, height))
    w = win32api.GetSystemMetrics(78) or win32api.GetSystemMetrics(0)
    h = win32api.GetSystemMetrics(79) or win32api.GetSystemMetrics(1)
    lines.append("virtual  %dx%d" % (w, h))
    lines.append("dpi_mode %s" % DPI_MODE)
    return "\n".join(lines)


def windows():
    import win32gui
    import win32process
    fg = user32.GetForegroundWindow()
    out = []

    def cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        if not title.strip():
            return True
        left, top, right, bottom = window_rect(hwnd)
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        out.append({"hwnd": hwnd, "title": title, "pid": pid,
                    "active": hwnd == fg,
                    "rect": (left, top, right - left, bottom - top)})
        return True

    win32gui.EnumWindows(cb, None)
    return out


def find_window(needle):
    allw = windows()
    if not needle:
        for w in allw:
            if w["active"]:
                return w
        return allw[0] if allw else None
    hits = [w for w in allw if needle.lower() in w["title"].lower()]
    if not hits:
        raise SystemExit("no window matching: %s" % needle)
    return hits[0]


def force_foreground(hwnd):
    """Windows refuses SetForegroundWindow from a background process; the
    AttachThreadInput trick is the standard way around the foreground lock."""
    user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.12)
    if user32.GetForegroundWindow() == hwnd:
        return True
    fg = user32.GetForegroundWindow()
    fg_tid = user32.GetWindowThreadProcessId(fg, None)
    tgt_tid = user32.GetWindowThreadProcessId(hwnd, None)
    try:
        user32.AttachThreadInput(fg_tid, tgt_tid, True)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.AttachThreadInput(fg_tid, tgt_tid, False)
    except Exception:
        pass
    time.sleep(0.2)
    return user32.GetForegroundWindow() == hwnd


def focus(win):
    ok = force_foreground(win["hwnd"])
    return "focused%s: %s" % ("" if ok else " (FOREGROUND DENIED)", win["title"])


def screenshot(path, win=None, monitor=None, scale=1.0):
    from PIL import Image, ImageGrab
    if win is not None:
        focus(win)
        time.sleep(0.35)
        left, top, width, height = win["rect"]
        img = ImageGrab.grab(bbox=(left, top, left + width, top + height),
                             all_screens=True)
    elif monitor is not None:
        left, top, width, height = _monitors()[monitor]["rect"]
        img = ImageGrab.grab(bbox=(left, top, left + width, top + height),
                             all_screens=True)
    else:
        img = ImageGrab.grab(all_screens=True)
    if scale != 1.0:
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    path = path or os.path.join(tempfile.gettempdir(), "desk-shot.png")
    img.save(path)
    return "saved=%s size=%dx%d bytes=%d" % (
        path, img.width, img.height, os.path.getsize(path))


def _button(button):
    return MOUSEEVENTF[button]


def click(x=None, y=None, button="left", double=False):
    if x is not None and y is not None:
        move_to(x, y)
    down, up = _button(button)
    user32.mouse_event(down, 0, 0, 0, None)
    user32.mouse_event(up, 0, 0, 0, None)
    if double:
        time.sleep(0.09)
        user32.mouse_event(down, 0, 0, 0, None)
        user32.mouse_event(up, 0, 0, 0, None)
    cx, cy = cursor()
    return "clicked %s at %d,%d%s" % (button, cx, cy, " (double)" if double else "")


def drag(x1, y1, x2, y2, steps=20, button="left"):
    down, up = _button(button)
    move_to(x1, y1)
    user32.mouse_event(down, 0, 0, 0, None)
    time.sleep(0.06)
    for i in range(1, steps + 1):
        user32.SetCursorPos(int(x1 + (x2 - x1) * i / steps),
                            int(y1 + (y2 - y1) * i / steps))
        time.sleep(0.012)
    user32.mouse_event(up, 0, 0, 0, None)
    return "dragged %d,%d -> %d,%d" % (x1, y1, x2, y2)


def scroll(delta):
    user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, ctypes.c_uint32(delta).value, None)
    return "scrolled %d" % delta


def _send_unicode(ch):
    code = ord(ch)
    down = INPUT(type=1)
    down.u.ki = KEYBDINPUT(0, code, KEYEVENTF_UNICODE, 0, None)
    up = INPUT(type=1)
    up.u.ki = KEYBDINPUT(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, None)
    sent = user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(INPUT))
    sent += user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(INPUT))
    if sent != 2:
        raise OSError("SendInput failed (err=%d)" % ctypes.get_last_error())


def type_text(text, delay=0):
    for ch in text:
        if ch == "\n":
            press_key("ENTER")
        else:
            _send_unicode(ch)
        if delay:
            time.sleep(delay / 1000.0)
    return "typed %d chars" % len(text)


def key_down(combo):
    for c in (vk_of(k) for k in combo.split("+")):
        user32.keybd_event(c, 0, 0, None)
    return "down %s" % combo


def key_up(combo):
    for c in (vk_of(k) for k in combo.split("+")):
        user32.keybd_event(c, 0, KEYEVENTF_KEYUP, None)
    return "up %s" % combo


def press_key(combo):
    codes = [vk_of(k) for k in combo.split("+")]
    for c in codes:
        user32.keybd_event(c, 0, 0, None)
    for c in reversed(codes):
        user32.keybd_event(c, 0, KEYEVENTF_KEYUP, None)
    return "pressed %s" % combo


UIA_PS1 = os.path.join(HERE, "uia_win.ps1")


def _uia(action, window=None, name=None, ctype=None, limit=120):
    cmd = [ps_exe(), "-NoProfile", "-ExecutionPolicy", "Bypass",
           "-File", UIA_PS1, action, "-Limit", str(limit)]
    if window:
        cmd += ["-Window", window]
    if name:
        cmd += ["-Name", name]
    if ctype:
        cmd += ["-Type", ctype]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=60)
    return (r.stdout or "").strip() or (r.stderr or "").strip()


def uia_dump(window=None, ctype=None, limit=120):
    return _uia("dump", window, None, ctype, limit)


def uia_rect(window=None, name=None):
    return _uia("rect", window, name)
