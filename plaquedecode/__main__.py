"""plaquedecode — reproduce the SM64 courtyard-plaque analysis.

  python -m plaquedecode extract  --rom "Super Mario 64 (USA).z64"            # -> texture.npy (stays local)
  python -m plaquedecode recipe   --font P052-BoldItalic.otf [--text "Eternal Star"] [--stage full]
  python -m plaquedecode word2    --recipes results/recipes_P052-BoldItalic.json
  python -m plaquedecode line2    --recipes results/recipes_P052-BoldItalic.json --mode dp|combo [--phrases file]
  python -m plaquedecode simulate --recipes ... --line2 results/line2_dp_P052-BoldItalic.json
  python -m plaquedecode claims   --fonts-dir fonts --font P052-BoldItalic.otf
  python -m plaquedecode figures                                               # report figures from results/*.json
Fonts are looked up in --fonts-dir (default ./fonts); see fonts/README.md.  A CUDA GPU is used when available."""
import argparse, json, os, sys, time
import numpy as np


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def load_T(path):
    if not os.path.exists(path):
        sys.exit("texture %s not found — run:  python -m plaquedecode extract --rom <your SM64 ROM>" % path)
    return np.load(path)


def best_recipe(path, font=None):
    from .core import Recipe
    R = json.load(open(path))
    R = [r for r in R if font is None or r["font"] == font]
    r = min(R, key=lambda r: r["sse"])
    return Recipe(**r)


def words_from(path):
    return [w.strip() for w in open(path, encoding="utf-8") if w.strip() and not w.startswith("#")]


