"""Work backwards from 'hope' (user idea 2026-10-14): assume the middle word of line 2 is 'hope' and fit line 2's OWN
typesetting on the pixels of that word only (4-column stone blocks 3-4 = texture cols 12-19): face/style, pixel size,
tracking, pair kerning, advance mode, exact pen position and baseline.  Canvas, resize filter, blur, gamma and ink level
are shared with line 1 (one image, resized once).  The calibrated line-2 setting is then used to re-score the
candidates for the first word and the ending."""
import json, itertools, os
import numpy as np
import torch
from .core import Line2, render_text
from . import candidates as CAND

HOPE_BLOCKS = [3, 4]


def fit(T, rec, fdir, fonts2, log, P2S=range(13, 22)):
    rows = []
    for f2 in fonts2:
        for TR2, kern, frac in itertools.product((-1, 0, 1, 2, 3), (False, True), ("glyph", False)):
            L2 = Line2(T, rec, fdir, font2=f2, tr2=TR2, kern2=kern, frac2=frac)
            WYb = L2.WY[L2.B0:L2.B1]
            for P2 in P2S:
                im, base_row, penx, _ = render_text(L2.fpath, "hope", P2, TR2, kern, frac, 0)
                hI, wI = im.shape; I = torch.tensor(im, device=L2.dev); MARG = wI + hI + 64
                WYp = torch.nn.functional.pad(WYb, (MARG, MARG)); WXp = torch.nn.functional.pad(L2.WX, (MARG, MARG))
                # pen positions so that 'hope' lands around texture cols 11..20
                xs = list(range(L2.OFFX + 9 * L2.kx, L2.OFFX + 16 * L2.kx))
                WXs = torch.stack([WXp[:, x - penx + MARG: x - penx + MARG + wI] for x in xs])        # (nx, 32, wI)
                best = None
                for yb in L2.YBS:
                    Zy = WYp[:, yb - base_row + MARG: yb - base_row + MARG + hI] @ I               # (HB, wI)
                    lin = torch.einsum("rw,xcw->xrc", Zy, WXs)                                   # (nx, HB, 32)
                    sb = L2.sse_blocks(lin)[:, HOPE_BLOCKS].sum(-1)
                    j = int(torch.argmin(sb)); v = float(sb[j])
                    if best is None or v < best[0]: best = (v, xs[j], yb)
                rows.append(dict(font2=f2, tracking2=TR2, kern2=kern, frac2=frac, P2=P2, sse_hope=best[0], x=best[1], yb=best[2]))
        log("  %s done, best so far %s" % (f2, min(rows, key=lambda r: r["sse_hope"])))
    rows.sort(key=lambda r: r["sse_hope"])
    return rows


def run(T, rec, fdir, fonts2, line2_best, out, log):
    rows = fit(T, rec, fdir, fonts2, log)
    b = rows[0]
    log("best 'hope' typesetting: %s" % b)
    L2 = Line2(T, rec, fdir, font2=b["font2"], tr2=b["tracking2"], kern2=b["kern2"], frac2=b["frac2"])
    cfg0 = (b["P2"], line2_best["esp"], line2_best["x"], b["yb"])
    res = dict(fit=rows[:200], best=b, font=rec.font)
    res["first"] = CAND.score_all(L2, [w + " hope so" for w in CAND.FIRST + CAND.JUNK_FIRST], cfg0)
    log("first word (local): %s" % sorted(((round(v["local"]["first"], 1), k.split()[0]) for k, v in res["first"].items()))[:12])
    res["ending"] = CAND.score_all(L2, ["We hope " + e for e in CAND.ENDINGS + CAND.JUNK_END], cfg0)
    log("ending (local): %s" % sorted(((round(v["local"]["ending"], 1), k.split(" ", 2)[2]) for k, v in res["ending"].items()))[:14])
    res["variants"] = CAND.score_all(L2, CAND.VARIANTS + ["By hope so", "Be hope so", "Be with us", "Me hope so"], cfg0)
    log("variants: %s" % sorted(((round(v["sse"], 1), k) for k, v in res["variants"].items()))[:14])
    json.dump(res, open(out, "w"))
