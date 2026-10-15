"""All report figures, regenerated from results/*.json (+ the texture and fonts for the image panels)."""
import json, os, glob, re
import numpy as np
import torch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from .core import Line1, Line2, Recipe, LINE1, LINE2, CLEAN

plt.rcParams.update({"font.family": "serif", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "savefig.bbox": "tight", "savefig.dpi": 220, "axes.titlesize": 10})
OURS, OTHER, GOOD, BAD, GREY = "#1b6ca8", "#b0b0b0", "#2a9d5b", "#c0392b", "#7f7f7f"

FAMILY = [("Palatino", r"alatino|P052"), ("Times", r"Times|NimbusRoman|tim|TNR|LiberationSerif|Adobe-TIBI|Adobe-TII"), ("New Century Schoolbook", r"C059|Century|ncen|Adobe-NCBI|Adobe-NCI"),
          ("Bookman", r"Bookman|Adobe-BKDI|Adobe-BKLI"), ("Georgia", r"Georgia"), ("Helvetica / Arial", r"Helvet|NimbusSans|Arial|helv|LiberationSans"),
          ("Avant Garde", r"Gothic"), ("Zapf Chancery", r"Z003|Chancery|Adobe-ZCMI"), ("Courier", r"Mono|Courier|cour"), ("New York", r"NewYork"),
          ("SM64 dialog font", r"SM64"), ("Garamond", r"Adobe-GDBI|Adobe-GDI|Garamond"), ("Lucida (B&H)", r"bh-.*/lu"), ("Trebuchet / Verdana / Comic (MS)", r"trebuc|Verdana|Comic|Impact|Andale")]
NICE = {"PalatinoBoldItalic.ttf": "Palatino Bold Italic (Apple 1996)", "PalatinoItalic.ttf": "Palatino Italic (Apple 1996)",
        "PalatinoBold.ttf": "Palatino Bold (Apple 1996)", "Palatino.ttf": "Palatino Roman (Apple 1996)",
        "TimesBoldItalic.ttf": "Times Bold Italic (Apple 1996)", "TimesItalic.ttf": "Times Italic (Apple 1996)",
        "Times-BoldItalic.pfa": "Times Bold Italic (Adobe, IRIX 5.3)", "Helvetica-BoldOblique.pfa": "Helvetica Bold Obl. (Adobe, IRIX 5.3)",
        "NewYork.ttf": "New York (Apple 1996)", "P052-BoldItalic.otf": "Palatino Bold Italic (URW P052)",
        "P052-Italic.otf": "Palatino Italic (URW P052)", "P052-Bold.otf": "Palatino Bold (URW P052)", "P052-Roman.otf": "Palatino Roman (URW P052)",
        "NimbusRoman-BoldItalic.otf": "Times Bold Italic (URW Nimbus)", "C059-BdIta.otf": "N. C. Schoolbook Bold Italic (URW)",
        "C059-Italic.otf": "N. C. Schoolbook Italic (URW)", "URWBookman-DemiItalic.otf": "Bookman Demi Italic (URW)",
        "URWBookman-LightItalic.otf": "Bookman Light Italic (URW)", "NimbusSans-BoldItalic.otf": "Helvetica Bold Italic (URW Nimbus)",
        "URWGothic-DemiOblique.otf": "Avant Garde Demi Obl. (URW)", "Z003-MediumItalic.otf": "Zapf Chancery (URW Z003)",
        "NimbusMonoPS-BoldItalic.otf": "Courier Bold Italic (URW)", "Timesbi.TTF": "Times New Roman Bold Italic (MS 1996)",
        "Georgiaz.TTF": "Georgia Bold Italic (MS 1996)", "Georgiai.TTF": "Georgia Italic (MS 1996)",
        "SM64-dialog": "SM64 in-game dialog font (from ROM)",
        "AdobePalatino-BoldItalic.pfb": "Palatino Bold Italic (Adobe Type 1, 1990)", "AdobePalatino-Italic.pfb": "Palatino Italic (Adobe Type 1)",
        "Adobe-TIBI.pfb": "Times Bold Italic (Adobe Type 1)", "Adobe-NCBI.pfb": "N. C. Schoolbook Bold Italic (Adobe Type 1)",
        "Adobe-GDBI.pfb": "Adobe Garamond Bold Italic (Type 1)", "Adobe-ZCMI.pfb": "Zapf Chancery (Adobe Type 1)",
        "Adobe-BKDI.pfb": "Bookman Demi Italic (Adobe Type 1)",
        "URWPalladio510-BoldItalic.pfb": "URW Palladio BI (Ghostscript 5.10, 1998)", "URWPalladio60-BoldItalic.pfb": "URW Palladio BI (Ghostscript 6.0, 1999)",
        "TeXLive-PalladioL-BoldItalic.pfb": "URW Palladio L BI (TeX Live)", "TeXGyrePagella-BoldItalic.otf": "TeX Gyre Pagella BI",
        "PalatinoLinotype-BoldItalic.ttf": "Palatino Linotype BI (1998)", "URWPalladio510-Italic.pfb": "URW Palladio Italic (gs 5.10)"}


def family(name):
    for f, pat in FAMILY:
        if re.search(pat, name): return f
    return "other"


FAM_COL = dict(zip([f for f, _ in FAMILY], ["#1b6ca8", "#e67e22", "#8e44ad", "#16a085", "#c0392b", "#7f8c8d", "#2c3e50", "#8d6e63", "#95a5a6", "#bdc3c7", "#d81b60", "#cddc39", "#795548", "#00bcd4"]))


def J(res, name):
    p = os.path.join(res, name)
    return json.load(open(p)) if os.path.exists(p) else None


def grey(ax, a, lo, hi, title=None, extent=None):
    ax.imshow(a, cmap="gray", vmin=lo, vmax=hi, interpolation="nearest", extent=extent)
    ax.set_xticks([]); ax.set_yticks([])
    if title: ax.set_title(title, fontsize=8)


