#!/usr/bin/env python3
"""desk.py - cross-platform desktop control for agents.

Same CLI on Windows, macOS and Linux; a platform backend is picked at import.

    python desk.py screen
    python desk.py windows
    python desk.py shot --out a.png [--window Chrome] [--scale 0.75]
    python desk.py focus --window Chrome
    python desk.py click --x 100 --y 200 [--double]
    python desk.py type --text "hello" --window Chrome
    python desk.py key --keys CTRL+S
    python desk.py ui-dump --window Chrome --type Button
    python desk.py ui-click --window Chrome --name "OK"
"""
import argparse
import importlib
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def load_backend():
    if sys.platform.startswith("win"):
        return importlib.import_module("be_win")
    if sys.platform == "darwin":
        return importlib.import_module("be_mac")
    return importlib.import_module("be_linux")


def resolve(be, a):
    """--hwnd / --pid exist because non-ASCII argv is mangled when a shell
    hands it to Python on Windows; locators sidestep title matching."""
    if getattr(a, "hwnd", None):
        for w in be.windows():
            if w["hwnd"] == a.hwnd:
                return w
        raise SystemExit("no window with hwnd %s" % a.hwnd)
    if getattr(a, "pid", None):
        for w in be.windows():
            if w["pid"] == a.pid:
                return w
        raise SystemExit("no window with pid %s" % a.pid)
    return be.find_window(a.window)


def wants_window(a):
    return bool(a.window or getattr(a, "hwnd", None) or getattr(a, "pid", None))


def selftest(be):
    checks = [
        ("screen", lambda: be.screen_info().splitlines()[0]),
        ("cursor", lambda: "%d,%d" % be.cursor()),
        ("windows", lambda: "%d visible" % len(be.windows())),
        ("screenshot", lambda: be.screenshot(
            os.path.join(os.environ.get("TEMP") or os.environ.get("TMPDIR") or "/tmp",
                         "desk-selftest.png"))),
    ]
    ok = bad = 0
    print("backend = %s" % be.NAME)
    for name, fn in checks:
        try:
            print("  PASS  %-12s -> %s" % (name, fn()))
            ok += 1
        except Exception as exc:
            print("  FAIL  %-12s -> %s" % (name, exc))
            bad += 1
    print("RESULT ok=%d fail=%d" % (ok, bad))
    return 0 if bad == 0 else 1


def main():
    ap = argparse.ArgumentParser(prog="desk.py", formatter_class=argparse.RawDescriptionHelpFormatter,
                                 description=__doc__)
    ap.add_argument("action")
    ap.add_argument("--out")
    ap.add_argument("--window")
    ap.add_argument("--hwnd", type=int)
    ap.add_argument("--pid", type=int)
    ap.add_argument("--monitor", type=int)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--x", type=int)
    ap.add_argument("--y", type=int)
    ap.add_argument("--x2", type=int)
    ap.add_argument("--y2", type=int)
    ap.add_argument("--steps", type=int, default=20)
    ap.add_argument("--button", default="left")
    ap.add_argument("--double", action="store_true")
    ap.add_argument("--delta", type=int, default=-120)
    ap.add_argument("--text")
    ap.add_argument("--text-file")
    ap.add_argument("--keys")
    ap.add_argument("--name")
    ap.add_argument("--type")
    ap.add_argument("--limit", type=int, default=120)
    ap.add_argument("--delay", type=int, default=0)
    a = ap.parse_args()

    be = load_backend()
    act = a.action.lower()

    if act == "selftest":
        sys.exit(selftest(be))
    if act == "screen":
        print(be.screen_info())
    elif act == "windows":
        for w in sorted(be.windows(), key=lambda w: (not w["active"], w["title"])):
            l, t, ww, hh = w["rect"]
            print("%s %10s pid=%-6s %5d,%-5d %dx%d  %s" % (
                "*" if w["active"] else " ", w["hwnd"], w["pid"], l, t, ww, hh, w["title"]))
    elif act == "state":
        w = resolve(be, a) if wants_window(a) else (be.windows() or [None])[0]
        cx, cy = be.cursor()
        print("cursor=%d,%d active=%s" % (cx, cy, w["title"] if w else "-"))
    elif act == "cursor":
        print("%d,%d" % be.cursor())
    elif act == "shot":
        print(be.screenshot(a.out, resolve(be, a) if wants_window(a) else None,
                            a.monitor, a.scale))
    elif act == "focus":
        print(be.focus(resolve(be, a)))
    elif act == "move":
        be.move_to(a.x, a.y)
        print("moved to %d,%d" % be.cursor())
    elif act == "click":
        if wants_window(a):
            be.focus(resolve(be, a))
        print(be.click(a.x, a.y, a.button, a.double))
    elif act == "drag":
        print(be.drag(a.x, a.y, a.x2, a.y2, a.steps, a.button))
    elif act == "scroll":
        print(be.scroll(a.delta))
    elif act == "type":
        text = a.text
        if a.text_file:
            with open(a.text_file, encoding="utf-8") as f:
                text = f.read()
        if not text:
            raise SystemExit("need --text or --text-file")
        if wants_window(a):
            be.focus(resolve(be, a))
        print(be.type_text(text, a.delay))
    elif act == "key":
        if wants_window(a):
            be.focus(resolve(be, a))
        print(be.press_key(a.keys))
    elif act == "keydown":
        print(be.key_down(a.keys))
    elif act == "keyup":
        print(be.key_up(a.keys))
    elif act == "ui-dump":
        win = resolve(be, a) if wants_window(a) else None
        print(be.uia_dump(win["title"] if win else None, a.type, a.limit))
    elif act == "ui-click":
        win = resolve(be, a) if wants_window(a) else None
        box = be.uia_rect(win["title"] if win else None, a.name)
        bx, by, bw, bh = (int(v) for v in box.split(","))
        if win:
            be.focus(win)
        print(be.click(bx + bw // 2, by + bh // 2))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
