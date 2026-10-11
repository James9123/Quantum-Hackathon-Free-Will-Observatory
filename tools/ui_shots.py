"""Baseline screenshots of the Observatory page in stub mode (for design reviews and the video).

    .venv/bin/python tools/ui_shots.py [--out build/ui-baseline] [--browser <path>]

Serves the repo on 127.0.0.1, drives each state through dev/index.html?auto=..., and
captures it with a headless Chromium-family browser. Nothing here is uploaded to Qollab.
"""
import argparse
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
BROWSERS = [
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]
STATES = [  # name, query, (width, height)
    ("desktop-idle", "backend=basic&slow=0&mount=0", (1280, 2400)),
    ("desktop-act1-open-futures", "backend=basic&slow=0&mount=0&auto=90|0|0", (1280, 2400)),
    ("desktop-act2-intention", "backend=basic&slow=0&mount=0&auto=180|0|0", (1280, 2400)),
    ("desktop-act3-constraint", "backend=basic&slow=0&mount=0&auto=90|1|0", (1280, 2400)),
    ("desktop-demon-half-coupling", "backend=basic&slow=0&mount=0&auto=90|0.5|0&persona=demon", (1280, 2400)),
    ("desktop-observer-perspective", "backend=basic&slow=0&mount=0&auto=90|0.5|45&persona=observer", (1280, 2400)),
    ("desktop-drawer-open", "backend=basic&slow=0&mount=0&auto=90|0|0&how=1", (1280, 3000)),
    ("desktop-ionq-one-job-lock", "backend=ionq&slow=0&mount=0&auto=90|0|0", (1280, 2400)),
    ("desktop-failed-run", "backend=error&slow=0&mount=0&auto=90|0|0", (1280, 2400)),
    ("desktop-reduced-motion", "backend=basic&slow=0&mount=0&reduce=1&auto=90|0|0", (1280, 2400)),
    ("desktop-no-webgl", "backend=basic&slow=0&mount=0&nowebgl=1&auto=90|0|0", (1280, 2400)),
    ("mobile-idle", "backend=basic&slow=0&mount=0", (390, 3200)),
    ("mobile-act1", "backend=basic&slow=0&mount=0&auto=90|0|0", (390, 3200)),
    ("mobile-act3", "backend=basic&slow=0&mount=0&auto=90|1|0", (390, 3200)),
]


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "build" / "ui-baseline"))
    ap.add_argument("--browser", default=next((b for b in BROWSERS if os.path.exists(b)), None))
    ap.add_argument("--budget-ms", type=int, default=25000)
    a = ap.parse_args()
    if not a.browser:
        sys.exit("no Chromium-family browser found; pass --browser")
    out = pathlib.Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    port = free_port()
    server = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
                              cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(0.8)
        for name, query, (w, h) in STATES:
            url = "http://127.0.0.1:%d/dev/index.html?%s" % (port, query)
            path = out / (name + ".png")
            cmd = [a.browser, "--headless=new", "--hide-scrollbars", "--use-gl=angle", "--use-angle=swiftshader",
                   "--window-size=%d,%d" % (w, h), "--virtual-time-budget=%d" % a.budget_ms,
                   "--screenshot=%s" % path, url]
            t0 = time.time()
            try:
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            except subprocess.TimeoutExpired:
                print("TIMEOUT %s" % name)
                continue
            print("%-32s %7d bytes  %.1fs" % (name, path.stat().st_size if path.exists() else 0, time.time() - t0))
    finally:
        server.terminate()
    (out / "README.txt").write_text(
        "Baseline screenshots of the Observatory page in local stub mode (canned simulator answers),\n"
        "captured headless at the viewport in each file name. States: idle, the three demo acts,\n"
        "Demon and Observer tabs, the open drawer, the one-job lock, a failed run, reduced motion,\n"
        "the no-WebGL text fallback, and three mobile views.\n")
    print("wrote", out)


if __name__ == "__main__":
    main()