# --------------------------------------------------------------------------------------------- figures
def fig_texture(T, out):
    fig, axs = plt.subplots(1, 2, figsize=(7.6, 3.4)); fig.subplots_adjust(wspace=0.55)
    axs[0].imshow(T, cmap="gray", interpolation="nearest", vmin=0, vmax=31); axs[0].set_title("plaque texture, 32x32, 5-bit grey (as stored)")
    axs[1].imshow(T, cmap="gray", interpolation="nearest", vmin=6, vmax=24); axs[1].set_title("contrast-stretched (levels 6..24)")
    for ax in axs:
        ax.set_xticks(range(0, 32, 4)); ax.set_yticks(range(0, 32, 4)); ax.tick_params(labelsize=6)
        for (r0, r1), lab, col in [(LINE1, "line 1 band", "#4aa3df"), (LINE2, "line 2 band", "#f39c12"), (CLEAN, "clean stone (noise floor)", "#2ecc71")]:
            ax.add_patch(Rectangle((-0.5, r0 - 0.5), 32, r1 - r0, fill=False, ec=col, lw=1.2, ls="--"))
            ax.text(32.0, (r0 + r1) / 2 - 0.5, lab.replace(" (", "\n("), color=col, fontsize=6, va="center")
    fig.savefig(out); plt.close(fig)


def fig_fonts_rigid(res, out):
    rows = []
    for p in glob.glob(os.path.join(res, "fontcmp_recipes_*.json")):
        R = json.load(open(p))
        if R: rows.append((R[0]["sse"], R[0]["font"]))
    if not rows: return None
    rows.sort()
    fl = J(res, "fontcmp_floor.json") or {"floor": 165.7}
    fig, ax = plt.subplots(figsize=(7.2, 0.24 * len(rows) + 0.9))
    y = np.arange(len(rows))[::-1]
    ax.barh(y, [r[0] for r in rows], color=[FAM_COL.get(family(r[1]), GREY) for r in rows])
    ax.set_yticks(y); ax.set_yticklabels([NICE.get(r[1], r[1]) for r in rows], fontsize=7)
    for yy, (v, f) in zip(y, rows): ax.text(v + 8, yy, "%.0f" % v, va="center", fontsize=6.5)
    ax.axvline(fl["floor"], color=GREY, ls=":"); ax.text(fl["floor"] + 5, y[-1] - 0.9, "noise floor", fontsize=6.5, color=GREY)
    ax.set_xlabel("line-1 error (SSE) of the best designer recipe for \"Eternal Star\"  — lower is better")
    ax.set_title("Same rigid process search for every era font (identical grid)")
    fams = []
    for _, f in rows:
        if family(f) not in fams: fams.append(family(f))
    ax.legend(handles=[Rectangle((0, 0), 1, 1, color=FAM_COL.get(f, GREY)) for f in fams], labels=fams, fontsize=6.5, loc="lower right", frameon=False)
    fig.savefig(out); plt.close(fig)
    return rows


def fig_fonts_flexible(res, out):
    Z = J(res, "font_tournament_flexible.json")
    if not Z: return None
    best = {}
    for f, v in Z["refined"].items():
        fa = family(f)
        if fa not in best or v < best[fa][0]: best[fa] = (v, f)
    items = sorted(best.items(), key=lambda kv: kv[1][0])
    fig, ax = plt.subplots(figsize=(7.2, 2.8))
    x = np.arange(len(items))
    ax.bar(x, [v[0] for _, v in items], color=[FAM_COL.get(k, GREY) for k, _ in items])
    ax.set_xticks(x); ax.set_xticklabels([k for k, _ in items], rotation=35, ha="right", fontsize=7)
    for xx, (_, v) in zip(x, items): ax.text(xx, v[0] + 10, "%.0f" % v[0], ha="center", fontsize=6.5)
    ax.set_ylabel("best \"Eternal Star\" error"); ax.set_title("Era-font tournament (flexible model): best member of each family")
    fig.savefig(out); plt.close(fig)
    return items


def fig_font_panels(T, res, fdir, out, pick=None):
    """'Eternal Star' as each family's best font + best recipe would print it, next to the real line 1."""
    rows = []
    for p in glob.glob(os.path.join(res, "fontcmp_recipes_*.json")):
        R = json.load(open(p))
        if R: rows.append(Recipe(**R[0]))
    if not rows: return
    bestfam = {}
    for r in sorted(rows, key=lambda r: r.sse):
        bestfam.setdefault(family(r.font), r)
    recs = list(bestfam.values())[:9]
    l1 = Line1(T); lo, hi = np.percentile(T, 1), np.percentile(T, 99)
    fig, axs = plt.subplots(len(recs) + 1, 2, figsize=(7.0, 0.9 * (len(recs) + 1)))
    band = slice(LINE1[0] - 1, LINE1[1] + 1)
    grey(axs[0, 0], T[band], lo, hi); axs[0, 0].set_ylabel("real", rotation=0, ha="right", fontsize=7)
    axs[0, 1].axis("off"); axs[0, 1].text(0, 0.5, "real plaque, line 1 (rows %d-%d)" % (band.start, band.stop - 1), fontsize=7.5)
    for i, r in enumerate(recs, 1):
        lin = l1.coverage(r, "Eternal Star", fdir)
        pred = T.copy(); pred[LINE1[0]:LINE1[1]] = l1.prediction(lin, r.gamma).cpu().numpy()
        grey(axs[i, 0], pred[band], lo, hi)
        d = np.abs(T - pred)[band]
        axs[i, 1].imshow(d, cmap="magma", vmin=0, vmax=10, interpolation="nearest"); axs[i, 1].set_xticks([]); axs[i, 1].set_yticks([])
        axs[i, 0].set_ylabel("%s\nSSE %.0f" % (NICE.get(r.font, r.font), r.sse), rotation=0, ha="right", va="center", fontsize=6.3)
    axs[1, 1].set_title("|real - model| (0..10 levels)", fontsize=7)
    fig.savefig(out); plt.close(fig)


