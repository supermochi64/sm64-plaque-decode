"""Calibration by simulation for the line-2 decoder.

Take the best real reading, remove its ink from the real texture and paint the ink of a known phrase in its place
(same recipe and configuration), keeping the real stone and the real fit residual.  Decode blind with the dictionary
search and record: exact-phrase rank, words recovered, and the gap between the true phrase's error and the best error
the decoder finds (this gap defines the "pixel-compatible window" used for the real plaque)."""
import json, random
import torch
from .core import Line2

SIMS = ["We hope so", "Rest in peace", "Shine on", "Tis my hope", "No hope in", "Our hope is", "May it shine", "For Mario",
        "Thank you", "Hope lives on", "Keep the hope", "We pray so", "Joy to all", "Light the way", "To hope is", "Good night"]
A = "We I My Our No So To The It Is In Of On All May Let For As".split()
B = "hope keep help pray play days ways eyes joy light night glory sleep happy magic".split()
C = "so on is in of us to be me we it as at".split()


def simulate(T, rec, fdir, line2_result, words, n, out, log, P2S=(16, 17, 18), seed=11, hope=None):
    L2 = Line2(T, rec, fdir) if hope is None else Line2(T, rec, fdir, hope["font2"], tr2=hope["tracking2"], kern2=hope["kern2"], frac2=hope["frac2"])
    best = line2_result["exact"][0]
    cfg = (best["P2"], best["esp"], best["x"], best["yb"])
    T2_real = L2.T2.clone()
    cov = lambda ph: (L2.BASE + L2.lin_text(ph, *cfg)).clamp(0, 1) ** L2.G
    cov_best = cov(best["phrase"])
    sims = list(SIMS); random.seed(seed)
    while len(sims) < n: sims.append("%s %s %s" % (random.choice(A), random.choice(B), random.choice(C)))
    res = []
    for k, ph in enumerate(sims[:n]):
        L2.T2 = T2_real - L2.L * cov_best + L2.L * cov(ph)
        L2.STONE = float(L2.sse_blocks(torch.zeros((L2.HB, 32), device=L2.dev)).sum())
        found, _ = L2.run_dp(words, list(P2S))
        ex = L2.rerank(found, 300)
        order = [r["phrase"] for r in ex]
        true_sse = L2.exact_refine(ph, cfg)[0]
        top = order[0]
        wok = sum(1 for x, y in zip(top.lower().split(), ph.lower().split()) if x == y)
        res.append(dict(true=ph, top=top, rank=order.index(ph) + 1 if ph in order else None, true_sse=true_sse,
                        top_sse=ex[0]["sse"], gap=true_sse - ex[0]["sse"], words_ok=wok, n_words=len(ph.split()), top10=order[:10]))
        log("SIM %2d true %-18r -> %-22r rank %s  gap %+.1f  words %d/%d" % (k, ph, top, res[-1]["rank"], res[-1]["gap"], wok, len(ph.split())))
        json.dump(res, open(out, "w"), indent=1)
    n1 = sum(1 for r in res if r["rank"] == 1); wo = sum(r["words_ok"] for r in res); wn = sum(r["n_words"] for r in res)
    log("exact #1 %d/%d, words %d/%d (%.0f%%), max gap truth-vs-best %.1f" % (n1, len(res), wo, wn, 100 * wo / wn, max(r["gap"] for r in res)))
