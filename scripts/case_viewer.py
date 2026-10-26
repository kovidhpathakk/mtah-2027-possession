"""Draw moments of the PRACTICE matches as top-down maps, to look at plays instead of inferring.

The open-data matches (DFL, Metrica) have no video, so their tracking is the only view of the play.
This draws a strip of snapshots around a frame: home players red, away blue, the ball white with
a short trail, the true label and a method's label on each panel, plus ball speed. Open data
only: it refuses our match, so no frame of BAR-ATH is ever drawn by it.

    .venv-video/bin/python scripts/case_viewer.py dfl-J03WMX 41250 --method v3 --out case.png
    .venv-video/bin/python scripts/case_viewer.py dfl-J03WMX 41250 --method v3 --zoom 15

--zoom R draws only the R metres around the ball, larger, with a 1 m circle round the ball and
the distance from the ball to each team's nearest player.
"""

import argparse
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from possession.external import load_source  # noqa: E402

# Params
FPS = 25
OFFSETS = (-2.0, -1.0, -0.5, 0.0, 0.5, 1.0)   # seconds around the frame, one panel each
SCALE = 4                                     # pixels per metre
MARGIN = 8
TRAIL = 12                                    # frames of ball trail
COLOURS = {0: (220, 40, 40), 1: (40, 90, 230)}


def panel(t, f, labels, pred, pitch, zoom=None, centre=None):
    length, width = pitch
    if zoom:
        scale, size = 400 / (2 * zoom), 400
        w, h = size + 2 * MARGIN, size + 2 * MARGIN + 30
        cx0, cy0 = centre[0] * length - zoom, centre[1] * width - zoom

        def px(x, y):
            return MARGIN + (x * length - cx0) * scale, MARGIN + (y * width - cy0) * scale
    else:
        scale = SCALE
        w, h = int(length * SCALE) + 2 * MARGIN, int(width * SCALE) + 2 * MARGIN + 30

        def px(x, y):
            return MARGIN + x * length * SCALE, MARGIN + y * width * SCALE
    img = Image.new("RGB", (w, h), (30, 110, 50))
    d = ImageDraw.Draw(img)
    d.rectangle([px(0, 0), px(1, 1)], outline=(230, 230, 230))
    d.line([px(0.5, 0), px(0.5, 1)], fill=(230, 230, 230))
    for code in (0, 1):
        for slot in np.flatnonzero(t["team"] == code):
            x, y = t["players"][f, slot]
            if not np.isnan(x):
                cx, cy = px(x, y)
                d.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=COLOURS[code])
    trail = t["ball"][max(0, f - TRAIL):f + 1]
    points = [px(x, y) for x, y in trail if not np.isnan(x)]
    if len(points) > 1:
        d.line(points, fill=(255, 255, 255), width=1)
    ball_m = t["ball"] * np.array(pitch)
    near = ""
    if not np.isnan(t["ball"][f, 0]):
        cx, cy = px(*t["ball"][f])
        if zoom:
            r = scale  # 1 m
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 255, 0))
        d.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=(255, 255, 255), outline=(0, 0, 0))
        dist = np.linalg.norm(t["players"][f] * np.array(pitch) - ball_m[f], axis=1)
        near = "  near H {:.1f} A {:.1f} m".format(
            np.nanmin(np.where(t["team"] == 0, dist, np.inf)),
            np.nanmin(np.where(t["team"] == 1, dist, np.inf)))
    speed = np.linalg.norm(ball_m[min(f + 2, len(ball_m) - 1)] - ball_m[max(f - 2, 0)]) * FPS / 4
    d.text((MARGIN, h - 26), "f {} truth {} pred {} ball {:.1f} m/s{}".format(
        f, labels[f], pred[f] if pred is not None else "-", speed, near), fill=(255, 255, 255))
    return img


def strip(name, frame, method=None, zoom=None):
    if name in ("tactical", "broadcast"):
        sys.exit("refusing to draw our match: open-data sources only")
    t = load_source(name)
    pred = None
    if method:
        from possession.methods import METHODS
        pred = METHODS[method](t)
    centre = t["ball"][frame] if not np.isnan(t["ball"][frame, 0]) else np.array([0.5, 0.5])
    panels = [panel(t, frame + int(o * FPS), t["labels"], pred, t["pitch"], zoom, centre)
              for o in OFFSETS]
    w, h = panels[0].size
    out = Image.new("RGB", (w * 3, h * 2))
    for k, p in enumerate(panels):
        out.paste(p, ((k % 3) * w, (k // 3) * h))
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source")
    parser.add_argument("frame", type=int)
    parser.add_argument("--method")
    parser.add_argument("--out", default="case.png")
    parser.add_argument("--zoom", type=float, help="metres around the ball")
    args = parser.parse_args()
    strip(args.source, args.frame, args.method, args.zoom).save(args.out)
    print("wrote", args.out)
