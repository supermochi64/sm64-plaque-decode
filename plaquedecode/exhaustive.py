"""Exhaustive slot checks: does any string at all beat the reading?

  line 1, word 2 : "Eternal " + every string of 3 or 4 letters (first letter any case, rest lower case) - 950 k strings
  line 2, first  : X + " hope so" for every string of 1-3 letters (first letter any case)
  line 2, middle : "We " + X + " so" for every lower-case string of 4 letters (457 k)
  line 2, ending : "We hope " + X for every string of 1-3 letters (first letter any case) + "so." / "so!"
Line 1 uses glyph tiles (coverage is linear in the artwork before gamma), so every candidate is scored exactly under the
locked recipe; line 2 uses the additive glyph-table search (run_combo) followed by an exact re-render of the best.
    python -m plaquedecode.exhaustive --recipes R --hopefit H --line2 L --out results/exhaustive.json
"""
import argparse, itertools, json, os, string
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont
from .core import Line1, Line2, render_text
from .__main__ import log, load_T, best_recipe

LOW, UP = string.ascii_lowercase, string.ascii_uppercase
VOCAB = set()


def strings(n, cap_first=True):
    first = (LOW + UP) if cap_first else LOW
    return ["".join(p) for p in itertools.product(first, *([LOW] * (n - 1)))]


def line1_word2(T, rec, fdir, lengths=(3, 4), esps=(-1.0, -0.5, 0.0, 0.5), chunk=40000):
    l1 = Line1(T); dev = l1.dev; WX, WY = rec.matrices(dev); WYb = WY[l1.R0:l1.R1]
    fpath = os.path.join(fdir, rec.font); f = ImageFont.truetype(fpath, rec.P); asc, desc = f.getmetrics(); Hh = asc + desc + 4
    _, _, _, (r0, r1, c0, c1) = render_text(fpath, "Eternal Star", rec.P, rec.tracking, rec.kern, rec.frac, int(round(rec.esp * rec.kx)))
    ox = rec.X + rec.offx - max(0, c0 - 1); oy = rec.Y + rec.offy - max(0, r0 - 1)
    adv = {c: (round(f.getlength(c)) if rec.frac == "glyph" else f.getlength(c)) for c in LOW + UP + " "}
    # glyph tiles: char c with its pen at line-image x -> (9, 32) linear coverage
    gl = {}
    for c in LOW + UP:
        im = Image.new("L", (4 * rec.P, Hh), 0); ImageDraw.Draw(im).text((rec.P, asc + 2), c, 255, font=f, anchor="ls")
        a = np.asarray(im, np.float32) / 255.0; cols = np.nonzero(a.sum(0) > 0)[0]
        gl[c] = (torch.tensor(a[:, cols.min():cols.max() + 1], device=dev), int(cols.min()) - rec.P)
    tiles = {}

    def tile(c, pen):
        k = (c, pen)
        if k not in tiles:
            g, dx = gl[c]; x0 = ox + rec.P + pen + dx; h, w = g.shape
            if x0 < 0 or x0 + w > WX.shape[1] or oy + h > WYb.shape[1]: tiles[k] = torch.zeros((l1.H, 32), device=dev)
            else: tiles[k] = WYb[:, oy:oy + h] @ g @ WX[:, x0:x0 + w].T
        return tiles[k]

    res = []
    for esp in esps:
        base_im, _, _, _ = render_text(fpath, "Eternal ", rec.P, rec.tracking, rec.kern, rec.frac, int(round(esp * rec.kx)))
        I = torch.tensor(base_im, device=dev); hI, wI = I.shape
        BASE = WYb[:, oy:oy + hI] @ I @ WX[:, ox:ox + wI].T
        pen0 = sum(adv[c] + rec.tracking for c in "Eternal") + adv[" "] + rec.tracking + int(round(esp * rec.kx))
        for n in lengths:
            cands = strings(n)
            for s0 in range(0, len(cands), chunk):
                cc = cands[s0:s0 + chunk]; lin = BASE.expand(len(cc), -1, -1).clone()
                # pens per position depend on the previous letters' advances
                pens = np.full(len(cc), pen0)
                for j in range(n):
                    chars = [w[j] for w in cc]
                    for c in set(chars):
                        idx = [i for i, ch in enumerate(chars) if ch == c]
                        for pen in set(pens[idx].tolist()):
                            sel = torch.tensor([i for i in idx if pens[i] == pen], device=dev)
                            lin[sel] += tile(c, int(pen))
                    pens = pens + np.array([adv[ch] + rec.tracking for ch in chars])
                a = (lin.clamp(0, 1) ** rec.gamma).reshape(len(cc), -1)
                Ma = a @ l1.M.T; num = Ma @ l1.Mt; den = (Ma * Ma).sum(1)
                s = l1.tMt - torch.where(num > 0, num * num / den.clamp_min(1e-9), torch.zeros_like(num))
                res += list(zip(s.tolist(), cc, [esp] * len(cc)))
        log("  line 1 word 2, esp %+.1f done (%d candidates so far)" % (esp, len(res)))
    best = {}
    for v, w, e in res:
        if w not in best or v < best[w][0]: best[w] = (v, e)
    order = sorted(best, key=lambda w: best[w][0])
    words = [w for w in order if w in VOCAB]
    return dict(n=len(order), top=[(w, round(best[w][0], 2)) for w in order[:60]], rank_Star=order.index("Star") + 1,
                rank_star=order.index("star") + 1, score_Star=best["Star"][0], best_any=best[order[0]][0],
                n_words=len(words), top_words=[(w, round(best[w][0], 2), order.index(w) + 1) for w in words[:30]],
                rank_Star_among_words=words.index("Star") + 1 if "Star" in words else None)


