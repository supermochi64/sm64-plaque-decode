"""Figures for the press summary (press/README.md).  Light background, big labels, one idea per picture.
Needs the locally extracted texture + stone (see the main README) and the Adobe Palatino Bold Italic file in fonts/:
    PLAQUE_STONE=stone/stone_box.npy PLAQUE_STONE_VAR=stone/stone_box_var.npy \
    python press/make_figures.py --fonts-dir fonts --out press/images
"""
import argparse, json, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

BG, INK, GREY, GREEN, RED, BLUE = (255, 255, 255), (25, 25, 30), (110, 112, 120), (26, 150, 80), (205, 55, 55), (60, 95, 185)
FB, FR = "/usr/share/fonts/noto/NotoSans-Bold.ttf", "/usr/share/fonts/noto/NotoSans-Regular.ttf"
FSYM = "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"                                  # has the "approximately equal" sign


def font(path, size):
    try: return ImageFont.truetype(path, size)
    except OSError: return ImageFont.load_default()


def tex(a, n, lo, hi):
    return Image.fromarray((np.clip((a - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)).resize((n[0], n[1]), Image.NEAREST).convert("RGB")


def arrow(d, x, y, s, col):
    w = max(4, int(s / 7)); d.line([(x, y), (x + s, y)], fill=col, width=w); d.polygon([(x + s + 4, y), (x + s - 14, y - 14), (x + s - 14, y + 14)], fill=col)


def check(d, x, y, s, col):
    d.line([(x, y + s * 0.55), (x + s * 0.38, y + s * 0.9), (x + s, y + s * 0.1)], fill=col, width=max(3, int(s / 6)))


def cross(d, x, y, s, col):
    w = max(3, int(s / 6)); d.line([(x, y), (x + s, y + s)], fill=col, width=w); d.line([(x + s, y), (x, y + s)], fill=col, width=w)


def hero(T, model, A, stone, out):
    lo, hi = np.percentile(T, 1), np.percentile(T, 99.5)
    art = A[30:190, 37:227]; st = np.asarray(Image.fromarray(stone.astype(np.float32), mode="F").resize((190, 160), Image.BICUBIC))
    Lk = np.where(np.arange(160)[:, None] < 72, 43.17, 47.56); hr = np.clip(st + Lk * np.clip(art, 0, 1) ** 1.4, 0, 31)
    W, H, S = 1900, 820, 520; im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
    d.text((W // 2, 52), "The plaque in Super Mario 64, and what it says", INK, font=font(FB, 46), anchor="mm")
    cols = [(tex(T, (S, S), lo, hi), "1. The real plaque", "the game stores only 32 × 32 pixels"),
            (tex(model, (S, S), lo, hi), "2. My reconstruction", "a typed guess, shrunk like the game did"),
            (Image.fromarray((np.clip((hr - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)).resize((S, S), Image.BICUBIC).convert("RGB"), "3. The guess, before shrinking", "\"Eternal Star / We hope so\"")]
    for i, (img, t, sub) in enumerate(cols):
        x = 70 + i * (S + 100); im.paste(img, (x, 110)); d.text((x + S // 2, 110 + S + 45), t, INK, font=font(FB, 34), anchor="mm")
        d.text((x + S // 2, 110 + S + 92), sub, GREY, font=font(FR, 28), anchor="mm")
        if i == 0:
            d.text((x + S + 50, 110 + S // 2), "\u2248", GREY, font=font(FSYM, 64), anchor="mm")
            d.text((x + S + 50, 110 + S // 2 + 60), "almost", GREY, font=font(FR, 20), anchor="mm"); d.text((x + S + 50, 110 + S // 2 + 84), "identical", GREY, font=font(FR, 20), anchor="mm")
        if i == 1: arrow(d, x + S + 22, 110 + S // 2, 50, GREY)
    im.save(os.path.join(out, "1_answer.png"))


def full_pred(T, rec, l1, fdir, text1, text2=None, cfg2=None):
    """whole-plaque model: line 1 with its recipe; line 2 (if claimed) with its own best placement, else real pixels."""
    from plaquedecode.core import Line2
    lin = l1.coverage(rec, text1, fdir); s1, _ = l1.score(lin, rec.gamma)
    pred = T.copy(); pred[l1.R0:l1.R1] = l1.prediction(lin, rec.gamma).cpu().numpy(); s2 = None
    if text2:
        L2 = Line2(T, rec, fdir, line1_text=text1); P2, esp, x, yb = cfg2
        cov = (L2.BASE + L2.lin_text(text2, P2, esp, x, yb)).clamp(0, 1) ** L2.G
        pred[L2.B0:L2.B1] = (l1.stone[0][L2.B0:L2.B1] + L2.L * cov).cpu().numpy(); s2 = L2.exact_score(text2, P2, esp, x, yb)
    return pred, s1, s2


def typed(fpath, l1t, l2t, w=430):
    """the guess as a designer types it: two centred lines (illustration)."""
    im = Image.new("L", (900, 420), 255); d = ImageDraw.Draw(im)
    d.text((450, 150), l1t, 25, font=font(fpath, 92), anchor="mm")
    if l2t: d.text((450, 290), l2t, 25, font=font(fpath, 70), anchor="mm")
    else: d.text((450, 290), "(line 2: not part of this reading)", 150, font=font(FR, 34), anchor="mm")
    return im.convert("RGB").resize((w, int(w * 420 / 900)), Image.LANCZOS)


def method(T, rows, fdir_font, out):
    """rows: (label1, label2, pred, total, ok). The fingerprint idea on the WHOLE plaque."""
    lo, hi = np.percentile(T, 1), np.percentile(T, 99.5); S = 330
    W, H = 2000, 230 + len(rows) * (S + 110) + 40; im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
    d.text((W // 2, 50), "How it works: every text leaves its own fingerprint when it is shrunk", INK, font=font(FB, 46), anchor="mm")
    d.text((W // 2, 104), "Type a guess in a 1990 font, shrink it exactly like the game, and compare it with the whole real plaque.", GREY, font=font(FR, 31), anchor="mm")
    xs, xr = 820, 1330
    for x, lab in ((290, "1. type a guess"), (xs + S // 2, "2. shrink it like the game"), (xr + S // 2, "3. compare with the real plaque")):
        d.text((x, 178), lab, GREY, font=font(FB, 30), anchor="mm")
    real = tex(T, (S, S), lo, hi)
    for k, (t1, t2, pred, score, ok) in enumerate(rows):
        y = 220 + k * (S + 110); col = GREEN if ok else RED
        d.rectangle((25, y, W - 25, y + S + 95), outline=col, width=4)
        tp = typed(fdir_font, t1, t2); im.paste(tp, (75, y + 20 + (S - tp.height) // 2))
        arrow(d, 545, y + 20 + S // 2, 50, GREY)
        g = tex(pred, (S, S), lo, hi)
        if not t2:                                                               # unclaimed line 2: shown as the real pixels, dimmed
            a = np.asarray(g).copy(); r0, r1 = int(S * 15 / 32), int(S * 24 / 32); a[r0:r1] = (a[r0:r1] * 0.45 + 140 * 0.55).astype(np.uint8); g = Image.fromarray(a)
        im.paste(g, (xs, y + 20)); im.paste(real, (xr, y + 20))
        cy = y + 20 + S // 2; mx = (xs + S + xr) // 2
        if ok: d.text((mx, cy), "\u2248", col, font=font(FSYM, 70), anchor="mm")
        else: d.text((mx, cy), "=", col, font=font(FB, 70), anchor="mm"); d.line([(mx - 22, cy + 26), (mx + 22, cy - 26)], fill=col, width=7)
        name = "\"%s%s\"" % (t1, " / " + t2 if t2 else "")
        (check if ok else cross)(d, 75, y + S + 42, 38, col)
        d.text((130, y + S + 61), "%s %s  ·  mismatch score %s" % (name, "matches" if ok else "does not match", score), col, font=font(FB, 32), anchor="lm")
        d.text((W - 60, y + S + 61), "", GREY, font=font(FR, 24), anchor="rm")
    d.text((W // 2, H - 30), "mismatch score = how different the pixels are (lower is better); every reading gets its own best size and position. Grey band = line 2 not claimed by the rumour.", GREY, font=font(FR, 23), anchor="mm")
    im.save(os.path.join(out, "2_how_it_works.png"))


def leaderboard(fw, out):
    top = fw["top"]; voc = {w for w, _, _ in fw["top_vocab"]}
    rows = [(i + 1, w, s, w in voc) for i, (w, s, _, isv) in enumerate(top[:5])]
    nxt = next(x for x in fw["top_vocab"] if x[0] != "Eternal"); rows.append(("...", "", None, None)); rows.append((nxt[2], nxt[0], nxt[1], True))
    W, H = 1600, 900; im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
    d.text((W // 2, 50), "I tried every possible first word: %s candidates" % "{:,}".format(fw["n_scored"]), INK, font=font(FB, 42), anchor="mm")
    d.text((W // 2, 100), "real dictionary words AND made-up letter combinations, all scored the same way", GREY, font=font(FR, 28), anchor="mm")
    d.text((150, 165), "rank", GREY, font=font(FB, 26), anchor="mm"); d.text((330, 165), "first word", GREY, font=font(FB, 26), anchor="mm")
    d.text((930, 165), "mismatch score (shorter bar = better)", GREY, font=font(FB, 26), anchor="mm"); d.text((1460, 165), "a real word?", GREY, font=font(FB, 26), anchor="mm")
    x0, x1, lo, hi = 470, 1330, 700, 1450
    for k, (rank, w, s, real) in enumerate(rows):
        y = 215 + k * 92
        if s is None: d.text((W // 2, y + 25), "... 13,211 more strings, none of them a real word ...", GREY, font=font(FR, 28), anchor="mm"); continue
        big = rank == 1; col = GREEN if big else (BLUE if real else (190, 192, 200))
        d.text((150, y + 25), "#{:,}".format(rank), INK, font=font(FB, 34 if big else 30), anchor="mm")
        d.text((330, y + 25), w, INK, font=font(FB if big else FR, 36 if big else 32), anchor="mm")
        d.rectangle((x0, y + 5, x0 + int((s - lo) / (hi - lo) * (x1 - x0)), y + 45), fill=col)
        d.text((x0 + int((s - lo) / (hi - lo) * (x1 - x0)) + 12, y + 25), "{:,}".format(round(s)), INK, font=font(FR, 28), anchor="lm")
        (check if real else cross)(d, 1440, y + 7, 36, GREEN if real else (170, 172, 180))
    d.text((W // 2, H - 40), "Only misspellings of \"Eternal\" come close. The next real English word, \"Sternal\", is #13,217.", INK, font=font(FB, 28), anchor="mm")
    im.save(os.path.join(out, "3_every_first_word.png"))


def blind(b, out):
    rows = b["rows"]; W, H = 1700, 1000; im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
    d.text((W // 2, 52), "Blind test: I hid 50 secret words in the plaque. The method found all 50.", INK, font=font(FB, 42), anchor="mm")
    d.text((W // 2, 104), "Random English words, locked away before decoding, each written into the real plaque as \"<word> Star\"", GREY, font=font(FR, 28), anchor="mm")
    for i, r in enumerate(rows):
        c, rr = i % 5, i // 5; x = 70 + c * 320; y = 160 + rr * 70
        check(d, x, y + 8, 34, GREEN); d.text((x + 55, y + 26), r["word"], INK, font=font(FR, 34), anchor="lm")
    d.text((W // 2, H - 90), "In every case the hidden word was the best-fitting real word (50 of 50).", INK, font=font(FB, 30), anchor="mm")
    d.text((W // 2, H - 45), "In %d of 50 it was #1 of about 1.2 million strings; in the others only a misspelling (like \"Dnration\") scored slightly better." % b["true_word_rank1"], GREY, font=font(FR, 26), anchor="mm")
    im.save(os.path.join(out, "4_blind_test.png"))


def fonts(era, modern, out):
    best = {}
    for st in ("quick", "fontcmp", "full"):
        for r in era[st]: best[r["face"]] = min(best.get(r["face"], 1e9), r["sse"])
    rows = [("Adobe Palatino Bold Italic (1990)", best["AdobePalatino-BoldItalic.pfb"], GREEN),
            ("Apple Palatino Bold Italic (1990s)", best["MacOS9-PalatinoBoldItalic.ttf"], (120, 190, 140)),
            ("best of 4,583 modern fonts (Google Fonts)", modern["full"][0]["sse"], BLUE),
            ("best 1990s font that is not a Palatino", min(v for k, v in best.items() if "Schneidler" in k), (150, 150, 160)),
            ("Times Bold Italic (on SGI computers)", 1116.0, (150, 150, 160))]
    W, H = 1700, 760; im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
    d.text((W // 2, 50), "Which font was it? Adobe's 1990 Palatino Bold Italic fits best", INK, font=font(FB, 42), anchor="mm")
    d.text((W // 2, 100), "about 470 fonts an artist could have had in 1993-96, plus 4,583 modern fonts as a check (shorter bar = better)", GREY, font=font(FR, 27), anchor="mm")
    x0, x1, lo, hi = 720, 1540, 700, 1150
    for k, (name, s, col) in enumerate(rows):
        y = 170 + k * 100; d.text((x0 - 20, y + 25), name, INK, font=font(FB if k == 0 else FR, 30), anchor="rm")
        w = int((s - lo) / (hi - lo) * (x1 - x0)); d.rectangle((x0, y + 4, x0 + w, y + 46), fill=col)
        d.text((x0 + w + 12, y + 25), "{:,}".format(round(s)), INK, font=font(FR, 28), anchor="lm")
    d.text((W // 2, H - 45), "The exact Adobe file could be installed on the SGI workstations the game was made on (1995).", INK, font=font(FB, 28), anchor="mm")
    im.save(os.path.join(out, "5_which_font.png"))


def canvas_alpha(rec, text, fdir):
    """typed text on the recipe's artwork canvas, cropped to the part that maps onto the 32x32 texture (0..1)."""
    from plaquedecode.core import render_text
    img, _, _, (r0, r1, c0, c1) = render_text(os.path.join(fdir, rec.font), text, rec.P, rec.tracking, rec.kern, rec.frac, int(round(rec.esp * rec.kx)))
    img = img[max(0, r0 - 1):r1 + 2, max(0, c0 - 1):c1 + 2]; H, W = 32 * rec.ky + 2 * rec.offy, 32 * rec.kx + 2 * rec.offx
    cv = np.zeros((H + img.shape[0], W + img.shape[1])); X, Y = rec.X + rec.offx, rec.Y + rec.offy
    cv[Y:Y + img.shape[0], X:X + img.shape[1]] = img
    return cv[rec.offy:rec.offy + 32 * rec.ky, rec.offx:rec.offx + 32 * rec.kx]


def canvas_alpha2(rec, text, cfg, fdir):
    """line-2 text with its own placement cfg = (P2, esp, x, yb), as Line2.lin_text places it, in texture space."""
    from plaquedecode.core import render_text
    P2, esp, x, yb = cfg; im, base_row, penx, _ = render_text(os.path.join(fdir, rec.font), text, P2, rec.tracking, False, rec.frac, int(round(esp * rec.kx)))
    H, W = 32 * rec.ky + 2 * rec.offy, 32 * rec.kx + 2 * rec.offx; M_ = im.shape[0] + im.shape[1]
    cv = np.zeros((H + 2 * M_, W + 2 * M_)); oy, ox = yb - base_row + M_, x - penx + M_
    cv[oy:oy + im.shape[0], ox:ox + im.shape[1]] = im; cv = cv[M_:M_ + H, M_:M_ + W]
    return cv[rec.offy:rec.offy + 32 * rec.ky, rec.offx:rec.offx + 32 * rec.kx]


def outline(alpha, S, col, base):
    """draw the outline of alpha (any size, mapped onto the S x S texture image) onto PIL image base."""
    a = np.asarray(Image.fromarray((np.clip(alpha, 0, 1) * 255).astype(np.uint8)).resize((S, S), Image.BILINEAR)) > 110
    e = a & ~(np.roll(a, 1, 0) & np.roll(a, -1, 0) & np.roll(a, 1, 1) & np.roll(a, -1, 1))
    e = e | np.roll(e, 1, 0) | np.roll(e, 1, 1)
    arr = np.asarray(base).copy(); arr[e] = col; return Image.fromarray(arr)


def overlay(T, A, rec_l, sec, fdir, out):
    """sec = (recipe, line-2 cfg) of 'A Secret star / lie here ~' from the claims run."""
    lo, hi = np.percentile(T, 1), np.percentile(T, 99.5); S = 600
    ours = outline(A[30:190, 37:227], S, (60, 230, 110), tex(T, (S, S), lo, hi))
    lis = outline(canvas_alpha(rec_l, "L is real 2401", fdir), S, (255, 80, 80), tex(T, (S, S), lo, hi))
    rs, cfg = sec; a_s = np.maximum(canvas_alpha(rs, "A Secret star", fdir), canvas_alpha2(rs, "lie here ~", cfg, fdir))
    secret = outline(a_s, S, (255, 80, 80), tex(T, (S, S), lo, hi))
    W, H = 3 * S + 4 * 50, S + 270; im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
    d.text((W // 2, 48), "Lay the letters on the real game pixels", INK, font=font(FB, 46), anchor="mm")
    d.text((W // 2, 98), "outlines of each reading, placed where it fits best, over the UNCHANGED plaque from the game", GREY, font=font(FR, 28), anchor="mm")
    for i, (img, t, sub, col) in enumerate([(ours, "\"Eternal Star / We hope so\"", "each bright blob sits under a letter", GREEN),
                                           (lis, "\"L is real 2401\"", "only fits with its word spaces squeezed out", RED),
                                           (secret, "\"A Secret star / lie here ~\"", "letters and blobs disagree on both lines", RED)]):
        x = 50 + i * (S + 50); im.paste(img, (x, 140)); d.text((x + S // 2, 140 + S + 45), t, col, font=font(FB, 34), anchor="mm")
        d.text((x + S // 2, 140 + S + 88), sub, GREY, font=font(FR, 26), anchor="mm")
    im.save(os.path.join(out, "6_letters_on_pixels.png"))


def errors(T, rows, out):
    """rows: (label, pred, score text, colour, line2_claimed)."""
    lo, hi = np.percentile(T, 1), np.percentile(T, 99.5); S = 520
    W, H = 3 * S + 4 * 50, S + 300; im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
    d.text((W // 2, 48), "Where a reading is wrong, the plaque glows red", INK, font=font(FB, 46), anchor="mm")
    d.text((W // 2, 98), "the whole real plaque; red = how much each pixel adds to the mismatch score", GREY, font=font(FR, 28), anchor="mm")
    d.text((W // 2, 136), "no reading is perfect (the artist touched up a few pixels by hand), but the wrong ones light up far more", GREY, font=font(FR, 24), anchor="mm")
    for k, (lab, pred, sc, col, claimed2) in enumerate(rows):
        err = np.abs(T - pred); err[:5] = 0; err[25:] = 0
        g = np.asarray(tex(T, (S, S), lo, hi)).astype(float) * 0.55
        e = np.asarray(Image.fromarray((np.clip((err / 7) ** 2, 0, 1) * 255).astype(np.uint8)).resize((S, S), Image.NEAREST)).astype(float) / 255
        rgb = g.copy(); rgb[..., 0] = np.clip(g[..., 0] + 255 * e, 0, 255); rgb[..., 1] = g[..., 1] * (1 - e); rgb[..., 2] = g[..., 2] * (1 - e)
        x = 50 + k * (S + 50); y = 170; im.paste(Image.fromarray(rgb.astype(np.uint8)), (x, y))
        if not claimed2:
            dd = ImageDraw.Draw(im, "RGBA"); r0, r1 = y + int(S * 15 / 32), y + int(S * 24 / 32)
            dd.rectangle((x, r0, x + S, r1), fill=(150, 150, 160, 150)); dd.text((x + S // 2, (r0 + r1) // 2), "line 2: not claimed", (255, 255, 255), font=font(FB, 28), anchor="mm")
        d.text((x + S // 2, y + S + 45), lab, col, font=font(FB, 32), anchor="mm"); d.text((x + S // 2, y + S + 88), sc, GREY, font=font(FR, 28), anchor="mm")
    im.save(os.path.join(out, "7_where_wrong.png"))


def readings(cl, out):
    """every reading proposed since the 1990s, final model, each with its own best settings."""
    C = {c["id"]: c for c in cl["claims"]}
    l1 = [("Eternal Star", "this work / Super Mario Wiki", C["eternal"]["line1_sse"], GREEN), ("Eternal star", "same words, small \"s\"", C["ours_lc"]["line1_sse"], (120, 190, 140)),
          ("L is real star", "reader comment, 2019", C["lisrealstar"]["line1_sse"], RED), ("L is real 2401", "the 1990s Luigi rumour", C["lisreal"]["line1_sse"], RED),
          ("L is real 2041", "variant spelling", C["lisreal2041"]["line1_sse"], RED), ("A Secret star", "Nintendo Life, 2019", C["secretstar"]["line1_sse"], RED)]
    l2 = [("We hope so", "this work", C["ours"]["line2_sse_starrecipe"], GREEN), ("My hope is", "proposed reading", C["myhopeis"]["line2_sse_starrecipe"], RED),
          ("my hope is", "same, lower case", C["myhopeis_lc"]["line2_sse_starrecipe"], RED), ("lie here ~", "Nintendo Life, 2019", C["lieherestar"]["line2_sse_starrecipe"], RED)]
    W = 1800; H = 230 + (len(l1) + len(l2)) * 88 + 120; im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
    d.text((W // 2, 50), "Every reading proposed in almost 30 years, scored the same way", INK, font=font(FB, 44), anchor="mm")
    d.text((W // 2, 100), "same font, same background; every reading gets its own best size and position (shorter bar = better)", GREY, font=font(FR, 28), anchor="mm")
    x0, x1, lo, hi = 700, 1600, 0, 2200; y = 150
    for title, rows in (("LINE 1", l1), ("LINE 2", l2)):
        d.text((60, y + 10), title, GREY, font=font(FB, 30), anchor="lm"); y += 50
        for t, sub, s_, col in rows:
            d.text((x0 - 30, y + 6), "\"%s\"" % t, INK, font=font(FB, 32), anchor="rm"); d.text((x0 - 30, y + 42), sub, GREY, font=font(FR, 23), anchor="rm")
            w = int((s_ - lo) / (hi - lo) * (x1 - x0)); d.rectangle((x0, y + 4, x0 + w, y + 50), fill=col)
            d.text((x0 + w + 14, y + 27), "{:,}".format(round(s_)), INK, font=font(FB, 28), anchor="lm"); y += 88
        y += 20
    tot = C["secretstar"]["total_joint"] / (C["ours"]["total_joint"])
    d.text((W // 2, H - 50), "Whole plaque: \"A Secret star / lie here ~\" scores %s, \"Eternal Star / We hope so\" %s (%.1f times better)." % ("{:,}".format(round(C["secretstar"]["total_joint"])), "{:,}".format(round(C["ours"]["total_joint"])), tot), INK, font=font(FB, 28), anchor="mm")
    im.save(os.path.join(out, "8_all_readings.png"))


def line2(dp, out):
    rows = dp["exact"][:8]; W, H = 1500, 300 + len(rows) * 78; im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
    d.text((W // 2, 50), "Line 2: a blind search through 17,700 English words", INK, font=font(FB, 44), anchor="mm")
    d.text((W // 2, 100), "the computer was not told any words. Its 8 best answers (lower score = better):", GREY, font=font(FR, 28), anchor="mm")
    sentence = {"We hope so", "We hope as", "We hope he", "We hope us", "We hope or"}
    for k, r in enumerate(rows):
        y = 160 + k * 78; words = r["phrase"].split(); x = 330
        d.text((150, y + 22), "#%d" % (k + 1), INK, font=font(FB, 32), anchor="mm")
        for j, w in enumerate(words):
            col = GREEN if (j == 1 and w == "hope") else (INK if w in ("We",) else GREY)
            f = font(FB if (k == 0 or (j == 1 and w == "hope")) else FR, 40); d.text((x, y + 22), w, col, font=f, anchor="lm"); x += int(d.textlength(w + " ", font=f))
        d.text((900, y + 22), "%.0f" % r["sse"], GREY, font=font(FR, 30), anchor="mm")
        ok = r["phrase"] == "We hope so"; d.text((1080, y + 22), "real words" if r["phrase"] in sentence else "not real words", GREEN if ok else GREY, font=font(FB if ok else FR, 28), anchor="lm")
    d.text((W // 2, H - 95), "\"hope\" is in every single answer. The best one is \"We hope so\".", INK, font=font(FB, 32), anchor="mm")
    d.text((W // 2, H - 45), "The last word is the least certain: \"he\" and \"as\" are close behind, but only \"We hope so\" is a natural sentence.", GREY, font=font(FR, 26), anchor="mm")
    im.save(os.path.join(out, "9_line2.png"))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--fonts-dir", default="fonts"); ap.add_argument("--out", default="press/images")
    ap.add_argument("--repo", default="."); ap.add_argument("--texture", default="texture.npy"); ap.add_argument("--stone", default="stone/stone_box.npy")
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True); R = lambda p: os.path.join(a.repo, p)
    from plaquedecode.core import Line1
    from plaquedecode.__main__ import best_recipe
    T = np.load(a.texture).astype(float); z = np.load(R("results/stone_bestfit.npz"))
    hero(z["real"].astype(float), z["model"].astype(float), z["alpha"], np.load(a.stone).astype(float), a.out)
    recs = {"Eternal Star": best_recipe(R("results/stone_recipes_Adobe.json")), "L is real 2401": best_recipe(R("results/stone_recipes_Adobe_L_is_real_2401.json"))}
    from plaquedecode.core import Recipe
    l1 = Line1(T); cl = json.load(open(R("results/stone_claims_Adobe.json"))); C = {c["id"]: c for c in cl["claims"]}
    rec_s = Recipe(**C["secretstar"]["recipe"])
    p_ours, a1, a2 = full_pred(T, recs["Eternal Star"], l1, a.fonts_dir, "Eternal Star", "We hope so", C["ours"]["line2_cfg_joint"])
    p_lis, b1, _ = full_pred(T, recs["L is real 2401"], l1, a.fonts_dir, "L is real 2401")
    p_sec, c1, c2 = full_pred(T, rec_s, l1, a.fonts_dir, "A Secret star", "lie here ~", C["secretstar"]["line2_cfg_joint"])
    print("whole plaque: ours %.1f+%.1f | L is real %.1f | secret %.1f+%.1f" % (a1, a2, b1, c1, c2))
    F = lambda v: "{:,}".format(round(v))
    pf = os.path.join(a.fonts_dir, recs["Eternal Star"].font)
    method(T, [("Eternal Star", "We hope so", p_ours, "%s (line 1 %s + line 2 %s)" % (F(a1 + a2), F(a1), F(a2)), True),
               ("L is real 2401", None, p_lis, "%s on line 1 alone" % F(b1), False),
               ("A Secret star", "lie here ~", p_sec, "%s (line 1 %s + line 2 %s)" % (F(c1 + c2), F(c1), F(c2)), False)], pf, a.out)
    errors(T, [("\"Eternal Star / We hope so\"", p_ours, "mismatch %s" % F(a1 + a2), GREEN, True),
               ("\"L is real 2401\"", p_lis, "mismatch %s on line 1 alone" % F(b1), RED, False),
               ("\"A Secret star / lie here ~\"", p_sec, "mismatch %s" % F(c1 + c2), RED, True)], a.out)
    sec = C["secretstar"]
    overlay(T, z["alpha"], recs["L is real 2401"], (rec_s, sec["line2_cfg_joint"]), a.fonts_dir, a.out)
    readings(cl, a.out); line2(json.load(open(R("results/line2_dp_AdobePalatino.json"))), a.out)
    leaderboard(json.load(open(R("results/stone_firstword_Adobe.json"))), a.out)
    blind(json.load(open(R("results/blind_firstword.json"))), a.out)
    fonts(json.load(open(R("results/era_fonts_stone.json"))), json.load(open(R("results/modern_fonts_stone.json"))), a.out)


if __name__ == "__main__":
    main()
