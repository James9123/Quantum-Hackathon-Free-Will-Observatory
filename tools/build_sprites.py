"""Build qollab_project/ui/sprites.js: the persona sprite sheets as data URIs.

    .venv/bin/python tools/build_sprites.py <sprite-folder>

<sprite-folder> holds the team's SpriteGen exports with a manifest.json that names one final
strip and sidecar per persona and action (see design/persona-sprites-handoff.md). The tool:

- copies each 128 px strip unchanged (horizontal strip of 128 x 128 cells, hard-edged alpha);
- makes a 64 px strip for phones by area-averaging every 2 x 2 block of the 128 px art: a
  cell pixel is opaque when at least two of its four source pixels are, its colour is the
  mean of those pixels mapped to the nearest colour already in the strip (so the art keeps
  its own palette), and alpha stays 0 or 255. Never CSS-scaled;
- reads per-frame timing from the frame file names when they encode it: a name like
  "sprite_01-61" means that image is shown for frames 1 to 61 (61 ticks), so the Observer's
  stare holds its first image for 61 ticks before the 7 movement frames;
- keeps the sidecar's play/hold (the Self's angry: play frames 1-4 once, hold on frame 4);
- validates frame counts against the image widths and alpha against {0, 255}.

The output carries no file paths. Images are embedded as data URIs because JavaScript on
Qollab cannot fetch project files.
"""
import argparse
import base64
import io
import json
import os
import re
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "qollab_project", "ui", "sprites.js")
CELL = 128
SMALL = 64
RANGE = re.compile(r"^sprite_(\d+)(?:-(\d+))?\.png$")


def _png_bytes(im):
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _data_uri(im):
    return "data:image/png;base64," + base64.b64encode(_png_bytes(im)).decode("ascii")


def _check_strip(im, frames, label):
    if im.mode != "RGBA":
        im = im.convert("RGBA")
    w, h = im.size
    if h != CELL or w != CELL * frames:
        raise SystemExit("%s: strip is %dx%d, expected %dx%d for %d frames" % (label, w, h, CELL * frames, CELL, frames, frames))
    alpha = set(im.getchannel("A").getdata())
    if not alpha <= {0, 255}:
        raise SystemExit("%s: alpha is not hard-edged (values %s)" % (label, sorted(alpha)[:6]))
    for i in range(frames):
        cell = im.crop((i * CELL, 0, (i + 1) * CELL, CELL))
        if cell.getchannel("A").getbbox() is None:
            raise SystemExit("%s: frame %d is empty" % (label, i + 1))
    return im


def half(im):
    """2 x 2 area average with hard alpha and the strip's own palette."""
    src = im.load()
    w, h = im.size
    palette = sorted({src[x, y][:3] for y in range(h) for x in range(w) if src[x, y][3] == 255})
    out = Image.new("RGBA", (w // 2, h // 2), (0, 0, 0, 0))
    dst = out.load()
    cache = {}

    def nearest(rgb):
        if rgb not in cache:
            cache[rgb] = min(palette, key=lambda p: (p[0] - rgb[0]) ** 2 + (p[1] - rgb[1]) ** 2 + (p[2] - rgb[2]) ** 2)
        return cache[rgb]

    for y in range(0, h, 2):
        for x in range(0, w, 2):
            px = [src[x + dx, y + dy] for dy in (0, 1) for dx in (0, 1)]
            solid = [p for p in px if p[3] == 255]
            if len(solid) >= 2:
                mean = tuple(round(sum(p[i] for p in solid) / len(solid)) for i in range(3))
                dst[x // 2, y // 2] = nearest(mean) + (255,)
    return out


def ticks_from_names(folder, frames):
    """Per-frame tick counts from names like sprite_01-61.png; None when no name has a range."""
    if not os.path.isdir(folder):
        return None
    spans = []
    for name in os.listdir(folder):
        m = RANGE.match(name)
        if m:
            a = int(m.group(1))
            b = int(m.group(2) or m.group(1))
            spans.append((a, b))
    spans.sort()
    if not spans or all(a == b for a, b in spans):
        return None
    if len(spans) != frames:
        raise SystemExit("%s: %d named frames, the strip has %d" % (folder, len(spans), frames))
    expected = 1
    for a, b in spans:
        if a != expected or b < a:
            raise SystemExit("%s: frame names do not tile the timeline (%s)" % (folder, spans))
        expected = b + 1
    return [b - a + 1 for a, b in spans]


def build(folder):
    manifest = json.load(open(os.path.join(folder, "manifest.json")))
    out = {}
    report = []
    for persona, actions in manifest["personas"].items():
        out[persona] = {}
        for action, info in actions.items():
            strip = os.path.join(folder, info["strip"])
            side = json.load(open(os.path.join(folder, info["sidecar"])))
            frames = int(side["frames"])
            if frames != int(info["frames"]):
                raise SystemExit("%s/%s: manifest and sidecar disagree on frames" % (persona, action))
            im = _check_strip(Image.open(strip), frames, persona + "/" + action)
            small = half(im)
            hd = os.path.join(os.path.dirname(strip), "frames-hd")
            ticks = ticks_from_names(hd, frames)
            play = side.get("play")
            hold = side.get("hold")
            out[persona][action] = {
                "frames": frames,
                "fps": float(side["fps"]),
                "loop": bool(side["loop"]),
                "ticks": ticks,
                "play": play,
                "hold": hold,
                "keyFrame": hold if hold is not None else 0,
                "baseline": side.get("baseline"),
                "src": {str(CELL): _data_uri(im), str(SMALL): _data_uri(small)},
            }
            report.append("%-8s %-8s %2d frames  %4.1f fps  loop=%-5s ticks=%s play=%s hold=%s"
                          % (persona, action, frames, side["fps"], side["loop"], ticks, play, hold))
    return out, report


def write(data):
    lines = [
        "// Persona sprite sheets for the dialogue-box portrait. GENERATED by tools/build_sprites.py",
        "// from the team's SpriteGen exports (credited in CREDITS.md); do not edit by hand.",
        "// Each animation is one horizontal strip of square cells: 128 px for wide screens and a",
        "// 64 px strip for phones (area-averaged from the 128 px art, never CSS-scaled).",
        "// ticks: per-frame durations in ticks (1/fps s) when the art encodes them (the stare holds",
        "// its first image for 61 ticks); play/hold: play these frames once, then hold one.",
        "",
        "export const SPRITE_SIZES = [%d, %d];" % (CELL, SMALL),
        "",
        "export const SPRITES = " + json.dumps(data, indent=1, sort_keys=True) + ";",
        "",
    ]
    text = "\n".join(lines)
    with open(OUT, "w", encoding="ascii") as fh:
        fh.write(text)
    return len(text.encode())


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("folder", help="folder with manifest.json and the persona strips")
    a = ap.parse_args()
    data, report = build(os.path.expanduser(a.folder))
    size = write(data)
    print("\n".join(report))
    print("wrote %s (%d bytes)" % (os.path.relpath(OUT, ROOT), size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
