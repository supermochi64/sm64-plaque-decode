"""List-bias test: can the curated sentence list produce a confident, sensible answer when the true line-2 text is NOT
in the list?  (Reviewer question, 2026-10-15.)

Same set-up as the real line-2 decode (Adobe recipe, line-2 typesetting calibrated on "hope", best configuration of the
real plaque).  For every planted phrase, the real line-2 ink is replaced by the planted phrase's ink (real stone and fit
residual kept, as in simulate.py), then the plaque is decoded twice:
  * LIST  = combo search over the curated sentence list (~1.5 M sensible phrases, phrases.curated()),
  * BLIND = dictionary DP over ~17.7 k words (no sentence list) = the best error reachable without the list.
Reported per plant: the list's answer, its error minus the planted truth's error, minus the blind optimum, and whether it
lies inside the pixel-compatible window (list error - optimum <= W).  The real plaque is decoded the same way as reference.

  python -m plaquedecode.listbias --recipes results/recipes_AdobePalatino-BoldItalic.json \\
      --line2 results/line2_dp_hopefit_adobe.json --hopefit results/hopefit_adobe.json --out results/listbias_adobe.json
"""
import argparse, json, os
import torch
from .core import Line2
from .phrases import curated
from .__main__ import log, load_T, best_recipe, words_from

# phrases that are NOT in the curated list (checked at run time): ordinary sign/plaque texts of similar length ...
OFF = ["Big Boo lives", "Go see Peach", "Run and jump", "Do not swim", "Sun is up", "Fish swim here", "Cake is ready",
       "Find the key", "Come back soon", "Mind the gap", "Watch your step", "Toad was here", "Look up high", "Wet paint",
       "Stay calm", "Be brave", "Have fun", "Gone fishing", "Keep out", "Lost and found", "Welcome home", "Sit and rest",
       "Bob was here", "Who knows", "Not for sale", "See you soon", "Push to open", "Made in Kyoto",
       # ... and hope-shaped sentences whose first or last word is not in the list (the critical case)
       "We hope not", "We hope yes", "No hope left", "Al hope so", "Ma hope so", "We hope lots"]
# controls that ARE in the list
ON = ["We hope so", "Shine on", "Rest in peace", "Thank you", "Joy to all", "My hope is", "Good night", "For Mario"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--texture", default="texture.npy"); ap.add_argument("--fonts-dir", default="fonts_cmp")
    ap.add_argument("--recipes", required=True); ap.add_argument("--line2", required=True); ap.add_argument("--hopefit", required=True)
    ap.add_argument("--vocab", default="data/vocab_en_core.txt"); ap.add_argument("--p2", default="18,19,20")
    ap.add_argument("--window", type=float, default=58.0, help="pixel-compatible window (max calibrated gap)")
    ap.add_argument("--n", type=int, default=0, help="only the first n plants (0 = all)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    T = load_T(a.texture); rec = best_recipe(a.recipes); hb = json.load(open(a.hopefit))["best"]
    L2 = Line2(T, rec, a.fonts_dir, hb["font2"], tr2=hb["tracking2"], kern2=hb["kern2"], frac2=hb["frac2"])
    best = json.load(open(a.line2))["exact"][0]
    cfg = (best["P2"], best["esp"], best["x"], best["yb"])
    P2S = [int(p) for p in a.p2.split(",")]
    LIST = sorted(curated()); LSET = set(LIST); words = words_from(a.vocab)
    off = [p for p in OFF if p not in LSET]; on = [p for p in ON if p in LSET]
    log("list %d phrases | off-list plants %d (dropped %s) | on-list controls %d | cfg %s" % (
        len(LIST), len(off), [p for p in OFF if p in LSET], len(on), cfg))
    T2_real = L2.T2.clone()
    cov = lambda ph: (L2.BASE + L2.lin_text(ph, *cfg)).clamp(0, 1) ** L2.G
    cov_best = cov(best["phrase"])

    def decode(tag, truth):
        L2.STONE = float(L2.sse_blocks(torch.zeros((L2.HB, 32), device=L2.dev)).sum())
        lx = L2.rerank(L2.run_combo(LIST, P2S), 40)
        dx = L2.rerank(L2.run_dp(words, P2S)[0], 300)
        s_true = L2.exact_refine(truth, cfg)[0] if truth else None
        s_list, s_dp = lx[0]["sse"], dx[0]["sse"]
        opt = min(x for x in (s_list, s_dp, s_true) if x is not None)
        r = dict(kind=tag, truth=truth, list_top=lx[0]["phrase"], list_2nd=lx[1]["phrase"], s_list=s_list,
                 s_list2=lx[1]["sse"], s_dp=s_dp, dp_top=dx[0]["phrase"], s_true=s_true, optimum=opt,
                 list_minus_opt=s_list - opt, list_minus_true=(s_list - s_true) if truth else None,
                 in_window=(s_list - opt) <= a.window, list_is_truth=(lx[0]["phrase"] == truth),
                 list_top5=[(x["phrase"], round(x["sse"], 1)) for x in lx[:5]])
        log("%-6s %-16r list -> %-16r  list-opt %+6.1f  list-true %s  in-window %s" % (
            tag, truth, r["list_top"], r["list_minus_opt"], "%+.1f" % r["list_minus_true"] if truth else "-", r["in_window"]))
        return r

    res = [decode("real", None)]
    plants = [("off", p) for p in off] + [("on", p) for p in on]
    if a.n: plants = plants[:a.n]
    for tag, ph in plants:
        L2.T2 = T2_real - L2.L * cov_best + L2.L * cov(ph)
        res.append(decode(tag, ph))
        L2.T2 = T2_real
        json.dump(dict(window=a.window, cfg=cfg, list_size=len(LIST), results=res), open(a.out, "w"), indent=1)
    offr = [r for r in res if r["kind"] == "off"]
    if offr:
        log("OFF-LIST: list answer inside the window in %d/%d plants; median list-opt %.1f" % (
            sum(r["in_window"] for r in offr), len(offr), sorted(r["list_minus_opt"] for r in offr)[len(offr) // 2]))


if __name__ == "__main__":
    main()
