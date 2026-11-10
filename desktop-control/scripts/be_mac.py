#!/usr/bin/env python3
"""macOS backend: Quartz CGEvent for input, `screencapture` for shots,
Accessibility API for the UI tree (best effort).

Requires: pyobjc-framework-Quartz, and the calling terminal must be granted
Accessibility + Screen Recording in System Settings > Privacy & Security.
"""
import os
import subprocess
import tempfile
import time

NAME = "macos"
HERE = os.path.dirname(os.path.abspath(__file__))

# CGKeyCode values (US layout). Modifiers are handled as flags, not keycodes.
KEYCODE = {
    "A": 0, "S": 1, "D": 2, "F": 3, "H": 4, "G": 5, "Z": 6, "X": 7, "C": 8,
    "V": 9, "B": 11, "Q": 12, "W": 13, "E": 14, "R": 15, "Y": 16, "T": 17,
    "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23, "=": 24, "9": 25,
    "7": 26, "-": 27, "8": 28, "0": 29, "]": 30, "O": 31, "U": 32, "[": 33,
    "I": 34, "P": 35, "L": 37, "J": 38, "'": 39, "K": 40, ";": 41, "\\": 42,
    ",": 43, "/": 44, "N": 45, "M": 46, ".": 47, "`": 50,
    "ENTER": 36, "RETURN": 36, "TAB": 48, "SPACE": 49, "BACKSPACE": 51,
    "ESC": 53, "ESCAPE": 53, "DELETE": 117, "HOME": 115, "END": 119,
    "PAGEUP": 116, "PAGEDOWN": 121, "UP": 126, "DOWN": 125, "LEFT": 123,
    "RIGHT": 124,
}
KEYCODE.update({"F%d" % i: 95 + i for i in range(1, 13)})

MOD_FLAGS = {"CTRL": 0x40000, "CONTROL": 0x40000, "SHIFT": 0x20000,
             "ALT": 0x80000, "OPTION": 0x80000, "CMD": 0x100000,
             "COMMAND": 0x100000, "META": 0x100000}


def _q():
    import Quartz
    return Quartz


def _flags(parts):
    f = 0
    for p in parts:
        f |= MOD_FLAGS.get(p.strip().upper(), 0)
    return f


def _keycode(name):
    key = name.strip().upper()
    if key in MOD_FLAGS:
        return None
    if key in KEYCODE:
        return KEYCODE[key]
    if len(key) == 1:
        raise SystemExit("unsupported character key on macOS: %s" % name)
    raise SystemExit("unknown key: %s" % name)


def screen_info():
    Quartz = _q()
    d = Quartz.CGMainDisplayID()
    w = Quartz.CGDisplayPixelsWide(d)
    h = Quartz.CGDisplayPixelsHigh(d)
    mode = Quartz.CGDisplayCopyDisplayMode(d)
    pw, ph = Quartz.CGDisplayModeGetPixelWidth(mode), Quartz.CGDisplayModeGetPixelHeight(mode)
    return "main      %dx%d (points %dx%d)\nretina    %s" % (
        pw, ph, w, h, "yes" if pw != w else "no")


def cursor():
    Quartz = _q()
    ev = Quartz.CGEventCreate(None)
    loc = Quartz.CGEventGetLocation(ev)
    return int(loc.x), int(loc.y)


def move_to(x, y):
    Quartz = _q()
    ev = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, (x, y),
                                        Quartz.kCGMouseButtonLeft)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
    time.sleep(0.05)


def _mouse(etype, x, y, button="left"):
    Quartz = _q()
    b = {"left": Quartz.kCGMouseButtonLeft,
         "right": Quartz.kCGMouseButtonRight,
         "middle": Quartz.kCGMouseButtonCenter}[button]
    ev = Quartz.CGEventCreateMouseEvent(None, etype, (x, y), b)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)


def click(x=None, y=None, button="left", double=False):
    Quartz = _q()
    if x is not None and y is not None:
        move_to(x, y)
    cx, cy = cursor()
    down = {"left": Quartz.kCGEventLeftMouseDown,
            "right": Quartz.kCGEventRightMouseDown,
            "middle": Quartz.kCGEventOtherMouseDown}[button]
    up = {"left": Quartz.kCGEventLeftMouseUp,
          "right": Quartz.kCGEventRightMouseUp,
          "middle": Quartz.kCGEventOtherMouseUp}[button]
    n = 2 if double else 1
    for i in range(n):
        _mouse(down, cx, cy, button)
        _mouse(up, cx, cy, button)
        if double and i == 0:
            time.sleep(0.09)
    return "clicked %s at %d,%d%s" % (button, cx, cy, " (double)" if double else "")


def drag(x1, y1, x2, y2, steps=20, button="left"):
    Quartz = _q()
    move_to(x1, y1)
    _mouse(Quartz.kCGEventLeftMouseDown, x1, y1, button)
    time.sleep(0.06)
    for i in range(1, steps + 1):
        _mouse(Quartz.kCGEventLeftMouseDragged,
               int(x1 + (x2 - x1) * i / steps),
               int(y1 + (y2 - y1) * i / steps), button)
        time.sleep(0.012)
    _mouse(Quartz.kCGEventLeftMouseUp, x2, y2, button)
    return "dragged %d,%d -> %d,%d" % (x1, y1, x2, y2)


