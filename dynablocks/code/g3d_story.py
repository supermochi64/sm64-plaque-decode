"""Story figure: original 2004 thumbnail | Roblox's 2026 AI upscale (dynablocks.com replica, Wayback capture) | what the
pixels actually say (our decode in the engine font).  One figure per screenshot + a stacked version.
    uv run python g3d_story.py IMGDIR AIDIR FNT calib.json bg2.png OUTDIR
"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.argv = [sys.argv[0], sys.argv[1], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6]] + sys.argv[2:3]   # reuse g3d_compare args
import g3d_compare as GC

imgs, fnt, cj, bg2, out, aidir = sys.argv[1:7]
FB, FR = os.environ.get("LABEL_FONT_BOLD", "/usr/share/fonts/noto/NotoSans-Bold.ttf"), os.environ.get("LABEL_FONT", "/usr/share/fonts/noto/NotoSans-Regular.ttf")
fT, fS, fH = ImageFont.truetype(FB, 30), ImageFont.truetype(FR, 21), ImageFont.truetype(FB, 40)
PH = 520; PW = int(PH * 806 / 632)
BG, FG, RED, GRN = (14, 15, 20), (235, 236, 240), (240, 90, 80), (90, 220, 120)


def panel(img):
    return img.convert("RGB").resize((PW, PH), Image.BICUBIC)


rows = []
for n, S in GC.SHOTS.items():
    orig = Image.open("%s/%d.png" % (imgs, n)).resize((PW, PH), Image.NEAREST)
    ai = panel(Image.open("%s/%d.jpg" % (aidir, n)))
    rd = GC.readable(n, S).resize((PW, PH), Image.LANCZOS)
    W = 3 * PW + 4 * 30; H = PH + 110
    im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
    for i, (p, t, c) in enumerate([(orig, "THE 2004 SCREENSHOT (144 × 113 px)", FG), (ai, "ROBLOX'S 2026 AI UPSCALE", RED), (rd, "WHAT THE PIXELS ACTUALLY SAY", GRN)]):
        x = 30 + i * (PW + 30); im.paste(p, (x, 60)); d.text((x, 16), t, c, font=fT)
    d.text((30, 60 + PH + 18), "Left: original thumbnail.  Middle: dynablocks.com, Sept 2026 (Wayback Machine): the AI invented the text.  "
           "Right: decoded with ROBLOX's own 2004 engine font (G3D dominant.fnt); colour = confidence.", (180, 182, 190), font=fS)
    im.save(os.path.join(out, "story_%d.png" % n)); rows.append(im)
W = rows[0].width; H = sum(r.height for r in rows) + 90
st = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(st)
d.text((30, 22), "Roblox's oldest screenshots: the AI 'restoration' made up the text. Here is what they really say.", FG, font=fH)
y = 90
for r in rows: st.paste(r, (0, y)); y += r.height
st.save(os.path.join(out, "story_both.png")); print("saved", out)
