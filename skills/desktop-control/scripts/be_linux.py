#!/usr/bin/env python3
"""Linux backend: xdotool for input and window control, ImageGrab/scrot/grim
for capture.

X11 works out of the box. Under Wayland xdotool cannot see other clients;
`screenshot` falls back to grim and input needs ydotool plus the
uinput permission. See SKILL.md for the caveats.
"""
import os
import shutil
import subprocess
import tempfile
import time

NAME = "linux"
HERE = os.path.dirname(os.path.abspath(__file__))

# our combo names -> xdotool keysym names
KEYSYM = {
    "CTRL": "ctrl", "CONTROL": "ctrl", "SHIFT": "shift", "ALT": "alt",
    "SUPER": "super", "META": "super", "WIN": "super",
    "ENTER": "Return", "RETURN": "Return", "TAB": "Tab", "ESC": "Escape",
    "ESCAPE": "Escape", "SPACE": "space", "BACKSPACE": "BackSpace",
    "DELETE": "Delete", "DEL": "Delete", "INSERT": "Insert",
    "HOME": "Home", "END": "End", "PAGEUP": "Page_Up", "PAGEDOWN": "Page_Down",
    "UP": "Up", "DOWN": "Down", "LEFT": "Left", "RIGHT": "Right",
}
KEYSYM.update({"F%d" % i: "F%d" % i for i in range(1, 13)})


def session_type():
    return os.environ.get("XDG_SESSION_TYPE", "x11").lower()


def _run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **kw)


def _need(tool, hint=""):
    if not shutil.which(tool):
        raise SystemExit("missing tool: %s%s" % (tool, ("  " + hint) if hint else ""))


def screen_info():
    out = ["session  %s" % session_type()]
    if shutil.which("xrandr"):
        r = _run(["xrandr", "--current"])
        for line in (r.stdout or "").splitlines():
            if " connected" in line and "x" in line:
                out.append("display  " + line.strip())
    else:
        out.append("xrandr not available")
    out.append("xdotool  %s" % ("yes" if shutil.which("xdotool") else "NO"))
    out.append("capture  %s" % (" ".join(
        t for t in ("grim", "scrot", "import", "gnome-screenshot") if shutil.which(t)) or "none"))
    return "\n".join(out)


def cursor():
    _need("xdotool")
    r = _run(["xdotool", "getmouselocation", "--shell"])
    vals = dict(line.split("=", 1) for line in (r.stdout or "").splitlines() if "=" in line)
    return int(vals.get("X", 0)), int(vals.get("Y", 0))


def move_to(x, y):
    _need("xdotool")
    _run(["xdotool", "mousemove", "--sync", str(int(x)), str(int(y))])
    time.sleep(0.05)


def click(x=None, y=None, button="left", double=False):
    _need("xdotool")
    if x is not None and y is not None:
        move_to(x, y)
    btn = {"left": "1", "middle": "2", "right": "3"}[button]
    _run(["xdotool", "click", "--repeat", "2" if double else "1",
          "--delay", "90", btn])
    cx, cy = cursor()
    return "clicked %s at %d,%d%s" % (button, cx, cy, " (double)" if double else "")


def drag(x1, y1, x2, y2, steps=20, button="left"):
    _need("xdotool")
    btn = {"left": "1", "middle": "2", "right": "3"}[button]
    move_to(x1, y1)
    _run(["xdotool", "mousedown", btn])
    time.sleep(0.06)
    for i in range(1, steps + 1):
        _run(["xdotool", "mousemove", "--sync",
              str(int(x1 + (x2 - x1) * i / steps)),
              str(int(y1 + (y2 - y1) * i / steps))])
        time.sleep(0.012)
    _run(["xdotool", "mouseup", btn])
    return "dragged %d,%d -> %d,%d" % (x1, y1, x2, y2)


