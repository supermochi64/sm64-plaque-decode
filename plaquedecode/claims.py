"""Score published / proposed readings of the plaque with the SAME forward model.

Line 1 of every claim gets its OWN exhaustive designer-recipe search (no advantage for our reading).  Line 2 is scored
(a) under that claim's own line-1 recipe and ink level (joint, self-consistent) and (b) under the 'Eternal Star'
recipe (isolates the line-2 text).  A claim without a stated second line is scored on line 1 only."""
import json, os
import numpy as np
import torch
from .core import Line1, Line2, Recipe, search_recipes

CLAIMS = [
    dict(id="lisreal", line1="L is real 2401", line2=None, who="1990s rumour ('Luigi is real'), whole phrase on row 1", year="1997-98"),
    dict(id="lisreal2041", line1="L is real 2041", line2=None, who="variant spelling, row 1 (e.g. MobyGames trivia)", year="-"),
    dict(id="secretstar", line1="A Secret star", line2="lie here ~", who="Daniel Nodd (No64DD), Nintendo Life", year="2015/2019"),
    dict(id="lisrealstar", line1="L is real star", line2=None, who="reader comment, Nintendo Life", year="2019"),
    dict(id="eternal", line1="Eternal Star", line2=None, who="Super Mario Wiki ('more likely')", year="-"),
    dict(id="myhopeis", line1="Eternal Star", line2="My hope is", who="proposed reading (two descenders + ascender)", year="-"),
    dict(id="myhopeis_lc", line1="Eternal Star", line2="my hope is", who="same, lower case", year="-"),
    dict(id="lieherestar", line1="Eternal Star", line2="lie here ~", who="Nodd's line 2 under Eternal Star", year="-"),
    dict(id="ours", line1="Eternal Star", line2="We hope so", who="this work", year="2026"),
    dict(id="ours_lc", line1="Eternal star", line2="We hope so", who="this work (lower-case s)", year="2026"),
]
FULL = dict(kxy=[(kx, ky) for kx in (4, 5, 6, 8) for ky in (4, 5, 6) if 1.0 <= kx / ky <= 1.5], filters=["bilinear", "bicubic5"],
            blurs=(0.0, 0.3, 0.45, 0.6), gammas=(1.0, 1.4, 1.8, 2.2), esps=(-1.0, -0.5, 0.0, 0.5), fracs=(False, "glyph"))


def line2_score(L2, text, P2S=range(13, 21)):
    if text == "": return L2.STONE, None
    found = L2.run_combo([text], list(P2S))
    r = L2.rerank(found, 1)[0]
    return r["sse"], (r["P2"], r["esp"], r["x"], r["yb"])


def score_claims(T, fdir, font, star_recipe: Recipe, out, log, cache_dir="results"):
    l1 = Line1(T)
    L2star = Line2(T, star_recipe, fdir)
    res = []
    for c in CLAIMS:
        cache = os.path.join(cache_dir, "recipes_%s_%s.json" % (os.path.splitext(font)[0], c["line1"].replace(" ", "_")))
        if c["line1"] == "Eternal Star":
            rec = star_recipe
        elif os.path.exists(cache):
            rec = Recipe(**min(json.load(open(cache)), key=lambda r: r["sse"]))
        else:
            log("recipe search for %r" % c["line1"])
            R = sorted(search_recipes(l1, fdir, font, c["line1"], **FULL), key=lambda r: r.sse)
            json.dump([r.to_dict() for r in R[:300]], open(cache, "w")); rec = R[0]
        r = dict(c, font=font, line1_sse=rec.sse, floor=l1.floor, recipe=rec.to_dict())
        if c["line2"] is not None:
            L2own = Line2(T, rec, fdir, line1_text=c["line1"])
            r["line2_sse_joint"], r["line2_cfg_joint"] = line2_score(L2own, c["line2"])
            r["line2_sse_starrecipe"], _ = line2_score(L2star, c["line2"])
            r["total_joint"] = rec.sse + r["line2_sse_joint"]
        res.append(r)
        log("%-16r / %-12r line1 %.1f  line2(joint) %s  line2(Star recipe) %s" % (c["line1"], c["line2"], rec.sse,
            "%.1f" % r["line2_sse_joint"] if "line2_sse_joint" in r else "-", "%.1f" % r["line2_sse_starrecipe"] if "line2_sse_starrecipe" in r else "-"))
        json.dump(res, open(out, "w"), indent=1)
    # descender evidence: row 20 (one below the line-2 baseline) against the clean-stone noise of the same operator
    Tt = torch.as_tensor(np.asarray(T, np.float32))
    ref = Tt[21:24].mean(0); exc = (Tt[20] - ref).tolist()
    sd = float(Tt[23:32].std())
    json.dump(dict(claims=res, row20_excess=exc, stone_sd=sd), open(out, "w"), indent=1)
    log("row-20 excess over rows 21-23 (descender evidence), stone sd %.2f:" % sd,
        ["c%d %+.1f" % (i, e) for i, e in enumerate(exc) if 5 <= i <= 25])
