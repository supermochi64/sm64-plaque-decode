"""Structured fit of a debug line "<sign><int>.<dec> <WORD>  <int>.<dec> <unit>": every layout (sign, integer digits,
decimals, word from a list, unit) is fitted with coordinate descent over the digit positions (all 10 digits tried per
position, 3 passes), engine renderer + fixed calibrated style.  Prints the best layouts with their digits.
    python3 g3d_numfit.py FNT calib.json job.json OUT.json
job.json: {"views": [{thumb,bg,win}], "y": 112.45, "x": [13.25], "dy": [-1.5,0,1.5], "words": [...], "units": [...],
           "int1": [1,2,3], "int2": [1,2,3], "dec": [3], "signs": ["", "-"], "seps": ["  "], "procs": 14}"""
import json, sys, itertools
import numpy as np
from multiprocessing import Pool
import g3d_text as G, g3d_font as GF

fnt, cj, jj, out = sys.argv[1:5]
gf = GF.Font(fnt); C = json.load(open(cj)); K = np.array(C["coef"]); bw, mode = C["bw"], C["mode"]
J = json.load(open(jj)); V = [(G.Model(v["thumb"], v["bg"], fnt), tuple(v["win"])) for v in J["views"]]
DIG = "0123456789"


def score(text):
    return min(sum(M.solve([M.feats_g3d(text, x, J["y"] + dy, 16, W, gf, bw, mode)], W, K)[0] for M, W in V)
               for x in J["x"] for dy in J["dy"])


def fit_layout(lay):
    if isinstance(lay, str): tmpl = lay                                      # template mode: '#' = free digit
    else:
        sign, i1, d1, word, sep, i2, d2, unit = lay
        tmpl = sign + "#" * i1 + ("." + "#" * d1 if d1 else "") + (" " + word if word else "") + sep + "#" * i2 + ("." + "#" * d2 if d2 else "") + " " + unit
    pos = [i for i, ch in enumerate(tmpl) if ch == "#"]; t = list(tmpl.replace("#", "5")); cur = score("".join(t))
    for _ in range(3):
        changed = False
        for p in pos:
            best = (cur, t[p])
            for dgt in DIG:
                if dgt == t[p]: continue
                q = t[:]; q[p] = dgt; v = score("".join(q))
                if v < best[0]: best = (v, dgt)
            if best[1] != t[p]: t[p] = best[1]; cur = best[0]; changed = True
        if not changed: break
    return cur, "".join(t)


if __name__ == "__main__":
    lays = J["templates"] if "templates" in J else list(itertools.product(J.get("signs", ["", "-"]), J.get("int1", [1, 2, 3]), J.get("dec", [3]), J["words"], J.get("seps", ["  "]),
                                  J.get("int2", [1, 2, 3]), J.get("dec2", [3]), J.get("units", ["msec"])))
    print(len(lays), "layouts", flush=True)
    with Pool(J.get("procs", 14)) as pool: res = sorted(pool.map(fit_layout, lays, chunksize=2))
    json.dump([(round(a, 2), b) for a, b in res[:300]], open(out, "w"), indent=0)
    print("TOP 30:"); [print("%9.2f  %r" % r) for r in res[:30]]
