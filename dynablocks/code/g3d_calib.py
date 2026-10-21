"""Calibrate the G3D text process on screenshot 1 line 1 (known text): font file, size, pen x/y, border width + mode;
style coefficients in closed form.  Prints the best settings and the controls under fixed style.
    uv run python g3d_calib.py THUMB SKY FNT_DIR OUT.json
"""
import json, sys, itertools
import numpy as np
import g3d_text as G, g3d_font as GF

thumb, sky, fd, out = sys.argv[1:5]
M = G.Model(thumb, sky, fd + "/dominant-small.fnt")
T = "Level 1: Build a bridge that doesn't break"; W = (6, 12, 0, 82)
CONTROLS = ["Level 2: Build a bridge that doesn't break", "Level 1: Build a bridge that does break",
            "Level 1: Make a bridge that won't break", "Level 1: Build a tower that doesn't fall", "Level 7: Build a bridge that doesn't break"]


def fit(gf, bw, mode, start, coef=None, text=T):
    p = list(start) + [1.0, 0.0][len(start) - 3:] if len(start) < 5 else list(start); cache = {}

    def sc(q):
        k = tuple(q)
        if k not in cache: cache[k] = M.solve([M.feats_g3d(text, q[0], q[1], q[2], W, gf, bw, mode, q[3], q[4])], W, coef)[0]
        return cache[k]
    cur = sc(p)
    for st in ((2, 2, 0.5, 0.04, 0.4), (1, 1, 0.25, 0.02, 0.2), (0.5, 0.5, 0.1, 0.01, 0.1), (0.25, 0.25, 0.05, 0.005, 0.05)):
        imp = True
        while imp:
            imp = False
            for i in range(5):
                for d in (-st[i], st[i]):
                    q = p[:]; q[i] = round(q[i] + d, 3); v = sc(q)
                    if v < cur: cur, p, imp = v, q, True
    return cur, p


if __name__ == "__main__":
    res = []
    for fn in ("dominant-small",):
        gf = GF.Font(fd + "/" + fn + ".fnt"); target = 421.0
        s0 = 22.67 * target / gf.width(T, 22.67)
        for bw, mode in itertools.product((1.0, 1.5, 2.0), ("cross", "ring")):
            best = min(fit(gf, bw, mode, (x, y, s0)) for x in (8, 11) for y in (28, 31))
            res.append((best[0], fn, bw, mode, best[1])); print("%-15s bw %.1f %-5s mse %.1f  x,y,size %s" % (fn, bw, mode, best[0], best[1]), flush=True)
    res.sort(key=lambda r: r[0]); e, fn, bw, mode, p = res[0]; gf = GF.Font(fd + "/" + fn + ".fnt")
    K = M.solve([M.feats_g3d(T, p[0], p[1], p[2], W, gf, bw, mode, p[3], p[4])], W)[1]
    print("BEST", res[0], "\ncoef", np.round(K, 3))
    for c in CONTROLS:
        print("control %-45s %.1f" % (c, fit(gf, bw, mode, p, K, c)[0]))
    json.dump(dict(font=fn, bw=bw, mode=mode, x=p[0], y=p[1], size=p[2], ax=p[3], track=p[4], coef=K.tolist(), mse=e), open(out, "w"), indent=1)