def main():
    ap = argparse.ArgumentParser(prog="plaquedecode", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--texture", default="texture.npy"); ap.add_argument("--fonts-dir", default="fonts")
    ap.add_argument("--results", default="results")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("extract"); s.add_argument("--rom", required=True)
    s = sub.add_parser("recipe"); s.add_argument("--font", required=True); s.add_argument("--text", default="Eternal Star")
    s.add_argument("--stage", choices=["square", "aniso", "full", "fontcmp"], default="full"); s.add_argument("--out")
    s = sub.add_parser("word2"); s.add_argument("--recipes", required=True); s.add_argument("--vocab", default="data/vocab_en_core.txt")
    s.add_argument("--out")
    s = sub.add_parser("line2"); s.add_argument("--recipes", required=True); s.add_argument("--mode", choices=["dp", "combo"], default="dp")
    s.add_argument("--vocab", default="data/vocab_en_core.txt"); s.add_argument("--phrases", help="text file, one phrase per line ('curated' = built-in set)")
    s.add_argument("--p2", default="13,14,15,16,17,18,19,20"); s.add_argument("--topn", type=int, default=3000); s.add_argument("--k", type=int, default=48)
    s.add_argument("--font2", help="other face for line 2"); s.add_argument("--first", help="dp: comma-separated allowed first words")
    s.add_argument("--hopefit", help="use the line-2 typesetting fitted on 'hope' (hopefit json)"); s.add_argument("--out")
    s = sub.add_parser("simulate"); s.add_argument("--recipes", required=True); s.add_argument("--line2", required=True)
    s.add_argument("--vocab", default="data/vocab_en_core.txt"); s.add_argument("--n", type=int, default=24)
    s.add_argument("--hopefit"); s.add_argument("--p2", default="16,17,18"); s.add_argument("--out")
    s = sub.add_parser("claims"); s.add_argument("--font", required=True); s.add_argument("--recipes", required=True); s.add_argument("--out")
    s = sub.add_parser("candidates"); s.add_argument("--recipes", required=True); s.add_argument("--line2", required=True); s.add_argument("--out")
    s = sub.add_parser("joint"); s.add_argument("--font", required=True); s.add_argument("--upper", required=True); s.add_argument("--lower", required=True)
    s.add_argument("--line2", default="We hope so"); s.add_argument("--topn", type=int, default=100); s.add_argument("--out")
    s = sub.add_parser("hopefit"); s.add_argument("--recipes", required=True); s.add_argument("--line2", required=True)
    s.add_argument("--fonts2", required=True, help="comma-separated faces to try for line 2"); s.add_argument("--out")
    s = sub.add_parser("invert"); s.add_argument("--recipes", required=True); s.add_argument("--hopefit", required=True)
    s.add_argument("--line2", required=True, help="line-2 dp result under the hope typesetting (for the 'We hope so' placement)")
    s.add_argument("--steps", type=int, default=2500); s.add_argument("--out")
    s = sub.add_parser("figures"); s.add_argument("--out", default="report/figures")
    a = ap.parse_args()
    os.makedirs(a.results, exist_ok=True)

    if a.cmd == "extract":
        from .rom import extract
        T, ver, raw = extract(a.rom)
        np.save(a.texture, T); log("plaque texture from %s ROM (sha1 ok) -> %s" % (ver.upper(), a.texture))
        if ver == "us":                                # the game's dialog font (US glyph set), for the font comparison
            from . import gamefont
            os.makedirs(a.fonts_dir, exist_ok=True); gamefont.save(a.rom, os.path.join(a.fonts_dir, "sm64_dialog_font.npz"))
            log("SM64 dialog font -> %s/sm64_dialog_font.npz (use --font SM64-dialog)" % a.fonts_dir)
        return

    T = load_T(a.texture)
    if a.cmd == "recipe":
        from .core import Line1, search_recipes, FILTERS_ALL
        l1 = Line1(T)
        if a.stage == "square":
            kxy, flt, kw = [(k, k) for k in (1, 2, 3, 4, 6, 8)], FILTERS_ALL, {}
        elif a.stage == "aniso":
            kxy = [(kx, ky) for kx in (3, 4, 5, 6, 8) for ky in (3, 4, 5, 6, 8) if 0.6 <= kx / ky <= 1.7]
            flt, kw = ["bilinear", "bicubic5", "bicubic75"], dict(fracs=(False,))
        elif a.stage == "fontcmp":                    # identical, slightly reduced grid for every font (family comparison)
            kxy = [(5, 4), (6, 5), (6, 6), (8, 6)]
            flt, kw = ["bilinear", "bicubic5"], dict(blurs=(0.0, 0.45), gammas=(1.0, 1.4, 1.8, 2.2),
                                                     esps=(-1.0, -0.5, 0.0, 0.5), fracs=(False, "glyph"))
        else:
            kxy = [(kx, ky) for kx in (4, 5, 6, 8) for ky in (4, 5, 6) if 1.0 <= kx / ky <= 1.5]
            flt, kw = ["bilinear", "bicubic5"], dict(blurs=(0.0, 0.3, 0.45, 0.6), gammas=(1.0, 1.4, 1.8, 2.2),
                                                     esps=(-1.0, -0.5, 0.0, 0.5), fracs=(False, "glyph"))
        log("line-1 noise floor %.1f; searching %s for %r (%s stage)" % (l1.floor, a.font, a.text, a.stage))
        R = search_recipes(l1, a.fonts_dir, a.font, a.text, kxy, flt, log=log, **kw)
        R.sort(key=lambda r: r.sse)
        out = a.out or os.path.join(a.results, ("fontcmp_" if a.stage == "fontcmp" else "") + "recipes_%s%s.json" % (os.path.splitext(a.font)[0], "" if a.text == "Eternal Star" else "_" + a.text.replace(" ", "_")))
        json.dump([r.to_dict() for r in R[:2000]], open(out, "w"), indent=0)
        b = R[0]
        log("best: SSE %.1f (%.2fx floor) canvas %dx%d %dpx tracking %+d kern %d advances %s %s blur %.2f gamma %.1f space %+.1f -> %s" % (
            b.sse, b.sse / l1.floor, 32 * b.kx, 32 * b.ky, b.P, b.tracking, b.kern, b.frac, b.filter, b.blur, b.gamma, b.esp, out))
        return

    if a.cmd == "word2":
        import torch
        from .core import Line1, render_text
        rec = best_recipe(a.recipes); l1 = Line1(T); WX, WY = rec.matrices()
        fpath = os.path.join(a.fonts_dir, rec.font)
        words = [w for w in words_from(a.vocab) if w.isalpha() and 2 <= len(w) <= 7]
        words = list(dict.fromkeys(words + ["Star", "star"]))
        img, _, _, (r0, r1, c0, c1) = render_text(fpath, "Eternal Star", rec.P, rec.tracking, rec.kern, rec.frac, int(round(rec.esp * rec.kx)))
        ox = rec.X + rec.offx - max(0, c0 - 1); oy = rec.Y + rec.offy - max(0, r0 - 1)
        WYb = WY[l1.R0:l1.R1]; scores = {}
        for w in words:
            best = None
            for esp in (-1.0, -0.5, 0.0, 0.5):
                im, _, _, _ = render_text(fpath, "Eternal " + w, rec.P, rec.tracking, rec.kern, rec.frac, int(round(esp * rec.kx)))
                hI, wI = im.shape; x1 = min(rec.canvas, ox + wI); y1 = min(rec.canvas, oy + hI)
                I = torch.tensor(im[:y1 - oy, :x1 - ox], device=l1.dev)
                cov = ((WYb[:, oy:y1] @ I @ WX[:, ox:x1].T).clamp(0, 1) ** rec.gamma).reshape(-1)
                Ma = l1.M @ cov; num = float(Ma @ l1.Mt); den = float(Ma @ Ma)
                v = l1.tMt - (num * num / den if num > 0 else 0)
                best = v if best is None else min(best, v)
            scores[w] = best
        order = sorted(scores, key=scores.get)
        log("word 2 under the frozen recipe: top 15", [(w, round(scores[w], 1)) for w in order[:15]])
        log("rank of Star %d, star %d of %d" % (order.index("Star") + 1, order.index("star") + 1, len(order)))
        out = a.out or os.path.join(a.results, "word2_%s.json" % os.path.splitext(rec.font)[0])
        json.dump(dict(recipe=rec.to_dict(), ranking=[(w, scores[w]) for w in order[:500]], n=len(order),
                       rank_Star=order.index("Star") + 1, rank_star=order.index("star") + 1), open(out, "w"))
        return

    if a.cmd == "line2":
        from .core import Line2
        rec = best_recipe(a.recipes)
        if a.hopefit:
            hb = json.load(open(a.hopefit))["best"]; a.font2 = hb["font2"]
            L2 = Line2(T, rec, a.fonts_dir, hb["font2"], tr2=hb["tracking2"], kern2=hb["kern2"], frac2=hb["frac2"])
        else:
            L2 = Line2(T, rec, a.fonts_dir, a.font2)
        P2S = [int(p) for p in a.p2.split(",")]
        log("recipe %s: line-1 SSE %.1f, ink %.2f | line-2 stone-only %.1f, floor %.1f" % (rec.font, L2.sse1, L2.L, L2.STONE, L2.floor))
        if a.mode == "dp":
            found, cfgs = L2.run_dp(words_from(a.vocab), P2S, K=a.k, log=log, first=a.first.split(",") if a.first else None)
            log("best configs (sse, P2, baseline, space):", [(round(c[0], 1),) + c[1:] for c in cfgs[:6]])
        else:
            if a.phrases in (None, "curated"):
                from .phrases import curated
                phrases = curated()
            elif a.phrases == "extra":
                from .phrases_extra import extra
                phrases = extra()
            else:
                phrases = words_from(a.phrases)
            found = L2.run_combo(phrases, P2S, log=log)
        ex = L2.rerank(found, a.topn)
        for r in ex[:25]: log("  %7.1f  %r" % (r["sse"], r["phrase"]))
        out = a.out or os.path.join(a.results, "line2_%s_%s.json" % (a.mode, os.path.splitext(a.font2 or rec.font)[0]))
        json.dump(dict(font=rec.font, font2=a.font2 or rec.font, L=L2.L, stone=L2.STONE, floor=L2.floor, exact=ex), open(out, "w"))
        return

    if a.cmd == "simulate":
        from .simulate import simulate
        simulate(T, best_recipe(a.recipes), a.fonts_dir, json.load(open(a.line2)), words_from(a.vocab), a.n,
                 a.out or os.path.join(a.results, "simulation.json"), log, P2S=[int(p) for p in a.p2.split(",")],
                 hope=json.load(open(a.hopefit))["best"] if a.hopefit else None)
        return

    if a.cmd == "claims":
        from .claims import score_claims
        score_claims(T, a.fonts_dir, a.font, best_recipe(a.recipes), a.out or os.path.join(a.results, "claims_%s.json" % os.path.splitext(a.font)[0]), log)
        return

    if a.cmd == "candidates":
        from .candidates import run
        rec = best_recipe(a.recipes)
        run(T, rec, a.fonts_dir, json.load(open(a.line2))["exact"][0],
            a.out or os.path.join(a.results, "line2_candidates_%s.json" % os.path.splitext(rec.font)[0]), log)
        return

    if a.cmd == "joint":
        from .joint import run
        run(T, a.fonts_dir, {"Eternal Star": a.upper, "Eternal star": a.lower}, a.line2,
            a.out or os.path.join(a.results, "joint_case_%s.json" % os.path.splitext(a.font)[0]), log, topn=a.topn)
        return

    if a.cmd == "hopefit":
        from .hopefit import run
        rec = best_recipe(a.recipes)
        run(T, rec, a.fonts_dir, a.fonts2.split(","), json.load(open(a.line2))["exact"][0],
            a.out or os.path.join(a.results, "hopefit_%s.json" % os.path.splitext(rec.font)[0]), log)
        return

    if a.cmd == "invert":
        from .invert import run
        rec = best_recipe(a.recipes); ex = json.load(open(a.line2))["exact"]
        r = next(r for r in ex if r["phrase"] == "We hope so")
        run(T, rec, a.fonts_dir, json.load(open(a.hopefit))["best"], (r["P2"], r["esp"], r["x"], r["yb"]),
            a.out or os.path.join(a.results, "inversion.npz"), log, steps=a.steps)
        return

    if a.cmd == "figures":
        from .figures import make_all
        make_all(T, a.results, a.fonts_dir, a.out, log)


if __name__ == "__main__":
    main()
