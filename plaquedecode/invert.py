"""Invert the fitted process: estimate the high-resolution artwork (canvas) from the 32x32 plaque.

forward:  texture = stone + L * ( WY @ X @ WX^T ).clamp(0,1) ** gamma        (X = canvas ink, 0..1)
The stone is removed exactly as in scoring (planes per 4-column block, both text bands); L and gamma come from the
line-1 fit.  The problem is heavily underdetermined (a 160x128 artwork from ~576 text pixels), so we report three
priors -- none (minimum-norm), total variation, total variation + binary ink -- and, crucially, apply the IDENTICAL
inversion to synthetic plaques whose text is known (same stone, same residual noise).  What the real inversion shows
can then be compared with what each hypothesis would show, instead of reading letters that a prior may invent."""
import json, os
import numpy as np
import torch
from .core import Line1, Line2, Recipe, LINE1, LINE2, block_ops, render_text

# (total variation, binary, sparsity) weights; "auto" = sparsity + TV scaled by the discrepancy principle
PRIORS = {"none": (0.0, 0.0, 0.0), "sparse+tv": None, "sparse+tv+binary": None}


def canvas_line1(L1, rec, text, fdir):
    img, _, _, (r0, r1, c0, c1) = render_text(os.path.join(fdir, rec.font), text, rec.P, rec.tracking, rec.kern, rec.frac,
                                             int(round(rec.esp * rec.kx)))
    img = img[max(0, r0 - 1):r1 + 2, max(0, c0 - 1):c1 + 2]
    C = np.zeros((rec.canvas, rec.canvas), np.float32); X, Y = rec.X + rec.offx, rec.Y + rec.offy
    h, w = img.shape; C[Y:Y + h, X:X + w] = np.maximum(C[Y:Y + h, X:X + w], img[:rec.canvas - Y, :rec.canvas - X])
    return C


def canvas_line2(L2, text, cfg):
    P2, esp, x, yb = cfg
    im, base_row, penx, _ = render_text(L2.fpath, text, P2, L2.TR, L2.KERN, L2.FRAC, int(round(esp * L2.kx)))
    C = np.zeros((L2.CANVAS, L2.CANVAS), np.float32); ox, oy = x - penx, yb - base_row
    h, w = im.shape
    ys, xs = max(0, oy), max(0, ox); ye, xe = min(L2.CANVAS, oy + h), min(L2.CANVAS, ox + w)
    C[ys:ye, xs:xe] = np.maximum(C[ys:ye, xs:xe], im[ys - oy:ye - oy, xs - ox:xe - ox])
    return C


class Inverter:
    def __init__(self, T, rec, WX, WY, L, gamma, dev):
        self.dev = dev; self.WX, self.WY, self.L, self.G = WX, WY, L, gamma
        self.R0, self.R1 = LINE1[0], LINE2[1]                       # rows 6..23 (both bands)
        self.MB1 = block_ops(LINE1[1] - LINE1[0], LINE1[0], dev); self.MB2 = block_ops(LINE2[1] - LINE2[0], LINE2[0], dev)
        # canvas rows/cols that can influence rows 6..23 (everything else is fixed at 0)
        rows = torch.nonzero(WY[self.R0:self.R1].abs().sum(0) > 0)[:, 0]
        self.cr = (int(rows.min()), int(rows.max()) + 1); self.cc = (0, WX.shape[1])

    def resid_sse(self, T, Xfull):
        cov = (self.WY @ Xfull @ self.WX.T).clamp(0, 1) ** self.G
        r = T - self.L * cov
        out = 0
        for (a, b), MB in ((LINE1, self.MB1), (LINE2, self.MB2)):
            H = b - a; rb = r[a:b].reshape(H, 8, 4).movedim(-2, -3).reshape(8, H * 4)
            out = out + (torch.einsum("kmn,kn->km", MB, rb) ** 2).sum()
        return out

    def run(self, T, prior, steps=2500, seed=0, lam=None):
        lam_tv, lam_bin, lam_l1 = lam if lam is not None else PRIORS[prior]
        torch.manual_seed(seed)
        H = self.cr[1] - self.cr[0]; W = self.cc[1] - self.cc[0]
        z = torch.full((H, W), -3.0, device=self.dev, requires_grad=True)     # sigmoid(-3) ~ 0.05: start blank
        opt = torch.optim.Adam([z], lr=0.05)
        Tt = torch.as_tensor(np.asarray(T, np.float32), device=self.dev)
        for it in range(steps):
            X = torch.sigmoid(z)
            Xf = torch.zeros((self.WY.shape[1], self.WX.shape[1]), device=self.dev)
            Xf[self.cr[0]:self.cr[1]] = X
            loss = self.resid_sse(Tt, Xf)
            if lam_tv: loss = loss + lam_tv * 1000 * ((X[1:] - X[:-1]).abs().sum() + (X[:, 1:] - X[:, :-1]).abs().sum()) / 100
            if lam_bin: loss = loss + lam_bin * 1000 * (X * (1 - X)).sum() / 100
            if lam_l1: loss = loss + lam_l1 * X.sum()
            opt.zero_grad(); loss.backward(); opt.step()
        X = torch.sigmoid(z).detach()
        Xf = torch.zeros((self.WY.shape[1], self.WX.shape[1]), device=self.dev); Xf[self.cr[0]:self.cr[1]] = X
        return Xf.cpu().numpy(), float(self.resid_sse(Tt, Xf))


