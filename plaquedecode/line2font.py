"""Is line 2 set in the same font as line 1?  And the final best fit.

The font tournaments (recipe search) are scored on line 1, where line 2 only chooses among Palatino faces. Here:
  screen  every face fitted to line 2 alone with a continuous typesetting model (size, width, slant, tracking,
          resampling kernel exp(-|d/a|^p), gamma 0.5-2, stroke weight, ink level <= 60), Adam through grid_sample;
          fixed stone, weights 1/(0.15 + var)                                      -> results/line2font_screen.json
  both    the screen's best faces + the Palatino files on both lines with the same model and wrong-text controls;
          line 1 is the control (there Palatino BI is established)                 -> results/line2font_both.json
  hinted  line 2 with the release pipeline's own rendering (core.Line2: hinted, true pixel size, line-1 recipe locked),
          free size/tracking/kerning/advances/word space, a paint-program skew 0-0.3, every position
                                                                                    -> results/line2font_hinted.json
  best    the designer's best version (190x160 artwork, hand kerning) with each Palatino BI file on line 2, its own
          setting re-searched, all glyphs re-nudged, artwork size re-searched      -> results/bestfit.json
          (+ results/stone_bestfit.npz, texture-derived, git-ignored)
  hero    title image from stone_bestfit.npz                                       -> report/figures/hero.png
  figure  the line-2 font figure                                                   -> report/figures/line2_font.png
Fixed-stone mode: PLAQUE_STONE=stone/stone_box.npy PLAQUE_STONE_VAR=stone/stone_box_var.npy.
    python -m plaquedecode.line2font screen --fonts-list FONTS.txt     (one font path per line)
"""
import argparse, itertools, json, math, os, time
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont
from .core import Line2, Recipe, render_text, LINE1, LINE2, DEV
from .__main__ import load_T

S = 96; SUB = 6; MARGIN = 2                                   # hi-res px per em, sub-pixel grid, filter margin
TEXTS2 = ["We hope so", "We hope so."]
RIVALS2 = ["We hope or", "We hope us", "He hope so", "Me hope so", "We hops so", "We hope he", "By hope so", "We love so"]
TEXTS1, RIVALS1 = ["Eternal Star"], ["Eternal Stat", "Eternal Stay", "Eternal Scar", "Eternal Stir", "External Star", "Eternal Stars"]
WIN = {1: (7, 14, 1, 31), 2: (15, 22, 5, 26)}                 # fitting windows (rows, cols; end exclusive)
STARTS = {1: [(x0, y0, math.log(s)) for s in (3.8, 4.3, 4.8, 5.3, 5.8) for x0 in (1.5, 2.5, 3.5, 4.5) for y0 in (11.6, 12.2, 12.8)],
          2: [(x0, y0, math.log(s)) for s in (2.6, 3.0, 3.4, 3.8, 4.3) for x0 in (5.5, 6.5, 7.5, 8.5) for y0 in (19.0, 19.6, 20.2)]}


