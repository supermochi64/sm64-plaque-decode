"""LaTeX tables + number macros for the report, generated from results/*.json (so text and data cannot drift)."""
import json, os, glob
import numpy as np
from .figures import NICE, family, J


def tex(s):
    return str(s).replace("\\", r"\textbackslash{}").replace("&", r"\&").replace("%", r"\%").replace("_", r"\_").replace("~", r"\textasciitilde{}").replace("#", r"\#")


def make_tables(res, outdir, log):
    os.makedirs(outdir, exist_ok=True)
    mac = {}
    # --- best recipes
    rows = []
    for f in ["P052-BoldItalic", "PalatinoBoldItalic"]:
        R = J(res, "research_recipes_%s.json" % f)
        if R: rows.append(R[0])
    if rows:
        with open(os.path.join(outdir, "recipe.tex"), "w") as o:
            o.write("\\begin{tabular}{lcc}\\toprule\n & %s & %s \\\\ \\midrule\n" % tuple(tex(NICE[r["font"]]) for r in rows))
            for lab, fn in [("artwork canvas", lambda r: "%d$\\times$%d px" % (32 * r["kx"], 32 * r["ky"])), ("font size", lambda r: "%d px" % r["P"]),
                            ("tracking", lambda r: "%+d px" % r["tracking"]), ("pair kerning", lambda r: "on" if r["kern"] else "off"),
                            ("advances", lambda r: "whole pixels per glyph" if r["frac"] == "glyph" else "rounded pen"),
                            ("word space", lambda r: "%+.1f texture px" % r["esp"]), ("resize filter", lambda r: r["filter"].replace("bicubic5", "bicubic ($a=-0.5$)")),
                            ("blur after resize", lambda r: "$\\sigma=%.2f$ px" % r["blur"]), ("gamma", lambda r: "%.1f" % r["gamma"]),
                            ("line-1 SSE", lambda r: "%.1f" % r["sse"]), ("SSE / noise floor", lambda r: "%.2f" % (r["sse"] / 165.7))]:
                o.write("%s & %s & %s \\\\\n" % (lab, fn(rows[0]), fn(rows[1])))
            o.write("\\bottomrule\\end{tabular}\n")
    # --- font comparison (rigid)
    fr = []
    for p in glob.glob(os.path.join(res, "fontcmp_recipes_*.json")):
        R = json.load(open(p))
        if R: fr.append(R[0])
    if fr:
        fr.sort(key=lambda r: r["sse"])
        with open(os.path.join(outdir, "fonts_rigid.tex"), "w") as o:
            o.write("\\begin{tabular}{rllrr}\\toprule\n\\# & font & family & SSE & $\\Delta$ to best \\\\ \\midrule\n")
            for i, r in enumerate(fr, 1):
                o.write("%d & %s & %s & %.1f & %+.1f \\\\\n" % (i, tex(NICE.get(r["font"], r["font"])), tex(family(r["font"])), r["sse"], r["sse"] - fr[0]["sse"]))
            o.write("\\bottomrule\\end{tabular}\n")
        best_other = next(r for r in fr if family(r["font"]) != "Palatino")
        mac.update(FontBest="%.1f" % fr[0]["sse"], FontBestName=tex(NICE.get(fr[0]["font"], fr[0]["font"])),
                   FontOtherBest="%.1f" % best_other["sse"], FontOtherName=tex(NICE.get(best_other["font"], best_other["font"])),
                   FontMargin="%.0f" % (best_other["sse"] - fr[0]["sse"]), FontN=str(len(fr)),
                   FontPalTop=str(sum(1 for r in fr[:next(i for i, r in enumerate(fr) if family(r["font"]) != "Palatino")])))
    # --- the game's own dialog font
    g1 = J(res, "fontcmp_recipes_SM64-dialog.json"); g2 = J(res, "recipes_SM64-dialog_full.json")
    if g1: mac["GameRigid"] = "%.0f" % g1[0]["sse"]; mac["GameRigidRatio"] = "%.1f" % (g1[0]["sse"] / 165.7)
    if g2: mac["GameFull"] = "%.0f" % g2[0]["sse"]; mac["GameFullInterp"] = tex(g2[0]["frac"])
    if fr and g1:
        allr = sorted([r["sse"] for r in fr]); mac["GameRank"] = str(1 + sum(1 for v in allr if v < g1[0]["sse"])); mac["GameOf"] = str(len(allr))
    T0 = J(res, "font_tournament_flexible.json")
    if T0 and "SM64 dialog font" in T0["refined"]: mac["GameFlex"] = "%.0f" % T0["refined"]["SM64 dialog font"]
    # --- claims
    C = J(res, "claims_PalatinoBoldItalic.json"); C2 = J(res, "claims_P052-BoldItalic.json")
    if C:
        other = {c["id"]: c for c in (C2["claims"] if C2 else [])}
        with open(os.path.join(outdir, "claims.tex"), "w") as o:
            o.write("\\begin{tabular}{>{\\raggedright\\arraybackslash}p{2.7cm}>{\\raggedright\\arraybackslash}p{2.0cm}>{\\raggedright\\arraybackslash}p{4.0cm}rrrr}\\toprule\n line 1 & line 2 & proposed by & \\multicolumn{2}{c}{line-1 SSE} & \\multicolumn{2}{c}{line-2 SSE} \\\\\n"
                    " & & & Apple & URW & Apple & URW \\\\ \\midrule\n")
            for c in C["claims"]:
                d = other.get(c["id"], {})
                f = lambda v: "%.0f" % v if isinstance(v, (int, float)) else "--"
                o.write("``%s'' & %s & %s & %s & %s & %s & %s \\\\\n" % (tex(c["line1"]), "(not claimed)" if c["line2"] is None else "``%s''" % tex(c["line2"]),
                        tex(c["who"]), f(c["line1_sse"]), f(d.get("line1_sse")), f(c.get("line2_sse_joint")), f(d.get("line2_sse_joint"))))
            o.write("\\bottomrule\\end{tabular}\n")
        exc = C["row20_excess"]; mac.update(DescCol="%d" % int(np.argmax(exc)), DescVal="%.1f" % max(exc), StoneSD="%.2f" % C["stone_sd"],
                                            DescSecond="%.1f" % sorted(exc[4:27])[-2])
        for c in C["claims"]:
            key = "Claim" + {"lisreal": "LisReal", "lisreal2041": "LisRealAlt", "secretstar": "SecretStar",
                             "lisrealstar": "LisRealStar", "eternal": "Eternal", "myhopeis": "MyHopeIs", "myhopeis_lc": "MyHopeIsLc",
                             "lieherestar": "LieHere", "ours": "Ours", "ours_lc": "OursLc"}.get(c["id"], "X")
            mac[key + "One"] = "%.0f" % c["line1_sse"]
            if c.get("line2_sse_joint") is not None: mac[key + "Two"] = "%.0f" % c["line2_sse_joint"]
    # --- line-2 endings / final variants
    A = J(res, "line2_final_PalatinoBoldItalic.json"); B = J(res, "line2_final_P052-BoldItalic.json")
    if A and B:
        a = {r["phrase"]: r["sse"] for r in A}; b = {r["phrase"]: r["sse"] for r in B}
        ks = sorted(set(a) & set(b), key=lambda k: a[k] + b[k])
        with open(os.path.join(outdir, "line2_variants.tex"), "w") as o:
            o.write("\\begin{tabular}{lrrr}\\toprule\n line 2 & Apple Palatino BI & URW P052 BI & mean \\\\ \\midrule\n")
            for k in ks:
                if k.startswith("Wt "): continue
                o.write("``%s'' & %.1f & %.1f & %.1f \\\\\n" % (tex(k), a[k], b[k], (a[k] + b[k]) / 2))
            o.write("\\bottomrule\\end{tabular}\n")
    # --- line-2 variants + close-ups from the candidates run (both fonts)
    A = J(res, "line2_candidates_PalatinoBoldItalic.json"); B = J(res, "line2_candidates_P052-BoldItalic.json")
    if A and B:
        ks = sorted(A["variants"], key=lambda k: A["variants"][k]["sse"] + B["variants"][k]["sse"])
        with open(os.path.join(outdir, "line2_variants.tex"), "w") as o:
            o.write("\\begin{tabular}{lrrrl}\\toprule\n line 2 & Apple & URW & mean & complete sentence? \\\\ \\midrule\n")
            for k in ks:
                a, b = A["variants"][k]["sse"], B["variants"][k]["sse"]
                ok = "yes" if k in ("We hope so", "We hope so.", "We hope so!", "We hope on", "We hope for it", "We hope to see", "My hope is",
                                    "my hope is", "He hopes so", "I hope so", "We Hope So", "No hope so", "To hope is") else "no"
                o.write("``%s'' & %.0f & %.0f & %.0f & %s \\\\\n" % (tex(k), a, b, (a + b) / 2, ok))
            o.write("\\bottomrule\\end{tabular}\n")
        for part in ("first", "ending"):
            for tag, X in (("A", A), ("B", B)):
                d = X[part]; key = (lambda k: k.split(" ")[0]) if part == "first" else (lambda k: k.split(" ", 2)[2])
                loc = {key(k): v["local"][part] for k, v in d.items()}
                for w in (("We", "By", "Me", "He", "My", "No") if part == "first" else ("so", "he", "or", "us", "to", "for", "is", "on")):
                    if w in loc: mac["Loc%s%s%s" % ("F" if part == "first" else "E", tag, "".join(ch for ch in w.title() if ch.isalpha()))] = "%.0f" % loc[w]
                mac["Loc%sBest%s" % ("F" if part == "first" else "E", tag)] = "%.0f" % min(loc.values())
    # --- alternative sentences (Be/By first words, "Be with us", Japanese-English phrasings)
    A = J(res, "line2_bewithus_PalatinoBoldItalic.json"); B = J(res, "line2_bewithus_P052-BoldItalic.json")
    if A and B:
        a = {r["phrase"]: r["sse"] for r in A["exact"]}; b = {r["phrase"]: r["sse"] for r in B["exact"]}
        ks = sorted(set(a) & set(b), key=lambda k: a[k] + b[k])
        with open(os.path.join(outdir, "line2_alternatives.tex"), "w") as o:
            o.write("\\begin{tabular}{lrrr}\\toprule\n line 2 & Apple & URW & mean \\\\ \\midrule\n")
            for k in ks: o.write("``%s'' & %.0f & %.0f & %.0f \\\\\n" % (tex(k), a[k], b[k], (a[k] + b[k]) / 2))
            o.write("\\bottomrule\\end{tabular}\n")
    for f, tag in (("PalatinoBoldItalic", "A"), ("P052-BoldItalic", "B")):
        E = J(res, "line2_extra_%s.json" % f)
        if E:
            for w in ("We", "Me", "He", "My", "By", "Be"):
                r = next((r for r in E["exact"] if r["phrase"].split(" ")[0] == w), None)
                if r: mac["Alt%s%s" % (tag, w)] = "%.0f" % r["sse"]; mac["AltPh%s%s" % (tag, w)] = tex(r["phrase"])
    # --- working backwards from 'hope'
    for fn, tag in (("hopefit_PalatinoBoldItalic.json", "U"), ("hopefit_apple_line2.json", "A")):
        H = J(res, fn)
        if not H: continue
        b = H["best"]
        mac.update({"Hope%sSize" % tag: str(b["P2"]), "Hope%sTrack" % tag: "%+d" % b["tracking2"], "Hope%sFit" % tag: "%.1f" % b["sse_hope"]})
        for part, key, ws in (("first", lambda k: k.split(" ")[0], ("We", "Me", "By", "He", "My", "Wr", "Wi")),
                              ("ending", lambda k: k.split(" ", 2)[2], ("so", "or", "us", "he", "as", "no", "nr", "se"))):
            loc = {key(k): v["local"][part] for k, v in H[part].items()}
            for w in ws:
                if w in loc: mac["Hope%s%s%s" % (tag, "F" if part == "first" else "E", w.title())] = "%.0f" % loc[w]
        V = {k: v["sse"] for k, v in H["variants"].items()}
        for k in ("We hope so", "We hope or", "We hope us", "We hope he", "We hope no", "We hope so.", "My hope is", "Be with us", "By hope so"):
            if k in V: mac["Hope%sV%s" % (tag, "".join(ch for ch in k.title() if ch.isalpha()))] = "%.0f" % V[k]
    for fn, tag in (("line2_dp_hopefit_P052line2.json", "U"), ("line2_dp_hopefit_Appleline2.json", "A")):
        D2 = J(res, fn)
        if not D2: continue
        ex = D2["exact"]; order = [r["phrase"] for r in ex]
        mac["HopeDP%sBest" % tag] = "%.1f" % ex[0]["sse"]; mac["HopeDP%sBestPh" % tag] = tex(ex[0]["phrase"])
        for ph in ("We hope so", "We hope So"):
            if ph in order: mac["HopeDP%sRank%s" % (tag, "Lc" if ph.endswith("so") else "Uc")] = str(order.index(ph) + 1); mac["HopeDP%sSse%s" % (tag, "Lc" if ph.endswith("so") else "Uc")] = "%.1f" % ex[order.index(ph)]["sse"]
    S2 = J(res, "simulation_hopefit.json")
    if S2:
        mac.update(HSimN=str(len(S2)), HSimExact=str(sum(1 for r in S2 if r["rank"] == 1)), HSimMaxGap="%.0f" % max(r["gap"] for r in S2),
                   HSimWordPct="%.0f" % (100 * sum(r["words_ok"] for r in S2) / sum(r["n_words"] for r in S2)))
    # --- joint two-line case test
    for f, tag in (("PalatinoBoldItalic", "A"), ("P052-BoldItalic", "U")):
        Jc = J(res, "joint_case_%s.json" % f)
        if Jc and "Eternal Star" in Jc and "Eternal star" in Jc:
            up, lo_ = Jc["Eternal Star"][0], Jc["Eternal star"][0]
            mac.update({"Joint%sUp" % tag: "%.1f" % up["total"], "Joint%sLo" % tag: "%.1f" % lo_["total"],
                        "Joint%sUpLTwo" % tag: "%.1f" % up["line2"], "Joint%sLoLTwo" % tag: "%.1f" % lo_["line2"],
                        "Joint%sDiff" % tag: "%.1f" % (lo_["total"] - up["total"])})
    # --- inversion similarity
    Iv = J(res, "inversion_similarity.json")
    if Iv:
        sm = Iv["similarity"]["sparse+tv"]
        for n, key in (("Eternal Star / We hope so", "Ours"), ("Eternal Star / My hope is", "MyHope"), ("A Secret star / lie here ~", "Secret"),
                       ("L is real 2401 / (row 2 not claimed)", "LisReal")):
            if n in sm:
                mac["Inv%sOne" % key] = "%.2f" % sm[n]["row1"]
                if sm[n]["row2"] is not None: mac["Inv%sTwo" % key] = "%.2f" % sm[n]["row2"]
    # --- the artist's font file (Adobe Type 1 Palatino)
    A = (J(res, "fontver.json") or []) + (J(res, "fontver_adobe.json") or [])
    if A:
        rows = sorted([r for r in A if r["ss"] == 1], key=lambda r: r["total"])
        with open(os.path.join(outdir, "fontver.tex"), "w") as o:
            o.write("\\begin{tabular}{lrrrr}\\toprule\n digitisation & line 1 & line 2 & total & hole (19,8) \\\\ \\midrule\n")
            for r in rows: o.write("%s & %.1f & %.1f & %.1f & %.1f \\\\\n" % (tex(NICE.get(r["font"], r["font"])), r["line1"], r["line2"], r["total"], r["hole_19_8"]))
            o.write("\\bottomrule\\end{tabular}\n")
        ad = next((r for r in rows if r["font"].startswith("AdobePalatino-Bold")), None)
        if ad:
            nxt = next(r for r in rows if r is not ad)
            mac.update(AdobeLineOne="%.1f" % ad["line1"], AdobeLineTwo="%.1f" % ad["line2"], AdobeTotal="%.1f" % ad["total"],
                       AdobeNextTotal="%.1f" % nxt["total"], AdobeGain="%.0f" % (nxt["total"] - ad["total"]), AdobeHoleW="%.1f" % ad["hole_19_8"],
                       AdobeHoleE="%.1f" % ad["hole_10_9"])
    for fn, tag in (("line2_dp_AdobePalatino.json", "AdobeDP"), ("line2_dp_hopefit_adobe.json", "AdobeDPHope")):
        D2 = J(res, fn)
        if D2:
            ex = D2["exact"]; mac[tag + "Top"] = tex(ex[0]["phrase"]); mac[tag + "TopSse"] = "%.1f" % ex[0]["sse"]
            mac[tag + "Second"] = tex(ex[1]["phrase"]); mac[tag + "SecondSse"] = "%.1f" % ex[1]["sse"]
    H = J(res, "hopefit_adobe.json")
    if H:
        loc = {k.split(" ", 2)[2]: v["local"]["ending"] for k, v in H["ending"].items()}
        mac.update(AdobeEndSo="%.1f" % loc["so"], AdobeEndNr="%.1f" % loc.get("nr", float("nan")), AdobeEndOr="%.1f" % loc.get("or", float("nan")))
    R = J(res, "recipes_AdobePalatino-BoldItalic.json")
    if R:
        r = R[0]; mac.update(AdobeCanvas="%d$\\times$%d" % (32 * r["kx"], 32 * r["ky"]), AdobeP=str(r["P"]), AdobeTrack="%+d" % r["tracking"],
                             AdobeGamma="%.1f" % r["gamma"], AdobeBlur="%.2f" % r["blur"], AdobeRatio="%.2f" % (r["sse"] / 165.7))
    # --- simulation
    S = J(res, "simulation_P052-BoldItalic.json")
    if S:
        mac.update(SimN=str(len(S)), SimExact=str(sum(1 for r in S if r["rank"] == 1)), SimTopTen=str(sum(1 for r in S if r["rank"] and r["rank"] <= 10)),
                   SimWords="%d/%d" % (sum(r["words_ok"] for r in S), sum(r["n_words"] for r in S)),
                   SimWordPct="%.0f" % (100 * sum(r["words_ok"] for r in S) / sum(r["n_words"] for r in S)), SimMaxGap="%.0f" % max(r["gap"] for r in S))
    D = J(res, "line2_dp_PalatinoBoldItalic.json")
    if D and S:
        mac["WindowHi"] = "%.0f" % (D["exact"][0]["sse"] + max(r["gap"] for r in S)); mac["WindowLo"] = "%.0f" % D["exact"][0]["sse"]
    if D:
        top = D["exact"][:60]
        mac.update(DPHopeShare="%d" % sum(1 for r in top if " hope" in " " + r["phrase"]), DPBest="%.1f" % top[0]["sse"], LineTwoStone="%.1f" % D["stone"])
    with open(os.path.join(outdir, "numbers.tex"), "w") as o:
        for k, v in sorted(mac.items()): o.write("\\newcommand{\\%s}{%s}\n" % (k, v))
    log("tables + %d number macros -> %s" % (len(mac), outdir))
