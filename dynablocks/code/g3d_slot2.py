"""Word search for one centred label slot with the engine renderer (g3d_font) and fixed calibrated style.
    python3 g3d_slot2.py THUMB SKY FNT calib.json slot.json vocab.txt OUT.json
slot.json: {"win": [...], "size": 16, "cx": 753.5, "y": 141, "fixed": [[text, cx, y], ...], "caps": true, "maxw": 90,
            "extra": [...], "procs": 14}"""
import json, sys
import numpy as np
from multiprocessing import Pool
import g3d_text as G, g3d_font as GF

thumb, sky, fnt, cj, sj, voc, out = sys.argv[1:8]
M = G.Model(thumb, sky, fnt); gf = GF.Font(fnt); C = json.load(open(cj)); K = np.array(C["coef"]); bw, mode = C["bw"], C["mode"]
S = json.load(open(sj)); W = tuple(S["win"]); size = S["size"]


def feat(w, cx, y):
    return M.feats_g3d(w, cx - gf.width(w, size) / 2, y, size, W, gf, bw, mode)


FIXED = [feat(t, cx, y) for t, cx, y in S.get("fixed", [])]


def score(w):
    return min(M.solve(FIXED + [feat(w, S["cx"] + dx, S["y"] + dy)], W, K)[0] for dx in (-2, 0, 2) for dy in (-1, 0, 1)), w


if __name__ == "__main__":
    words = {w.strip() for w in open(voc) if w.strip() and not w.startswith("#")} | set(S.get("extra", []))
    if S.get("caps", True): words = {w for w in words if w[0].isupper() or w[0].isdigit() or w[0] in "(-"}
    words = sorted(w for w in words if all(ord(ch) < 128 for ch in w) and 2 <= gf.width(w, size) <= S.get("maxw", 90))
    with Pool(S.get("procs", 14)) as pool: res = pool.map(score, words, chunksize=32)
    res.sort(); json.dump([(round(a, 2), b) for a, b in res[:300]], open(out, "w"), indent=0)
    print(len(words), "words; top 25:", [(round(a, 1), b) for a, b in res[:25]])
    for w in S.get("extra", []): print("  %-10s rank %d" % (w, 1 + [b for _, b in res].index(w)) if w in [b for _, b in res] else "")
