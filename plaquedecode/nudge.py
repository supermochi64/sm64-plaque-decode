"""Per-letter nudges combined with the recipe search (line 1), with a noise-only control.

The words and the font are known, the exact transformation is not: does a different recipe win once
every letter may be shifted by hand?  For each of the top-K recipes of a recipe search (canvas, size, tracking,
kerning, advances, word space, filter, blur), every glyph of "Eternal Star" may move by an integer number of canvas
pixels (what an artist kerning by hand in a paint program does), fitted by coordinate descent together with the gamma.
Glyph tiles are linear in the artwork, so every candidate is scored exactly under the fixed-stone metric.
Control: synthetic plaques = the un-nudged best fit + the real residual of the band, permuted; the same nudge fit on
them measures what 11 free shifts buy on pure noise.
    PLAQUE_STONE=... PLAQUE_STONE_VAR=... python -m plaquedecode.nudge --recipes results/stone_recipes_Adobe.json \
        --top 400 --out results/stone_nudge_Adobe.json
"""
import argparse, json, os
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont
from .core import Line1, Line2, Recipe, render_text
from .__main__ import log, load_T

TEXT = "Eternal Star"
GAMMAS = (1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.8, 2.0, 2.2)


class Glyphs:
    """glyph tiles of `text` typed with `rec`; tile(i, dx) = linear 32x32 coverage of glyph i shifted by dx canvas px."""
    def __init__(self, l1, rec, fdir, text=TEXT):
        fpath = os.path.join(fdir, rec.font); f = ImageFont.truetype(fpath, rec.P); asc, _ = f.getmetrics()
        esp = int(round(rec.esp * rec.kx)); xs, x, prev = [], 0.0, None
        for c in text:                                            # pen positions exactly as render_text
            if prev is not None and rec.kern and c != " " and prev != " ":
                x += f.getlength(prev + c) - f.getlength(prev) - f.getlength(c)
            xs.append(x if rec.frac else round(x)); adv = f.getlength(c)
            if rec.frac == "glyph": adv = round(adv)
            x += adv + rec.tracking + (esp if c == " " else 0); prev = c
        full, _, _, (r0, r1, c0, c1) = render_text(fpath, text, rec.P, rec.tracking, rec.kern, rec.frac, esp)
        Hh, W = full.shape
        self.WX, self.WY = rec.matrices(l1.dev)
        X0 = rec.X + rec.offx - max(0, c0 - 1); Y0 = rec.Y + rec.offy - max(0, r0 - 1)
        self.tiles, self.chars, self.cache = [], [], {}
        for c, xx in zip(text, xs):
            if c == " ": continue
            im = Image.new("L", (W, Hh), 0); ImageDraw.Draw(im).text((rec.P + xx, asc + 2), c, 255, font=f, anchor="ls")
            a = np.asarray(im, np.float32) / 255.0; rr = np.nonzero(a.sum(1) > 0)[0]; cc = np.nonzero(a.sum(0) > 0)[0]
            g = torch.tensor(a[rr.min():rr.max() + 1, cc.min():cc.max() + 1], device=l1.dev)
            self.tiles.append((g, X0 + int(cc.min()), Y0 + int(rr.min()))); self.chars.append(c)

    def tile(self, i, dx):
        k = (i, dx)
        if k not in self.cache:
            g, x, y = self.tiles[i]; h, w = g.shape; x += dx
            if x < 0 or x + w > self.WX.shape[1] or y < 0 or y + h > self.WY.shape[1]:
                self.cache[k] = torch.zeros((32, 32), device=g.device)
            else:
                self.cache[k] = self.WY[:, y:y + h] @ g @ self.WX[:, x:x + w].T
        return self.cache[k]

    def lin(self, dxs):
        return sum(self.tile(i, d) for i, d in enumerate(dxs))


def score(l1, lin, G):
    """lin (B,32,32) -> best SSE over gammas G and the gamma index, for every batch member."""
    a = lin[:, l1.R0:l1.R1].clamp(0, 1).reshape(lin.shape[0], -1)
    best = None
    for gi, g in enumerate(G):
        Ma = (a ** g) @ l1.M.T; num = Ma @ l1.Mt; den = (Ma * Ma).sum(1)
        s = l1.tMt - torch.where(num > 0, num * num / den.clamp_min(1e-9), torch.zeros_like(num))
        if best is None: best, bi = s, torch.zeros_like(s, dtype=torch.long)
        else: m = s < best; best = torch.where(m, s, best); bi = torch.where(m, torch.full_like(bi, gi), bi)
    return best, bi


