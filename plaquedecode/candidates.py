"""Close-up of the uncertain parts of line 2: the first word ('We') and the ending ('so').

For each candidate the rest of the line is held fixed ("___ hope so" / "We hope ___"), the whole line is rendered
exactly with the locked recipe, and the error is reported both for the whole band and for the 4-column stone blocks
that contain that word only (its LOCAL evidence).  Model predictions are stored so the figures need no GPU."""
import json
import numpy as np
from .core import Line2

FIRST = ["We", "He", "Me", "My", "No", "So", "To", "Tis", "'Tis", "I", "Ye", "Be", "By", "Oh", "Our", "Mr", "Wo", "Wee", "Who",
         "We'll", "Lo", "Mo", "Ha", "Hi", "In", "An", "As", "At", "It", "Is", "Do", "Go", "Us", "Two", "The", "We,"]
JUNK_FIRST = ["Wi", "Wr", "Wt"]                     # best non-words of the exhaustive search (reference)
ENDINGS = ["so", "so.", "so!", "to", "for", "he", "or", "us", "as", "be", "no", "an", "on", "it", "is", "in", "ye", "we", "me", "all",
           "you", "too", "one", "at", "do", "go", "my", "of", "up", "~", "!", "...", "so~"]
JUNK_END = ["ne", "nr", "ae", "se"]         # best non-word endings (reference)
VARIANTS = ["We hope so", "We hope so.", "We hope so!", "We hope for", "We hope he", "We hope to", "We hope on", "We hope it",
            "We hope is", "We hope or", "We hope us", "We hope no", "We hope all", "We hope you", "We hope too", "We hope one",
            "My hope is", "my hope is", "My hope so", "He hopes so", "He hope so", "I hope so", "Me hope so", "No hope so",
            "'Tis hope so", "To hope is", "We Hope So", "We hope", "We hope for it", "We hope to see", "We hope ~", "We hope!"]
REGIONS = {"first": [0, 1, 2], "middle": [3, 4], "ending": [5, 6, 7]}   # 4-col stone blocks: cols 0-11 | 12-19 | 20-31


def score_all(L2, phrases, cfg0):
    out = {}
    for ph in phrases:
        v, cfg = L2.exact_refine(ph, cfg0)
        for P2b in (cfg0[0] - 1, cfg0[0] + 1):
            v2, c2 = L2.exact_refine(ph, (P2b, cfg[1], cfg[2], cfg[3]))
            if v2 < v: v, cfg = v2, c2
        lin = L2.lin_text(ph, *cfg)
        blocks = L2.sse_blocks(lin).cpu().numpy().tolist()
        out[ph] = dict(sse=v, cfg=list(cfg), blocks=blocks,
                       local={k: float(sum(blocks[b] for b in bl)) for k, bl in REGIONS.items()},
                       pred=L2.prediction(lin).cpu().numpy().round(3).tolist())
    return out


def run(T, rec, fdir, line2_best, out, log):
    L2 = Line2(T, rec, fdir)
    cfg0 = (line2_best["P2"], line2_best["esp"], line2_best["x"], line2_best["yb"])
    res = dict(font=rec.font, stone_blocks=L2.sse_blocks(L2.BASE * 0).cpu().numpy().tolist())
    res["first"] = score_all(L2, [w + " hope so" for w in FIRST + JUNK_FIRST], cfg0)
    log("first word: %s" % sorted(((round(v["local"]["first"], 1), k) for k, v in res["first"].items()))[:12])
    res["ending"] = score_all(L2, ["We hope " + e for e in ENDINGS + JUNK_END], cfg0)
    log("ending: %s" % sorted(((round(v["local"]["ending"], 1), k) for k, v in res["ending"].items()))[:12])
    res["variants"] = score_all(L2, VARIANTS, cfg0)
    log("variants: %s" % sorted(((round(v["sse"], 1), k) for k, v in res["variants"].items()))[:12])
    json.dump(res, open(out, "w"))