def fig_progression(res, out):
    P = J(res, "recipe_progression.json")
    if not P: return
    fonts = ["P052-BoldItalic.otf", "PalatinoBoldItalic.ttf"]
    fig, ax = plt.subplots(figsize=(6.4, 2.6))
    x = np.arange(len(P)); w = 0.38
    for k, f in enumerate(fonts):
        vals = [p["best"].get(f, np.nan) for p in P]
        ax.bar(x + (k - 0.5) * w, vals, w, label=NICE[f], color=[OURS, "#7fb3d5"][k])
        for xx, v in zip(x, vals):
            if v == v: ax.text(xx + (k - 0.5) * w, v + 8, "%.0f" % v, ha="center", fontsize=6.5)
    ax.set_xticks(x); ax.set_xticklabels([p["stage"].replace(", ", ",\n").replace("+ non-square", "+ non-square\n").replace("+ whole-pixel", "+ whole-pixel\n") for p in P], fontsize=7)
    ax.set_ylim(600, 960); ax.set_ylabel("line-1 SSE"); ax.legend(fontsize=7, frameon=False)
    ax.set_title("Adding designer-plausible process steps (one global setting each, no per-letter freedom)")
    fig.savefig(out); plt.close(fig)


def fig_ablation(res, out):
    A = J(res, "flexible_ablation.json")
    if not A: return
    nod = {r["font"]: r["sse"] for r in A["nodev"]}
    flex = {r["font"]: r["sse"] for r in A["grid"] if r["text"] == "Eternal Star" and not r["dy"]}
    items = [("flexible, per-letter x shifts\n(Typed P052 BI)", flex.get("Typed P052-BoldItalic @14px"), OTHER),
             ("designer recipe, rigid\n(P052 BI)", 756.9, OURS), ("designer recipe, rigid\n(Apple Palatino BI)", 759.2, OURS)]
    for f, lab in [("Typed P052-BoldItalic @14px", "Typed P052 BI"), ("Apple753 Palatino-BoldItalic", "Apple Palatino BI"), ("Apple753 Palatino-Italic", "Apple Palatino It.")]:
        if f in nod: items.append(("flexible, NO per-letter\nshifts (%s)" % lab, nod[f], GREY))
    fig, ax = plt.subplots(figsize=(7.4, 2.9))
    x = np.arange(len(items))
    ax.bar(x, [i[1] for i in items], color=[i[2] for i in items])
    for xx, i in zip(x, items): ax.text(xx, i[1] + 10, "%.0f" % i[1], ha="center", fontsize=7)
    ax.set_xticks(x); ax.set_xticklabels([i[0] for i in items], fontsize=6, rotation=20, ha="right"); ax.set_ylabel("line-1 SSE")
    ax.set_title("The rigid recipe beats every rigid layout of the flexible model; the rest is letter spacing")
    fig.savefig(out); plt.close(fig)


def fig_word2(res, out):
    W = J(res, "word2_fixed_recipe.json")
    if not W: return
    fig, axs = plt.subplots(1, len(W), figsize=(7.2, 3.2))
    for ax, w in zip(np.atleast_1d(axs), W):
        top = w["top"][:15]
        y = np.arange(len(top))[::-1]
        ax.barh(y, [t[1] for t in top], color=[OURS if t[0] in ("Star", "star") else OTHER for t in top])
        ax.set_yticks(y); ax.set_yticklabels([t[0] for t in top], fontsize=7)
        ax.set_xlim(top[0][1] - 30, top[-1][1] + 10); ax.set_xlabel("SSE with \"Eternal ___\" (frozen recipe)")
        ax.set_title("%s\n27,122 words, rank of Star = %d" % (NICE.get(w["font"], w["font"]), w["rank_Star"]), fontsize=8)
    fig.savefig(out); plt.close(fig)


def fig_rivals(res, out):
    R = J(res, "line1_rivals.json")
    if not R: return
    words = sorted(R, key=lambda w: np.mean(list(R[w].values())))
    fonts = ["P052-BoldItalic.otf", "PalatinoBoldItalic.ttf"]
    fig, ax = plt.subplots(figsize=(6.4, 2.4)); x = np.arange(len(words)); w = 0.38
    for k, f in enumerate(fonts):
        vals = [R[wd].get(f, np.nan) for wd in words]
        ax.bar(x + (k - 0.5) * w, vals, w, color=[OURS, "#7fb3d5"][k], label=NICE[f])
        for xx, v in zip(x, vals):
            if v == v: ax.text(xx + (k - 0.5) * w, v + 2, "%.0f" % v, ha="center", fontsize=6.5)
    ax.set_xticks(x); ax.set_xticklabels(["Eternal " + wd for wd in words], fontsize=7.5); ax.set_ylim(730, 820)
    ax.set_ylabel("line-1 SSE"); ax.legend(fontsize=7, frameon=False, loc="upper left")
    ax.set_title("Fairness check: every rival gets its OWN full recipe search")
    fig.savefig(out); plt.close(fig)


def fig_line2_slots(res, out):
    fig, axs = plt.subplots(1, 3, figsize=(7.4, 3.6))
    for ax, (sl, title, key) in zip(axs, [("first", "first word: \"___ hope so\"\n(157k strings, 1-3 letters + words)", 0),
                                          ("mid", "middle word: \"We ___ so\"\n(12,556 words)", 1), ("end", "ending: \"We hope ___\"\n(8,535 endings)", 2)]):
        Jp = J(res, "line2_slot_%s_PalatinoBoldItalic.json" % sl)
        if not Jp: continue
        top = Jp["exact"][:14]
        lab = [t["phrase"].split(" ")[key] if len(t["phrase"].split(" ")) > key else t["phrase"] for t in top]
        y = np.arange(len(top))[::-1]
        col = [OURS if l in ("We", "hope", "so") else OTHER for l in lab]
        ax.barh(y, [t["sse"] for t in top], color=col)
        ax.set_yticks(y); ax.set_yticklabels(lab, fontsize=7); ax.set_xlim(top[0]["sse"] - 25, top[-1]["sse"] + 8)
        ax.set_title(title, fontsize=7.5); ax.set_xlabel("line-2 SSE", fontsize=7)
    fig.suptitle("Exhaustive slot tests, genuine Apple 1996 Palatino Bold Italic, locked recipe", fontsize=9, y=1.06)
    fig.savefig(out); plt.close(fig)


