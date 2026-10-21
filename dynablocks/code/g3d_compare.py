"""Whole-image comparison: original thumbnail | recreation (every text area = background + our decoded text through the
fitted engine process; undecoded text left blank on purpose) | readable full-size screen (our readings drawn in the
engine font, colour = confidence).
    uv run python g3d_compare.py IMGDIR FNT calib.json bg2.png OUTDIR
"""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import g3d_text as G, g3d_font as GF

imgs, fnt, cj, bg2, out = sys.argv[1:6]
gf = GF.Font(fnt); C = json.load(open(cj)); K = np.array(C["coef"]); BW, MODE = C["bw"], C["mode"]
SURE, LIKELY, SHAPE = (90, 220, 120), (255, 200, 60), (170, 170, 180)
T1 = (13.25, 28.75, 23.8)
BTN = [("Run", 753.5, 86.5, SURE), ("Move", 751, 141, SURE), ("Delete", 751.5, 195.5, SURE)]
SHOTS = {
    1: dict(bg=imgs + "/3.png", items=[("Level 1: Build a bridge that doesn't break", T1[0], T1[1], T1[2], None, SURE)]
            + [(t, cx, y, 16, "c", c) for t, cx, y, c in BTN] + [("---", 752, 251, 16, "c", LIKELY)]
            + [("100 average fps", 9.25, 68.5, 16, None, LIKELY), ("29 physics fps", 10.75, 89.5, 16, None, SHAPE),
               ("64.702 SIM  467.701 msec", 13.25, 112.45, 16, None, SHAPE), ("-67.474 ERR  73.889 msec", 13.25, 136.45, 16, None, SHAPE)]
            + [("Join Block", 754, 304.7, 16, "c", LIKELY), ("( 21 )", 737.2, 325.2, 16, None, SURE),
               ("Create Block", 754, 357.7, 16, "c", LIKELY), ("( 33 )", 735.8, 378.2, 16, None, SHAPE),
               ("Shop open", 10, 563, 16, None, SHAPE), ("Cost: 18.86", 11, 589, 16, None, SHAPE)],
            wins=[(6, 13, 0, 84), (13, 29, 0, 40), (14, 53, 124, 143), (53, 73, 124, 143), (100, 111, 0, 24)],
            keep=[(53, 56, 124, 143), (53, 64, 124, 128), (53, 64, 140, 143), (62, 65, 124, 143)]),
    2: dict(bg=bg2, items=[("Level 4: Big Wheels", T1[0], T1[1], T1[2], None, LIKELY)]
            + [("100 average fps", 9.25, 68.5, 16, None, LIKELY), ("99 physics fps", 7.75, 89.5, 16, None, SHAPE),
               ("52.440 SIM  629.599 msec", 13.25, 112.45, 16, None, SHAPE), ("-787.440 ERR  71.939 msec", 13.25, 136.45, 16, None, SHAPE)]
            + [("Join Block", 754, 304.7, 16, "c", LIKELY), ("( 10 )", 736.9, 326.7, 16, None, SHAPE),
               ("Create Block", 754, 357.7, 16, "c", LIKELY), ("( 34 )", 735.0, 381.2, 16, None, SHAPE),
               ("Big Block", 754, 410.7, 16, "c", SHAPE), ("( 40 )", 736.1, 434.2, 16, None, SHAPE),
               ("Heavy Block", 754, 463.7, 16, "c", SHAPE), ("( 14 )", 736.5, 488.7, 16, None, SHAPE),
               ("Ball", 754, 516.7, 16, "c", SHAPE), ("( 36 )", 735.8, 541.7, 16, None, SHAPE),
               ("Beam", 754, 569.7, 16, "c", SHAPE), ("( 22 )", 737.2, 588.7, 16, None, SHAPE),
               ("Shop open", 10, 563, 16, None, SHAPE), ("Cost: 133.98", 11, 589, 16, None, SHAPE)],
            wins=[(6, 13, 0, 45), (13, 29, 0, 40), (52, 111, 121, 143), (100, 111, 0, 24)],
            keep=[(92, 94, 121, 143), (92, 103, 121, 127), (92, 103, 140, 143), (101, 103, 121, 143)]),
}
BUTTONS2 = [(t, cx, y, 16, "c", c) for t, cx, y, c in BTN]           # drawn in the readable panel only (bg unknown there)