def run(T, rec, fdir, hope, line2_cfg, out, log, steps=2500):
    """rec: line-1 recipe (Apple Palatino BI); hope: hope-calibrated line-2 typesetting; line2_cfg: (P2, esp, x, yb)."""
    L1 = Line1(T); dev = L1.dev
    L2 = Line2(T, rec, fdir, hope["font2"], tr2=hope["tracking2"], kern2=hope["kern2"], frac2=hope["frac2"])
    WX, WY = rec.matrices(dev)
    inv = Inverter(T, rec, WX, WY, L2.L, rec.gamma, dev)
    T = np.asarray(T, np.float32)
    # synthetic plaques: replace the ink of the best reading by the ink of a hypothesis (stone + residual stay real)
    ours1 = canvas_line1(L1, rec, "Eternal Star", fdir); ours2 = canvas_line2(L2, "We hope so", line2_cfg)
    tex = lambda C: (WY @ torch.tensor(C, device=dev) @ WX.T).clamp(0, 1) ** rec.gamma
    ink_ours = (L2.L * tex(np.maximum(ours1, ours2))).cpu().numpy()
    hyps = {"Eternal Star / We hope so": (ours1, ours2)}
    # rivals: line 1 with the claim's text in the same process; line 2 per claim (or the real ink when not claimed)
    for name, l1, l2 in [("L is real 2401 / (row 2 not claimed)", "L is real 2401", None),
                         ("A Secret star / lie here ~", "A Secret star", "lie here ~"),
                         ("Eternal Star / My hope is", "Eternal Star", "My hope is")]:
        c1 = canvas_line1(L1, rec, l1, fdir) if l1 != "Eternal Star" else ours1
        c2 = canvas_line2(L2, l2, L2.exact_refine(l2, line2_cfg)[1]) if l2 else ours2
        hyps[name] = (c1, c2)
    # discrepancy principle: scale the sparsity+TV prior so that the residual on the REAL plaque equals the noise floor
    target = L1.floor + L2.floor
    lo_, hi_ = 0.01, 100.0
    for _ in range(9):
        mid = (lo_ * hi_) ** 0.5
        _, sse = inv.run(T, None, steps // 2, lam=(0.02 * mid, 0.0, 1.0 * mid))
        log("  discrepancy search: scale %.3f -> residual %.1f (target %.1f)" % (mid, sse, target))
        if sse < target: lo_ = mid
        else: hi_ = mid
    sc = (lo_ * hi_) ** 0.5
    LAMS = {"none": (0.0, 0.0, 0.0), "sparse+tv": (0.02 * sc, 0.0, 1.0 * sc), "sparse+tv+binary": (0.02 * sc, 0.05, 1.0 * sc)}
    log("prior scale %.3f (noise-floor target %.1f)" % (sc, target))
    res = {"real": {}}
    for prior in PRIORS:
        X, sse = inv.run(T, prior, steps, lam=LAMS[prior]); res["real"][prior] = dict(X=X, sse=sse)
        log("real plaque, prior %-16s residual SSE %.1f" % (prior, sse))
    # neutral background shared by ALL hypotheses: smooth stone (planes fitted under the best reading) + real stone
    # NOISE taken from the clean rows 23..31 (not from the text rows), so no hypothesis inherits the real text residual
    Tt = torch.as_tensor(T, device=dev); ink_t = torch.as_tensor(ink_ours, device=dev)
    MBc = block_ops(9, 23, dev); Tc = Tt[23:32]
    noise = torch.einsum("kmn,kn->km", MBc, Tc.reshape(9, 8, 4).movedim(-2, -3).reshape(8, 36)).reshape(8, 9, 4).movedim(0, 1).reshape(9, 32)
    Tbg = Tt.clone()
    for (a, b), MB, nz in ((LINE1, inv.MB1, noise), (LINE2, inv.MB2, torch.flip(noise, [1]))):
        r = (Tt[a:b] - ink_t[a:b]).reshape(b - a, 8, 4).movedim(-2, -3).reshape(8, (b - a) * 4)
        smooth = r - torch.einsum("kmn,kn->km", MB, r)
        Tbg[a:b] = smooth.reshape(8, b - a, 4).movedim(0, 1).reshape(b - a, 32) + nz
    Tbg = Tbg.cpu().numpy()
    for name, (c1, c2) in hyps.items():
        Tsyn = Tbg + (L2.L * tex(np.maximum(c1, c2))).cpu().numpy()
        if "not claimed" in name: Tsyn[LINE2[0]:LINE2[1]] = T[LINE2[0]:LINE2[1]]      # row 2: real pixels, no hypothesis
        res[name] = {"truth": np.maximum(c1, c2)}
        for prior in PRIORS:
            X, sse = inv.run(Tsyn, prior, steps, lam=LAMS[prior]); res[name][prior] = dict(X=X, sse=sse)
        log("synthetic %-38s done" % name)
    # crop region for display (text rows/cols of the canvas)
    crop = dict(r0=int(rec.offy + 5 * rec.ky), r1=int(rec.offy + 23 * rec.ky), c0=int(rec.offx + 1 * rec.kx), c1=int(rec.offx + 31 * rec.kx))
    np.savez_compressed(out, crop=json.dumps(crop), names=json.dumps(list(res)),
                        **{"%d_%s" % (i, k): (v if isinstance(v, np.ndarray) else v["X"]) for i, (n, d) in enumerate(res.items()) for k, v in d.items()},
                        sses=json.dumps({n: {k: v["sse"] for k, v in d.items() if isinstance(v, dict)} for n, d in res.items()}))
    # similarity of the REAL inversion to each synthetic inversion, per text row (canvas space)
    r1 = slice(rec.offy + LINE1[0] * rec.ky, rec.offy + LINE1[1] * rec.ky); r2 = slice(rec.offy + LINE2[0] * rec.ky, rec.offy + LINE2[1] * rec.ky)
    cc = slice(crop["c0"], crop["c1"])
    def ncc(a, b):
        a = a - a.mean(); b = b - b.mean(); return float((a * b).sum() / np.sqrt((a * a).sum() * (b * b).sum()))
    sim = {pr: {n: dict(row1=ncc(res["real"][pr]["X"][r1, cc], d[pr]["X"][r1, cc]),
                        row2=None if "not claimed" in n else ncc(res["real"][pr]["X"][r2, cc], d[pr]["X"][r2, cc]))
                for n, d in res.items() if n != "real"} for pr in ("sparse+tv", "sparse+tv+binary")}
    json.dump(dict(similarity=sim, prior_scale=sc, sse={n: {k: v["sse"] for k, v in d.items() if isinstance(v, dict)} for n, d in res.items()}),
              open(os.path.join(os.path.dirname(out), "inversion_similarity.json"), "w"), indent=1)
    log("similarity (sparse+tv): %s" % {n: (round(v["row1"], 3), v["row2"] and round(v["row2"], 3)) for n, v in sim["sparse+tv"].items()})
    log("saved %s" % out)
