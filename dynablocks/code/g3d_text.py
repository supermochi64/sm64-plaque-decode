"""Forward model of the two 144x113 DynaBlocks (early ROBLOX) screenshots.  Canvas 806x632 (Windows XP window, 800x600
client) = background (the rebuilt sky layer for screenshot 1, an estimate for screenshot 2) + HUD text; shrunk to 144x113
with PIL Lanczos over the source box BOX (fitted on the sky).  feats_g3d() renders text with the engine's own GFont
(g3d_font.py) and returns linear features (text alpha, outline ring, both times the background); solve() combines them
with fixed style coefficients (results/calib.json) and returns the mismatch over a thumbnail window.
The TrueType helpers (canvas, mask, linfit) are the first, superseded model and are kept for reference.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont

BOX = (-1.25, -3.0, 806.9, 631.9); TW, TH = 144, 113; PAD = 16
SX, SY = (BOX[2] - BOX[0]) / TW, (BOX[3] - BOX[1]) / TH


class Model:
    def __init__(self, thumb_png, sky_png, font_path):
        self.T = np.asarray(Image.open(thumb_png).convert("RGB")).astype(np.float32)
        self.sky = np.asarray(Image.open(sky_png).convert("RGB")).astype(np.float32)
        self.font_path = font_path; self._f = {}; self._g = {}; self._s0 = {}; self.stroke = 0; self.weight = np.ones(self.T.shape[:2], np.float32)

    def set_mask(self, rects):
        """zero weight for thumb rects (r0, r1, c0, c1), e.g. the purple selection box."""
        for r0, r1, c0, c1 in rects: self.weight[r0:r1, c0:c1] = 0

    def font(self, size):
        if size not in self._f: self._f[size] = ImageFont.truetype(self.font_path, size)
        return self._f[size]

    def canvas(self, items, base=None):
        """items: dicts text, x, y (top-left of the text box, px), size, fill (r,g,b), shadow (dx,dy,(r,g,b),alpha) or None,
        panel ((x0,y0,x1,y1), (r,g,b), alpha) or None.  Returns the 806x632 float canvas."""
        im = Image.fromarray(np.clip(self.sky if base is None else base, 0, 255).astype(np.uint8)).convert("RGBA")
        for it in items:
            if it.get("panel"):
                (x0, y0, x1, y1), col, a = it["panel"]; ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
                ImageDraw.Draw(ov).rectangle((x0, y0, x1, y1), fill=tuple(col) + (int(a * 255),)); im = Image.alpha_composite(im, ov)
            f = self.font(it["size"])
            if it.get("shadow"):
                dx, dy, col, a = it["shadow"]; ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
                ImageDraw.Draw(ov).text((it["x"] + dx, it["y"] + dy), it["text"], fill=tuple(col) + (int(a * 255),), font=f); im = Image.alpha_composite(im, ov)
            ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
            ImageDraw.Draw(ov).text((it["x"], it["y"]), it["text"], fill=tuple(it.get("fill", (255, 255, 255))) + (255,), font=f); im = Image.alpha_composite(im, ov)
        return np.asarray(im.convert("RGB")).astype(np.float32)

    def shrink(self, can):
        P = np.pad(can, ((PAD, PAD), (PAD, PAD), (0, 0)), mode="edge")
        im = Image.fromarray(np.clip(P, 0, 255).astype(np.uint8))
        b = (BOX[0] + PAD, BOX[1] + PAD, BOX[2] + PAD, BOX[3] + PAD)
        return np.asarray(im.resize((TW, TH), Image.LANCZOS, box=b)).astype(np.float32)

    def shrink_win(self, a, win, mg=24):
        """shrink only thumb window (r0, r1, c0, c1): crop the source with a margin larger than the Lanczos support."""
        r0, r1, c0, c1 = win
        xs0, xs1 = BOX[0] + c0 * SX, BOX[0] + c1 * SX; ys0, ys1 = BOX[1] + r0 * SY, BOX[1] + r1 * SY
        X0, Y0 = int(np.floor(xs0)) - mg, int(np.floor(ys0)) - mg
        P = np.pad(a, ((PAD + mg, PAD + mg), (PAD + mg, PAD + mg)) + (((0, 0),) if a.ndim == 3 else ()), mode="edge")
        cr = P[Y0 + PAD + mg:int(np.ceil(ys1)) + mg + PAD + mg, X0 + PAD + mg:int(np.ceil(xs1)) + mg + PAD + mg]
        out = []
        for ch in ([cr] if cr.ndim == 2 else [cr[..., i] for i in range(cr.shape[2])]):
            im = Image.fromarray(ch.astype(np.float32), mode="F")
            out.append(np.asarray(im.resize((c1 - c0, r1 - r0), Image.LANCZOS, box=(xs0 - X0, ys0 - Y0, xs1 - X0, ys1 - Y0))))
        return out[0] if a.ndim == 2 else np.stack(out, -1)

    def geom(self, win, mg=24):
        """source crop (X0, Y0, X1, Y1) around a thumb window, the resize box inside it, and the sky crop (cached)."""
        key = tuple(win)
        if key not in self._g:
            r0, r1, c0, c1 = win
            xs0, xs1 = BOX[0] + c0 * SX, BOX[0] + c1 * SX; ys0, ys1 = BOX[1] + r0 * SY, BOX[1] + r1 * SY
            X0, Y0, X1, Y1 = int(np.floor(xs0)) - mg, int(np.floor(ys0)) - mg, int(np.ceil(xs1)) + mg, int(np.ceil(ys1)) + mg
            q = PAD + mg; P = np.pad(self.sky, ((q, q), (q, q), (0, 0)), mode="edge")
            self._g[key] = (X0, Y0, X1, Y1, (xs0 - X0, ys0 - Y0, xs1 - X0, ys1 - Y0), P[Y0 + q:Y1 + q, X0 + q:X1 + q])
        return self._g[key]

    def rs(self, a, win):
        X0, Y0, X1, Y1, box, _ = self.geom(win); r0, r1, c0, c1 = win
        f = lambda ch: np.asarray(Image.fromarray(np.ascontiguousarray(ch, np.float32), mode="F").resize((c1 - c0, r1 - r0), Image.LANCZOS, box=box))
        return f(a) if a.ndim == 2 else np.stack([f(a[..., i]) for i in range(a.shape[2])], -1)

    def feats(self, text, x, y, size, margin, win, panel=True):
        """per-line linear features on the thumb window: t, t*sky (3), p*sky (3), p — rendered in the window's crop only."""
        X0, Y0, X1, Y1, _, sk = self.geom(win)
        im = Image.new("L", (X1 - X0, Y1 - Y0), 0); ImageDraw.Draw(im).text((x - X0, y - Y0), text, fill=255, font=self.font(size))
        t = np.asarray(im, np.float32) / 255.0; p = np.zeros_like(t)
        if self.stroke:                                              # G3D GFont border: the text drawn at offsets around itself
            r = self.stroke; d = t.copy()
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if (dx or dy) and dx * dx + dy * dy <= r * r + 1: d = np.maximum(d, np.roll(np.roll(t, dy, 0), dx, 1))
            p = np.clip(d - t, 0, 1)                                     # the outline ring (behind the text)
        elif panel:
            bb = self.font(size).getbbox(text)
            p[max(0, int(y + bb[1] - margin) - Y0):max(0, int(y + bb[3] + margin) - Y0), max(0, int(x + bb[0] - margin) - X0):max(0, int(x + bb[2] + margin) - X0)] = 1
        return dict(t=self.rs(t, win), ts=self.rs(t[..., None] * sk, win), ps=self.rs(p[..., None] * sk, win), p=self.rs(p, win))

    def feats_g3d(self, text, x, y, size, win, gfont, bw=1.0, mode="cross", ax=1.0, track=0.0):
        """features from the engine's own GFont renderer (g3d_font): font alpha t, border ring r = B * (1 - t)."""
        import g3d_font as GF
        X0, Y0, X1, Y1, _, sk = self.geom(win)
        # render only the text's own box (+ border margin), then embed into the crop
        h = 1.5 * size; wid = gfont.width(text, size, ax, track); m = int(np.ceil(bw)) + 3
        bx0 = max(X0, int(np.floor(x - h * 0.5)) - m); bx1 = min(X1, int(np.ceil(x + wid + h * 0.5)) + m)
        by0 = max(Y0, int(np.floor(y)) - m); by1 = min(Y1, int(np.ceil(y + h)) + m)
        t = np.zeros((Y1 - Y0, X1 - X0), np.float32); r = np.zeros_like(t)
        if bx1 > bx0 and by1 > by0:
            ts, tss = GF.render(gfont, text, x, y, size, bx1 - bx0, by1 - by0, bx0, by0, ax=ax, track=track)
            t[by0 - Y0:by1 - Y0, bx0 - X0:bx1 - X0] = ts
            if bw > 0: r[by0 - Y0:by1 - Y0, bx0 - X0:bx1 - X0] = GF.border(tss, bw, mode) * (1 - ts)
        return dict(t=self.rs(t, win), ts=self.rs(t[..., None] * sk, win), ps=self.rs(r[..., None] * sk, win), p=self.rs(r, win))

    def solve(self, fs, win, coef=None, base=None):
        """sum the features of several lines, least squares per channel (or apply fixed coef). Returns mse, coef, pred."""
        r0, r1, c0, c1 = win
        if base is None:
            if tuple(win) not in self._s0: self._s0[tuple(win)] = self.rs(self.geom(win)[5], win)
            S0 = self._s0[tuple(win)]
        else: S0 = base
        F = {k: sum((f[k] for f in fs), np.zeros((r1 - r0, c1 - c0, 3) if k in ("ts", "ps") else (r1 - r0, c1 - c0), np.float32)) for k in ("t", "ts", "ps", "p")}; Y = self.T[r0:r1, c0:c1]; tot, K, pred = 0.0, [], S0.copy()
        for c in range(3):
            X = np.stack([F["t"].ravel(), F["ts"][..., c].ravel(), F["ps"][..., c].ravel(), F["p"].ravel()], 1); yv = (Y[..., c] - S0[..., c]).ravel()
            k = np.linalg.lstsq(X, yv, rcond=None)[0] if coef is None else coef[c]
            wv = self.weight[r0:r1, c0:c1].ravel(); r = yv - X @ k; tot += float((wv * r ** 2).sum() / max(wv.sum(), 1e-9)); K.append(k); pred[..., c] += (X @ k).reshape(r1 - r0, c1 - c0)
        return tot / 3, np.array(K), pred

    def mask(self, text, x, y, size):
        im = Image.new("L", (806, 632), 0); ImageDraw.Draw(im).text((x, y), text, fill=255, font=self.font(size))
        return np.asarray(im).astype(np.float32) / 255.0

    def shrink1(self, a):
        return self.shrink(np.repeat(a[..., None], 3, -1))[..., 0] if a.ndim == 2 else self.shrink(a)

    def linfit(self, lines, win, margin=2, ret=False):
        """lines: [(text, x, y, size)] sharing one style.  Thumb - shrink(sky) = sum over features, solved per channel:
        text coverage t (light ink: a_c * t), t * sky (ink replaces sky: b * t * sky), panel p * sky (darkening: d * p * sky).
        Panel = text bbox + margin.  Returns (mse, coefficients, prediction)."""
        t = np.zeros((632, 806), np.float32); p = np.zeros_like(t)
        for text, x, y, size in lines:
            t = np.maximum(t, self.mask(text, x, y, size)); bb = self.font(size).getbbox(text)
            p[max(0, int(y + bb[1] - margin)):int(y + bb[3] + margin), max(0, int(x + bb[0] - margin)):int(x + bb[2] + margin)] = 1
        S0 = self.shrink(self.sky); r0, r1, c0, c1 = win
        ft = self.shrink1(t); fts = self.shrink(t[..., None] * self.sky); fps = self.shrink(p[..., None] * self.sky); fp = self.shrink1(p)
        tot, coef, pred = 0.0, [], S0.copy()
        for c in range(3):
            X = np.stack([ft[r0:r1, c0:c1].ravel(), fts[r0:r1, c0:c1, c].ravel(), fps[r0:r1, c0:c1, c].ravel(), fp[r0:r1, c0:c1].ravel()], 1)
            yv = (self.T[r0:r1, c0:c1, c] - S0[r0:r1, c0:c1, c]).ravel()
            k, *_ = np.linalg.lstsq(X, yv, rcond=None); res = yv - X @ k; tot += float((res ** 2).mean()); coef.append(k)
            pred[..., c] = S0[..., c] + k[0] * ft + k[1] * fts[..., c] + k[2] * fps[..., c] + k[3] * fp
        return tot / 3, np.array(coef), pred

    def error(self, items, win, base=None):
        """mean squared error over the thumb window (r0, r1, c0, c1)."""
        r0, r1, c0, c1 = win; s = self.shrink(self.canvas(items, base))
        return float(((s[r0:r1, c0:c1] - self.T[r0:r1, c0:c1]) ** 2).mean()), s