def fig_line2_dp(res, out, files=None, titles=None, suptitle=None):
    fig, axs = plt.subplots(1, 2, figsize=(7.4, 3.8))
    files = files or ["line2_dp_PalatinoBoldItalic.json", "line2_dp_P052-BoldItalic.json"]
    for i_, (ax, fn) in enumerate(zip(axs, files)):
        D = J(res, fn); f = "PalatinoBoldItalic" if "Palatino" in fn else "P052-BoldItalic"
        if not D: continue
        top = D["exact"][:22]; y = np.arange(len(top))[::-1]
        ax.barh(y, [t["sse"] for t in top], color=[OURS if " hope " in " %s " % t["phrase"] else OTHER for t in top])
        ax.set_yticks(y); ax.set_yticklabels([t["phrase"] for t in top], fontsize=6.5)
        ax.set_xlim(top[0]["sse"] - 15, top[-1]["sse"] + 5); ax.set_xlabel("line-2 SSE")
        ax.set_title(titles[i_] if titles else NICE[f + (".ttf" if f.startswith("Palatino") else ".otf")], fontsize=7.5)
    if suptitle:
        fig.suptitle(suptitle, fontsize=8.5, y=1.02); fig.savefig(out); plt.close(fig); return
    fig.suptitle("Unconstrained dictionary search (17.7k words, any count/position): blue = contains \"hope\"", fontsize=8.5, y=1.02)
    fig.savefig(out); plt.close(fig)


def fig_simulation(res, out, fn="simulation_P052-BoldItalic.json"):
    S = J(res, fn)
    if not S: return
    gaps = [r["gap"] for r in S]; W = max(gaps)
    fig, axs = plt.subplots(1, 2, figsize=(7.4, 3.0)); fig.subplots_adjust(wspace=0.3)
    axs[0].hist(gaps, bins=np.arange(-40, 71, 10), color=OURS, ec="white")
    axs[0].axvline(W, color=BAD, ls="--"); axs[0].text(W + 1, 0.5, "window\n(+%.0f)" % W, color=BAD, fontsize=7)
    axs[0].set_xlabel("SSE(true phrase) - SSE(best string found)"); axs[0].set_ylabel("simulations")
    axs[0].set_title("Truth always lies within ~%.0f of the optimum" % W, fontsize=8)
    wo = [r["words_ok"] / r["n_words"] for r in S]
    axs[1].bar(range(len(S)), wo, color=[GOOD if r["rank"] == 1 else OURS for r in S])
    axs[1].set_xticks(range(len(S))); axs[1].set_xticklabels([r["true"] for r in S], rotation=80, fontsize=5.5)
    axs[1].set_ylabel("fraction of words recovered"); axs[1].set_title("Blind decoding of planted phrases (green = exact)", fontsize=8)
    fig.savefig(out); plt.close(fig)


def fig_claims(res, out):
    C = None
    for f in ["claims_PalatinoBoldItalic.json", "claims_P052-BoldItalic.json"]:
        C = J(res, f)
        if C: fname = f; break
    if not C: return None
    cl = C["claims"]
    fig, axs = plt.subplots(1, 2, figsize=(7.4, 3.2))
    l1 = {}
    for c in cl: l1[c["line1"]] = c["line1_sse"]
    it = sorted(l1.items(), key=lambda kv: kv[1]); y = np.arange(len(it))[::-1]
    axs[0].barh(y, [v for _, v in it], color=[OURS if k.lower() == "eternal star" else OTHER for k, _ in it])
    axs[0].set_yticks(y); axs[0].set_yticklabels(['"%s"' % k for k, _ in it], fontsize=7)
    for yy, (_, v) in zip(y, it): axs[0].text(v + 15, yy, "%.0f" % v, va="center", fontsize=6.5)
    axs[0].set_xlabel("line-1 SSE (own best recipe)"); axs[0].set_title("Line 1 claims", fontsize=8.5)
    l2 = [(c["line2"], c["line2_sse_starrecipe"]) for c in cl if c.get("line2")]
    l2 = sorted(dict(l2).items(), key=lambda kv: kv[1]); y = np.arange(len(l2))[::-1]
    axs[1].barh(y, [v for _, v in l2], color=[OURS if k == "We hope so" else OTHER for k, _ in l2])
    axs[1].set_yticks(y); axs[1].set_yticklabels(['"%s"' % k for k, _ in l2], fontsize=7)
    for yy, (_, v) in zip(y, l2): axs[1].text(v + 15, yy, "%.0f" % v, va="center", fontsize=6.5)
    best = min(r["sse"] for r in (J(res, "line2_dp_PalatinoBoldItalic.json") or {"exact": [{"sse": 343.6}]})["exact"][:1])
    Sg = J(res, "simulation_P052-BoldItalic.json"); W = max(r["gap"] for r in Sg) if Sg else 50
    axs[1].axvspan(0, best + W, color=GOOD, alpha=0.12); axs[1].text(best + W + 2, y[-1] - 0.6, "pixel-compatible\nwindow", fontsize=6, color=GOOD)
    axs[1].set_xlabel("line-2 SSE (locked 'Eternal Star' process)"); axs[1].set_title("Line 2 claims", fontsize=8.5)
    fig.suptitle("Published and proposed readings, scored with the same model (%s)" % ("Apple Palatino BI" if "Palatino" in fname else "URW P052 BI"), fontsize=9)
    fig.savefig(out); plt.close(fig)
    return C


def plaque_prediction(T, fdir, rec, line1, line2, cfg):
    l1 = Line1(T); pred = T.copy()
    lin1 = l1.coverage(rec, line1, fdir); pred[LINE1[0]:LINE1[1]] = l1.prediction(lin1, rec.gamma).cpu().numpy()
    if line2 is not None and cfg is not None:
        L2 = Line2(T, rec, fdir, line1_text=line1)
        pred[LINE2[0]:LINE2[1]] = L2.prediction(L2.lin_text(line2, *cfg)).cpu().numpy()
    return pred


