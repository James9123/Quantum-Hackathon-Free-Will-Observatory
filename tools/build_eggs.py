"""Build qollab_project/ui/eggs.js: the side panel's easter egg (a bucket of water and the Self).

    .venv/bin/python tools/build_eggs.py <self-angry.gif> <bucket.gif>

self-angry.gif: the team's 8-frame, 256 px, hard-alpha animation of the Self frowning after
the splash (frame 1 is the still pose). bucket.gif: the 8-frame, 384 px bucket that tips and
pours. Frames are area-averaged with the rules of tools/build_sprites.py (hard alpha, the art's
own palette): the Self to 128 px cells, each frame first pinned to frame 1's feet and ground line
so the figure does not jitter. The bucket is drawn at 0.65 of 96 px, so its frames are
box-filtered straight from 384 to 62 px with alpha cut back to hard edges. The strips are embedded as data
URIs because JavaScript on Qollab cannot fetch project files; no paths are written out.
"""
import json
import os
import sys

from PIL import Image, ImageSequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_sprites import _data_uri, half  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "qollab_project", "ui", "eggs.js")


def feet(frame):
    """Ground line and feet centre: the lowest opaque row, and the mean x of the opaque pixels
    in the lowest 14 rows (the boots)."""
    a = frame.getchannel("A")
    bottom = a.getbbox()[3] - 1
    px = a.load()
    xs = [x for y in range(max(0, bottom - 13), bottom + 1) for x in range(frame.size[0]) if px[x, y]]
    return bottom, sum(xs) / len(xs)


def steady(frames):
    """Pin every frame's feet and ground line to frame 1's, so the figure does not jitter
    between frames (the GIF's frames were drawn at slightly different spots)."""
    bottom0, cx0 = feet(frames[0])
    out = []
    for f in frames:
        bottom, cx = feet(f)
        dx, dy = int(round(cx0 - cx)), bottom0 - bottom
        moved = Image.new("RGBA", f.size, (0, 0, 0, 0))
        moved.paste(f, (dx, dy), f)
        if moved.getchannel("A").getbbox() != (f.getchannel("A").getbbox()[0] + dx, f.getchannel("A").getbbox()[1] + dy,
                                              f.getchannel("A").getbbox()[2] + dx, f.getchannel("A").getbbox()[3] + dy):
            raise SystemExit("steadying would clip a frame (dx %d, dy %d)" % (dx, dy))
        out.append(moved)
    return out


def strip(path, src_px, halvings, pin_feet=False):
    frames = [f.convert("RGBA").copy() for f in ImageSequence.Iterator(Image.open(path))]
    durs = [f.info.get("duration") or 100 for f in ImageSequence.Iterator(Image.open(path))]
    name = os.path.basename(path)
    if len(frames) != 8 or any(f.size != (src_px, src_px) for f in frames):
        raise SystemExit("%s: expected 8 frames of %d px" % (name, src_px))
    if any(not set(f.getchannel("A").getdata()) <= {0, 255} for f in frames):
        raise SystemExit("%s: alpha is not hard-edged" % name)
    if pin_feet:
        frames = steady(frames)
    big = Image.new("RGBA", (src_px * 8, src_px), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        big.paste(f, (i * src_px, 0))
    for _ in range(halvings):
        big = half(big)
    cell = big.size[1]
    return {"frames": 8, "cell": cell, "fps": round(1000.0 / durs[0], 3), "src": _data_uri(big)}


def strip_scaled(path, src_px, cell):
    """Box-filter each frame straight to `cell` px (any ratio), alpha back to hard edges."""
    frames = [f.convert("RGBA").copy() for f in ImageSequence.Iterator(Image.open(path))]
    durs = [f.info.get("duration") or 100 for f in ImageSequence.Iterator(Image.open(path))]
    if len(frames) != 8 or any(f.size != (src_px, src_px) for f in frames):
        raise SystemExit("%s: expected 8 frames of %d px" % (os.path.basename(path), src_px))
    out = Image.new("RGBA", (cell * 8, cell), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        small = f.resize((cell, cell), Image.BOX)
        a = small.getchannel("A").point(lambda v: 255 if v >= 128 else 0)
        small.putalpha(a)
        out.paste(small, (i * cell, 0))
    return {"frames": 8, "cell": cell, "fps": round(1000.0 / durs[0], 3), "src": _data_uri(out)}


BUCKET_PX = 62          # 0.65 x 96


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    data = {"angry": strip(sys.argv[1], 256, 1, pin_feet=True), "bucket": strip_scaled(sys.argv[2], 384, BUCKET_PX)}
    text = "\n".join([
        "// The side panel's easter egg: a bucket of water tips onto the Self, who frowns. GENERATED",
        "// by tools/build_eggs.py from the team's GIFs; do not edit by hand. Each is one strip of 8",
        "// square cells (cell px); frame 1 of the Self's strip is its still pose.",
        "",
        "export const EGGS = " + json.dumps(data, indent=1, sort_keys=True) + ";",
        "",
    ])
    with open(OUT, "w", encoding="ascii") as fh:
        fh.write(text)
    print("wrote %s (%d bytes)" % (os.path.relpath(OUT, ROOT), len(text)))


if __name__ == "__main__":
    main()