def pen(it):
    t, x, y, s, al, _ = it
    return (x - gf.width(t, s) / 2 if al == "c" else x), y


def recreate(n, S):
    M = G.Model("%s/%d.png" % (imgs, n), S["bg"], fnt); R = M.T.copy()
    for W in S["wins"]:
        r0, r1, c0, c1 = W; fs = []
        for it in S["items"]:
            x, y = pen(it); fs.append(M.feats_g3d(it[0], x, y, it[3], W, gf, BW, MODE))
        _, _, pred = M.solve(fs, W, K); R[r0:r1, c0:c1] = pred
    for r0, r1, c0, c1 in S["keep"]: R[r0:r1, c0:c1] = M.T[r0:r1, c0:c1]          # the purple selection box
    return M.T, R


def readable(n, S):
    """full-size screen: the original thumbnail enlarged (blurred) + our text drawn crisp in the engine font."""
    base = Image.open("%s/%d.png" % (imgs, n)).convert("RGB").resize((806, 632), Image.BICUBIC)
    A = np.asarray(base).astype(np.float32) * 0.55 + 40
    items = S["items"] + (BUTTONS2 if n == 2 else [])
    for it in items:
        x, y = pen(it); t, s, col = it[0], it[3], it[5]
        a, ass = GF.render(gf, t, x, y, s, 806, 632, 0, 0); b = GF.border(ass, BW, MODE) * (1 - a)
        A = A * (1 - b[..., None]) + 0 * b[..., None]
        A = A * (1 - a[..., None]) + np.array(col, np.float32) * a[..., None]
    return Image.fromarray(np.clip(A, 0, 255).astype(np.uint8))


if __name__ == "__main__":
    os.makedirs(out, exist_ok=True)
    fT = ImageFont.truetype(os.environ.get("LABEL_FONT_BOLD", "/usr/share/fonts/noto/NotoSans-Bold.ttf"), 30); fS = ImageFont.truetype(os.environ.get("LABEL_FONT", "/usr/share/fonts/noto/NotoSans-Regular.ttf"), 22)
    for n, S in SHOTS.items():
        T, R = recreate(n, S); z = 5
        up = lambda a: Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).resize((144 * z, 113 * z), Image.NEAREST)
        RD = readable(n, S).resize((int(806 * 565 / 632), 565), Image.LANCZOS)
        W = 720 * 2 + RD.width + 4 * 30; H = 565 + 200
        im = Image.new("RGB", (W, H), (14, 15, 20)); d = ImageDraw.Draw(im)
        for i, (p, t) in enumerate([(up(T), "ORIGINAL (144 × 113)"), (up(R), "RECREATION (our text, same process)"), (RD, "WHAT IT SAYS (our reading)")]):
            x = 30 + i * (720 + 30); im.paste(p, (x, 60)); d.text((x, 18), t, (235, 236, 240), font=fT)
        x = 30 + 2 * 750; y = 60 + 565 + 22
        for col, lab in ((SURE, "sure"), (LIKELY, "likely"), (SHAPE, "best fit (words/digits not certain)")):
            d.rectangle((x, y + 6, x + 22, y + 28), fill=col); d.text((x + 32, y), lab, (220, 220, 225), font=fS); y += 34
        d.text((30, 60 + 565 + 22), "Recreation: every text area is redrawn from our best-fit text through the same engine font, outline and shrink.",
               (190, 190, 198), font=fS)
        im.save(os.path.join(out, "compare_%d.png" % n)); print("saved", os.path.join(out, "compare_%d.png" % n))
