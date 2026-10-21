"""Background estimate for screenshot 2 (unknown camera, no rebuilt sky): inside each text block the thumb is replaced
by a per-column linear interpolation between the clean rows just above and below the block, then upscaled to the
806x632 canvas (bicubic).  Blocks: (row_above, row_below, c0, c1).
    uv run python g3d_bg.py THUMB2 OUT.png
"""
import sys
import numpy as np
from PIL import Image

BLOCKS = [(6, 12, 0, 60),        # title line
          (12, 29, 0, 40),       # stats lines (sky gradient; the ground edge crosses at the far right)
          (100, 110, 0, 22),     # bottom-left lines (flat green)
          ]

if __name__ == "__main__":
    T = np.asarray(Image.open(sys.argv[1]).convert("RGB")).astype(np.float32); bg = T.copy()
    for a, b, c0, c1 in BLOCKS:
        for r in range(a + 1, b): w = (r - a) / (b - a); bg[r, c0:c1] = (1 - w) * T[a, c0:c1] + w * T[b, c0:c1]
    # stats block: sky and ground are split by a straight edge -> separate quadratic surfaces, class by the fitted edge
    R, Cc = np.mgrid[0:113, 0:144]; G = T[..., 1] - np.maximum(T[..., 0], T[..., 2]) > 25
    zone = (R >= 4) & (R < 60) & (Cc >= 1) & (Cc < 70); txt = np.zeros_like(G); txt[13:30, 0:42] = True
    edge = [(r, int(np.argmax(G[r, 1:70])) + 1) for r in range(30, 60) if G[r, 1:70].any()]                # first green col per row
    edge += [(r, int(np.argmax(G[r, 1:70])) + 1) for r in range(4, 6) if G[r, 1:70].any()]
    er, ec = np.array(edge, float).T; k = np.polyfit(er, ec, 1)                                              # col = k0*row + k1
    green_px = Cc >= np.polyval(k, R)
    X = np.stack([np.ones_like(R), R, Cc, R * R, Cc * Cc, R * Cc], -1).astype(np.float64)
    for cls in (False, True):
        m = zone & ~txt & (green_px == cls) & (G == cls)
        for ch in range(3):
            kk = np.linalg.lstsq(X[m], T[..., ch][m], rcond=None)[0]; sel = txt & (green_px == cls) & zone
            bg[..., ch][sel] = (X[sel] @ kk)
    print("edge col = %.2f*row + %.1f" % tuple(k))
    # right column on the green ground: quadratic fit per channel to the green (text-free) pixels
    r0, r1, c0, c1 = 50, 112, 112, 143
    R, Cc = np.mgrid[r0:r1, c0:c1]; P = T[r0:r1, c0:c1]
    green = (P[..., 1] - np.maximum(P[..., 0], P[..., 2]) > 25)
    X = np.stack([np.ones_like(R), R, Cc, R * R, Cc * Cc, R * Cc], -1).reshape(-1, 6).astype(np.float64); m = green.ravel()
    for ch in range(3):
        k = np.linalg.lstsq(X[m], P[..., ch].reshape(-1)[m], rcond=None)[0]; bg[r0:r1, c0:c1, ch] = (X @ k).reshape(r1 - r0, c1 - c0)
    print("right-column green fit residual on green pixels: %.2f" % float(np.abs(bg[r0:r1, c0:c1] - P)[green].mean()))
    full = Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8)).resize((806, 632), Image.BICUBIC); full.save(sys.argv[2])
