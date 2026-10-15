"""Forward model of the Super Mario 64 courtyard plaque texture.

texture (32x32, 5-bit grey) = stone background + L * coverage(text)^gamma

coverage(text): the text is typed once on a 32kx x 32ky canvas (font, integer pixel size, tracking, optional kerning,
whole-pixel advances), resized to 32x32 with a standard filter (support scaled like PIL/Photoshop), optionally
Gaussian-blurred, then a gamma is applied.  The stone is treated as a nuisance: inside every 4-column block of a text
band it is a plane (a + b*x + c*y) that is projected out exactly, the ink level L is solved in closed form (line 1) or
fixed to line 1's value (line 2).  The honest noise floor is the same operator applied to the clean stone rows 23..31.
"""
import math, itertools, os
from dataclasses import dataclass, asdict
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont

DEV = "cuda" if torch.cuda.is_available() else "cpu"
LINE1 = (6, 15)          # texture rows of the line-1 band (half-open)
LINE2 = (15, 24)         # texture rows of the line-2 band
CLEAN = (23, 32)         # clean stone rows used for the noise floor
FILTERS_ALL = ["nearest", "box", "bilinear", "bicubic5", "bicubic75", "lanczos3"]


# ----------------------------------------------------------------------------------------------- stone operators
def planes_op(H, W, r0, dev=DEV):
    """Dense residual-maker: removes a plane (1, x, y) inside every 4-column block of an H x W band."""
    M = torch.zeros((H * W, H * W), device=dev, dtype=torch.float64)
    for k in range(W // 4):
        idx = [r * W + c for r in range(H) for c in range(4 * k, 4 * k + 4)]
        X = torch.tensor([[1.0, (i % W) - 4 * k, (i // W) + r0 - 10] for i in idx], device=dev, dtype=torch.float64)
        ii = torch.tensor(idx, device=dev)
        M[ii[:, None], ii[None, :]] = torch.eye(len(idx), device=dev, dtype=torch.float64) - X @ torch.linalg.pinv(X)
    return M.float()


def block_ops(H, r0, dev=DEV):
    """Same operator in block form: (8, 4H, 4H), block pixel order row-major (r, c)."""
    Ms = []
    for k in range(8):
        Xm = np.array([[1.0, c, r + r0 - 10] for r in range(H) for c in range(4)])
        Ms.append(np.eye(len(Xm)) - Xm @ np.linalg.pinv(Xm))
    return torch.tensor(np.stack(Ms), device=dev, dtype=torch.float32)


# ----------------------------------------------------------------------------------------------- resampling
def kern1d(name):
    if name == "box": return 0.5, lambda d: (np.abs(d) <= 0.5).astype(float)
    if name == "bilinear": return 1.0, lambda d: np.clip(1 - np.abs(d), 0, None)
    if name in ("bicubic5", "bicubic75"):
        a = -0.5 if name == "bicubic5" else -0.75
        def f(d):
            x = np.abs(d)
            return np.where(x <= 1, (a + 2) * x ** 3 - (a + 3) * x ** 2 + 1, np.where(x < 2, a * x ** 3 - 5 * a * x ** 2 + 8 * a * x - 4 * a, 0))
        return 2.0, f
    if name == "lanczos3": return 3.0, lambda d: np.where(np.abs(d) < 3, np.sinc(d) * np.sinc(d / 3), 0)
    raise ValueError(name)


def weight_matrix(name, k, ntex, ncanvas, off, dev=DEV):
    """W[u, j]: weight of canvas pixel j (canvas starts `off` px before texture pixel 0) for texture pixel u (downscale by k)."""
    Wm = np.zeros((ntex, ncanvas))
    for u in range(ntex):
        if name == "nearest":
            j = int(math.floor((u + 0.5) * k)) + off
            if 0 <= j < ncanvas: Wm[u, j] = 1.0
            continue
        sup, f = kern1d(name)
        c = (u + 0.5) * k
        j0 = int(math.floor(c - sup * k)) - 1; j1 = int(math.ceil(c + sup * k)) + 1
        js = np.arange(j0, j1 + 1); w = f((js + 0.5 - c) / k)
        if w.sum() == 0: continue
        w = w / w.sum()
        for j, wv in zip(js, w):
            if 0 <= j + off < ncanvas: Wm[u, j + off] += wv
    return torch.tensor(Wm, device=dev, dtype=torch.float32)


def gauss_matrix(sig, n=32, dev=DEV):
    if sig <= 0: return torch.eye(n, device=dev)
    i = np.arange(n); G = np.exp(-0.5 * ((i[:, None] - i[None, :]) / sig) ** 2); G /= G.sum(1, keepdims=True)
    return torch.tensor(G, device=dev, dtype=torch.float32)


# ----------------------------------------------------------------------------------------------- typesetting
def render_text(fpath, text, P, TR, kern, frac, ESP=0):
    """Type `text` once like a 1990s paint program: font at integer pixel size P, tracking TR (canvas px), optional pair
    kerning, advance mode frac: True = fractional, False = round the pen, "glyph" = every advance rounded (Mac
    FractEnable off); ESP = extra word-space px.  Returns (image 0..1, baseline row, pen-x origin, ink bbox)."""
    f = ImageFont.truetype(fpath, P)
    asc, desc = f.getmetrics()
    xs, x = [], 0.0; prev = None
    for c in text:
        if prev is not None and kern and c != " " and prev != " ":
            x += f.getlength(prev + c) - f.getlength(prev) - f.getlength(c)
        xs.append(x if frac else round(x))
        adv = f.getlength(c)
        if frac == "glyph": adv = round(adv)
        x += adv + TR + (ESP if c == " " else 0); prev = c
    W = int(math.ceil(x)) + 4 * P; Hh = asc + desc + 4
    SS = int(os.environ.get("PLAQUE_SS", "1"))      # >1: draw outlines at SSx size and box-average down = unhinted AA
    if SS > 1:
        fS = ImageFont.truetype(fpath, P * SS)
        im = Image.new("L", (W * SS, Hh * SS), 0); d = ImageDraw.Draw(im)
        for c, xx in zip(text, xs):
            if c != " ": d.text(((P + xx) * SS, (asc + 2) * SS), c, 255, font=fS, anchor="ls")
        a = np.asarray(im, np.float32).reshape(Hh, SS, W, SS).mean((1, 3)) / 255.0
    else:
        im = Image.new("L", (W, Hh), 0); d = ImageDraw.Draw(im)
        for c, xx in zip(text, xs):
            if c != " ": d.text((P + xx, asc + 2), c, 255, font=f, anchor="ls")
        a = np.asarray(im, np.float32) / 255.0
    rows = np.nonzero(a.sum(1) > 0)[0]; cols = np.nonzero(a.sum(0) > 0)[0]
    return a, asc + 2, P, (rows.min(), rows.max(), cols.min(), cols.max())


@dataclass
class Recipe:
    """One complete designer process for line 1 (positions X, Y = canvas offset of the ink crop, minus the canvas margin)."""
    font: str; P: int; tracking: int; kern: bool; frac: object; filter: str; kx: int; ky: int
    blur: float = 0.0; gamma: float = 1.0; esp: float = 0.0; X: int = 0; Y: int = 0
    sse: float = float("nan"); ink: float = float("nan")

    @property
    def canvas(self): return 32 * max(self.kx, self.ky) + 12 * max(self.kx, self.ky)
    @property
    def offx(self): return 6 * self.kx
    @property
    def offy(self): return 6 * self.ky

    def matrices(self, dev=DEV):
        WX = gauss_matrix(self.blur, dev=dev) @ weight_matrix(self.filter, self.kx, 32, self.canvas, self.offx, dev)
        WY = gauss_matrix(self.blur, dev=dev) @ weight_matrix(self.filter, self.ky, 32, self.canvas, self.offy, dev)
        return WX, WY

    def to_dict(self): return asdict(self)


# ----------------------------------------------------------------------------------------------- line 1
class Line1:
    """Scoring context for line 1 ('Eternal Star' band, rows 6..14)."""
    def __init__(self, T, dev=DEV):
        self.dev = dev
        self.T = torch.as_tensor(np.asarray(T, np.float32), device=dev)
        self.R0, self.R1 = LINE1; self.H = self.R1 - self.R0
        self.M = planes_op(self.H, 32, self.R0, dev)
        self.t = self.T[self.R0:self.R1].reshape(-1); self.Mt = self.M @ self.t; self.tMt = float((self.Mt * self.Mt).sum())
        Mc = planes_op(CLEAN[1] - CLEAN[0], 32, CLEAN[0], dev)
        self.floor = float(((Mc @ self.T[CLEAN[0]:CLEAN[1]].reshape(-1)) ** 2).sum())

    def coverage(self, rec: Recipe, text, fdir=""):
        """Linear (pre-gamma) coverage of the whole 32x32 texture for `text` typed with recipe `rec`."""
        import os
        if rec.font == "SM64-dialog":
            from . import gamefont as GFm
            img, _, _, (r0, r1, c0, c1) = GFm.render(GFm.load(os.path.join(fdir, "sm64_dialog_font.npz")), text, rec.P / 16.0,
                                                     rec.tracking, rec.frac, int(round(rec.esp * rec.kx)))
        else:
            img, _, _, (r0, r1, c0, c1) = render_text(os.path.join(fdir, rec.font), text, rec.P, rec.tracking, rec.kern, rec.frac,
                                                     int(round(rec.esp * rec.kx)))
        img = img[max(0, r0 - 1):r1 + 2, max(0, c0 - 1):c1 + 2]
        WX, WY = rec.matrices(self.dev); X, Y = rec.X + rec.offx, rec.Y + rec.offy
        I = torch.tensor(img, device=self.dev); h, w = I.shape
        return WY[:, Y:Y + h] @ I @ WX[:, X:X + w].T

    def score(self, lin, gamma):
        """SSE and ink level for a linear coverage map (32x32)."""
        a = (lin.clamp(0, 1) ** gamma)[self.R0:self.R1].reshape(-1); Ma = self.M @ a
        num = float(Ma @ self.Mt); den = float(Ma @ Ma); L = num / den if den > 0 else 0.0
        return float(((self.M @ (self.t - L * a)) ** 2).sum()), L

    def prediction(self, lin, gamma):
        """stone planes (fitted to the residual) + ink, for the line-1 band."""
        a = (lin.clamp(0, 1) ** gamma)[self.R0:self.R1].reshape(-1); _, L = self.score(lin, gamma)
        return (self.t - self.M @ (self.t - L * a)).reshape(self.H, 32)


def search_recipes(line1: Line1, fdir, font, text, kxy, filters, blurs=(0.0,), gammas=(1.0,), esps=(0.0,),
                   fracs=(True, False), log=None):
    """Exhaustive designer-recipe search for one font and one line-1 text.  Returns a list of Recipe (one per
    (kx, ky, P, tracking, kern, frac, esp, filter, blur) with the best position + gamma)."""
    import os
    dev = line1.dev; fpath = os.path.join(fdir, font)
    G = torch.tensor(gammas, device=dev)
    bitmap = font == "SM64-dialog"                     # the game's own dialog font (bitmap, from the user's ROM)
    if bitmap:
        from . import gamefont as GFm
        gfont = GFm.load(os.path.join(fdir, "sm64_dialog_font.npz"))
        rr = np.nonzero(gfont[0]["E"].sum(1) > 0.3)[0]; cap_ratio = (rr.max() - rr.min() + 1) / 16.0
        fracs, kerns = ("nearest", "bicubic"), (False,)
        rend = lambda text_, P_, TR_, kern_, frac_, esp_: GFm.render(gfont, text_, P_ / 16.0, TR_, frac_, esp_)
    else:
        f96 = ImageFont.truetype(fpath, 96); capE = f96.getbbox("E"); cap_ratio = (capE[3] - capE[1]) / 96.0
        kerns = (True, False)
        rend = lambda text_, P_, TR_, kern_, frac_, esp_: render_text(fpath, text_, P_, TR_, kern_, frac_, esp_)
    out = []
    for kx, ky in kxy:
        P0 = 4.5 * ky / cap_ratio
        Ps = sorted(set(int(round(P0 * s)) for s in np.arange(0.82, 1.21, 0.04)))
        TRs = [0] if kx == 1 else list(range(-max(1, kx // 2), kx + 1))
        if len(blurs) > 1: TRs = [t for t in TRs if abs(t) <= max(1, kx // 2)]
        proto = Recipe(font, 0, 0, False, False, "bilinear", kx, ky)
        CANVAS, OFFX, OFFY = proto.canvas, proto.offx, proto.offy
        WX = {(fl, b): gauss_matrix(b, dev=dev) @ weight_matrix(fl, kx, 32, CANVAS, OFFX, dev) for fl in filters for b in blurs}
        WY = {(fl, b): (gauss_matrix(b, dev=dev) @ weight_matrix(fl, ky, 32, CANVAS, OFFY, dev))[line1.R0:line1.R1] for fl in filters for b in blurs}
        for P, TR, kern, frac, esp in itertools.product(Ps, TRs, kerns, fracs, esps):
            if P < 4: continue
            img, _, _, (r0, r1, c0, c1) = rend(text, P, TR, kern, frac, int(round(esp * kx)))
            img = img[max(0, r0 - 1):r1 + 2, max(0, c0 - 1):c1 + 2]; ys0 = max(0, r0 - 1); xs0 = max(0, c0 - 1)
            hI, wI = img.shape; I = torch.tensor(img, device=dev)
            Xc = int(round(2.4 * kx)) + OFFX - (c0 - xs0); Yc = int(round(8.1 * ky)) + OFFY - (r0 - ys0)
            Xs = [X for X in range(Xc - int(1.6 * kx) - 1, Xc + int(1.6 * kx) + 2) if X >= 0 and X + wI <= CANVAS]
            Ys = [Y for Y in range(Yc - int(1.4 * ky) - 1, Yc + int(1.4 * ky) + 2) if Y >= 0 and Y + hI <= CANVAS]
            if not Xs or not Ys: continue
            for fl, bl in itertools.product(filters, blurs):
                wx, wy = WX[(fl, bl)], WY[(fl, bl)]
                WXs = torch.stack([wx[:, X:X + wI] for X in Xs])
                best = None
                for Y in Ys:
                    cov = torch.einsum("rw,xcw->xrc", wy[:, Y:Y + hI] @ I, WXs).reshape(len(Xs), -1)
                    cov = (cov.clamp(0, 1)[None] ** G[:, None, None]).reshape(-1, cov.shape[1])
                    Ma = cov @ line1.M; num = Ma @ line1.Mt; den = (Ma * Ma).sum(1)
                    s = line1.tMt - torch.where(num > 0, num * num / den.clamp_min(1e-9), torch.zeros_like(num))
                    j = int(torch.argmin(s)); v = float(s[j])
                    if best is None or v < best[0]:
                        best = (v, Xs[j % len(Xs)], Y, float(num[j] / den[j]), float(G[j // len(Xs)]))
                v, X, Y, L, g = best
                out.append(Recipe(font, P, TR, kern, frac, fl, kx, ky, bl, g, esp, X - OFFX, Y - OFFY, v, L))
        if log: log("  %s %r canvas %dx%d done, best so far %.1f" % (font, text, 32 * kx, 32 * ky, min(r.sse for r in out)))
    return out


# ----------------------------------------------------------------------------------------------- line 2
class Line2:
    """Line-2 decoder under a LOCKED line-1 recipe: same face, canvas, tracking, advance rounding, filter, blur, gamma
    and the same ink level L.  Free: pixel size P2, baseline yb, start pen x, word space."""
    ESPS = (-1.0, -0.5, 0.0, 0.5)

    def __init__(self, T, rec: Recipe, fdir, font2=None, line1_text="Eternal Star", dev=DEV, tr2=None, kern2=False, frac2=None):
        import os
        self.dev = dev; self.rec = rec
        self.fpath = os.path.join(fdir, font2 or rec.font)
        self.line1 = Line1(T, dev)
        # line-2 typesetting (own tracking / kerning / advance mode allowed; canvas, filter, blur, gamma are shared)
        self.TR = rec.tracking if tr2 is None else tr2; self.G = rec.gamma; self.KERN = kern2
        self.FRAC = rec.frac if frac2 is None else frac2; self.ROUND = self.FRAC == "glyph"
        self.kx, self.ky = rec.kx, rec.ky; self.CANVAS = rec.canvas; self.OFFX, self.OFFY = rec.offx, rec.offy
        self.WX, self.WY = rec.matrices(dev)
        self.LIN1 = self.line1.coverage(rec, line1_text, fdir)
        self.sse1, self.L = self.line1.score(self.LIN1, rec.gamma)
        self.B0, self.B1 = LINE2; self.HB = self.B1 - self.B0
        self.T2 = self.line1.T[self.B0:self.B1]; self.BASE = self.LIN1[self.B0:self.B1]
        self.MB = block_ops(self.HB, self.B0, dev)
        Tc = self.line1.T[CLEAN[0]:CLEAN[1]]
        self.floor = float(sum(((self.MB[k] @ Tc[:, 4 * k:4 * k + 4].reshape(-1)) ** 2).sum() for k in range(8)))
        self.STONE = float(self.sse_blocks(torch.zeros((self.HB, 32), device=dev)).sum())
        self.XS = torch.arange(self.OFFX + 2 * self.kx, self.OFFX + 27 * self.kx, device=dev)
        self.YBS = sorted(set(int(round(self.OFFY + (b + 0.5) * self.ky)) for b in np.arange(18.6, 21.01, 1.0 / self.ky)))

    MIN_STEP = 2      # minimum word gap (canvas px, ~0.4 texture px): words may not touch or overlap

    def space_step(self, P2, esp):
        """canvas px from the end of a word's last advance to the next word's pen (space + tracking + extra space)."""
        if not hasattr(self, "_space"): self._space = {}
        if P2 not in self._space:
            a_ = ImageFont.truetype(self.fpath, P2).getlength(" "); self._space[P2] = round(a_) if self.ROUND else a_
        return int(round(self._space[P2] + self.TR + esp * self.kx))

    def esp_ok(self, P2, esp):
        return self.space_step(P2, esp) >= self.MIN_STEP

    def sse_blocks(self, lin):
        cov = (self.BASE + lin).clamp(0, 1) ** self.G
        r = self.T2 - self.L * cov
        sh = r.shape[:-2]
        rb = r.reshape(*sh, self.HB, 8, 4).movedim(-2, -3).reshape(*sh, 8, self.HB * 4)
        p = torch.einsum("kmn,...kn->...km", self.MB, rb)
        return (p * p).sum(-1)

    def prediction(self, lin):
        cov = (self.BASE + lin).clamp(0, 1) ** self.G
        r = self.T2 - self.L * cov
        rb = r.reshape(self.HB, 8, 4).movedim(-2, -3).reshape(8, self.HB * 4)
        p = torch.einsum("kmn,kn->km", self.MB, rb).reshape(8, self.HB, 4).movedim(0, 1).reshape(self.HB, 32)
        return self.T2 - p

    # --- glyph tiles: every glyph at every integer canvas pen x pushed through the resize matrices once
    def tiles_for(self, P2, yb, chars):
        f = ImageFont.truetype(self.fpath, P2); asc, desc = f.getmetrics()
        MARG = 4 * P2 + 8
        WYp = torch.nn.functional.pad(self.WY[self.B0:self.B1], (MARG, MARG)); WXp = torch.nn.functional.pad(self.WX, (MARG, MARG))
        tl = torch.zeros((len(chars) + 1, self.CANVAS + 2 * MARG, self.HB, 32), device=self.dev)
        adv = {}
        for i, c in enumerate(chars):
            a_ = f.getlength(c); adv[c] = round(a_) if self.ROUND else a_
            if c == " ": continue
            im = Image.new("L", (4 * P2 + 8, asc + desc + 8), 0); ImageDraw.Draw(im).text((P2, asc + 4), c, 255, font=f, anchor="ls")
            g = np.asarray(im, np.float32) / 255.0
            rows = np.nonzero(g.sum(1) > 0)[0]; cols = np.nonzero(g.sum(0) > 0)[0]
            if len(rows) == 0: continue
            g = g[rows.min():rows.max() + 1, cols.min():cols.max() + 1]; dy = int(rows.min()) - (asc + 4); dx = int(cols.min()) - P2
            hg, wg = g.shape
            A = WYp[:, yb + dy + MARG: yb + dy + MARG + hg] @ torch.tensor(g, device=self.dev)
            U = WXp.unfold(1, wg, 1)
            st = torch.arange(self.CANVAS, device=self.dev) + dx + MARG
            ok = (st >= 0) & (st < U.shape[1])
            tl[i, :self.CANVAS][ok] = torch.einsum("rw,cnw->nrc", A, U[:, st[ok]])
        return tl, adv

    def encode(self, words, chars, adv):
        ci = {c: i for i, c in enumerate(chars)}; Lm = max(len(w) for w in words)
        idx = np.full((len(words), Lm), len(chars), np.int64); off = np.zeros((len(words), Lm), np.int64); wadv = np.zeros(len(words), np.int64)
        for k, w in enumerate(words):
            x = 0.0
            for j, c in enumerate(w):
                idx[k, j] = ci[c]; off[k, j] = int(round(x)); x += adv[c] + self.TR
            wadv[k] = int(round(x))
        t = lambda a: torch.tensor(a, device=self.dev)
        return t(idx), t(off), t(wadv)

    @staticmethod
    def place(tl, idx, off, xs):
        out = 0
        for j in range(idx.shape[1]):
            out = out + tl[idx[:, j][:, None], (xs[None, :] + off[:, j][:, None]).clamp(0, tl.shape[1] - 1)]
        return out

    # --- exact (whole-string) rendering
    def lin_text(self, text, P2, esp, x, yb, fpath=None):
        im, base_row, penx, _ = render_text(fpath or self.fpath, text, P2, self.TR, self.KERN, self.FRAC, int(round(esp * self.kx)))
        hI, wI = im.shape; ox = x - penx; oy = yb - base_row; MARG = wI + hI + 64
        WYp = torch.nn.functional.pad(self.WY[self.B0:self.B1], (MARG, MARG)); WXp = torch.nn.functional.pad(self.WX, (MARG, MARG))
        return WYp[:, oy + MARG: oy + MARG + hI] @ torch.tensor(im, device=self.dev) @ WXp[:, ox + MARG: ox + MARG + wI].T

    def exact_score(self, text, P2, esp, x, yb):
        return float(self.sse_blocks(self.lin_text(text, P2, esp, x, yb)).sum())

    def exact_refine(self, text, cfg):
        P2, esp, x, yb = cfg
        multi = " " in text
        best = (self.exact_score(text, P2, esp, x, yb), cfg) if (not multi or self.esp_ok(P2, esp)) else (float("inf"), cfg)
        for dxx, dyy in itertools.product((-2, -1, 0, 1, 2), (-1, 0, 1)):
            for e2 in self.ESPS:
                if multi and not self.esp_ok(P2, e2): continue
                v = self.exact_score(text, P2, e2, x + dxx, yb + dyy)
                if v < best[0]: best = (v, (P2, e2, x + dxx, yb + dyy))
        return best

    # --- word-sequence search (K-best dynamic programme, additive approximation, exact re-render afterwards)
    def run_dp(self, words, P2S, K=48, log=None, first=None):
        """first: optional list of allowed FIRST words (they are added to the vocabulary); the rest of the line is free."""
        if first: words = list(dict.fromkeys(list(words) + list(first)))
        chars = sorted(set("".join(words)) | {" "})
        found = {}; cfg_best = []
        for P2 in P2S:
            for yb in self.YBS:
                tl, adv = self.tiles_for(P2, yb, chars)
                idx, off, wadv = self.encode(words, chars, adv)
                V = len(words); nx = len(self.XS)
                DT = torch.empty((V, nx), device=self.dev)
                for s in range(0, V, 1500):
                    sl = slice(s, min(V, s + 1500))
                    DT[sl] = self.sse_blocks(self.place(tl, idx[sl], off[sl], self.XS)).sum(-1) - self.STONE
                for esp in self.ESPS:
                    step = int(round(adv[" "] + self.TR + esp * self.kx))
                    if step < self.MIN_STEP: continue
                    PADN = nx + int(wadv.max()) + step + 2
                    Fs = torch.full((PADN, K), float("inf"), device=self.dev); Fs[:, 0] = 0.0
                    Fw = torch.full((PADN, K), -1, device=self.dev, dtype=torch.long)
                    Fn = torch.zeros((PADN, K), device=self.dev, dtype=torch.long); Fr = torch.zeros((PADN, K), device=self.dev, dtype=torch.long)
                    for i in range(nx - 1, -1, -1):
                        nxt = i + wadv + step
                        cand = DT[:, i][:, None] + Fs[nxt]
                        flat = torch.cat([cand.reshape(-1), torch.zeros(1, device=self.dev)])
                        v, j = torch.topk(-flat, K); v = -v
                        stop = j == V * K
                        w = torch.where(stop, torch.full_like(j, -1), j // K); rk = torch.where(stop, torch.zeros_like(j), j % K)
                        Fs[i] = v; Fw[i] = w; Fn[i] = torch.where(stop, torch.zeros_like(j), nxt[w.clamp_min(0)]); Fr[i] = rk
                    Fs_c, Fw_c, Fn_c, Fr_c = Fs.cpu().numpy(), Fw.cpu().numpy(), Fn.cpu().numpy(), Fr.cpu().numpy()
                    if first:
                        fi = torch.tensor([words.index(w) for w in first], device=self.dev)
                        tot = DT[fi][:, :, None] + Fs[(torch.arange(nx, device=self.dev)[None, :] + wadv[fi][:, None] + step)]   # (A, nx, K)
                        flat = tot.reshape(-1); v, j = torch.topk(-flat, min(K * 12, flat.numel()))
                        for vv, jj in zip((-v).tolist(), j.tolist()):
                            a_, rem = divmod(jj, nx * K); i, r = divmod(rem, K)
                            seq = [first[a_]]; ii = i + int(wadv[fi[a_]]) + step; rr = r
                            while ii < nx and Fw_c[ii, rr] >= 0:
                                seq.append(words[Fw_c[ii, rr]]); ii, rr = Fn_c[ii, rr], Fr_c[ii, rr]
                            ph = " ".join(seq); tot_ = self.STONE + vv
                            if ph not in found or tot_ < found[ph][0]:
                                found[ph] = (tot_, (P2, esp, int(self.XS[i]), yb))
                        cfg_best.append((self.STONE + float(-v[0]), P2, yb, esp))
                        continue
                    ent = sorted((Fs_c[i, r], i, r) for i in range(nx) for r in range(K) if Fw_c[i, r] >= 0)
                    for sc, i, r in ent[:K * 6]:
                        seq = []; ii, rr = i, r
                        while ii < nx and Fw_c[ii, rr] >= 0:
                            seq.append(words[Fw_c[ii, rr]]); ii, rr = Fn_c[ii, rr], Fr_c[ii, rr]
                        ph = " ".join(seq); tot = self.STONE + float(sc)
                        if ph not in found or tot < found[ph][0]:
                            found[ph] = (tot, (P2, esp, int(self.XS[i]), yb))
                    cfg_best.append((self.STONE + float(Fs_c[:nx][Fw_c[:nx] >= 0].min()), P2, yb, esp))
            if log: log("  P2 %d done: %d phrases, best config so far %s" % (P2, len(found), min(cfg_best)))
        return found, sorted(cfg_best)

    def run_combo(self, phrases, P2S, log=None):
        """Additive scoring of phrase lists from per-word tables (fast for millions of phrases)."""
        toks = [p.split(" ") for p in phrases]
        vocab = sorted({w for t in toks for w in t}); vi = {w: i for i, w in enumerate(vocab)}
        chars = sorted(set("".join(vocab)) | {" "})
        nW = max(len(t) for t in toks)
        TI = torch.tensor([[vi[w] for w in t] + [-1] * (nW - len(t)) for t in toks], device=self.dev)
        found_v = torch.full((len(phrases),), float("inf"), device=self.dev)
        found_c = torch.zeros((len(phrases), 4), device=self.dev, dtype=torch.long)
        nx = len(self.XS)
        for P2 in P2S:
            for yb in self.YBS:
                tl, adv = self.tiles_for(P2, yb, chars)
                idx, off, wadv = self.encode(vocab, chars, adv)
                DT = torch.empty((len(vocab), nx), device=self.dev)
                for s_ in range(0, len(vocab), 1500):
                    sl = slice(s_, min(len(vocab), s_ + 1500))
                    DT[sl] = self.sse_blocks(self.place(tl, idx[sl], off[sl], self.XS)).sum(-1) - self.STONE
                DTp = torch.cat([DT, torch.full((len(vocab), int(wadv.max()) * nW + 40), 1e4, device=self.dev)], 1)
                for ei, esp in enumerate(self.ESPS):
                    step = int(round(adv[" "] + self.TR + esp * self.kx))
                    if step < self.MIN_STEP and nW > 1: continue
                    for s_ in range(0, len(phrases), 200000):
                        sl = slice(s_, min(len(phrases), s_ + 200000)); ti = TI[sl]
                        pos = torch.arange(nx, device=self.dev)[None, :].expand(ti.shape[0], nx).clone()
                        tot = torch.full((ti.shape[0], nx), self.STONE, device=self.dev)
                        for j in range(nW):
                            w = ti[:, j]; valid = (w >= 0)[:, None]; wc = w.clamp_min(0)
                            tot = tot + torch.where(valid, DTp[wc[:, None], pos], torch.zeros_like(tot))
                            pos = pos + torch.where(valid, wadv[wc][:, None] + step, torch.zeros_like(pos))
                        m, am = tot.min(1)
                        better = m < found_v[sl]
                        found_v[sl] = torch.where(better, m, found_v[sl])
                        cfg = torch.stack([torch.full_like(am, P2), torch.full_like(am, ei), self.XS[am], torch.full_like(am, yb)], 1)
                        found_c[sl] = torch.where(better[:, None], cfg, found_c[sl])
            if log: log("  P2 %d done" % P2)
        fv, fc = found_v.cpu().tolist(), found_c.cpu().tolist()
        return {p: (v, (c[0], self.ESPS[c[1]], c[2], c[3])) for p, v, c in zip(phrases, fv, fc)}

    def rerank(self, found, topn):
        approx = sorted(found.items(), key=lambda kv: kv[1][0])
        ex = []
        for ph, (v, cfg) in approx[:topn]:
            e, c2 = self.exact_refine(ph, cfg)
            ex.append(dict(phrase=ph, sse=e, approx=v, P2=c2[0], esp=c2[1], x=c2[2], yb=c2[3]))
        ex.sort(key=lambda r: r["sse"])
        return ex