def fit(l1, Gl, D, sweeps=3, G=GAMMAS):  # noqa: E302
    n = len(Gl.tiles); dx = [0] * n; base = Gl.lin(dx)
    s0, _ = score(l1, base[None], G); s0 = float(s0[0]); cur = s0
    cands = list(range(-D, D + 1))
    for _ in range(sweeps):
        moved = False
        for i in range(n):
            lin = base[None] - Gl.tile(i, dx[i])[None] + torch.stack([Gl.tile(i, d) for d in cands])
            s, _ = score(l1, lin, G); j = int(torch.argmin(s)); v = float(s[j])
            if v < cur - 1e-6 and cands[j] != dx[i]:
                base = base - Gl.tile(i, dx[i]) + Gl.tile(i, cands[j]); dx[i] = cands[j]; cur = v; moved = True
        if not moved: break
    s, gi = score(l1, base[None], G)
    return s0, float(s[0]), dx, float(G[int(gi[0])]), base


class Glyphs2:
    """line-2 glyph tiles of `text` in Line2's typesetting (P2, word space, start pen x, baseline yb)."""
    def __init__(self, L2, text, P2, esp, x, yb):
        f = ImageFont.truetype(L2.fpath, P2); asc, _ = f.getmetrics(); e = int(round(esp * L2.kx)); xs, xx, prev = [], 0.0, None
        for c in text:
            if prev is not None and L2.KERN and c != " " and prev != " ":
                xx += f.getlength(prev + c) - f.getlength(prev) - f.getlength(c)
            xs.append(xx if L2.FRAC else round(xx)); adv = f.getlength(c)
            if L2.FRAC == "glyph": adv = round(adv)
            xx += adv + L2.TR + (e if c == " " else 0); prev = c
        full, base_row, penx, _ = render_text(L2.fpath, text, P2, L2.TR, L2.KERN, L2.FRAC, e)
        Hh, W = full.shape; ox, oy = x - penx, yb - base_row
        self.WX, self.WY = L2.WX, L2.WY[L2.B0:L2.B1]; self.tiles, self.chars, self.cache = [], [], {}
        for c, px in zip(text, xs):
            if c == " ": continue
            im = Image.new("L", (W, Hh), 0); ImageDraw.Draw(im).text((P2 + px, asc + 2), c, 255, font=f, anchor="ls")
            a = np.asarray(im, np.float32) / 255.0; rr = np.nonzero(a.sum(1) > 0)[0]; cc = np.nonzero(a.sum(0) > 0)[0]
            g = torch.tensor(a[rr.min():rr.max() + 1, cc.min():cc.max() + 1], device=L2.dev)
            self.tiles.append((g, ox + int(cc.min()), oy + int(rr.min()))); self.chars.append(c)
        self.HB = L2.HB

    def tile(self, i, dx):
        k = (i, dx)
        if k not in self.cache:
            g, x, y = self.tiles[i]; h, w = g.shape; x += dx
            t = torch.zeros((self.HB, 32), device=g.device)
            if 0 <= x and x + w <= self.WX.shape[1]:
                y0, y1 = max(0, y), min(self.WY.shape[1], y + h)
                if y1 > y0: t = self.WY[:, y0:y1] @ g[y0 - y:y1 - y] @ self.WX[:, x:x + w].T
            self.cache[k] = t
        return self.cache[k]

    def lin(self, dxs):
        return sum(self.tile(i, d) for i, d in enumerate(dxs))


def fit2(L2, Gl, D, sweeps=3):
    n = len(Gl.tiles); dx = [0] * n; base = Gl.lin(dx); s0 = float(L2.sse_blocks(base).sum()); cur = s0
    cands = list(range(-D, D + 1))
    for _ in range(sweeps):
        moved = False
        for i in range(n):
            lin = base[None] - Gl.tile(i, dx[i])[None] + torch.stack([Gl.tile(i, d) for d in cands])
            s = L2.sse_blocks(lin).sum(-1); j = int(torch.argmin(s)); v = float(s[j])
            if v < cur - 1e-6 and cands[j] != dx[i]:
                base = base - Gl.tile(i, dx[i]) + Gl.tile(i, cands[j]); dx[i] = cands[j]; cur = v; moved = True
        if not moved: break
    return s0, cur, dx, base