def scroll(delta):
    Quartz = _q()
    ev = Quartz.CGEventCreateScrollWheelEvent(
        None, Quartz.kCGScrollEventUnitLine, 1, int(-delta / 120))
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
    return "scrolled %d" % delta


def type_text(text, delay=0):
    """Unicode path, so CJK works regardless of keyboard layout."""
    Quartz = _q()
    for ch in text:
        ev = Quartz.CGEventCreateKeyboardEvent(None, 0, True)
        Quartz.CGEventKeyboardSetUnicodeString(ev, len(ch), ch)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
        ev2 = Quartz.CGEventCreateKeyboardEvent(None, 0, False)
        Quartz.CGEventKeyboardSetUnicodeString(ev2, len(ch), ch)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev2)
        if delay:
            time.sleep(delay / 1000.0)
    return "typed %d chars" % len(text)


def _send(name, is_down, flags=0):
    Quartz = _q()
    code = _keycode(name)
    ev = Quartz.CGEventCreateKeyboardEvent(None, code, is_down)
    if flags:
        Quartz.CGEventSetFlags(ev, flags)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)


def key_down(combo):
    parts = combo.split("+")
    f = _flags(parts[:-1])
    _send(parts[-1], True, f)
    return "down %s" % combo


def key_up(combo):
    parts = combo.split("+")
    f = _flags(parts[:-1])
    _send(parts[-1], False, f)
    return "up %s" % combo


def press_key(combo):
    parts = combo.split("+")
    f = _flags(parts[:-1])
    _send(parts[-1], True, f)
    time.sleep(0.02)
    _send(parts[-1], False, f)
    return "pressed %s" % combo


def windows():
    Quartz = _q()
    opts = (Quartz.kCGWindowListOptionOnScreenOnly |
            Quartz.kCGWindowListExcludeDesktopElements)
    raw = Quartz.CGWindowListCopyWindowInfo(opts, Quartz.kCGNullWindowID)
    out = []
    for w in raw:
        title = w.get("kCGWindowName") or ""
        layer = w.get("kCGWindowLayer", 0)
        if layer != 0 or not str(title).strip():
            continue
        b = w["kCGWindowBounds"]
        out.append({
            "hwnd": int(w["kCGWindowNumber"]),
            "title": str(title),
            "pid": int(w.get("kCGWindowOwnerPID", 0)),
            "owner": str(w.get("kCGWindowOwnerName", "")),
            "active": False,
            "rect": (int(b["X"]), int(b["Y"]), int(b["Width"]), int(b["Height"])),
        })
    return out


def find_window(needle):
    allw = windows()
    if not needle:
        return allw[0] if allw else None
    hits = [w for w in allw if needle.lower() in w["title"].lower()
            or needle.lower() in w.get("owner", "").lower()]
    if not hits:
        raise SystemExit("no window matching: %s" % needle)
    return hits[0]


def focus(win):
    owner = win.get("owner") or win["title"]
    subprocess.run(["osascript", "-e",
                    'tell application "%s" to activate' % owner],
                   capture_output=True)
    time.sleep(0.35)
    return "focused: %s" % win["title"]


def screenshot(path, win=None, monitor=None, scale=1.0):
    from PIL import Image
    path = path or os.path.join(tempfile.gettempdir(), "desk-shot.png")
    cmd = ["screencapture", "-x"]
    if win is not None:
        focus(win)
        time.sleep(0.3)
        left, top, width, height = win["rect"]
        cmd += ["-R", "%d,%d,%d,%d" % (left, top, width, height)]
    cmd.append(path)
    subprocess.run(cmd, check=True)
    img = Image.open(path)
    if scale != 1.0:
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
        img.save(path)
    return "saved=%s size=%dx%d bytes=%d" % (
        path, img.width, img.height, os.path.getsize(path))


def uia_dump(window=None, ctype=None, limit=120):
    """Accessibility walk. Needs pyobjc ApplicationServices + permission."""
    try:
        from ApplicationServices import (
            AXUIElementCreateApplication, AXUIElementCopyAttributeValue,
            kAXChildrenAttribute, kAXTitleAttribute, kAXRoleAttribute)
    except Exception:
        raise SystemExit("uia-dump on macOS needs pyobjc-framework-ApplicationServices")
    win = find_window(window)
    app = AXUIElementCreateApplication(win["pid"])
    lines, count = [], [0]

    def walk(el, depth):
        if count[0] >= limit:
            return
        role = AXUIElementCopyAttributeValue(el, kAXRoleAttribute, None)
        title = AXUIElementCopyAttributeValue(el, kAXTitleAttribute, None)
        if role or title:
            lines.append("%s%s  %s" % ("  " * depth, role, title))
            count[0] += 1
        kids = AXUIElementCopyAttributeValue(el, kAXChildrenAttribute, None)
        for k in (kids or []):
            walk(k, depth + 1)

    walk(app, 0)
    return "\n".join(lines) + "\nmatched=%d" % count[0]


def uia_rect(window=None, name=None):
    raise SystemExit("ui-click by name is not implemented on macOS yet; "
                     "use screenshot + click coordinates")
