"""Score complete text hypotheses for one HUD line over one or more views (shared x/y search), engine renderer +
fixed calibrated style.  Hypotheses: a file of lines, or generated "w1 w2" pairs from a vocabulary with a width window.
    python3 g3d_lines.py FNT calib.json job.json OUT.json
job.json: {"views": [...as g3d_beam2...], "size": 16, "x": [..], "y": [..], "cands": "file" | null,
           "pairs": {"vocab": "vocab.txt", "w1": [min,max] px, "total": [min,max] px, "sep": " ", "k1": 400}, "procs": 14}"""
import json, sys, itertools
import numpy as np
from multiprocessing import Pool
import g3d_text as G, g3d_font as GF

fnt, cj, jj, out = sys.argv[1:5]
gf = GF.Font(fnt); C = json.load(open(cj)); K = np.array(C["coef"]); bw, mode = C["bw"], C["mode"]
J = json.load(open(jj)); size = J["size"]
V = []
for v in J["views"]:
    M = G.Model(v["thumb"], v["bg"], fnt); M.set_mask(v.get("mask", []))
    FX = [M.feats_g3d(t, fx, fy, fs, tuple(v["win"]), gf, bw, mode) for t, fx, fy, fs in v.get("fixed", [])]   # known neighbouring text
    V.append((M, tuple(v["win"]), FX, v.get("dy", 0)))


def score_xy(text, x, y):
    return sum(M.solve(FX + [M.feats_g3d(text, x, y + dy, size, W, gf, bw, mode)], W, K)[0] for M, W, FX, dy in V)


def score(text):
    """x list = left pen positions, or with "cx": offsets around a centre (centred labels)."""
    xs = [J["cx"] + d - gf.width(text, size) / 2 for d in J["x"]] if "cx" in J else J["x"]
    best = min((score_xy(text, x, y), x, y) for x in xs for y in J["y"])
    return best[0], text, best[1], best[2]


def s1(w):
    P = J["pairs"]; V1 = [(M, (W[0], W[1], W[2], P["w1col"]), dy) for M, W, FX, dy in V]
    pre = P.get("prefix", "")
    return min(sum(M.solve([M.feats_g3d(pre + w, x, y + dy, size, W1, gf, bw, mode)], W1, K)[0] for M, W1, dy in V1) for x in J["x"] for y in J["y"]), w


if __name__ == "__main__":
    if J.get("cands"): cands = [l.rstrip("\n") for l in open(J["cands"]) if l.strip()]
    else:
        P = J["pairs"]; voc = sorted({w.strip() for w in open(P["vocab"]) if w.strip() and not w.startswith("#") and all(ord(c) < 128 for c in w.strip())} | set(P.get("extra", [])))
        w1 = [w for w in voc if P["w1"][0] <= gf.width(w, size) <= P["w1"][1] and (not P.get("cap1") or w[0].isupper())]
        # stage 1: first word alone (its own columns only) keeps the k1 best
        with Pool(J.get("procs", 14)) as pool: r1 = sorted(pool.map(s1, w1, chunksize=32))
        keep = [w for _, w in r1[:P.get("k1", 300)]]; print("stage1 top:", [(round(a, 1), b) for a, b in r1[:20]], flush=True)
        w2 = [w for w in voc if gf.width(w, size) <= P["total"][1] and (not P.get("cap2") or w[0].isupper())]
        pre = P.get("prefix", "")
        cands = [pre + a + P.get("sep", " ") + b for a in keep for b in w2 if P["total"][0] <= gf.width(a + P.get("sep", " ") + b, size) <= P["total"][1]]
        print(len(cands), "pair candidates", flush=True)
    with Pool(J.get("procs", 14)) as pool: res = sorted(pool.map(score, cands, chunksize=16))
    json.dump([(round(a, 2), b, c, d) for a, b, c, d in res[:500]], open(out, "w"), indent=0)
    print("TOP 30:"); [print("%9.2f  %-30r x %.1f y %.1f" % r) for r in res[:30]]
