"""Feasibility of a centred label slot: plant known words into the REAL thumbnail background (the model's own
prediction of the planted word replaces the slot, plus the measured residual noise of the real fit), then rank the
true word among the vocabulary exactly like g3d_slot2.  Reports the rank distribution.
    python3 g3d_feas.py THUMB SKY FNT calib.json slot.json vocab.txt N_TRIALS
"""
import json, sys, random
import numpy as np
from multiprocessing import Pool
import g3d_text as G, g3d_font as GF

thumb, sky, fnt, cj, sj, voc, n = sys.argv[1:8]; n = int(n)
gf = GF.Font(fnt); C = json.load(open(cj)); K = np.array(C["coef"]); bw, mode = C["bw"], C["mode"]
S = json.load(open(sj)); W = tuple(S["win"]); size = S["size"]; r0, r1, c0, c1 = W
M = G.Model(thumb, sky, fnt)
words = sorted({w.strip() for w in open(voc) if w.strip() and not w.startswith("#") and all(ord(c) < 128 for c in w.strip())})
words = [w for w in words if w[0].isupper() and 2 <= gf.width(w, size) <= S.get("maxw", 90)]
feat = lambda w, cx, y: M.feats_g3d(w, cx - gf.width(w, size) / 2, y, size, W, gf, bw, mode)
FIXED = [feat(t, cx, y) for t, cx, y in S.get("fixed", [])]
NOISE = float(S.get("noise_mse", 30.0)) ** 0.5
REAL = M.T.copy()


def plant(w, seed):
    rng = np.random.default_rng(seed); _, _, pred = M.solve(FIXED + [feat(w, S["cx"], S["y"])], W, K)
    T = REAL.copy(); T[r0:r1, c0:c1] = pred + rng.normal(0, NOISE, pred.shape); return np.clip(T, 0, 255)


def rank(args):
    w, seed = args; M.T = plant(w, seed); res = []
    for v in words:
        res.append(min(M.solve(FIXED + [feat(v, S["cx"] + dx, S["y"] + dy)], W, K)[0] for dx in (-2, 0, 2) for dy in (-1, 0, 1)))
    order = np.argsort(res); return w, 1 + int(np.where(np.array(words)[order] == w)[0][0])


if __name__ == "__main__":
    random.seed(1); trials = [(w, i) for i, w in enumerate(random.sample(words, n))]
    with Pool(S.get("procs", 14)) as pool: out = pool.map(rank, trials)
    rk = np.array([r for _, r in out]); print("planted words:", out)
    print("rank 1: %d/%d   top-10: %d   top-50: %d   median rank %d of %d" % ((rk == 1).sum(), n, (rk <= 10).sum(), (rk <= 50).sum(), np.median(rk), len(words)))
