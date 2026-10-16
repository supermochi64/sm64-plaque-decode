"""The plain stone behind the text (fixed-stone mode).

Every pixel outside two text boxes is stone and kept verbatim. Inside the boxes the stone is filled by Gaussian-process
inpainting from all other pixels: an anisotropic exponential kernel along the visible streak direction (bottom-left
to top-right) plus a quadratic trend.  The boxes are drawn around the visible text pixels:
    line 1: rows 8-12, columns 2-29        line 2: rows 16-20, columns 6-24
    python -m plaquedecode stone   -> stone/stone_box.npy (+ stone_box_var.npy, posterior variance per pixel)
Then score against it with  PLAQUE_STONE=stone/stone_box.npy PLAQUE_STONE_VAR=stone/stone_box_var.npy  (see core.py).
"""
import math, os
import numpy as np

N = 32
BOXES = [(8, 12, 2, 29), (16, 20, 6, 24)]                     # (row0, row1, col0, col1), inclusive
# kernel + trend fitted by maximum marginal likelihood on the plaque's stone pixels (rows 0-5 and 24-31 + margins):
# streak axis -30 deg, correlation 10 px along / 4.5 px across, variance 2.0, pixel noise 0.15 (5-bit levels^2)
HP = dict(theta=-30.0, l1=10.0, l2=4.5, s2=2.0, sn2=0.15,
          beta=[9.466947302608549, -0.5609825368671303, -0.004853568153286749,
                0.020786375346126824, 0.016055055523004427, -0.01576843146571252])
RR, CC = np.meshgrid(np.arange(N), np.arange(N), indexing="ij")
R, C = RR.ravel().astype(float), CC.ravel().astype(float)
TREND = np.stack([np.ones_like(R), R, C, R * R, C * C, R * C], 1)


def inside_mask(boxes=BOXES):
    m = np.zeros((N, N), bool)
    for r0, r1, c0, c1 in boxes: m[r0:r1 + 1, c0:c1 + 1] = True
    return m


def kernel(theta_deg, l1, l2, s2):
    th = math.radians(theta_deg); u = np.array([math.cos(th), math.sin(th)]); v = np.array([-math.sin(th), math.cos(th)])
    d = np.stack([C[:, None] - C[None, :], R[:, None] - R[None, :]], -1)
    return s2 * np.exp(-np.abs(d @ u) / l1) * np.exp(-np.abs(d @ v) / l2)


def estimate(T, boxes=BOXES, hp=HP):
    """stone (32x32, verbatim outside the boxes) and its posterior variance (0 outside)."""
    inside = inside_mask(boxes); y = T.astype(float).ravel(); idx = np.arange(N * N)
    var_obs = np.where(inside.ravel(), 1e6, hp["sn2"])       # pixels inside the boxes carry no information
    Kall = kernel(hp["theta"], hp["l1"], hp["l2"], hp["s2"]); mean = TREND @ np.asarray(hp["beta"])
    Ki = np.linalg.inv(Kall + np.diag(var_obs))
    mu = (mean + Kall @ Ki @ (y - mean)).reshape(N, N)
    var = np.clip(np.diag(Kall) - np.einsum("ij,jk,ik->i", Kall, Ki, Kall), 0, None).reshape(N, N)
    stone = T.astype(float).copy(); stone[inside] = mu[inside]
    return stone, np.where(inside, var, 0.0)


def main(T, outdir="stone", log=print):
    os.makedirs(outdir, exist_ok=True); s, v = estimate(T)
    np.save(os.path.join(outdir, "stone_box.npy"), s); np.save(os.path.join(outdir, "stone_box_var.npy"), v)
    log("stone -> %s/stone_box.npy (%d pixels filled inside the text boxes, the rest verbatim)" % (outdir, int(inside_mask().sum())))