def scroll(delta):
    _need("xdotool")
    button = "4" if delta < 0 else "5"
    repeat = max(1, abs(int(delta)) // 120)
    _run(["xdotool", "click", "--repeat", str(repeat), button])
    return "scrolled %d" % delta


def _keysym(part):
    up = part.strip().upper()
    if up in KEYSYM:
        return KEYSYM[up]
    if len(up) == 1:
        return up.lower()
    raise SystemExit("unknown key: %s" % part)


def type_text(text, delay=0):
    _need("xdotool")
    _run(["xdotool", "type", "--clearmodifiers", "--delay", str(max(delay, 12)), "--", text])
    return "typed %d chars" % len(text)


def key_down(combo):
    _need("xdotool")
    _run(["xdotool", "keydown"] + [_keysym(p) for p in combo.split("+")])
    return "down %s" % combo


def key_up(combo):
    _need("xdotool")
    _run(["xdotool", "keyup"] + [_keysym(p) for p in combo.split("+")])
    return "up %s" % combo


def press_key(combo):
    _need("xdotool")
    _run(["xdotool", "key", "--clearmodifiers",
          "+".join(_keysym(p) for p in combo.split("+"))])
    return "pressed %s" % combo


def windows():
    _need("xdotool")
    r = _run(["xdotool", "search", "--onlyvisible", "--name", ".*"])
    ids = [int(x) for x in (r.stdout or "").split() if x.strip().isdigit()]
    out = []
    fg = _run(["xdotool", "getactivewindow"]).stdout.strip()
    for wid in ids:
        name = (_run(["xdotool", "getwindowname", str(wid)]).stdout or "").strip()
        if not name:
            continue
        geo = (_run(["xdotool", "getwindowgeometry", "--shell", str(wid)]).stdout or "")
        vals = dict(l.split("=", 1) for l in geo.splitlines() if "=" in l)
        pid = (_run(["xdotool", "getwindowpid", str(wid)]).stdout or "").strip()
        out.append({
            "hwnd": wid, "title": name, "pid": int(pid) if pid.isdigit() else 0,
            "active": str(wid) == fg,
            "rect": (int(vals.get("X", 0)), int(vals.get("Y", 0)),
                     int(vals.get("WIDTH", 0)), int(vals.get("HEIGHT", 0))),
        })
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


def focus(win):
    _need("xdotool")
    _run(["xdotool", "windowactivate", "--sync", str(win["hwnd"])])
    time.sleep(0.25)
    return "focused: %s" % win["title"]


def screenshot(path, win=None, monitor=None, scale=1.0):
    from PIL import Image
    path = path or os.path.join(tempfile.gettempdir(), "desk-shot.png")
    ids = None
    if win is not None:
        focus(win)
        time.sleep(0.3)
        ids = str(win["hwnd"])

    if session_type() == "wayland" and shutil.which("grim"):
        cmd = ["grim", path]
        subprocess.run(cmd, check=True)
    elif shutil.which("scrot"):
        # -u uses the focused window's geometry when capturing a window
        cmd = ["scrot", "-o"] + (["-u"] if ids else []) + [path]
        subprocess.run(cmd, check=True)
    elif shutil.which("import"):
        target = "-window %s" % ids if ids else "-window root"
        subprocess.run(["sh", "-c", "import %s %s" % (target, path)], check=True)
    else:
        from PIL import ImageGrab
        box = None
        if win is not None:
            left, top, width, height = win["rect"]
            box = (left, top, left + width, top + height)
        ImageGrab.grab(bbox=box, xdisplay=None).save(path)

    img = Image.open(path)
    if scale != 1.0:
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
        img.save(path)
    return "saved=%s size=%dx%d bytes=%d" % (
        path, img.width, img.height, os.path.getsize(path))


def uia_dump(window=None, ctype=None, limit=120):
    """AT-SPI tree. Needs the pyatspi module and an accessibility bus."""
    try:
        import pyatspi
    except Exception:
        raise SystemExit("uia-dump on Linux needs pyatspi (apt install python3-pyatspi)")
    win = find_window(window)
    desk = pyatspi.Registry.getDesktop(0)
    lines, n = [], 0

    def walk(node, depth):
        nonlocal n
        if n >= limit:
            return
        try:
            if win["title"] and win["title"] in (node.name or ""):
                lines.append("%s%s  %s" % ("  " * depth, node.getRoleName(), node.name))
                n += 1
            for c in node:
                walk(c, depth + 1)
        except Exception:
            pass

    for app in desk:
        walk(app, 0)
    return "\n".join(lines) + "\nmatched=%d" % n


def uia_rect(window=None, name=None):
    raise SystemExit("ui-click by name is not implemented on Linux yet; "
                     "use screenshot + click coordinates")
