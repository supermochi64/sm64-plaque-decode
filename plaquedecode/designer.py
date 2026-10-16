"""The designer's canvas: both lines typed on ONE artwork canvas, hand-kerned letters, then classic 1990s text effects,
then the resize to 32x32 - fitted against the fixed stone, every effect checked against a noise-only control.

Canvas (A = text alpha 0..1 at artwork resolution, both lines):
    line 1 = 'Eternal Star' with the line-1 recipe, line 2 = 'We hope so' in the hope typesetting (stone_hopefit),
    each glyph shifted by an integer number of canvas px (hand kerning), each line optionally moved up/down as a block.
Effects (layers composited on the canvas before the resize; strengths fitted by least squares):
    shadow   D = blur(shift(A, sx, sy)) * (1 - A)  -> darkens (K > 0) or lightens (K < 0) the stone: engraved / drop shadow
    emboss   shadow at (sx, sy) + light at (-sx, -sy), two strengths
    outline  D = dilate(A, r) * (1 - A)
    sharpen  unsharp mask on the text contribution after the resize (radius, amount)
Texture model per line band: stone + L_line * (WY A WX^T)^gamma - sum_k K_k * (WY D_k WX^T).
Control: fake plaques = the plain (nudged, no-effect) fit + the real residual permuted inside each band; the same
effect search + nudge refit on them gives the gain that the extra parameters buy on noise.
    PLAQUE_STONE=... PLAQUE_STONE_VAR=... python -m plaquedecode.designer --recipes results/stone_recipes_Adobe.json \
        --hopefit results/stone_hopefit_Adobe.json --line2 results/stone_line2_dp_hopefit_Adobe.json --out results/designer.json
"""
import argparse, itertools, json, os
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont
from .core import Line1, Recipe, LINE1, LINE2, render_text, gauss_matrix
from .__main__ import log, load_T

T1, T2 = "Eternal Star", "We hope so"


def glyph_images(fpath, text, P, TR, kern, frac, esp_px):
    """per-glyph (image, x, y) in render-image coordinates + the render crop info, pens exactly as render_text."""
    f = ImageFont.truetype(fpath, P); asc, _ = f.getmetrics(); xs, x, prev = [], 0.0, None
    for c in text:
        if prev is not None and kern and c != " " and prev != " ":
            x += f.getlength(prev + c) - f.getlength(prev) - f.getlength(c)
        xs.append(x if frac else round(x)); adv = f.getlength(c)
        if frac == "glyph": adv = round(adv)
        x += adv + TR + (esp_px if c == " " else 0); prev = c
    full, base_row, penx, bbox = render_text(fpath, text, P, TR, kern, frac, esp_px)
    Hh, W = full.shape; out = []
    for c, px in zip(text, xs):
        if c == " ": continue
        im = Image.new("L", (W, Hh), 0); ImageDraw.Draw(im).text((P + px, asc + 2), c, 255, font=f, anchor="ls")
        a = np.asarray(im, np.float32) / 255.0; rr = np.nonzero(a.sum(1) > 0)[0]; cc = np.nonzero(a.sum(0) > 0)[0]
        out.append((c, a[rr.min():rr.max() + 1, cc.min():cc.max() + 1], int(cc.min()), int(rr.min())))
    return out, base_row, penx, bbox


class Canvas:
    def __init__(self, T, rec, fdir, hb, cfg2, dev):
        self.dev = dev; self.rec = rec; self.C = rec.canvas
        g1, _, _, (r0, r1, c0, c1) = glyph_images(os.path.join(fdir, rec.font), T1, rec.P, rec.tracking, rec.kern, rec.frac, int(round(rec.esp * rec.kx)))
        X0 = rec.X + rec.offx - max(0, c0 - 1); Y0 = rec.Y + rec.offy - max(0, r0 - 1)
        self.glyphs = [(c, g, X0 + x, Y0 + y, 0) for c, g, x, y in g1]
        g2, base_row, penx, _ = glyph_images(os.path.join(fdir, hb["font2"]), T2, cfg2["P2"], hb["tracking2"], hb["kern2"], hb["frac2"],
                                             int(round(cfg2["esp"] * rec.kx)))
        ox, oy = cfg2["x"] - penx, cfg2["yb"] - base_row
        self.glyphs += [(c, g, ox + x, oy + y, 1) for c, g, x, y in g2]
        self.n1 = len(g1)
        self.WX, self.WY = rec.matrices(dev)
        self.Tt = torch.as_tensor(np.asarray(T, np.float32), device=dev)

    def alpha(self, dx, dy_line=(0, 0)):
        A = np.zeros((self.C, self.C), np.float32)
        for (c, g, x, y, ln), d in zip(self.glyphs, dx):
            x += d; y += dy_line[ln]; h, w = g.shape
            xa, ya = max(0, x), max(0, y); xb, yb = min(self.C, x + w), min(self.C, y + h)
            if xb > xa and yb > ya:
                A[ya:yb, xa:xb] = 1 - (1 - A[ya:yb, xa:xb]) * (1 - g[ya - y:yb - y, xa - x:xb - x])   # paint over
        return A

    def tex(self, A):
        return self.WY @ torch.as_tensor(np.asarray(A, np.float32), device=self.dev) @ self.WX.T


