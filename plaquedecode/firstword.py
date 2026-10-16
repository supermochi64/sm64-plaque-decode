"""Line 1, FIRST word: does any string at all beat "Eternal"?  (Reddit question: "does assuming 'Eternal' bias it?")

Under the locked line-1 recipe (font, canvas, size, tracking, kerning, advances, filter, blur, gamma), X + " Star" is
scored for
  * every vocabulary entry (data/vocab_big.txt, as written and capitalised), and
  * every letter string of 4-10 letters (first letter any case, rest lower case), found by a beam search: strings are
    built letter by letter and each prefix is scored on the texture columns its letters already determine completely
    (the resize footprint ends left of the next pen), keeping the best K prefixes per length and per line shift.
Only words whose advance width is within --wtol artwork px of "Eternal" can put "Star" on its pixels (the line may
shift by -12..+12 px, e.g. when centred); all of them are re-scored exactly: every shift, free ink level, fixed stone
(PLAQUE_STONE).  Glyph tiles are linear before gamma (as exhaustive.py); pens = whole-pixel advances + rounded pair
kerning for every candidate alike.
    PLAQUE_STONE=stone/stone_box.npy PLAQUE_STONE_VAR=stone/stone_box_var.npy \
    python -m plaquedecode.firstword --recipes results/stone_recipes_Adobe.json --out results/stone_firstword_Adobe.json
"""
import argparse, json, os, string, time
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont
from .core import Line1, render_text
from .__main__ import log, load_T, best_recipe

LOW, UP = string.ascii_lowercase, string.ascii_uppercase
ABC = LOW + UP + " "
SHIFTS = range(-12, 13)
OFFP = 40                                                                       # pen-table offset (negative pens)


class Model:
    def __init__(self, T, rec, fdir, maxpen=420):
        self.l1 = l1 = Line1(T); self.dev = dev = l1.dev; self.rec = rec
        WX, WY = rec.matrices(dev); WYb = WY[l1.R0:l1.R1]
        fpath = os.path.join(fdir, rec.font); self.f = f = ImageFont.truetype(fpath, rec.P); asc, desc = f.getmetrics(); Hh = asc + desc + 4
        _, _, _, (r0, r1, c0, c1) = render_text(fpath, "Eternal Star", rec.P, rec.tracking, rec.kern, rec.frac, int(round(rec.esp * rec.kx)))
        ox = rec.X + rec.offx - max(0, c0 - 1); oy = rec.Y + rec.offy - max(0, r0 - 1); self.x_origin = ox + rec.P
        self.adv = np.array([(round(f.getlength(c)) if rec.frac == "glyph" else f.getlength(c)) for c in ABC], dtype=np.int64)
        self.ci = {c: i for i, c in enumerate(ABC)}; n = len(ABC); NP = maxpen + 2 * OFFP
        self.KM = np.zeros((n, n), dtype=np.int64)
        if rec.kern:
            for i, a in enumerate(LOW + UP):
                for j, b in enumerate(LOW + UP): self.KM[i, j] = int(round(f.getlength(a + b) - f.getlength(a) - f.getlength(b)))
        TT = torch.zeros((n, NP, l1.H, 32), device=dev)                         # glyph c with its pen at x (index x+OFFP)
        for i, c in enumerate(LOW + UP):
            im = Image.new("L", (4 * rec.P, Hh), 0); ImageDraw.Draw(im).text((rec.P, asc + 2), c, 255, font=f, anchor="ls")
            a = np.asarray(im, np.float32) / 255.0; cols = np.nonzero(a.sum(0) > 0)[0]
            g = torch.tensor(a[:, cols.min():cols.max() + 1], device=dev); dx = int(cols.min()) - rec.P; h, w = g.shape
            A = WYb[:, oy:oy + h] @ g
            for p in range(-OFFP, maxpen + OFFP):
                x0 = ox + rec.P + p + dx
                if 0 <= x0 and x0 + w <= WX.shape[1] and oy + h <= WYb.shape[1]: TT[i, p + OFFP] = A @ WX[:, x0:x0 + w].T
        self.TT = TT; self.NP = NP
        nz = (WX.abs() > 1e-9); idx = torch.arange(WX.shape[1], device=dev)
        self.lastcol = torch.where(nz.any(1), (nz * idx).max(1).values, torch.zeros(32, dtype=torch.long, device=dev))   # (32,)
        self.W = (l1.M.diagonal() ** 2).reshape(l1.H, 32); self.t = l1.t.reshape(l1.H, 32)
        self.space = int(self.adv[self.ci[" "]] + rec.tracking + round(rec.esp * rec.kx))

    def width(self, w):
        x, prev = 0, None
        for c in w:
            if prev is not None: x += int(self.KM[self.ci[prev], self.ci[c]])
            x += int(self.adv[self.ci[c]]) + self.rec.tracking; prev = c
        return x

    def encode(self, words):
        """char indices and pens for word + ' Star' (padding = space glyph, which is empty)."""
        full = [w + " Star" for w in words]; Lm = max(len(s) for s in full)
        idx = np.full((len(full), Lm), self.ci[" "], dtype=np.int64); pen = np.zeros((len(full), Lm), dtype=np.int64)
        for k, s in enumerate(full):
            x, prev = 0, None
            for j, c in enumerate(s):
                if prev is not None and c != " " and prev != " ": x += int(self.KM[self.ci[prev], self.ci[c]])
                idx[k, j] = self.ci[c]; pen[k, j] = x
                x += int(self.adv[self.ci[c]]) + self.rec.tracking + (int(round(self.rec.esp * self.rec.kx)) if c == " " else 0); prev = c
        return torch.tensor(idx, device=self.dev), torch.tensor(pen, device=self.dev)

    def score(self, lins):
        a = (lins.clamp(0, 1) ** self.rec.gamma).reshape(lins.shape[0], -1); Ma = a @ self.l1.M.T
        num = Ma @ self.l1.Mt; den = (Ma * Ma).sum(1)
        return self.l1.tMt - torch.where(num > 0, num * num / den.clamp_min(1e-9), torch.zeros_like(num))

    def exact(self, words, chunk=4096):
        best = np.full(len(words), np.inf); bsh = np.zeros(len(words), dtype=np.int64)
        for s0 in range(0, len(words), chunk):
            idx, pen = self.encode(words[s0:s0 + chunk]); b = torch.full((idx.shape[0],), float("inf"), device=self.dev); bs = torch.zeros_like(b)
            for sh in SHIFTS:
                p = (pen + sh + OFFP).clamp(0, self.NP - 1); lins = self.TT[idx, p].sum(1)
                s = self.score(lins); m = s < b; b = torch.where(m, s, b); bs = torch.where(m, torch.full_like(bs, sh), bs)
            best[s0:s0 + idx.shape[0]] = b.cpu().numpy(); bsh[s0:s0 + idx.shape[0]] = bs.cpu().numpy().astype(np.int64)
        return best, bsh