def fig_claim_panels(T, res, fdir, out):
    C = J(res, "claims_PalatinoBoldItalic.json") or J(res, "claims_P052-BoldItalic.json")
    if not C: return
    want = ["ours", "myhopeis", "secretstar", "lisreal"]
    cl = {c["id"]: c for c in C["claims"]}
    lo, hi = np.percentile(T, 1), np.percentile(T, 99)
    fig, axs = plt.subplots(len(want), 3, figsize=(6.6, 2.25 * len(want)))
    for i, k in enumerate(want):
        c = cl.get(k)
        if not c: continue
        rec = Recipe(**c["recipe"])
        pred = plaque_prediction(T, fdir, rec, c["line1"], c["line2"], c.get("line2_cfg_joint"))
        d = np.abs(T - pred)
        if c["line2"] is None:                                   # claim says nothing about row 2: not modelled, not scored
            d = np.ma.masked_array(d, mask=np.zeros_like(d, bool)); d.mask[LINE2[0]:LINE2[1]] = True
        grey(axs[i, 0], T, lo, hi, "real" if i == 0 else None)
        grey(axs[i, 1], pred, lo, hi, '"%s"' % c["line1"] + (' / "%s"' % c["line2"] if c["line2"] is not None else "\n(row 2 not claimed)"))
        cm = plt.get_cmap("magma").copy(); cm.set_bad("#d9d9d9")
        axs[i, 2].imshow(d, cmap=cm, vmin=0, vmax=10, interpolation="nearest"); axs[i, 2].set_xticks([]); axs[i, 2].set_yticks([])
        axs[i, 2].set_title(("|diff|  SSE %.0f + %.0f" % (c["line1_sse"], c["line2_sse_joint"])) if c["line2"] is not None
                            else "|diff| row 1 only, SSE %.0f" % c["line1_sse"], fontsize=7.5)
        axs[i, 0].set_ylabel(c["who"][:34], fontsize=6.5)
    fig.savefig(out); plt.close(fig)


def fig_descender(T, res, fdir, out):
    C = J(res, "claims_PalatinoBoldItalic.json") or J(res, "claims_P052-BoldItalic.json")
    if not C: return
    exc = np.array(C["row20_excess"]); sd = C["stone_sd"]
    cl = {c["id"]: c for c in C["claims"]}
    fig, ax = plt.subplots(figsize=(7.2, 2.6))
    cols = np.arange(32)
    ax.bar(cols, exc, color=[BAD if e > 2.5 * sd else OTHER for e in exc], width=0.8, label="observed: row 20 minus mean of rows 21-23")
    ax.axhspan(-2 * sd, 2 * sd, color=GREY, alpha=0.15, label="+-2 sd of clean stone")
    for k, col, ls in [("ours", OURS, "-"), ("myhopeis", "#e67e22", "--")]:
        c = cl.get(k)
        if not c or not c.get("line2_cfg_joint"): continue
        rec = Recipe(**c["recipe"]); L2 = Line2(T, rec, fdir, line1_text=c["line1"])
        cov = (L2.lin_text(c["line2"], *c["line2_cfg_joint"]).clamp(0, 1) ** L2.G).cpu().numpy()
        ink = L2.L * cov[20 - LINE2[0]] - L2.L * cov[21 - LINE2[0]:24 - LINE2[0]].mean(0)
        ax.plot(cols, ink, color=col, ls=ls, marker="o", ms=2.5, lw=1.2, label='predicted descender ink, "%s"' % c["line2"])
    ax.set_xlabel("texture column"); ax.set_ylabel("grey levels"); ax.set_xlim(3.5, 26.5)
    ax.set_title("Descenders below line 2: only ONE column (16) is significantly bright")
    ax.legend(fontsize=6.5, frameon=False, loc="upper right")
    fig.savefig(out); plt.close(fig)


def fig_line2_band_panels(T, res, fdir, out, phrases):
    C = J(res, "claims_PalatinoBoldItalic.json")
    recs = Recipe(**C["claims"][[c["id"] for c in C["claims"]].index("ours")]["recipe"]) if C else Recipe(**J(res, "research_recipes_PalatinoBoldItalic.json")[0])
    L2 = Line2(T, recs, fdir)
    D = J(res, "line2_dp_PalatinoBoldItalic.json"); b = D["exact"][0]
    lo, hi = np.percentile(T, 1), np.percentile(T, 99)
    fig, axs = plt.subplots(len(phrases), 3, figsize=(7.2, 0.95 * len(phrases)))
    for i, ph in enumerate(phrases):
        v, cfg = L2.exact_refine(ph, (b["P2"], b["esp"], b["x"], b["yb"]))
        for P2b in (b["P2"] - 1, b["P2"] + 1):
            v2, c2 = L2.exact_refine(ph, (P2b, cfg[1], cfg[2], cfg[3]))
            if v2 < v: v, cfg = v2, c2
        pred = L2.prediction(L2.lin_text(ph, *cfg)).cpu().numpy(); real = T[LINE2[0]:LINE2[1]]
        grey(axs[i, 0], real, lo, hi, "real line 2" if i == 0 else None); grey(axs[i, 1], pred, lo, hi, "model" if i == 0 else None)
        axs[i, 2].imshow(np.abs(real - pred), cmap="magma", vmin=0, vmax=10, interpolation="nearest"); axs[i, 2].set_xticks([]); axs[i, 2].set_yticks([])
        axs[i, 0].set_ylabel('"%s"\nSSE %.0f' % (ph, v), rotation=0, ha="right", va="center", fontsize=7)
    fig.savefig(out); plt.close(fig)


TEX = None          # the user's own texture (set by make_all); never stored in results/


def _real_band():
    return np.asarray(TEX, np.float32)[LINE2[0]:LINE2[1]]


def _cand(res, font="PalatinoBoldItalic", src=None):
    return J(res, src[font] if src else "line2_candidates_%s.json" % font)


