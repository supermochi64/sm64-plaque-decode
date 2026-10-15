"""Super Mario 64's own dialog font (US), for testing the popular claim that the plaque uses the in-game font.

Glyphs are extracted from YOUR OWN US ROM at run time (segment 2, 16x8 IA4, stored rotated; upright = transpose+flip),
advances are the game's gDialogCharWidths; offsets come from the public decompilation.  Nothing is redistributed.
The renderer mimics a designer who typed the line in the game font and scaled it up as pixel art (nearest) or with
Photoshop's default (bicubic) interpolation, before the same canvas -> 32x32 process as every other font."""
import numpy as np
from PIL import Image
from .rom import to_z64, mio0

SEGMENT2_US = 1083968
GLYPHS = {
    '0': (0x05900, 7),
    '1': (0x05940, 7),
    '2': (0x05980, 7),
    '3': (0x059c0, 7),
    '4': (0x05a00, 7),
    '5': (0x05a40, 7),
    '6': (0x05a80, 7),
    '7': (0x05ac0, 7),
    '8': (0x05b00, 7),
    '9': (0x05b40, 7),
    'A': (0x05b80, 6),
    'B': (0x05bc0, 6),
    'C': (0x05c00, 6),
    'D': (0x05c40, 6),
    'E': (0x05c80, 6),
    'F': (0x05cc0, 6),
    'G': (0x05d00, 6),
    'H': (0x05d40, 6),
    'I': (0x05d80, 5),
    'J': (0x05dc0, 6),
    'K': (0x05e00, 6),
    'L': (0x05e40, 5),
    'M': (0x05e80, 8),
    'N': (0x05ec0, 8),
    'O': (0x05f00, 6),
    'P': (0x05f40, 6),
    'Q': (0x05f80, 6),
    'R': (0x05fc0, 6),
    'S': (0x06000, 6),
    'T': (0x06040, 5),
    'U': (0x06080, 6),
    'V': (0x060c0, 6),
    'W': (0x06100, 8),
    'X': (0x06140, 7),
    'Y': (0x06180, 6),
    'Z': (0x061c0, 6),
    'a': (0x06200, 6),
    'b': (0x06240, 5),
    'c': (0x06280, 5),
    'd': (0x062c0, 6),
    'e': (0x06300, 5),
    'f': (0x06340, 5),
    'g': (0x06380, 6),
    'h': (0x063c0, 5),
    'i': (0x06400, 4),
    'j': (0x06440, 5),
    'k': (0x06480, 5),
    'l': (0x064c0, 3),
    'm': (0x06500, 7),
    'n': (0x06540, 5),
    'o': (0x06580, 5),
    'p': (0x065c0, 5),
    'q': (0x06600, 6),
    'r': (0x06640, 5),
    's': (0x06680, 5),
    't': (0x066c0, 5),
    'u': (0x06700, 5),
    'v': (0x06740, 5),
    'w': (0x06780, 7),
    'x': (0x067c0, 7),
    'y': (0x06800, 5),
    'z': (0x06840, 5),
    "'": (0x06b80, 4),
    '.': (0x06a80, 4),
    ',': (0x06b40, 4),
    '!': (0x068c0, 5),
    '?': (0x06bc0, 7),
    '~': (0x06a40, 8),
    '&': (0x06d80, 8),
    '★': (0x06c00, 10),
    '☆': (0x06c40, 10),
}
SPACE_ADV = 5
NAME = "SM64-dialog"


def extract(rom_path):
    if str(rom_path).lower().endswith(".zip"):
        import zipfile
        z = zipfile.ZipFile(rom_path); d = z.read(z.namelist()[0])
    else:
        d = open(rom_path, "rb").read()
    d = to_z64(d)
    seg = mio0(d, SEGMENT2_US) if d[SEGMENT2_US:SEGMENT2_US + 4] == b"MIO0" else d[SEGMENT2_US:]
    out = {}
    for c, (off, adv) in GLYPHS.items():
        raw = np.frombuffer(seg[off:off + 64], np.uint8)
        nib = np.stack([raw >> 4, raw & 15], 1).reshape(-1)              # IA4: 3-bit intensity + 1-bit alpha
        img = ((nib >> 1) / 7.0 * (nib & 1)).reshape(8, 16)             # stored 16 wide x 8 high (rotated)
        out[c] = Image.fromarray((img * 255).astype(np.uint8)).transpose(Image.TRANSVERSE)
    return {c: np.asarray(im, np.float32) / 255.0 for c, im in out.items()}


def save(rom_path, path):
    G = extract(rom_path)
    np.savez_compressed(path, chars=np.array(list(G)), glyphs=np.stack([G[c] for c in G]),
                        adv=np.array([GLYPHS[c][1] for c in G]))


def load(path):
    Z = np.load(path)
    return {str(c): g for c, g in zip(Z["chars"], Z["glyphs"])}, {str(c): int(a) for c, a in zip(Z["chars"], Z["adv"])}


def render(font, text, scale, TR, interp, ESP=0):
    """Line typed in the dialog font, each glyph scaled by `scale` (nearest = pixel art, bicubic = Photoshop default),
    pen advances = round(game width * scale) + TR.  Same return signature as core.render_text."""
    G, A = font
    P = int(round(16 * scale)); x = P; xs = []
    for c in text:
        xs.append(x); x += (round((A.get(c, SPACE_ADV)) * scale) if c != " " else round(SPACE_ADV * scale) + ESP) + TR
    W = x + 2 * P; H = int(round(16 * scale)) + 8
    im = np.zeros((H, W), np.float32)
    rs = Image.NEAREST if interp == "nearest" else Image.BICUBIC
    for c, xx in zip(text, xs):
        if c == " ": continue
        if c not in G: raise KeyError(c)
        g = np.asarray(Image.fromarray((G[c] * 255).astype(np.uint8)).resize((max(1, round(8 * scale)), max(1, round(16 * scale))), rs),
                       np.float32) / 255.0
        h, w = g.shape
        im[4:4 + h, xx:xx + w] = np.maximum(im[4:4 + h, xx:xx + w], g)
    rows = np.nonzero(im.sum(1) > 0)[0]; cols = np.nonzero(im.sum(0) > 0)[0]
    return im, 4 + int(round(13 * scale)), P, (rows.min(), rows.max(), cols.min(), cols.max())