def beam(m, L_ink, shift, K, maxlen, minlen=4, chunk=8192):
    """scores every extension of every kept prefix, keeps the best K; only the kept coverages are rebuilt (memory)."""
    g = m.rec.gamma
    pref = [""]; last = np.array([-1]); pen = np.array([0]); lin = torch.zeros((1, m.l1.H, 32), device=m.dev); out = []
    for depth in range(maxlen):
        alpha = (LOW + UP) if depth == 0 else LOW
        scores, pens_c, nxts_c = [], [], []
        for c in alpha:
            ci = m.ci[c]; kern = np.where(last >= 0, m.KM[np.maximum(last, 0), ci], 0); p = pen + kern
            nxt = p + int(m.adv[ci]) + m.rec.tracking; sc = torch.empty(len(pref), device=m.dev)
            for s0 in range(0, len(pref), chunk):
                sl = slice(s0, s0 + chunk)
                pt = torch.tensor(np.clip(p[sl] + shift + OFFP, 0, m.NP - 1), device=m.dev)
                nl = lin[sl] + m.TT[ci, pt]; x = torch.tensor(m.x_origin + nxt[sl] + shift, device=m.dev)
                final = (m.lastcol[None, :] < x[:, None]).float()                # (n, 32) columns fully determined
                r = m.t[None] - L_ink * nl.clamp(0, 1) ** g; s = (m.W[None] * r * r * final[:, None, :]).sum((1, 2))
                sc[sl] = s / final.sum(1).clamp_min(1)                            # per-column, so widths compare fairly
            scores.append(sc); pens_c.append(p); nxts_c.append(nxt)
        allsc = torch.cat(scores); k = min(K, allsc.numel()); keep = torch.topk(-allsc, k).indices.cpu().numpy(); n0 = len(pref)
        a_idx, i_idx = keep // n0, keep % n0
        newpref = [pref[i] + alpha[a] for a, i in zip(a_idx, i_idx)]
        newpen = np.array([nxts_c[a][i] for a, i in zip(a_idx, i_idx)]); kept_p = np.array([pens_c[a][i] for a, i in zip(a_idx, i_idx)])
        ci_t = torch.tensor([m.ci[alpha[a]] for a in a_idx], device=m.dev)
        pt = torch.tensor(np.clip(kept_p + shift + OFFP, 0, m.NP - 1), device=m.dev)
        lin = lin[torch.tensor(i_idx, device=m.dev)] + m.TT[ci_t, pt]
        pref, last, pen = newpref, np.array([m.ci[alpha[a]] for a in a_idx]), newpen
        best_s = allsc
        if depth + 1 >= minlen: out += pref
        log("    shift %+3d  length %2d: kept %d of %d, best prefix %r" % (shift, depth + 1, k, best_s.numel(), pref[0]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--texture", default="texture.npy"); ap.add_argument("--fonts-dir", default="fonts_cmp")
    ap.add_argument("--recipes", required=True); ap.add_argument("--vocab", default="data/vocab_big.txt")
    ap.add_argument("--K", type=int, default=40000); ap.add_argument("--maxlen", type=int, default=10)
    ap.add_argument("--wtol", type=int, default=24); ap.add_argument("--out", required=True)
    a = ap.parse_args(); T = load_T(a.texture); rec = best_recipe(a.recipes); t0 = time.time()
    m = Model(T, rec, a.fonts_dir); wE = m.width("Eternal")
    ref, refsh = m.exact(["Eternal"]); log("recipe %s P%d | 'Eternal Star' tile score %.2f (recipe sse %.2f), shift %+d, width %d px" % (rec.font, rec.P, ref[0], rec.sse, refsh[0], wE))
    idx, pen = m.encode(["Eternal"]); lin = m.TT[idx, (pen + int(refsh[0]) + OFFP).clamp(0, m.NP - 1)].sum(1)
    a_ = (lin.clamp(0, 1) ** rec.gamma).reshape(1, -1); Ma = a_ @ m.l1.M.T; L_ink = float((Ma @ m.l1.Mt) / (Ma * Ma).sum())
    vocab = {w.strip() for w in open(a.vocab, encoding="utf-8") if w.strip()}
    vocab = {v for w in vocab for v in (w, w[:1].upper() + w[1:]) if v.isalpha() and v.isascii() and 2 <= len(v) <= 14}
    cands = set(vocab); nb = 0; beamset = set()
    for sh in (-12, -6, 0, 6, 12):
        b = beam(m, L_ink, sh, a.K, a.maxlen); nb += len(b); cands.update(b); beamset.update(b)
        log("  beam shift %+d done (%d strings), %d candidates in total (%.0f s)" % (sh, len(b), len(cands), time.time() - t0))
    fit = sorted(w for w in cands if abs(m.width(w) - wE) <= a.wtol); log("width filter |w - %d| <= %d px: %d of %d candidates" % (wE, a.wtol, len(fit), len(cands)))
    if "Eternal" not in fit: fit.append("Eternal")
    sc, sh = m.exact(fit); order = np.argsort(sc); rank = {fit[i]: r + 1 for r, i in enumerate(order)}
    top = [(fit[i], round(float(sc[i]), 2), int(sh[i]), fit[i] in vocab) for i in order[:100]]
    words = [(fit[i], round(float(sc[i]), 2), rank[fit[i]]) for i in order if fit[i] in vocab][:50]
    beam_ranked = [w for w in (fit[i] for i in order) if w in beamset]
    out = dict(recipe=rec.to_dict(), n_scored=len(fit), eternal_found_by_blind_beam="Eternal" in beamset,
               rank_Eternal_among_beam_strings=(beam_ranked.index("Eternal") + 1) if "Eternal" in beamset else None, n_candidates=len(cands), n_vocab=len(vocab), n_beam=nb, width_Eternal=wE, wtol=a.wtol,
               score_Eternal=float(sc[fit.index("Eternal")]), rank_Eternal=rank["Eternal"],
               rank_Eternal_among_vocab=next((i + 1 for i, w in enumerate(words) if w[0] == "Eternal"), None), top=top, top_vocab=words)
    json.dump(out, open(a.out, "w"), indent=1)
    log("FIRST WORD: Eternal rank %d of %d scored (%s among vocabulary entries)" % (out["rank_Eternal"], len(fit), out["rank_Eternal_among_vocab"]))
    log("blind letter-by-letter beam found 'Eternal' on its own: %s (rank among beam strings %s)" % (out["eternal_found_by_blind_beam"], out["rank_Eternal_among_beam_strings"]))
    log("best 25: %s" % top[:25]); log("best vocabulary words: %s  (%.0f s)" % (words[:15], time.time() - t0))


if __name__ == "__main__":
    main()