def fig_cand_bars(res, out, part, src=None, fonts=("PalatinoBoldItalic", "P052-BoldItalic"), titles=None):
    from .candidates import JUNK_FIRST, JUNK_END
    fig, axs = plt.subplots(1, 2, figsize=(7.4, 4.6))
    for i_, (ax, font) in enumerate(zip(axs, fonts)):
        C = _cand(res, font, src)
        if not C: continue
        d = C[part]; lab = (lambda k: k.split(" ")[0]) if part == "first" else (lambda k: k.split(" ", 2)[2])
        items = sorted(d.items(), key=lambda kv: kv[1]["local"][part])[:24]
        y = np.arange(len(items))[::-1]; best = items[0][1]["local"][part]
        junk = JUNK_FIRST if part == "first" else JUNK_END
        col = [OURS if lab(k) in ("We", "so") else ("#dddddd" if lab(k) in junk else OTHER) for k, _ in items]
        ax.barh(y, [v["local"][part] for _, v in items], color=col, hatch=None)
        ax.set_yticks(y); ax.set_yticklabels(['"%s"%s' % (lab(k), "*" if lab(k) in junk else "") for k, _ in items], fontsize=6.5)
        for yy, (k, v) in zip(y, items): ax.text(v["local"][part] + 1, yy, "%+.0f" % (v["local"][part] - best), va="center", fontsize=5.5)
        ax.set_xlim(best - 20, items[-1][1]["local"][part] + 15)
        ax.set_xlabel("local SSE (%s region only)" % ("first-word, cols 0-11" if part == "first" else "ending, cols 20-31"), fontsize=7)
        ax.set_title(titles[i_] if titles else NICE[font + (".ttf" if font.startswith("Palatino") else ".otf")], fontsize=7.5)
    fig.suptitle(('First word: "___ hope so"' if part == "first" else 'Ending: "We hope ___"') + "  (* = best non-word strings, for reference)", fontsize=9)
    fig.savefig(out); plt.close(fig)


def fig_cand_crops(res, out, part, n=14, font="PalatinoBoldItalic", src=None):
    from .candidates import JUNK_FIRST, JUNK_END
    C = _cand(res, font, src)
    if not C: return
    d = C[part]; real = _real_band()
    lab = (lambda k: k.split(" ")[0]) if part == "first" else (lambda k: k.split(" ", 2)[2])
    junk = JUNK_FIRST if part == "first" else JUNK_END
    items = [kv for kv in sorted(d.items(), key=lambda kv: kv[1]["local"][part]) if lab(kv[0]) not in junk][:n]
    cs = slice(3, 14) if part == "first" else slice(17, 28); rs = slice(1, 7)          # band rows 16..21
    lo, hi = np.percentile(real, 1), np.percentile(real, 99.5)
    ncol = 7; nrow = int(np.ceil((len(items) + 1) / ncol))
    fig, axs = plt.subplots(nrow * 2, ncol, figsize=(7.4, 0.8 * nrow * 2), gridspec_kw=dict(hspace=0.45, wspace=0.08))
    for ax in axs.ravel(): ax.axis("off")
    cells = [("real plaque", real, None)] + [('"%s"' % lab(k), np.array(v["pred"]), v["local"][part]) for k, v in items]
    best = items[0][1]["local"][part]
    for i, (t, a, sc) in enumerate(cells):
        r, c = divmod(i, ncol)
        ax = axs[2 * r, c]; ax.imshow(a[rs, cs], cmap="gray", vmin=lo, vmax=hi, interpolation="nearest"); ax.axis("on"); ax.set_xticks([]); ax.set_yticks([])
        ax.set_title(t if sc is None else "%s  %+.0f" % (t, sc - best), fontsize=7, color=OURS if t.strip('"') in ("We", "so") else "black")
        ax2 = axs[2 * r + 1, c]
        if sc is not None:
            ax2.imshow(np.abs(real - a)[rs, cs], cmap="magma", vmin=0, vmax=10, interpolation="nearest"); ax2.axis("on"); ax2.set_xticks([]); ax2.set_yticks([])
    fig.subplots_adjust(top=0.88)
    fig.suptitle(("First word close-up (texture cols 3-13, rows 16-21)" if part == "first" else "Ending close-up (texture cols 17-27, rows 16-21)")
                 + ": model above, |diff| below; number = local SSE vs best", fontsize=8.5)
    fig.savefig(out); plt.close(fig)


def fig_variants(res, out, font="PalatinoBoldItalic"):
    A = _cand(res, "PalatinoBoldItalic"); B = _cand(res, "P052-BoldItalic")
    if not A: return
    ks = list(A["variants"])
    mean = {k: np.mean([X["variants"][k]["sse"] for X in (A, B) if X and k in X["variants"]]) for k in ks}
    ks.sort(key=lambda k: mean[k])
    fig, ax = plt.subplots(figsize=(7.4, 0.2 * len(ks) + 1.0))
    y = np.arange(len(ks))[::-1]
    for j, (X, c, lab) in enumerate([(A, OURS, "Apple Palatino BI"), (B, "#7fb3d5", "URW P052 BI")]):
        if X: ax.barh(y + (0.2 if j == 0 else -0.2), [X["variants"][k]["sse"] for k in ks], 0.4, color=c, label=lab)
    ax.set_yticks(y); ax.set_yticklabels(['"%s"' % k for k in ks], fontsize=7)
    D = J(res, "line2_dp_PalatinoBoldItalic.json"); opt = D["exact"][0]["sse"] if D else 343.6
    Sg = J(res, "simulation_P052-BoldItalic.json"); W = max(r["gap"] for r in Sg) if Sg else 50
    ax.axvspan(opt, opt + W, color=GOOD, alpha=0.12); ax.text(opt + 2, y[0] + 0.8, "pixel-compatible window", fontsize=6.5, color=GOOD)
    ax.set_xlabel("line-2 SSE (whole band)"); ax.legend(fontsize=7, frameon=False, loc="lower right")
    ax.set_title("Line-2 variants, exact rendering with the locked recipe")
    fig.savefig(out); plt.close(fig)


def fig_variant_panels(res, out, keys=("We hope so", "We hope so.", "We hope for", "We hope he", "We hope to", "We hope on",
                                        "We hope is", "My hope is", "He hopes so", "I hope so"), src=None, font="PalatinoBoldItalic"):
    C = _cand(res, font, src)
    if not C: return
    real = _real_band(); lo, hi = np.percentile(real, 1), np.percentile(real, 99.5)
    keys = [k for k in keys if k in C["variants"]]
    fig, axs = plt.subplots(len(keys) + 1, 2, figsize=(7.0, 0.82 * (len(keys) + 1)))
    grey(axs[0, 0], real[1:7], lo, hi); axs[0, 0].set_ylabel("real", rotation=0, ha="right", va="center", fontsize=7); axs[0, 1].axis("off")
    for i, k in enumerate(keys, 1):
        v = C["variants"][k]; a = np.array(v["pred"])
        grey(axs[i, 0], a[1:7], lo, hi)
        axs[i, 0].set_ylabel('"%s"\nSSE %.0f' % (k, v["sse"]), rotation=0, ha="right", va="center", fontsize=6.8)
        axs[i, 1].imshow(np.abs(real - a)[1:7], cmap="magma", vmin=0, vmax=10, interpolation="nearest"); axs[i, 1].set_xticks([]); axs[i, 1].set_yticks([])
    axs[1, 1].set_title("|real - model| (0..10 levels)", fontsize=7)
    fig.savefig(out); plt.close(fig)


