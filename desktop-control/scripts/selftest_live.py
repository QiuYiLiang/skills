#!/usr/bin/env python3
"""Non-destructive live check: screenshot, window listing, cursor move.

Runs on all three platforms. It never types or clicks anywhere, so it is safe
to run on a machine someone is using.

    python selftest_live.py [--out shot.png]
"""
import argparse
import importlib
import os
import sys
import tempfile
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def load_backend():
    if sys.platform.startswith("win"):
        return importlib.import_module("be_win")
    if sys.platform == "darwin":
        return importlib.import_module("be_mac")
    return importlib.import_module("be_linux")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(tempfile.gettempdir(), "desk-live.png"))
    a = ap.parse_args()

    be = load_backend()
    results = []

    def check(name, fn, expect=None):
        try:
            value = fn()
            ok = True if expect is None else expect(value)
            results.append((name, bool(ok), str(value)[:90]))
        except Exception as exc:
            results.append((name, False, "%s: %s" % (type(exc).__name__, exc)))

    print("backend = %s" % be.NAME)

    check("screen", lambda: be.screen_info().splitlines()[0])
    check("windows", lambda: "%d visible" % len(be.windows()),
          lambda v: int(v.split()[0]) > 0)
    check("cursor", lambda: "%d,%d" % be.cursor(), lambda v: "," in v)
    check("screenshot", lambda: be.screenshot(a.out), lambda v: "saved=" in v)

    def move_restore():
        before = be.cursor()
        be.move_to(120, 120)
        moved = be.cursor()
        be.move_to(*before)
        if moved != (120, 120):
            return "move did not take effect"
        return "restored" if be.cursor() == before else "restore failed"

    check("cursor move + restore", move_restore, lambda v: v == "restored")

    print()
    for name, ok, value in results:
        print("%s  %-22s %s" % ("PASS" if ok else "FAIL", name, value))
    passed = sum(1 for _, ok, _ in results if ok)
    print("\nRESULT %d/%d passed" % (passed, len(results)))
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
