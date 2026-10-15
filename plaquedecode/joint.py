"""Joint two-line test for the case of 'Star' vs 'star': for each spelling take its top-N line-1 recipes, and for each
recipe score line 2 ("We hope so", free size/position/word space) under that same process + ink level.
The best SUM over both lines decides which spelling is consistent with one process for the whole plaque."""
import json
from .core import Line2, Recipe


def run(T, fdir, recipe_files, line2_text, out, log, topn=100, P2S=(15, 16, 17, 18, 19)):
    res = {}
    for text, path in recipe_files.items():
        R = sorted(json.load(open(path)), key=lambda r: r["sse"])[:topn]
        rows = []
        for r in R:
            rec = Recipe(**r); L2 = Line2(T, rec, fdir, line1_text=text)
            found = L2.run_combo([line2_text], list(P2S))
            e = L2.rerank(found, 1)[0]
            rows.append(dict(line1=rec.sse, line2=e["sse"], total=rec.sse + e["sse"], recipe=r))
        rows.sort(key=lambda x: x["total"])
        res[text] = rows
        log("%r: best joint total %.1f (line 1 %.1f + line 2 %.1f); best line-1-only recipe gives total %.1f" % (
            text, rows[0]["total"], rows[0]["line1"], rows[0]["line2"], min(rows, key=lambda x: x["line1"])["total"]))
        json.dump(res, open(out, "w"))