def line2_slot(L2, phrases, keep, P2S, slot):
    found = L2.run_combo(phrases, P2S); ex = L2.rerank(found, 400)
    order = [r["phrase"] for r in ex]
    isword = lambda ph: ph.split(" ")[slot].rstrip(".!?") in VOCAB
    words = [r for r in ex if isword(r["phrase"])]
    return dict(n=len(phrases), top=[(r["phrase"], round(r["sse"], 2)) for r in ex[:40]],
                ranks={k: (order.index(k) + 1 if k in order else None) for k in keep},
                top_words=[(r["phrase"], round(r["sse"], 2), order.index(r["phrase"]) + 1) for r in words[:20]])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--texture", default="texture.npy"); ap.add_argument("--fonts-dir", default="fonts_cmp")
    ap.add_argument("--recipes", required=True); ap.add_argument("--hopefit", required=True); ap.add_argument("--line2", required=True)
    ap.add_argument("--p2", default="18,19,20,21"); ap.add_argument("--out", required=True); ap.add_argument("--vocab", default="data/vocab_big.txt")
    a = ap.parse_args(); T = load_T(a.texture); rec = best_recipe(a.recipes); out = {}
    VOCAB.update(w.strip() for w in open(a.vocab, encoding="utf-8") if w.strip())
    log("recipe:", rec.to_dict())
    out["line1_word2"] = line1_word2(T, rec, a.fonts_dir)
    log("LINE 1 word 2: Star rank %d (among real words %s), star rank %d of %d; top 15 %s; best real words %s" % (out["line1_word2"]["rank_Star"], out["line1_word2"]["rank_Star_among_words"], out["line1_word2"]["rank_star"], out["line1_word2"]["n"], out["line1_word2"]["top"][:15], out["line1_word2"]["top_words"][:10]))
    json.dump(out, open(a.out, "w"), indent=1)
    hb = json.load(open(a.hopefit))["best"]
    L2 = Line2(T, rec, a.fonts_dir, hb["font2"], tr2=hb["tracking2"], kern2=hb["kern2"], frac2=hb["frac2"]); P2S = [int(p) for p in a.p2.split(",")]
    s123 = strings(1) + strings(2) + strings(3)
    out["line2_first"] = line2_slot(L2, [x + " hope so" for x in s123] + ["'Tis hope so", "Tis hope so"], ["We hope so", "My hope so", "Be hope so", "No hope so"], P2S, 0)
    log("LINE 2 first word: ranks %s; top 12 %s; best real %s" % (out["line2_first"]["ranks"], out["line2_first"]["top"][:12], out["line2_first"]["top_words"][:8])); json.dump(out, open(a.out, "w"), indent=1)
    out["line2_ending"] = line2_slot(L2, ["We hope " + x for x in s123] + ["We hope so.", "We hope so!", "We hope so?"], ["We hope so", "We hope or", "We hope to", "We hope on", "We hope he", "We hope us"], P2S, 2)
    log("LINE 2 ending: ranks %s; top 12 %s; best real %s" % (out["line2_ending"]["ranks"], out["line2_ending"]["top"][:12], out["line2_ending"]["top_words"][:8])); json.dump(out, open(a.out, "w"), indent=1)
    out["line2_middle"] = line2_slot(L2, ["We " + x + " so" for x in strings(4, cap_first=False)], ["We hope so", "We hops so", "We help so"], P2S, 1)
    log("LINE 2 middle word: ranks %s; top 12 %s; best real %s" % (out["line2_middle"]["ranks"], out["line2_middle"]["top"][:12], out["line2_middle"]["top_words"][:8]))
    json.dump(out, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