def fig_hero(T, res, fdir, out):
    C = J(res, "claims_PalatinoBoldItalic.json")
    if not C: return
    c = {x["id"]: x for x in C["claims"]}["ours"]
    rec = Recipe(**c["recipe"]); pred = plaque_prediction(T, fdir, rec, c["line1"], c["line2"], c["line2_cfg_joint"])
    lo, hi = np.percentile(T, 1), np.percentile(T, 99)
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 3.6))
    grey(axs[0], T, lo, hi, "the real plaque texture (32x32, from the ROM)")
    grey(axs[1], pred, lo, hi, '"Eternal Star / We hope so" - Palatino Bold Italic,\n1996 Mac process, rendered by our model')
    fig.savefig(out); plt.close(fig)


def fig_hopefit(res, out):
    H = J(res, "hopefit_PalatinoBoldItalic.json")
    if not H: return
    rows = H["fit"]
    fig, axs = plt.subplots(1, 2, figsize=(7.4, 2.8)); fig.subplots_adjust(wspace=0.3)
    for f2, col in [("P052-BoldItalic.otf", OURS), ("PalatinoBoldItalic.ttf", "#7fb3d5"), ("P052-Italic.otf", "#e67e22"), ("PalatinoItalic.ttf", "#f5b041")]:
        P = sorted({r["P2"] for r in rows if r["font2"] == f2})
        if not P: continue
        axs[0].plot(P, [min(r["sse_hope"] for r in rows if r["font2"] == f2 and r["P2"] == p) for p in P], "o-", ms=3, color=col, label=NICE.get(f2, f2))
    axs[0].set_xlabel("line-2 font size P2 (px)"); axs[0].set_ylabel("SSE on the 'hope' pixels only"); axs[0].legend(fontsize=6.5, frameon=False)
    axs[0].set_title("'hope': face and size", fontsize=8.5)
    b = H["best"]
    TRs = sorted({r["tracking2"] for r in rows})
    axs[1].bar([str(t) for t in TRs], [min(r["sse_hope"] for r in rows if r["tracking2"] == t and r["font2"] == b["font2"] and r["P2"] == b["P2"]) for t in TRs], color=OURS)
    axs[1].set_xlabel("line-2 tracking (canvas px)"); axs[1].set_title("'hope' at %d px: tracking" % b["P2"], fontsize=8.5)
    fig.savefig(out); plt.close(fig)


def fig_inversion(res, out):
    p = os.path.join(res, "inversion.npz")
    if not os.path.exists(p): return
    Z = np.load(p); crop = json.loads(str(Z["crop"])); names = json.loads(str(Z["names"])); sses = json.loads(str(Z["sses"]))
    cr = (slice(crop["r0"], crop["r1"]), slice(crop["c0"], crop["c1"]))
    priors = ["none", "sparse+tv", "sparse+tv+binary"]
    fig, axs = plt.subplots(len(names), 4, figsize=(7.6, 1.05 * len(names)), gridspec_kw=dict(wspace=0.04, hspace=0.32))
    for i, n in enumerate(names):
        if n == "real":
            axs[i, 0].imshow(TEX[LINE1[0] - 1:LINE2[1] - 1], cmap="gray", interpolation="nearest", aspect="auto"); axs[i, 0].set_title("real plaque (rows 5-22)", fontsize=6.5)
        else:
            axs[i, 0].imshow(Z["%d_truth" % i][cr], cmap="gray_r", vmin=0, vmax=1, interpolation="nearest", aspect="auto")
            axs[i, 0].set_title("known artwork", fontsize=6.5)
        for j, pr in enumerate(priors, 1):
            axs[i, j].imshow(Z["%d_%s" % (i, pr)][cr], cmap="gray_r", vmin=0, vmax=1, interpolation="nearest", aspect="auto")
            if i == 0: axs[i, j].set_title("inverted, prior: %s" % pr, fontsize=6.5)
        axs[i, 0].set_ylabel("REAL PLAQUE" if n == "real" else "synthetic:\n" + n.replace(" / ", "\n/ "), rotation=0, ha="right", va="center",
                             fontsize=6.5, color=OURS if n in ("real", "Eternal Star / We hope so") else "black")
        for ax in axs[i]: ax.set_xticks([]); ax.set_yticks([])
    fig.suptitle("Inverting the fitted process: real plaque vs. synthetic plaques with known text (same stone and noise)", fontsize=8.5)
    fig.savefig(out); plt.close(fig)


def fig_fontver(res, out):
    A = (J(res, "fontver.json") or []) + (J(res, "fontver_adobe.json") or [])
    if not A: return
    rows = sorted([r for r in A if r["ss"] == 1], key=lambda r: r["total"])
    fig, axs = plt.subplots(1, 2, figsize=(7.6, 0.32 * len(rows) + 1.2), gridspec_kw=dict(width_ratios=(2.2, 1), wspace=0.12))
    y = np.arange(len(rows))[::-1]
    col = [OURS if "Adobe" in r["font"] else ("#7fb3d5" if "Palatino" in r["font"] or "Palladio" in r["font"] or "P052" in r["font"] or "Pagella" in r["font"] else OTHER) for r in rows]
    axs[0].barh(y + 0.2, [r["line1"] for r in rows], 0.4, color=col, label="line 1")
    axs[0].barh(y - 0.2, [r["line2"] for r in rows], 0.4, color=col, alpha=0.55, label="line 2")
    for yy, r in zip(y, rows): axs[0].text(r["line1"] + 8, yy + 0.2, "%.0f" % r["line1"], va="center", fontsize=6.5); axs[0].text(r["line2"] + 8, yy - 0.2, "%.0f" % r["line2"], va="center", fontsize=6.5)
    axs[0].set_yticks(y); axs[0].set_yticklabels([NICE.get(r["font"], r["font"]) for r in rows], fontsize=7)
    axs[0].set_xlabel("SSE: line 1 (dark) and line 2 'We hope so' (light)", fontsize=7.5); axs[0].legend(fontsize=7, frameon=False, loc="upper right")
    axs[1].barh(y, [r["hole_19_8"] for r in rows], color=col); axs[1].axvline(8, color=BAD, ls="--")
    axs[1].text(8.2, y[-1] - 0.7, "real: 8 (bare stone)", fontsize=6.5, color=BAD); axs[1].set_xlim(6, 17); axs[1].set_yticks([])
    axs[1].set_xlabel("model value at the W hole", fontsize=7.5)
    fig.suptitle("Palatino digitisations of 1990-1999 + modern, identical pipeline (hinted rendering)", fontsize=9)
    fig.savefig(out); plt.close(fig)