def shift(A, sx, sy):
    out = np.zeros_like(A); H, W = A.shape
    out[max(0, sy):H + min(0, sy), max(0, sx):W + min(0, sx)] = A[max(0, -sy):H + min(0, -sy), max(0, -sx):W + min(0, -sx)]
    return out


def blur_np(A, s):
    if s <= 0: return A
    r = int(3 * s + 1); k = np.exp(-0.5 * (np.arange(-r, r + 1) / s) ** 2); k /= k.sum()
    A = np.apply_along_axis(lambda v: np.convolve(v, k, "same"), 0, A)
    return np.apply_along_axis(lambda v: np.convolve(v, k, "same"), 1, A)


def dilate(A, r):
    out = A.copy()
    for dx, dy in itertools.product(range(-r, r + 1), repeat=2):
        if dx * dx + dy * dy <= r * r: out = np.maximum(out, shift(A, dx, dy))
    return out


class Scorer:
    """weighted least squares per band: data (T - stone) ~ L_line * ink_line + sum_k K_k * layer_k (K shared)."""
    def __init__(self, T, dev):
        l1 = Line1(T, dev); assert l1.stone is not None, "fixed-stone mode needed (PLAQUE_STONE)"
        S_, W_ = l1.stone; Tt = torch.as_tensor(np.asarray(T, np.float32), device=dev)
        self.bands = [slice(*LINE1), slice(*LINE2)]
        self.d = [(Tt - S_)[b].reshape(-1) for b in self.bands]; self.w = [W_[b].reshape(-1) for b in self.bands]
        self.stone = S_

    WGRID = torch.arange(4.0, 60.01, 0.25)

    def fit(self, ink, layers=(), sharpen=None, blend="add"):
        """ink: 32x32 (cov^gamma); layers: list of 32x32 linear effect maps. Returns SSE, coefficients.
        blend (how the text layer meets the stone; W = text brightness per line):
          add    out = S + W a              normal  out = S + a (W - S)     (alpha-composited light text)
          screen out = S + W a (1 - S/31)   lighten out = max(S, W a)       (text layer on black, Lighten mode)"""
        if sharpen:
            Gs = gauss_matrix(sharpen[0], n=32, dev=ink.device); sh = lambda M: M + sharpen[1] * (M - Gs @ M @ Gs.T)
            ink = sh(ink); layers = [sh(L) for L in layers]
        if blend == "lighten":
            tot, beta = 0.0, []
            for b, d, w in zip(self.bands, self.d, self.w):
                a = ink[b].reshape(-1); S = self.stone[b].reshape(-1)
                m = torch.clamp(self.WGRID[:, None] * a[None] - S[None], min=0)
                e = (w[None] * (d[None] - m) ** 2).sum(1); j = int(torch.argmin(e)); tot += float(e[j]); beta.append(float(self.WGRID[j]))
            return tot, beta
        cols, ys = [], []
        for li, (b, d) in enumerate(zip(self.bands, self.d)):
            a = ink[b].reshape(-1); S = self.stone[b].reshape(-1); z = torch.zeros_like(a)
            if blend == "normal": d = d + a * S
            if blend == "screen": a = a * (1 - S / 31.0)
            cols.append([a if li == 0 else z, a if li == 1 else z] + [L[b].reshape(-1) for L in layers]); ys.append(d)
        X = torch.cat([torch.stack(c, 1) for c in cols]); y = torch.cat(ys); w = torch.cat(self.w)
        Xw = X * w.sqrt()[:, None]; yw = y * w.sqrt()
        beta = torch.linalg.lstsq(Xw, yw[:, None]).solution[:, 0]
        r = yw - Xw @ beta
        return float((r * r).sum()), beta.tolist()

    def predict(self, ink, layers, beta, sharpen=None, blend="add"):
        if sharpen:
            Gs = gauss_matrix(sharpen[0], n=32, dev=ink.device); sh = lambda M: M + sharpen[1] * (M - Gs @ M @ Gs.T)
            ink = sh(ink); layers = [sh(L) for L in layers]
        out = self.stone.clone()
        for li, b in enumerate(self.bands):
            S, a = self.stone[b], ink[b]
            if blend == "lighten": out[b] = torch.maximum(S, beta[li] * a); continue
            core = {"add": beta[li] * a, "normal": a * (beta[li] - S), "screen": beta[li] * a * (1 - S / 31.0)}[blend]
            out[b] = S + core + sum(k * L[b] for k, L in zip(beta[2:], layers))
        return out


