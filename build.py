#!/usr/bin/env python3
"""Compose the silver-ponytail petdex spritesheet (v1: 8 cols x 9 rows, 192x208 cells).

Inputs:  assets/poses/pose-*.png   (1024x1024, magenta #FF00FF background)
Output:  silver-ponytail/spritesheet.png
         assets/preview.png        (same sheet with grid lines, for docs)

Requires: Pillow, numpy.  Run from anywhere: paths are relative to this file.
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageOps

BASE = os.path.dirname(os.path.abspath(__file__))

POSES = {
    "stand":  "pose-stand.png",
    "wave":   "pose-wave.png",
    "jump":   "pose-jump.png",
    "sad":    "pose-sad.png",
    "run":    "pose-run.png",
    "review": "pose-review.png",
}

MAGENTA = np.array([255.0, 0.0, 255.0])
KEY_TOL = 110.0


def magenta_family(rgb):
    """Loose magenta-family test to catch glow gradients around the character."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    return (r > 140) & (b > 140) & (g < 0.75 * np.minimum(r, b))


def pinkish(rgb):
    """Light-pink glow test: high red+blue, green clearly below both."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    return (r > 195) & (b > 195) & (g < np.minimum(r, b) - 35)


def shift4(m):
    """Return dict of m shifted 1px in 4 directions (bool arrays)."""
    p = np.pad(m, 1, constant_values=False)
    return {
        "u": p[:-2, 1:-1],
        "d": p[2:, 1:-1],
        "l": p[1:-1, :-2],
        "r": p[1:-1, 2:],
    }


def flood_from_border(bg):
    """Pixels of bg connected to image border."""
    reached = np.zeros_like(bg)
    reached[0, :] = bg[0, :]
    reached[-1, :] = bg[-1, :]
    reached[:, 0] = bg[:, 0]
    reached[:, -1] = bg[:, -1]
    while True:
        grown = reached.copy()
        for s in shift4(reached).values():
            grown |= s & bg
        if grown.sum() == reached.sum():
            return grown
        reached = grown


def defringe(rgb, alpha):
    """Replace pink/magenta-tinted opaque pixels near edges with nearby colors."""
    magentaish = magenta_family(rgb) | pinkish(rgb)
    near_trans = np.zeros_like(alpha, dtype=bool)
    a = alpha < 128
    for _ in range(2):
        acc = np.zeros_like(a)
        for s in shift4(near_trans).values():
            acc |= s
        near_trans = acc
    fringe = magentaish & near_trans & (alpha >= 128)
    if not fringe.any():
        return rgb
    colors = rgb.astype(np.float32).copy()
    good = ~fringe
    for _ in range(3):
        cnt = np.zeros(rgb.shape[:2], np.float32)
        acc = np.zeros_like(colors)
        for s in shift4(good).values():
            m = s & fringe
            cnt += m
            for c in range(3):
                acc[..., c] += np.where(m, colors[..., c], 0)
        upd = fringe & (cnt > 0)
        for c in range(3):
            colors[..., c] = np.where(upd, acc[..., c] / np.maximum(cnt, 1), colors[..., c])
        good = good | upd
        fringe = fringe & ~upd
    return colors


def load_pose(path):
    img = Image.open(path).convert("RGB")
    rgb = np.asarray(img).astype(np.float32)
    dist = np.sqrt(((rgb - MAGENTA) ** 2).sum(-1))
    bg = (dist < KEY_TOL) | magenta_family(rgb) | pinkish(rgb)
    reached = flood_from_border(bg)
    # shave rim: pink/magenta-ish pixels adjacent to keyed region
    rim = ~reached & (magenta_family(rgb) | pinkish(rgb))
    for _ in range(2):
        adj = np.zeros_like(reached)
        for s in shift4(reached).values():
            adj |= s
        newly = adj & rim
        if not newly.any():
            break
        reached |= newly
        rim &= ~reached
    alpha = np.where(reached, 0, 255).astype(np.uint8)
    rgb = defringe(rgb, alpha)
    out = np.dstack([np.clip(rgb, 0, 255).astype(np.uint8), alpha])
    im = Image.fromarray(out, "RGBA")
    im = im.crop(im.getbbox())
    return im


def bleed_resize(sprite, height, max_width):
    """Resize with colors bled into transparent padding to avoid black/magenta halo."""
    a = np.asarray(sprite)
    pad = 12
    rgb = np.pad(a[..., :3], ((pad, pad), (pad, pad), (0, 0)), mode="edge")
    alpha = np.pad(a[..., 3], pad, constant_values=0)
    p = Image.fromarray(np.dstack([rgb, alpha]), "RGBA")
    w0, h0 = sprite.size
    s = height / h0
    if w0 * s > max_width:
        s = max_width / w0
    nw = round(w0 * s) + 2 * round(pad * s)
    nh = round(h0 * s) + 2 * round(pad * s)
    p = p.resize((nw, nh), Image.LANCZOS)
    return p.crop(p.getbbox())


CELL_W, CELL_H = 192, 208
MARGIN_BOTTOM = 10
N_COLS, N_ROWS = 8, 9


def frame(pose, dy=0, dx=0, rot=0, sy=1.0, mirror=False):
    sp = ImageOps.mirror(pose) if mirror else pose
    w, h = sp.size
    nh = max(1, int(round(h * sy)))
    sp = sp.resize((w, nh), Image.LANCZOS) if nh != h else sp
    canvas = Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 0))
    x = (CELL_W - sp.size[0]) // 2 + dx
    y = CELL_H - MARGIN_BOTTOM - sp.size[1] + dy
    canvas.paste(sp, (x, y), sp)
    if rot:
        canvas = canvas.rotate(
            rot, center=(CELL_W / 2, CELL_H - MARGIN_BOTTOM),
            resample=Image.BICUBIC,
        )
    return canvas


def dilate_bool(m, n=1):
    for _ in range(n):
        p = np.pad(m, 1, constant_values=False)
        m = p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
    return m


def clean_edges(img):
    """Fix colors of semi-transparent and near-edge magenta-ish pixels."""
    a = np.asarray(img).astype(np.float32)
    alpha = a[..., 3]
    colors = a[..., :3].copy()
    mag = magenta_family(colors) | pinkish(colors)
    op = alpha >= 250
    semi = (alpha > 0) & (alpha < 250)
    near_trans = dilate_bool(alpha < 64, 2)
    fix = semi | (op & near_trans & mag)
    good = op & ~fix
    remaining = fix.copy()
    for _ in range(8):
        acc = np.zeros_like(colors)
        cnt = np.zeros(colors.shape[:2], np.float32)
        for sm in shift4(good).values():
            m = sm & remaining
            cnt += m
            acc += np.where(m[..., None], colors, 0)
        upd = remaining & (cnt > 0)
        if not upd.any():
            break
        colors = np.where(upd[..., None], acc / np.maximum(cnt, 1)[..., None], colors)
        good = good | upd
        remaining = remaining & ~upd
    out = np.dstack([np.clip(colors, 0, 255).astype(np.uint8),
                     alpha.astype(np.uint8)])
    return Image.fromarray(out, "RGBA")


def L(*vals):
    return list(vals)


# Per-row motion. Qoder's loader plays these with fixed frame delays, so idle-class
# rows must stay near-still (<=2px single breath) or the pet visibly flickers.
ROWS = [
    # 0 idle (6): one slow 2px breath, then long rest - no oscillation
    ("stand", [dict(dy=v) for v in L(0, 1, 2, 1, 0, 0)]),
    # 1 runningRight (8): single gentle gait arc, constant lean
    ("run", [dict(dy=v, rot=-2) for v in L(0, 1, 2, 3, 2, 1, 0, 0)]),
    # 2 runningLeft (8): mirrored
    ("run", [dict(dy=v, rot=2, mirror=True) for v in L(0, 1, 2, 3, 2, 1, 0, 0)]),
    # 3 waving (4): slight friendly lean and return
    ("wave", [dict(rot=r, dy=d) for r, d in zip(L(0, 2, 2, 0), L(0, 1, 1, 0))]),
    # 4 jumping (5): smooth large arc
    ("jump",
     [dict(dy=d, sy=s) for d, s in zip(L(0, 14, 24, 14, 0), L(0.97, 1.0, 1.03, 1.0, 0.97))]),
    # 5 failed (8): slow single droop-sway and recovery
    ("sad",
     [dict(rot=r, dy=d) for r, d in zip(L(0, -1, -2, -2, -1, 0, 0, 0), L(0, 0, 1, 2, 2, 1, 0, 0))]),
    # 6 waiting (6): slow lean and return
    ("stand",
     [dict(dx=x, dy=d, rot=r) for x, d, r in zip(L(0, 1, 2, 3, 1, 0), L(0, 1, 1, 1, 0, 0), L(0, 1, 1, 1, 0, 0))]),
    # 7 running (6): single gait arc, neutral direction
    ("run", [dict(dy=v) for v in L(0, 1, 2, 2, 1, 0)]),
    # 8 review (6): slow nod forward and back
    ("review",
     [dict(dy=d, rot=r) for d, r in zip(L(0, 1, 2, 3, 2, 1), L(0, 1, 1, 2, 1, 0))]),
]

FRAME_COUNTS = [6, 8, 8, 4, 5, 8, 6, 6, 6]


def main():
    size_specs = {"stand": (184, 180), "wave": (176, 184), "jump": (168, 184),
                  "sad": (180, 184), "run": (172, 180), "review": (180, 184)}
    poses = {}
    for name, fname in POSES.items():
        h, mw = size_specs[name]
        poses[name] = bleed_resize(load_pose(os.path.join(BASE, "assets", "poses", fname)), h, mw)

    sheet = Image.new("RGBA", (CELL_W * N_COLS, CELL_H * N_ROWS), (0, 0, 0, 0))
    for row_idx, (pose_name, frame_specs) in enumerate(ROWS):
        assert len(frame_specs) == FRAME_COUNTS[row_idx], f"row {row_idx} frame count mismatch"
        assert len(frame_specs) <= N_COLS
        for col_idx, kw in enumerate(frame_specs):
            cell = frame(poses[pose_name], **kw)
            sheet.paste(cell, (col_idx * CELL_W, row_idx * CELL_H))

    sheet = clean_edges(sheet)

    for name, sp in poses.items():
        print(f"pose {name}: {sp.size[0]}x{sp.size[1]}")

    sheet_path = os.path.join(BASE, "silver-ponytail", "spritesheet.png")
    os.makedirs(os.path.dirname(sheet_path), exist_ok=True)
    sheet.save(sheet_path, "PNG")
    print("sheet:", sheet_path, sheet.size)

    pv = sheet.copy().convert("RGB")
    d = ImageDraw.Draw(pv)
    for i in range(1, N_COLS):
        d.line([(i * CELL_W, 0), (i * CELL_W, pv.size[1])], fill=(255, 0, 0), width=2)
    for i in range(1, N_ROWS):
        d.line([(0, i * CELL_H), (pv.size[0], i * CELL_H)], fill=(255, 0, 0), width=2)
    pv_path = os.path.join(BASE, "assets", "preview.png")
    pv.save(pv_path, "PNG")
    print("preview:", pv_path)


if __name__ == "__main__":
    main()