# ------------------------------------------------------------------------------------------- continuous model
def render(path, text):
    """characters as hi-res images on a common 2S x 2S canvas (baseline y = S, pen x = S/2) + pen positions (em)."""
    f = ImageFont.truetype(path, S); ims, pens = [], []
    for i, ch in enumerate(text):
        if ch == " ": continue
        im = Image.new("L", (2 * S, 2 * S), 0); ImageDraw.Draw(im).text((S // 2, S), ch, 255, font=f, anchor="ls")
        ims.append(np.asarray(im, np.float32) / 255.0); pens.append(f.getlength(text[:i]) / S)
    return ims, pens


class Batch:
    def __init__(self, combos, dev):
        ims, pens, ci, ki = [], [], [], []
        for k, (path, text) in enumerate(combos):
            im, pe = render(path, text); ims += im; pens += pe; ci += list(range(len(im))); ki += [k] * len(im)
        kb = torch.exp(-0.5 * (torch.arange(-6, 7, dtype=torch.float32, device=dev) / 2.0) ** 2); kb /= kb.sum()
        g = torch.tensor(np.stack(ims), device=dev)[:, None]
        self.g = torch.nn.functional.conv2d(torch.nn.functional.conv2d(g, kb.view(1, 1, 1, -1), padding=(0, 6)), kb.view(1, 1, -1, 1), padding=(6, 0))
        self.pens = torch.tensor(pens, device=dev); self.ci = torch.tensor(ci, device=dev, dtype=torch.float32); self.k = torch.tensor(ki, device=dev)


class LineModel:
    """one text line against the fixed stone: score = sum w (T - stone - L cov)^2, one free ink level 0 < L <= LMAX."""
    LMAX = 60.0

    def __init__(self, T, line, dev=DEV):
        self.dev = dev; r0, r1, c0, c1 = WIN[line]
        S_, V_ = np.load(os.environ["PLAQUE_STONE"]), np.load(os.environ["PLAQUE_STONE_VAR"])
        d = (np.asarray(T, float) - S_)[r0:r1, c0:c1]; w = 1.0 / (0.15 + V_[r0:r1, c0:c1])
        self.y = torch.tensor(d.ravel(), dtype=torch.float32, device=dev); self.w = torch.tensor(w.ravel(), dtype=torch.float32, device=dev)
        self.yy = float((self.w * self.y * self.y).sum())
        self.ur = torch.arange(r0 - MARGIN, r1 + MARGIN, 1.0 / SUB, device=dev) + 0.5 / SUB
        self.vc = torch.arange(c0 - MARGIN, c1 + MARGIN, 1.0 / SUB, device=dev) + 0.5 / SUB
        self.rc = torch.arange(r0, r1, device=dev) + 0.5; self.cc = torch.arange(c0, c1, device=dev) + 0.5

    def coverage(self, P, bt):
        K, B = P["x0"].shape; fr, fc = len(self.ur), len(self.vc); sel = lambda v: v[bt.k]
        sx, sy = torch.exp(sel(P["lsx"])), torch.exp(sel(P["lsy"]))
        ey = (self.ur[None, None, :, None] - sel(P["y0"])[..., None, None]) / sy[..., None, None]
        ex = (self.vc[None, None, None, :] - sel(P["x0"])[..., None, None]) / sx[..., None, None] + sel(P["shear"])[..., None, None] * ey
        px = S // 2 + (ex - bt.pens[:, None, None, None] - sel(P["track"])[..., None, None] * bt.ci[:, None, None, None]) * S
        py = (S + ey * S).expand_as(px)
        grid = torch.stack([px / (2 * S - 1) * 2 - 1, py / (2 * S - 1) * 2 - 1], -1).reshape(len(bt.k), B * fr, fc, 2)
        smp = torch.nn.functional.grid_sample(bt.g, grid, align_corners=True, padding_mode="zeros")[:, 0].reshape(len(bt.k), B, fr, fc)
        t = torch.sigmoid(sel(P["t"]))[..., None, None] * 0.6 + 0.2
        fine = torch.zeros((K, B, fr, fc), device=self.dev).index_add(0, bt.k, torch.sigmoid((smp - t) / 0.06)).clamp(0, 1)
        a = torch.nn.functional.softplus(P["a"])[..., None, None] + 0.15; p = 1 + torch.nn.functional.softplus(P["p"])[..., None, None]
        kr = torch.exp(-(((self.ur[None, None, None, :] - self.rc[None, None, :, None]).abs() / a) ** p)); kr = kr / kr.sum(-1, keepdim=True)
        kc = torch.exp(-(((self.vc[None, None, None, :] - self.cc[None, None, :, None]).abs() / a) ** p)); kc = kc / kc.sum(-1, keepdim=True)
        return (kr @ fine @ kc.transpose(-1, -2)).clamp_min(1e-6) ** torch.exp(P["lg"])[..., None, None]

    def score(self, cov):
        c = cov.reshape(*cov.shape[:2], -1); b = (c * self.w * self.y).sum(-1); d = (c * c * self.w).sum(-1)
        return self.yy - torch.relu(b) ** 2 / d.clamp_min(1e-9), b / d.clamp_min(1e-9)


def fit(model, combos, starts, steps):
    """fit every (font, text) combo from all starts at once -> [(score, params, ink)] per combo."""
    bt = Batch(combos, model.dev); K, B = len(combos), len(starts); dev = model.dev
    T_ = lambda col: torch.tensor([s[col] for s in starts], device=dev, dtype=torch.float32).repeat(K, 1)
    Z = lambda v: torch.full((K, B), v, device=dev)
    P = dict(x0=T_(0), y0=T_(1), lsx=T_(2), lsy=T_(2), shear=Z(0.0), track=Z(0.0), a=Z(0.3), p=Z(0.5), lg=Z(0.0), t=Z(0.0))
    for v in P.values(): v.requires_grad_(True)
    opt = torch.optim.Adam([{"params": [P["x0"], P["y0"]], "lr": 0.05}, {"params": [P["lsx"], P["lsy"], P["shear"], P["track"]], "lr": 0.01},
                            {"params": [P["a"], P["p"], P["lg"], P["t"]], "lr": 0.03}])
    for _ in range(steps):
        opt.zero_grad(); s, L = model.score(model.coverage(P, bt))
        (s + 2.0 * P["shear"] ** 2 + 20.0 * P["track"] ** 2 + torch.relu(L - model.LMAX) ** 2).sum().backward(); opt.step()
        with torch.no_grad(): P["shear"].clamp_(-0.35, 0.35); P["track"].clamp_(-0.15, 0.15); P["lg"].clamp_(-0.7, 0.7)
    with torch.no_grad():
        s, L = model.score(model.coverage(P, bt)); s = torch.where((L > 0) & (L <= model.LMAX), s, torch.full_like(s, float("inf"))); j = torch.argmin(s, 1)
        return [(float(s[k, j[k]]), {n: float(v[k, j[k]]) for n, v in P.items()}, float(L[k, j[k]])) for k in range(K)]


def readable(p):
    sx, sy = math.exp(p["lsx"]), math.exp(p["lsy"])
    return dict(x0=round(p["x0"], 2), y0=round(p["y0"], 2), size_px_per_em=round(sy, 3), width_ratio=round(sx / sy, 3), shear=round(p["shear"], 3),
                track_em=round(p["track"], 3), filt_a=round(math.log1p(math.exp(p["a"])) + 0.15, 3), filt_p=round(1 + math.log1p(math.exp(p["p"])), 2),
                gamma=round(math.exp(p["lg"]), 3))


def screen(T, fonts, steps, group, log):
    model = LineModel(T, 2); res = []; t0 = time.time()
    for n in range(0, len(fonts), group):
        grp = []
        for path in fonts[n:n + group]:
            try: [render(path, t) for t in TEXTS2]; grp.append(path)
            except Exception: continue
        if not grp: continue
        out = fit(model, [(p, t) for p in grp for t in TEXTS2], STARTS[2], steps)
        for fi, path in enumerate(grp):
            s, p, L = min(out[fi * len(TEXTS2):(fi + 1) * len(TEXTS2)], key=lambda r: r[0])
            res.append(dict(score=s, font=os.path.basename(path), ink=L, params=readable(p)))
        log("  %d/%d  %.0f s" % (n + len(grp), len(fonts), time.time() - t0))
    res.sort(key=lambda r: r["score"]); return dict(null=model.yy, faces=res)


def both(T, fonts, steps, log):
    out = {}
    for ln, texts, rivals in ((1, TEXTS1, RIVALS1), (2, TEXTS2, RIVALS2)):
        model = LineModel(T, ln); out[ln] = dict(null=model.yy, faces={})
        for path in fonts:
            tt = texts + rivals; res = fit(model, [(path, t) for t in tt], STARTS[ln], steps)
            sc = {t: r[0] for t, r in zip(tt, res)}; bt = min(texts, key=lambda t: sc[t]); riv = min((sc[t], t) for t in rivals)
            out[ln]["faces"][os.path.basename(path)] = dict(score=sc[bt], text=bt, rival=riv, params=readable(res[tt.index(bt)][1]))
            log("  line %d  %8.2f  %-46s rival %s %+.2f" % (ln, sc[bt], os.path.basename(path), riv[1], riv[0] - sc[bt]))
            if DEV == "cuda": torch.cuda.empty_cache()
    return out


# ------------------------------------------------------------------------------------------- hinted true-size line 2
SKEWS = (0.0, 0.1, 0.2, 0.25, 0.3)


def skewed(im, base_row, s):
    """paint-program skew of the text layer about the baseline (top leans right for s > 0); pen origin kept."""
    if s == 0: return im
    pad = int(math.ceil(s * im.shape[0])) + 2; a = np.pad(im, ((0, 0), (pad, pad)))
    out = Image.fromarray((a * 255).astype(np.uint8)).transform((a.shape[1], a.shape[0]), Image.AFFINE, (1, s, -s * base_row, 0, 1, 0), Image.BILINEAR)
    return np.asarray(out, np.float32)[:, pad:] / 255.0


def hinted_best(L2, text, P2, esp, s):
    im, base_row, penx, _ = render_text(L2.fpath, text, P2, L2.TR, L2.KERN, L2.FRAC, int(round(esp * L2.kx)))
    im = skewed(im, base_row, s); hI, wI = im.shape; I = torch.tensor(np.ascontiguousarray(im), device=L2.dev); MARG = wI + hI + 64
    WYp = torch.nn.functional.pad(L2.WY[L2.B0:L2.B1], (MARG, MARG)); WXp = torch.nn.functional.pad(L2.WX, (MARG, MARG))
    xs = list(range(L2.OFFX + 3 * L2.kx, L2.OFFX + 10 * L2.kx)); WXs = torch.stack([WXp[:, x - penx + MARG: x - penx + MARG + wI] for x in xs])
    best = (float("inf"), None, None)
    for yb in L2.YBS:
        sb = L2.sse_blocks(torch.einsum("rw,xcw->xrc", WYp[:, yb - base_row + MARG: yb - base_row + MARG + hI] @ I, WXs)).sum(-1); j = int(torch.argmin(sb))
        if float(sb[j]) < best[0]: best = (float(sb[j]), xs[j], yb)
    return best


def hinted(T, rec, fdir, fonts, log):
    out = {}
    for f2 in fonts:
        rows = []
        for TR2, kern, frac in itertools.product((-1, 0, 1, 2, 3), (False, True), ("glyph", False)):
            L2 = Line2(T, rec, fdir, font2=f2, tr2=TR2, kern2=kern, frac2=frac)
            for P2, esp, s in itertools.product(range(14, 23), L2.ESPS, SKEWS):
                if not L2.esp_ok(P2, esp): continue
                v, x, yb = hinted_best(L2, TEXTS2[0], P2, esp, s)
                rows.append(dict(sse=v, tracking2=TR2, kern2=kern, frac2=frac, P2=P2, esp=esp, skew=s, x=x, yb=yb))
        rows.sort(key=lambda d: d["sse"]); b = rows[0]
        L2 = Line2(T, rec, fdir, font2=f2, tr2=b["tracking2"], kern2=b["kern2"], frac2=b["frac2"])
        riv = sorted((hinted_best(L2, t, b["P2"], b["esp"], b["skew"])[0], t) for t in RIVALS2)
        out[os.path.basename(f2)] = dict(best=b, upright=min((d for d in rows if d["skew"] == 0), key=lambda d: d["sse"]), rivals=riv)
        log("  %8.2f  %-44s P2 %d skew %.2f | best rival %s %+.2f" % (b["sse"], os.path.basename(f2), b["P2"], b["skew"], riv[0][1], riv[0][0] - b["sse"]))
    return out


# ------------------------------------------------------------------------------------------- final best fit
def best(T, rec, fdir, hb, cfg2, sb, fonts2, log):
    from . import designer as DS
    dev = "cpu"; sc = DS.Scorer(T, dev); g = rec.gamma; n1 = len(DS.T1.replace(" ", ""))
    scale = (sb["w"] / 32, sb["h"] / 32, sb["offx"], sb["offy"]); dx1 = sb["dx"][:n1]

    def canvas(f2, P2, TR2, kern2, frac2, esp, x, yb, scl):
        cv = DS.Canvas(T, rec, fdir, dict(font2=f2, tracking2=TR2, kern2=kern2, frac2=frac2), dict(P2=P2, esp=esp, x=x, yb=yb), dev)
        DS.set_scale(cv, *scl); return cv
    cv0 = DS.Canvas(T, rec, fdir, hb, cfg2, dev); DS.set_scale(cv0, *scale); ref = DS.evaluate(cv0, sc, sb["dx"], g, None)[0]
    log("designer best version reproduced: %.2f" % ref); rows = []
    for f2 in fonts2:
        for P2, TR2, kern2, frac2, esp in itertools.product((18, 19, 20), (-1, 0, 1, 2), (False, True), ("glyph", False), (-1.0, -0.5, 0.0, 0.5)):
            bb = None
            for x, yb in itertools.product(range(cfg2["x"] - 9, cfg2["x"] + 10), range(cfg2["yb"] - 3, cfg2["yb"] + 4)):
                cv = canvas(f2, P2, TR2, kern2, frac2, esp, x, yb, scale)
                if len(cv.glyphs) != len(sb["dx"]): continue
                v = DS.evaluate(cv, sc, dx1 + [0] * (len(cv.glyphs) - n1), g, None)[0]
                if bb is None or v < bb[0]: bb = (v, x, yb)
            if bb: rows.append((bb[0], f2, (P2, TR2, kern2, frac2, esp, bb[1], bb[2])))
        log("  %-40s line-2 placement %.2f" % (os.path.basename(f2), min(r[0] for r in rows if r[1] == f2)))
    rows.sort(key=lambda r: r[0]); final = []
    for f2 in fonts2:                                              # every file: its best line-2 setting, refitted
        v0, _, c2 = min(r for r in rows if r[1] == f2)
        cv = canvas(f2, *c2, scale); s1, dx = DS.nudge(cv, sc, dx1 + [0] * (len(cv.glyphs) - n1), g, None, rec.kx, sweeps=3)
        top, _ = DS.scale_search(cv, sc, dx, g, [w / 32 for w in range(184, 197)], [h / 32 for h in range(154, 167)], top=4); bb = (s1, scale, dx)
        for s, kx, ky, ox, oy in top:
            DS.set_scale(cv, kx, ky, ox, oy); v, dxn = DS.nudge(cv, sc, dx, g, None, rec.kx, sweeps=3)
            if v < bb[0]: bb = (v, (kx, ky, ox, oy), dxn)
        final.append(dict(sse=bb[0], font2=os.path.basename(f2), line2=c2, artwork=[round(bb[1][0] * 32), round(bb[1][1] * 32), bb[1][2], bb[1][3]],
                          dx=bb[2], placement_only=v0, _scl=bb[1], _f2=f2))
        log("  refit %-40s %.2f" % (os.path.basename(f2), bb[0]))
    final.sort(key=lambda d: d["sse"]); w = final[0]
    cv = canvas(w["_f2"], *w["line2"], w["_scl"]); blends = {}
    for bl in ("add", "screen", "normal", "lighten"):
        DS.BLEND[0] = bl; blends[bl] = DS.evaluate(cv, sc, w["dx"], g, None)[0]
    DS.BLEND[0] = "add"; s, beta, ink, _, _ = DS.evaluate(cv, sc, w["dx"], g, None); pred = sc.predict(ink, [], beta).cpu().numpy()
    np.savez("results/stone_bestfit.npz", real=np.asarray(T, np.float32), model=pred, alpha=cv.alpha(w["dx"]))
    for d in final: d.pop("_scl"); d.pop("_f2")
    return dict(report_version=ref, best=final[0], ink=beta[:2], files=final, blends=blends)


# ------------------------------------------------------------------------------------------- figures
def hero(npz, out, sse=None):
    Z = np.load(npz); real, model, A = Z["real"], Z["model"], Z["alpha"]; lo, hi = np.percentile(real, 1), np.percentile(real, 99.5)
    tex = lambda a: Image.fromarray((np.clip((a - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)).resize((576, 576), Image.NEAREST).convert("RGB")
    r, m = tex(real), tex(model); bb = Image.fromarray((A > 0.02).astype(np.uint8) * 255).getbbox()
    art = Image.fromarray(((1 - A) * 255).astype(np.uint8)).crop((bb[0] - 14, bb[1] - 14, bb[2] + 14, bb[3] + 14))
    art = art.resize((art.width * 4, art.height * 4), Image.LANCZOS).convert("RGB")
    W = 2 * 576 + 30 + 80; H = 60 + 576 + 50 + art.height + 40; im = Image.new("RGB", (W, H), (250, 250, 247)); d = ImageDraw.Draw(im)
    try: f = ImageFont.truetype("DejaVuSans.ttf", 22); fs = ImageFont.truetype("DejaVuSans.ttf", 17)
    except OSError: f = fs = ImageFont.load_default()
    im.paste(r, (40, 60)); im.paste(m, (646, 60))
    d.text((40, 22), "Real plaque texture (ROM, 32x32)", (20, 20, 20), font=f); d.text((646, 22), "Our best model" + (" (error %.2f)" % sse if sse else ""), (20, 20, 20), font=f)
    d.text((40, 654), "The artwork we reconstruct: 190x160 canvas, Adobe Palatino Bold Italic 26 px / 19 px, hand-kerned", (20, 20, 20), font=fs)
    im.paste(art, ((W - art.width) // 2, 686)); im.save(out)


NAMES = {"RALEIGDB.PFB": "Raleigh Demibold", "RALEIGHB.PFB": "Raleigh Bold", "RALEIGHM.PFB": "Raleigh Medium",
         "RALEIGHN.PFB": "Raleigh Regular", "RALEIGHL.PFB": "Raleigh Light", "RALEIGXB.PFB": "Raleigh ExtraBold",
         "RALEIGHM.TTF": "Raleigh Medium (TrueType)", "MATANTQN.TTF": "MattAntique (Bitstream)", "COOPERM.PFB": "Cooper Medium (Bitstream)",
         "CHARTRBI.PFB": "Charter Bold Italic (Bitstream)", "usb_____.pfb": "ITC Usherwood Bold", "ovbi____.pfb": "ITC Officina Serif BI (IRIX)",
         "AI55IRIX-ITCOfficinaSerif-BoldItalic.pfb": "ITC Officina Serif BI", "URWBookman-DemiItalic.t1": "URW Bookman Demi Italic",
         "Palatino__sfnt_32751_Palatino_Bold_Italic.ttf": "Palatino BI (KanjiTalk 7.5)", "MacOS9-PalatinoBoldItalic.ttf": "Palatino BI (Mac OS 9)",
         "PalatinoBoldItalic.ttf": "Palatino BI (Apple)", "AdobePalatino-BoldItalic.pfb": "Palatino BI (Adobe 1990)",
         "AdobePalatino-Italic.pfb": "Palatino Italic (Adobe)", "P052-BoldItalic.otf": "P052 Bold Italic (URW)"}


def figure(res, out):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    B = json.load(open(os.path.join(res, "line2font_both.json"))); H = json.load(open(os.path.join(res, "line2font_hinted.json")))
    nice = lambda f: NAMES.get(f, f.rsplit(".", 1)[0].replace("AI55IRIX-", "")[:30])
    pal = lambda f: "alatino" in f or "P052" in f
    fig, axs = plt.subplots(1, 3, figsize=(13.0, 4.6)); fig.subplots_adjust(wspace=0.95, left=0.14, right=0.97, bottom=0.12, top=0.9)
    for ax, ln in zip(axs[:2], ("1", "2")):
        F = B[ln]["faces"]; ks = sorted(F, key=lambda k: F[k]["score"])
        ax.barh(range(len(ks)), [F[k]["score"] for k in ks], color=["#2e86c1" if pal(k) else "#bbbbbb" for k in ks])
        ax.set_yticks(range(len(ks))); ax.set_yticklabels([nice(k) for k in ks], fontsize=6); ax.invert_yaxis()
        ax.set_title("line %s, smooth (unhinted) model" % ln, fontsize=9); ax.set_xlabel("error (lower = better)", fontsize=8)
        lo = min(F[k]["score"] for k in ks); ax.set_xlim(lo * 0.9, max(F[k]["score"] for k in ks) * 1.02)
    ks = sorted(H, key=lambda k: H[k]["best"]["sse"]); ax = axs[2]
    ax.barh(range(len(ks)), [H[k]["best"]["sse"] for k in ks], color=["#2e86c1" if pal(k) else "#bbbbbb" for k in ks])
    for i, k in enumerate(ks):
        gap = H[k]["rivals"][0][0] - H[k]["best"]["sse"]
        ax.text(H[k]["best"]["sse"] + 3, i, "skew %.2f, rival %+.0f" % (H[k]["best"]["skew"], gap), va="center", fontsize=5.5)
    ax.set_yticks(range(len(ks))); ax.set_yticklabels([nice(k) for k in ks], fontsize=6); ax.invert_yaxis()
    ax.set_title("line 2, hinted at true pixel size", fontsize=9); ax.set_xlabel("error (lower = better)", fontsize=8)
    ax.set_xlim(200, 700); fig.savefig(out, dpi=200); plt.close(fig)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["screen", "both", "hinted", "best", "hero", "figure"])
    ap.add_argument("--texture", default="texture.npy"); ap.add_argument("--fonts-dir", default="fonts")
    ap.add_argument("--fonts-list", help="one font path per line"); ap.add_argument("--results", default="results")
    ap.add_argument("--recipes", default="results/stone_recipes_Adobe.json"); ap.add_argument("--hopefit", default="results/stone_hopefit_Adobe.json")
    ap.add_argument("--line2", default="results/stone_line2_dp_hopefit_Adobe.json"); ap.add_argument("--scale", default="results/stone_designer_scale_Adobe.json")
    ap.add_argument("--steps", type=int, default=150); ap.add_argument("--group", type=int, default=10); a = ap.parse_args()
    log = lambda s: print(s, flush=True); R = lambda n: os.path.join(a.results, n)
    if a.cmd == "hero": return hero(R("stone_bestfit.npz"), "report/figures/hero.png", json.load(open(R("bestfit.json")))["best"]["sse"])
    if a.cmd == "figure": return figure(a.results, "report/figures/line2_font.png")
    T = load_T(a.texture); fonts = [l.strip() for l in open(a.fonts_list) if l.strip()] if a.fonts_list else []
    d = json.load(open(a.recipes))[0]; rec = Recipe(**{f: d[f] for f in Recipe.__dataclass_fields__ if f in d})
    if a.cmd == "screen": json.dump(screen(T, fonts, a.steps, a.group, log), open(R("line2font_screen.json"), "w"), indent=0)
    if a.cmd == "both": json.dump(both(T, fonts, 400, log), open(R("line2font_both.json"), "w"), indent=0)
    if a.cmd == "hinted": json.dump(hinted(T, rec, a.fonts_dir, fonts, log), open(R("line2font_hinted.json"), "w"), indent=0)
    if a.cmd == "best":
        hb = json.load(open(a.hopefit))["best"]; cfg2 = next(r for r in json.load(open(a.line2))["exact"] if r["phrase"] == "We hope so")
        sb = json.load(open(a.scale))["best"]
        json.dump(best(T, rec, a.fonts_dir, hb, cfg2, sb, fonts or [hb["font2"]], log), open(R("bestfit.json"), "w"), indent=0, default=str)


if __name__ == "__main__":
    main()
