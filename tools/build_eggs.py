"""Build qollab_project/ui/eggs.js: the side panel's easter egg (a bucket of water and the Self).

    .venv/bin/python tools/build_eggs.py <self-angry.gif> <bucket.gif>

self-angry.gif: the team's 8-frame, 256 px, hard-alpha animation of the Self frowning after
the splash (frame 1 is the still pose). bucket.gif: the 8-frame, 384 px bucket that tips and
pours. Frames are area-averaged with the rules of tools/build_sprites.py (hard alpha, the art's
own palette): the Self to 128 px cells, the bucket to 96 px. The strips are embedded as data
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


def strip(path, src_px, halvings):
    frames = [f.convert("RGBA").copy() for f in ImageSequence.Iterator(Image.open(path))]
    durs = [f.info.get("duration") or 100 for f in ImageSequence.Iterator(Image.open(path))]
    name = os.path.basename(path)
    if len(frames) != 8 or any(f.size != (src_px, src_px) for f in frames):
        raise SystemExit("%s: expected 8 frames of %d px" % (name, src_px))
    if any(not set(f.getchannel("A").getdata()) <= {0, 255} for f in frames):
        raise SystemExit("%s: alpha is not hard-edged" % name)
    big = Image.new("RGBA", (src_px * 8, src_px), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        big.paste(f, (i * src_px, 0))
    for _ in range(halvings):
        big = half(big)
    cell = big.size[1]
    return {"frames": 8, "cell": cell, "fps": round(1000.0 / durs[0], 3), "src": _data_uri(big)}


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    data = {"angry": strip(sys.argv[1], 256, 1), "bucket": strip(sys.argv[2], 384, 2)}
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