EFFECTS = {"none": [None]}
EFFECTS["shadow"] = [("shadow", sx, sy, sb) for sx in range(-6, 7, 1) for sy in range(-5, 6, 1) for sb in (0.0, 1.5, 3.0) if (sx, sy) != (0, 0)]
EFFECTS["emboss"] = [("emboss", sx, sy, sb) for sx in range(-4, 5, 1) for sy in range(-4, 5, 1) for sb in (0.0, 1.5) if (sx, sy) > (0, 0)]
EFFECTS["outline"] = [("outline", r, 0, sb) for r in (1, 2, 3, 4) for sb in (0.0, 1.5)]
EFFECTS["sharpen"] = [("sharpen", r, a, 0) for r in (0.5, 0.7, 1.0) for a in (0.25, 0.5, 1.0, 1.5)]
EFFECTS["lineshift"] = [("lineshift", d1, d2, 0) for d1 in range(-3, 4) for d2 in range(-3, 4) if (d1, d2) != (0, 0)]


BLEND = ["add"]


def evaluate(cv, sc, dx, gamma, eff):
    dyl = (eff[1], eff[2]) if eff and eff[0] == "lineshift" else (0, 0)
    A = cv.alpha(dx, dyl); ink = cv.tex(A).clamp(0, 1) ** gamma; layers, sharpen = [], None
    if eff and eff[0] == "shadow":
        layers = [cv.tex(blur_np(shift(A, eff[1], eff[2]), eff[3]) * (1 - A))]
    elif eff and eff[0] == "emboss":
        layers = [cv.tex(blur_np(shift(A, eff[1], eff[2]), eff[3]) * (1 - A)), cv.tex(blur_np(shift(A, -eff[1], -eff[2]), eff[3]) * (1 - A))]
    elif eff and eff[0] == "outline":
        layers = [cv.tex(blur_np(dilate(A, eff[1]), eff[3]) * (1 - A))]
    elif eff and eff[0] == "sharpen":
        sharpen = (eff[1], eff[2])
    if BLEND[0] == "lighten" and layers: return float("inf"), [], ink, layers, sharpen
    s, beta = sc.fit(ink, layers, sharpen, BLEND[0])
    return s, beta, ink, layers, sharpen


def nudge(cv, sc, dx, gamma, eff, D, sweeps=2):
    dx = list(dx); cur = evaluate(cv, sc, dx, gamma, eff)[0]
    for _ in range(sweeps):
        moved = False
        for i in range(len(dx)):
            for d in range(-D, D + 1):
                if d == dx[i]: continue
                t = dx[:i] + [d] + dx[i + 1:]; v = evaluate(cv, sc, t, gamma, eff)[0]
                if v < cur - 1e-6: cur, dx, moved = v, t, True
        if not moved: break
    return cur, dx