def make_all(T, res, fdir, outdir, log):
    os.makedirs(outdir, exist_ok=True)
    T = np.asarray(T, np.float32)
    global TEX; TEX = T
    jobs = [("hero.png", lambda o: fig_hero(T, res, fdir, o)), ("texture.pdf", lambda o: fig_texture(T, o)), ("fonts_rigid.pdf", lambda o: fig_fonts_rigid(res, o)),
            ("fonts_flexible.pdf", lambda o: fig_fonts_flexible(res, o)), ("font_panels.pdf", lambda o: fig_font_panels(T, res, fdir, o)),
            ("progression.pdf", lambda o: fig_progression(res, o)), ("ablation.pdf", lambda o: fig_ablation(res, o)),
            ("word2.pdf", lambda o: fig_word2(res, o)), ("rivals.pdf", lambda o: fig_rivals(res, o)),
            ("line2_dp.pdf", lambda o: fig_line2_dp(res, o)), ("line2_slots.pdf", lambda o: fig_line2_slots(res, o)),
            ("simulation.pdf", lambda o: fig_simulation(res, o)), ("simulation_hope.pdf", lambda o: fig_simulation(res, o, "simulation_hopefit.json")), ("claims.pdf", lambda o: fig_claims(res, o)),
            ("claim_panels.pdf", lambda o: fig_claim_panels(T, res, fdir, o)), ("descender.pdf", lambda o: fig_descender(T, res, fdir, o)),
            ("cand_first_bars.pdf", lambda o: fig_cand_bars(res, o, "first")), ("cand_end_bars.pdf", lambda o: fig_cand_bars(res, o, "ending")),
            ("cand_first_crops.pdf", lambda o: fig_cand_crops(res, o, "first")), ("cand_end_crops.pdf", lambda o: fig_cand_crops(res, o, "ending")),
            ("variants.pdf", lambda o: fig_variants(res, o)), ("variant_panels.pdf", lambda o: fig_variant_panels(res, o)),
            ("alt_panels.pdf", lambda o: fig_line2_band_panels(T, res, fdir, o, ["We hope so", "By hope so", "Be hope so", "We pray so",
                                                                                 "We hope you", "Be with us", "By your side", "We love you"])),
            ("hopefit.pdf", lambda o: fig_hopefit(res, o)),
            ("hope_variant_panels.pdf", lambda o: fig_variant_panels(res, o, keys=("We hope so", "We hope so.", "We hope or", "We hope he", "We hope to",
                                         "We hope for", "My hope is", "Me hope so", "By hope so", "Be with us"), src={"P052": "hopefit_PalatinoBoldItalic.json"}, font="P052")),
            ("hope_first_bars.pdf", lambda o: fig_cand_bars(res, o, "first", src={"P052": "hopefit_PalatinoBoldItalic.json", "Apple": "hopefit_apple_line2.json"},
                                                            fonts=("P052", "Apple"), titles=("line 2 in URW P052 BI (hope-calibrated)", "line 2 in Apple Palatino BI (hope-calibrated)"))),
            ("hope_end_bars.pdf", lambda o: fig_cand_bars(res, o, "ending", src={"P052": "hopefit_PalatinoBoldItalic.json", "Apple": "hopefit_apple_line2.json"},
                                                          fonts=("P052", "Apple"), titles=("line 2 in URW P052 BI (hope-calibrated)", "line 2 in Apple Palatino BI (hope-calibrated)"))),
            ("hope_first_crops.pdf", lambda o: fig_cand_crops(res, o, "first", font="P052", src={"P052": "hopefit_PalatinoBoldItalic.json"})),
            ("hope_end_crops.pdf", lambda o: fig_cand_crops(res, o, "ending", font="P052", src={"P052": "hopefit_PalatinoBoldItalic.json"})),
            ("hope_dp.pdf", lambda o: fig_line2_dp(res, o, files=["line2_dp_hopefit_P052line2.json", "line2_dp_hopefit_Appleline2.json"],
                                                   titles=("line 2 in URW P052 BI", "line 2 in Apple Palatino BI"),
                                                   suptitle="Unconstrained dictionary search with the hope-calibrated line-2 typesetting (blue = contains \"hope\")")),
            ("inversion.pdf", lambda o: fig_inversion(res, o)),
            ("fontver.pdf", lambda o: fig_fontver(res, o)),
            ("adobe_dp.pdf", lambda o: fig_line2_dp(res, o, files=["line2_dp_AdobePalatino.json", "line2_dp_hopefit_adobe.json"],
                                                    titles=("Adobe Palatino BI: line-1 typesetting", "Adobe Palatino BI: hope-calibrated line 2"),
                                                    suptitle="Blind dictionary search (17.7k words) with Adobe's 1990 Palatino Bold Italic: #1 is \"We hope so\" in both")),
            ("line2_panels.pdf", lambda o: fig_line2_band_panels(T, res, fdir, o, ["We hope so", "We hope he", "My hope is", "lie here ~",
                                                                                   "No hope so", "Rest in peace", "2401"]))]
    for name, fn in jobs:
        try:
            fn(os.path.join(outdir, name)); log("figure", name)
        except Exception as e:
            import traceback; traceback.print_exc(); log("figure %s FAILED: %s" % (name, e))
    from .tables import make_tables
    make_tables(res, os.path.join(os.path.dirname(os.path.abspath(outdir)), "tables"), log)
