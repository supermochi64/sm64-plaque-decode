"""G3D GFont renderer from the engine's own .fnt files (dominant.fnt / dominant-small.fnt, G3D data10/common/font,
free to use).  Reproduces GFont::appendToPackedArray layout: h = 1.5 * size, w = h * charWidth / charHeight, glyph quad
left edge = pen x - (charWidth - subWidth[c]) * propW / 2, pen += propW * subWidth[c] (spaces only advance).
Sampling: bilinear from the alpha texture, SS x SS supersampled per screen pixel (stands in for mipmapping).
Border (outline): max of the glyph alpha shifted by `bw` screen px in 4 directions (cross, as the G3D shader) or 4
diagonals / 8 neighbours (older draw-the-string-at-offsets variants).
    render(font, text, x, y, size, W, H, x0, y0) -> (font alpha, border alpha) on the crop [y0:y0+H, x0:x0+W]
"""
import struct, zlib
import numpy as np


class Font:
    def __init__(self, path):
        b = open(path, "rb").read(); d = zlib.decompress(b[4:])
        ver = struct.unpack("<i", d[:4])[0]
        if ver == 1: cs, off = 128, 4
        else: cs, off = struct.unpack("<i", d[4:8])[0], 8
        self.sub = np.array(struct.unpack("<%dH" % cs, d[off:off + 2 * cs]), float); off += 2 * cs
        self.baseline, tw = struct.unpack("<HH", d[off:off + 4]); off += 4
        self.cw = self.ch = tw // 16; self.cs = cs
        n = len(d) - off; H = n // tw
        self.tex = np.frombuffer(d[off:off + tw * H], np.uint8).reshape(H, tw).astype(np.float32) / 255.0

    def cell(self, c):
        r, q = divmod(c, 16); return self.tex[r * self.ch:(r + 1) * self.ch, q * self.cw:(q + 1) * self.cw]

    def width(self, text, size, ax=1.0, track=0.0):
        h = 1.5 * size; pw = h * self.cw / self.ch / self.cw * ax
        return sum(pw * self.sub[ord(ch) & (self.cs - 1)] + track for ch in text)


def _bilinear(img, u, v):
    H, W = img.shape; u = np.clip(u - 0.5, 0, W - 1); v = np.clip(v - 0.5, 0, H - 1)
    u0 = np.floor(u).astype(int); v0 = np.floor(v).astype(int); u1 = np.minimum(u0 + 1, W - 1); v1 = np.minimum(v0 + 1, H - 1)
    fu, fv = u - u0, v - v0
    return (img[v0, u0] * (1 - fu) * (1 - fv) + img[v0, u1] * fu * (1 - fv) + img[v1, u0] * (1 - fu) * fv + img[v1, u1] * fu * fv)


def render(font, text, x, y, size, W, H, x0, y0, SS=4, trim=True, ax=1.0, track=0.0):
    """font alpha on the crop (H, W) whose top-left is canvas (x0, y0); (x, y) = pen top-left as in draw2D (YALIGN_TOP)."""
    A = np.zeros((H * SS, W * SS), np.float32)
    h = 1.5 * size; w = h * font.cw / font.ch * ax; pw = w / font.cw; pen = float(x)
    sy = h / font.ch if trim else 0.0                       # G3D shrinks the quad by 1 texel top/bottom (trim)
    for ch in text:
        c = ord(ch) & (font.cs - 1)
        if ch != " ":
            qx = pen - (font.cw - font.sub[c]) * pw * 0.5; qy0, qy1 = y + sy, y + h - sy
            ty0, ty1 = (1, font.ch - 2) if trim else (0, font.ch)
            px0 = max(0, int(np.floor((qx - x0) * SS))); px1 = min(W * SS, int(np.ceil((qx + w - x0) * SS)))
            py0 = max(0, int(np.floor((qy0 - y0) * SS))); py1 = min(H * SS, int(np.ceil((qy1 - y0) * SS)))
            if px1 > px0 and py1 > py0:
                cx = (np.arange(px0, px1) + 0.5) / SS + x0; cy = (np.arange(py0, py1) + 0.5) / SS + y0
                u = (cx - qx) / w * (font.cw - 1); v = ty0 + (cy - qy0) / (qy1 - qy0) * (ty1 - ty0)
                inside = ((cx >= qx) & (cx < qx + w))[None, :] & ((cy >= qy0) & (cy < qy1))[:, None]
                g = _bilinear(font.cell(c), u[None, :].repeat(len(v), 0), v[:, None].repeat(len(u), 1)) * inside
                A[py0:py1, px0:px1] = np.maximum(A[py0:py1, px0:px1], g)
        pen += pw * font.sub[c] + track
    return A.reshape(H, SS, W, SS).mean((1, 3)), A


def border(Ass, bw, mode, SS=4):
    """border alpha from the supersampled font alpha: shifts of bw screen px."""
    s = int(round(bw * SS)); B = np.zeros_like(Ass)
    offs = {"cross": [(s, 0), (-s, 0), (0, s), (0, -s)], "diag": [(s, s), (s, -s), (-s, s), (-s, -s)],
            "ring": [(dx, dy) for dx in (-s, 0, s) for dy in (-s, 0, s) if dx or dy]}[mode]
    for dx, dy in offs: B = np.maximum(B, np.roll(np.roll(Ass, dy, 0), dx, 1))
    H, W = Ass.shape[0] // SS, Ass.shape[1] // SS
    return B.reshape(H, SS, W, SS).mean((1, 3))