def search(cv, sc, dx0, gamma, D, families, top=3):
    """per effect family: grid with the plain nudges, then nudge refit for the best `top` settings."""
    base = evaluate(cv, sc, dx0, gamma, None)[0]; res = {"none": dict(sse=base, eff=None, dx=dx0)}
    for fam in families:
        grid = sorted(((evaluate(cv, sc, dx0, gamma, e)[0], e) for e in EFFECTS[fam]), key=lambda t: t[0])[:top]
        best = None
        for s, e in grid:
            v, dx = nudge(cv, sc, dx0, gamma, e, D)
            if best is None or v < best["sse"]: best = dict(sse=v, eff=e, dx=dx, grid_sse=s)
        res[fam] = best
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--texture", default="texture.npy"); ap.add_argument("--fonts-dir", default="fonts_cmp")
    ap.add_argument("--recipes", required=True); ap.add_argument("--hopefit", required=True); ap.add_argument("--line2", required=True)
    ap.add_argument("--fakes", type=int, default=4); ap.add_argument("--out", required=True)
    a = ap.parse_args(); T = load_T(a.texture); dev = "cpu"
    d = json.load(open(a.recipes))[0]; rec = Recipe(**{f: d[f] for f in Recipe.__dataclass_fields__ if f in d})
    hb = json.load(open(a.hopefit))["best"]; cfg2 = next(r for r in json.load(open(a.line2))["exact"] if r["phrase"] == T2)
    cv = Canvas(T, rec, a.fonts_dir, hb, cfg2, dev); sc = Scorer(T, dev); D = rec.kx
    n = len(cv.glyphs); g = rec.gamma
    s_plain = evaluate(cv, sc, [0] * n, g, None)[0]
    s_nud, dx0 = nudge(cv, sc, [0] * n, g, None, D, sweeps=3)
    log("one canvas, both lines, free ink per line: plain %.1f -> hand-kerned %.1f  dx %s" % (s_plain, s_nud, dx0))
    blends = {}
    for bl in ("add", "normal", "screen", "lighten"):
        BLEND[0] = bl; best = None
        for gg in (1.0, 1.2, 1.4, 1.6, 1.8, 2.2, 2.6, 3.0):
            v, dxb = nudge(cv, sc, dx0, gg, None, D, sweeps=2)
            if best is None or v < best[0]: best = (v, gg, dxb)
        blends[bl] = dict(sse=best[0], gamma=best[1], dx=best[2], beta=evaluate(cv, sc, best[2], best[1], None)[1])
        log("  blend %-8s best %.1f (gamma %.1f, text level %s)" % (bl, best[0], best[1], [round(x, 1) for x in blends[bl]["beta"][:2]]))
    blend = min(blends, key=lambda k: blends[k]["sse"]); BLEND[0] = blend; g = blends[blend]["gamma"]; dx0 = blends[blend]["dx"]; s_nud = blends[blend]["sse"]
    log("-> blend %s, gamma %.1f: %.1f; effects on top of it:" % (blend, g, s_nud))
    fams = ["shadow", "emboss", "outline", "sharpen", "lineshift"]
    real = search(cv, sc, dx0, g, D, fams)
    for f in fams:
        r = real[f]; log("  %-9s %.1f (gain %.1f) effect %s" % (f, r["sse"], s_nud - r["sse"], r["eff"]))
    # noise-only control: plain nudged fit + permuted residual per band; same search
    s, beta, ink, _, _ = evaluate(cv, sc, dx0, g, None); pred = sc.predict(ink, [], beta, None, BLEND[0]).cpu().numpy()
    chk = sum(float((sc.w[k] * ((torch.as_tensor(np.asarray(T, np.float32))[b] - torch.as_tensor(pred)[b]).reshape(-1)) ** 2).sum()) for k, b in enumerate(sc.bands))
    log("control base: prediction reproduces the fit: %.1f vs %.1f" % (chk, s)); assert abs(chk - s) < 0.5
    Tn = np.asarray(T, np.float64); rng = np.random.default_rng(5); ctrl = {f: [] for f in fams}
    for k in range(a.fakes):
        Tf = Tn.copy()
        for b in (slice(*LINE1), slice(*LINE2)):
            r = Tn[b] - pred[b]; Tf[b] = pred[b] + rng.permutation(r.ravel()).reshape(r.shape)
        cvf = Canvas(Tf, rec, a.fonts_dir, hb, cfg2, dev); scf = Scorer(Tf, dev)
        BLEND[0] = "add"; a0, dxa = nudge(cvf, scf, dx0, rec.gamma, None, D, sweeps=2)
        bb = []
        for bl in ("normal", "screen", "lighten"):
            BLEND[0] = bl
            bb.append(min(nudge(cvf, scf, dxa, gg, None, D, sweeps=1)[0] for gg in (1.0, 1.2, 1.4, 1.6, 1.8, 2.2, 2.6, 3.0)))
        ctrl.setdefault("blend", []).append(a0 - min(bb + [a0]))
        BLEND[0] = blend
        b0, dxf = nudge(cvf, scf, dx0, g, None, D, sweeps=2)
        rf = search(cvf, scf, dxf, g, D, fams)
        for f in fams: ctrl[f].append(b0 - rf[f]["sse"])
        log("  fake %d: gains %s" % (k + 1, {f: round(ctrl[f][-1], 1) for f in fams}))
    BLEND[0] = blend
    out = dict(plain=s_plain, nudged=s_nud, dx=dx0, chars=[c for c, *_ in cv.glyphs], blends=blends, blend=blend, gamma=g,
               blend_noise_gains=ctrl.get("blend"),
               effects={f: dict(sse=real[f]["sse"], gain=s_nud - real[f]["sse"], eff=real[f]["eff"], dx=real[f]["dx"],
                                noise_gains=ctrl[f]) for f in fams})
    json.dump(out, open(a.out, "w"), indent=1)
    # predictions for the figure: plain nudged + best real effect
    bestf = min(fams, key=lambda f: real[f]["sse"] - np.mean(ctrl[f]) * 0 if False else real[f]["sse"])
    figs = {}
    for tag, eff, dx in (("nudged", None, dx0), ("best_effect", real[bestf]["eff"], real[bestf]["dx"])):
        s, beta, ink, layers, shp = evaluate(cv, sc, dx, g, eff); figs[tag] = sc.predict(ink, layers, beta, shp, BLEND[0]).cpu().numpy()
    BLEND[0] = "add"; s, beta, ink, _, _ = evaluate(cv, sc, blends["add"]["dx"], blends["add"]["gamma"], None)
    figs["add_nudged"] = sc.predict(ink, [], beta).cpu().numpy()
    np.savez(os.path.splitext(a.out)[0] + ".npz", real=Tn.astype(np.float32), **figs)
    log("-> %s (best effect family %s)" % (a.out, bestf))