def both(a, T):
    """both lines with one recipe + one gamma: line 1 nudged, line 2 'We hope so' (hope typesetting) nudged; controls."""
    keys = Recipe.__dataclass_fields__; d = json.load(open(a.recipes))[0]; rec = Recipe(**{f: d[f] for f in keys if f in d})
    l1 = Line1(T); G1 = Glyphs(l1, rec, a.fonts_dir); D = int(round(a.range * rec.kx))
    s0, s1, dx1, _, lin1 = fit(l1, G1, D, G=(rec.gamma,))
    hb = json.load(open(a.hopefit))["best"]; ex = json.load(open(a.line2))["exact"]
    cfg = next(r for r in ex if r["phrase"] == a.text2)
    L2 = Line2(T, rec, a.fonts_dir, hb["font2"], tr2=hb["tracking2"], kern2=hb["kern2"], frac2=hb["frac2"])
    G2 = Glyphs2(L2, a.text2, cfg["P2"], cfg["esp"], cfg["x"], cfg["yb"])
    exact = L2.exact_score(a.text2, cfg["P2"], cfg["esp"], cfg["x"], cfg["yb"])
    t0, t1, dx2, lin2 = fit2(L2, G2, D)
    log("line 1: rigid %.1f -> nudged %.1f (dx %s) | line 2 %r: rigid %.1f (exact render %.1f) -> nudged %.1f (dx %s)" % (s0, s1, dx1, a.text2, t0, exact, t1, dx2))
    rng = np.random.default_rng(11); g1, g2 = [], []
    p1 = l1.prediction(G1.lin([0] * len(G1.tiles)), rec.gamma).cpu().numpy(); p2 = L2.prediction(G2.lin([0] * len(G2.tiles))).cpu().numpy()
    Tn = np.asarray(T, np.float64)
    for _ in range(a.fakes):
        Tf = Tn.copy(); r1 = Tn[l1.R0:l1.R1] - p1; Tf[l1.R0:l1.R1] = p1 + rng.permutation(r1.ravel()).reshape(r1.shape)
        lf = Line1(Tf); u0, u1, _, _, _ = fit(lf, Glyphs(lf, rec, a.fonts_dir), D, G=(rec.gamma,)); g1.append(u0 - u1)
        Tf = Tn.copy(); r2 = Tn[L2.B0:L2.B1] - p2; Tf[L2.B0:L2.B1] = p2 + rng.permutation(r2.ravel()).reshape(r2.shape)
        L2f = Line2(Tf, rec, a.fonts_dir, hb["font2"], tr2=hb["tracking2"], kern2=hb["kern2"], frac2=hb["frac2"])
        v0, v1, _, _ = fit2(L2f, Glyphs2(L2f, a.text2, cfg["P2"], cfg["esp"], cfg["x"], cfg["yb"]), D); g2.append(v0 - v1)
    log("controls: line 1 real gain %.1f vs noise %s | line 2 real gain %.1f vs noise %s" % (s0 - s1, [round(x, 1) for x in g1], t0 - t1, [round(x, 1) for x in g2]))
    out = dict(R0=l1.R0, B0=L2.B0, real=Tn.astype(np.float32), stone=l1.stone[0].cpu().numpy(),
               l1_rigid=p1, l1_nudged=l1.prediction(lin1, rec.gamma).cpu().numpy(), l2_rigid=p2, l2_nudged=L2.prediction(lin2).cpu().numpy())
    np.savez(os.path.splitext(a.out)[0] + ".npz", **out)
    json.dump(dict(recipe=d, text2=a.text2, line2_cfg=cfg, hopefit=hb, line1=dict(rigid=s0, nudged=s1, dx=dx1, chars=G1.chars, noise_gains=g1),
                   line2=dict(rigid=t0, exact=exact, nudged=t1, dx=dx2, chars=G2.chars, noise_gains=g2)), open(a.out, "w"), indent=1)
    log("-> %s" % a.out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--texture", default="texture.npy"); ap.add_argument("--fonts-dir", default="fonts_cmp")
    ap.add_argument("--recipes", required=True); ap.add_argument("--top", type=int, default=400)
    ap.add_argument("--range", type=float, default=1.0, help="max shift per letter in texture px (x kx canvas px)")
    ap.add_argument("--fakes", type=int, default=5); ap.add_argument("--control-top", type=int, default=5)
    ap.add_argument("--out", required=True)
    ap.add_argument("--both", action="store_true", help="line 1 + line 2 with the top recipe (needs --hopefit --line2)")
    ap.add_argument("--hopefit"); ap.add_argument("--line2"); ap.add_argument("--text2", default="We hope so")
    a = ap.parse_args(); T = load_T(a.texture)
    if a.both: return both(a, T)
    l1 = Line1(T)
    assert l1.stone is not None, "set PLAQUE_STONE / PLAQUE_STONE_VAR (fixed-stone mode)"
    R = json.load(open(a.recipes)); keys = Recipe.__dataclass_fields__
    rows = []
    for k, d in enumerate(R[:a.top]):
        rec = Recipe(**{f: d[f] for f in keys if f in d}); Gl = Glyphs(l1, rec, a.fonts_dir)
        s0, s1, dx, g, _ = fit(l1, Gl, int(round(a.range * rec.kx)))
        rows.append(dict(rank_rigid=k + 1, recipe=d, sse_rigid_tiles=s0, sse_nudged=s1, gain=s0 - s1, dx=dx, gamma=g))
        if k % 50 == 0: log("  %d/%d recipes; best nudged so far %.1f" % (k + 1, min(len(R), a.top), min(r["sse_nudged"] for r in rows)))
    rows.sort(key=lambda r: r["sse_nudged"])
    log("rigid #1 %.1f (tiles %.1f) -> best nudged %.1f (rigid rank %d: %dpx %dx%d tr %+d kern %d %s blur %.2f esp %+.1f, gamma %.1f, dx %s)" % (
        R[0]["sse"], next(r for r in rows if r["rank_rigid"] == 1)["sse_rigid_tiles"], rows[0]["sse_nudged"], rows[0]["rank_rigid"],
        rows[0]["recipe"]["P"], 32 * rows[0]["recipe"]["kx"], 32 * rows[0]["recipe"]["ky"], rows[0]["recipe"]["tracking"], rows[0]["recipe"]["kern"],
        rows[0]["recipe"]["filter"], rows[0]["recipe"]["blur"], rows[0]["recipe"]["esp"], rows[0]["gamma"], rows[0]["dx"]))
    # noise-only control on the best nudged recipes: un-nudged fit + permuted real residual of the band
    S_ = l1.stone[0]; rng = np.random.default_rng(7)
    for r in rows[:a.control_top]:
        rec = Recipe(**{f: r["recipe"][f] for f in keys if f in r["recipe"]}); Gl = Glyphs(l1, rec, a.fonts_dir)
        lin0 = Gl.lin([0] * len(Gl.tiles)); _, gi = score(l1, lin0[None], GAMMAS); g0 = GAMMAS[int(gi[0])]
        pred = l1.prediction(lin0, g0).cpu().numpy(); band = np.asarray(T, np.float64)[l1.R0:l1.R1]; res = band - pred
        gains = []
        for _ in range(a.fakes):
            Tf = np.asarray(T, np.float64).copy(); Tf[l1.R0:l1.R1] = pred + rng.permutation(res.ravel()).reshape(res.shape)
            lf = Line1(Tf); s0f, s1f, _, _, _ = fit(lf, Glyphs(lf, rec, a.fonts_dir), int(round(a.range * rec.kx)))
            gains.append(s0f - s1f)
        r["control_gains"] = gains
        log("  control rigid rank %d: real gain %.1f vs noise-only gains %s (mean %.1f)" % (r["rank_rigid"], r["gain"], [round(x, 1) for x in gains], np.mean(gains)))
    best = rows[0]; rec = Recipe(**{f: best["recipe"][f] for f in keys if f in best["recipe"]}); Gl = Glyphs(l1, rec, a.fonts_dir)
    lin = Gl.lin(best["dx"]); pred = l1.prediction(lin, best["gamma"]).cpu().numpy()
    np.savez(os.path.splitext(a.out)[0] + "_best.npz", band=np.asarray(T, np.float32)[l1.R0:l1.R1], pred=pred,
             stone=l1.stone[0][l1.R0:l1.R1].cpu().numpy(), R0=l1.R0)
    json.dump(dict(text=TEXT, chars=Gl.chars, range_texture_px=a.range, rows=rows), open(a.out, "w"), indent=0)
    log("-> %s" % a.out)


if __name__ == "__main__":
    main()