# ------------------------------------------------------------------------------------------- non-integer canvas
def band_sse_batched(sc, tex, gamma):
    """tex (..., 32, 32) linear coverage -> SSE with a free ink level per line (add blend), batched."""
    tot = 0
    for b, d, w in zip(sc.bands, sc.d, sc.w):
        a = tex[..., b, :].clamp(0, 1).reshape(*tex.shape[:-2], -1) ** gamma
        sad = (w * a * d).sum(-1); saa = (w * a * a).sum(-1)
        tot = tot + (w * d * d).sum() - torch.where(saa > 0, sad * sad / saa.clamp_min(1e-9), torch.zeros_like(sad))
    return tot


def scale_search(cv, sc, dx, gamma, kxs, kys, rng_x=10, rng_y=8, top=8):
    """artwork W x H = 32*kx x 32*ky (any integer size) resized to 32x32; the text block position re-searched."""
    from .core import weight_matrix
    rec = cv.rec; A = torch.as_tensor(cv.alpha(dx), device=cv.dev); G = gauss_matrix(rec.blur, dev=cv.dev)
    ox0, oy0 = rec.offx, rec.offy; res = []
    for kx in kxs:
        offs_x = list(range(ox0 - rng_x, ox0 + rng_x + 1))
        WXs = torch.stack([G @ weight_matrix(rec.filter, kx, 32, cv.C, o, cv.dev) for o in offs_x])     # (nx,32,C)
        Q = torch.einsum("rc,xuc->xru", A, WXs)                                                        # (nx,C,32)
        for ky in kys:
            offs_y = list(range(oy0 - rng_y, oy0 + rng_y + 1))
            WYs = torch.stack([G @ weight_matrix(rec.filter, ky, 32, cv.C, o, cv.dev) for o in offs_y])  # (ny,32,C)
            tex = torch.einsum("yvr,xru->yxvu", WYs, Q)
            s = band_sse_batched(sc, tex, gamma); j = int(torch.argmin(s))
            res.append((float(s.reshape(-1)[j]), kx, ky, offs_x[j % len(offs_x)], offs_y[j // len(offs_x)]))
    res.sort()
    return res[:top], res


def set_scale(cv, kx, ky, ox, oy):
    from .core import weight_matrix
    G = gauss_matrix(cv.rec.blur, dev=cv.dev)
    cv.WX = G @ weight_matrix(cv.rec.filter, kx, 32, cv.C, ox, cv.dev); cv.WY = G @ weight_matrix(cv.rec.filter, ky, 32, cv.C, oy, cv.dev)


def scale_main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--texture", default="texture.npy"); ap.add_argument("--fonts-dir", default="fonts_cmp")
    ap.add_argument("--recipes", required=True); ap.add_argument("--hopefit", required=True); ap.add_argument("--line2", required=True)
    ap.add_argument("--fakes", type=int, default=4); ap.add_argument("--out", required=True)
    a = ap.parse_args(); T = load_T(a.texture); dev = "cpu"
    d = json.load(open(a.recipes))[0]; rec = Recipe(**{f: d[f] for f in Recipe.__dataclass_fields__ if f in d})
    hb = json.load(open(a.hopefit))["best"]; cfg2 = next(r for r in json.load(open(a.line2))["exact"] if r["phrase"] == T2)
    kxs = [w / 32 for w in range(176, 209)]; kys = [h / 32 for h in range(136, 185)]; g = rec.gamma; D = rec.kx

    def run(Tx, dx_start):
        cv = Canvas(Tx, rec, a.fonts_dir, hb, cfg2, dev); sc = Scorer(Tx, dev)
        base, dx0 = nudge(cv, sc, dx_start, g, None, D, sweeps=2)
        top, allr = scale_search(cv, sc, dx0, g, kxs, kys)
        best = None
        for s, kx, ky, ox, oy in top[:4]:
            set_scale(cv, kx, ky, ox, oy); v, dxn = nudge(cv, sc, dx0, g, None, D, sweeps=2)
            if best is None or v < best[0]: best = (v, kx, ky, ox, oy, dxn)
        return base, best, allr, cv, sc

    base, best, allr, cv, sc = run(T, [0] * 19)
    log("integer canvas 192x160 (hand-kerned): %.1f | best any canvas: %.1f at %dx%d px (offsets %d,%d), dx %s" % (
        base, best[0], round(best[1] * 32), round(best[2] * 32), best[3], best[4], best[5]))
    grid = {(round(kx * 32), round(ky * 32)): s for s, kx, ky, _, _ in allr}
    log("  rigid-position scores near the optimum: " + ", ".join("%dx%d %.0f" % (w, h, grid[(w, h)]) for w, h in sorted(grid, key=grid.get)[:10]))
    # control: fakes from the integer-canvas hand-kerned fit
    cv0 = Canvas(T, rec, a.fonts_dir, hb, cfg2, dev); sc0 = Scorer(T, dev); _, dx0 = nudge(cv0, sc0, [0] * 19, g, None, D, sweeps=2)
    s, beta, ink, _, _ = evaluate(cv0, sc0, dx0, g, None); pred = sc0.predict(ink, [], beta).cpu().numpy()
    Tn = np.asarray(T, np.float64); rng = np.random.default_rng(3); gains = []
    for k in range(a.fakes):
        Tf = Tn.copy()
        for b in (slice(*LINE1), slice(*LINE2)):
            r = Tn[b] - pred[b]; Tf[b] = pred[b] + rng.permutation(r.ravel()).reshape(r.shape)
        bf, bestf, _, _, _ = run(Tf, dx0); gains.append(bf - bestf[0])
        log("  fake %d: any-canvas gain %.1f (at %dx%d)" % (k + 1, gains[-1], round(bestf[1] * 32), round(bestf[2] * 32)))
    set_scale(cv, *best[1:5]); s, beta, ink, _, _ = evaluate(cv, sc, best[5], g, None)
    np.savez(os.path.splitext(a.out)[0] + ".npz", real=Tn.astype(np.float32), best=sc.predict(ink, [], beta).cpu().numpy())
    json.dump(dict(integer=base, best=dict(sse=best[0], w=round(best[1] * 32), h=round(best[2] * 32), offx=best[3], offy=best[4], dx=best[5]),
                   real_gain=base - best[0], noise_gains=gains, grid=[(round(kx * 32), round(ky * 32), s) for s, kx, ky, _, _ in allr]),
              open(a.out, "w"), indent=0)
    log("real gain %.1f vs noise-only %s -> %s" % (base - best[0], [round(x, 1) for x in gains], a.out))


if __name__ == "__main__":
    import sys
    if "--scale" in sys.argv: sys.argv.remove("--scale"); scale_main()
    else: main()
