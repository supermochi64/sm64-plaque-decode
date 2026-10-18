"""The plaque challenge: try to disprove "Eternal Star / We hope so".  (See CHALLENGE.md for the rules.)

Challenge 1, "Beat Eternal Star": score any reading of the plaque exactly the way every published reading was scored
(fixed stone, line 1 gets its own designer-recipe search, line 2 its own best size and position):
    python -m plaquedecode.challenge score "Eternal Star" "We hope so"
    python -m plaquedecode.challenge score "L is real 2401"                      # line 1 only
    python -m plaquedecode.challenge score "My line 1" "my line 2" --font SomeOtherFont.ttf

Challenge 2, "Fool the decoder": write a secret English word into your copy of the real plaque as "<word> Star"
(deterministic; same procedure as the 50-word blind test), publish the PNG and the hash, let us decode it:
    python -m plaquedecode.challenge make   --word Harness --out my_plaque.png    # prints the hash to publish
    python -m plaquedecode.challenge decode --png my_plaque.png                   # what the decoder reads
    python -m plaquedecode.challenge verify --png my_plaque.png --word Harness --salt <salt>   # anyone can check

Needs texture.npy (python -m plaquedecode extract), the fixed stone (python -m plaquedecode stone), the font in fonts/,
and PLAQUE_STONE=stone/stone_box.npy PLAQUE_STONE_VAR=stone/stone_box_var.npy PLAQUE_L2_RATIO=1.10 in the environment.
"""
import argparse, hashlib, json, os, secrets
import numpy as np
from PIL import Image
from .__main__ import log, load_T, best_recipe

LEADERBOARD = "results/challenge_leaderboard.json"


def vocab_check(text, vocab_file="data/vocab_en_core.txt"):
    words = {w.strip().lower() for w in open(vocab_file, encoding="utf-8") if w.strip()}
    bad = [w for w in text.replace("~", " ").split() if w.lower().strip(".,!?'") not in words]
    return bad


def score(a):
    from .core import Line1, Line2, search_recipes, Recipe
    from .claims import FULL, line2_score
    T = load_T(a.texture); l1 = Line1(T); font = a.font
    if a.line1 == "Eternal Star" and font == "AdobePalatino-BoldItalic.pfb" and os.path.exists(a.recipes):
        rec = best_recipe(a.recipes)
    else:
        log("recipe search for %r in %s (about a minute) ..." % (a.line1, font))
        rec = sorted(search_recipes(l1, a.fonts_dir, font, a.line1, **FULL), key=lambda r: r.sse)[0]
    s1 = rec.sse; s2 = None
    if a.line2:
        s2, cfg = line2_score(Line2(T, rec, a.fonts_dir, line1_text=a.line1), a.line2)
    total = s1 + (s2 if s2 is not None else 0.0)
    for t in (a.line1, a.line2 or ""):
        bad = vocab_check(t) if t else []
        if bad: log("NOTE: not in the core English word list (rule 1): %s" % bad)
    log("line 1 %r: %.1f" % (a.line1, s1) + ("   line 2 %r: %.1f   whole plaque: %.1f" % (a.line2, s2, total) if a.line2 else "   (no line 2 claimed)"))
    if os.path.exists(LEADERBOARD):
        board = json.load(open(LEADERBOARD))
        key = "total" if a.line2 else "line1"; ref = [r for r in board if r.get(key) is not None]
        rank = 1 + sum(1 for r in ref if r[key] < (total if a.line2 else s1))
        best = min(ref, key=lambda r: r[key])
        log("rank %d of %d on the %s leaderboard (best: %r %.1f)" % (rank, len(ref) + 1, "whole-plaque" if a.line2 else "line-1", best["reading"], best[key]))
    out = dict(reading=a.line1 + (" / " + a.line2 if a.line2 else ""), font=font, line1=round(s1, 1), line2=None if s2 is None else round(s2, 1),
               total=round(total, 1) if a.line2 else None)
    print(json.dumps(out))
    return out


def _plaque(T, rec, word, m, ink, shE, wE):
    """deterministic: real texture with the fitted 'Eternal Star' ink replaced by '<word> Star' (line re-centred), 5-bit."""
    from .blind import ink as ink_of
    import torch
    shW = shE + int(round((wE - m.width(word)) / 2)); R0, R1 = m.l1.R0, m.l1.R1
    Ts = np.array(T, dtype=np.float32)
    band = torch.as_tensor(Ts[R0:R1], device=m.dev) - ink * ink_of(m, "Eternal", shE) + ink * ink_of(m, word, shW)
    Ts[R0:R1] = band.cpu().numpy(); return np.clip(np.round(Ts), 0, 31).astype(np.uint8)


def _setup(a):
    from .firstword import Model
    T = load_T(a.texture); rec = best_recipe(a.recipes); m = Model(T, rec, a.fonts_dir)
    sc, sh = m.exact(["Eternal"]); shE = int(sh[0]); wE = m.width("Eternal")
    from .blind import ink as ink_of
    aE = ink_of(m, "Eternal", shE).reshape(-1); Ma = m.l1.M @ aE; L = float((Ma @ m.l1.Mt) / (Ma @ Ma))
    return T, rec, m, L, shE, wE


def make(a):
    w = a.word.strip(); w = w[:1].upper() + w[1:]
    if not (w.isalpha() and w.isascii() and 4 <= len(w) <= 10): raise SystemExit("rule 2: one English word, 4-10 letters A-Z")
    if vocab_check(w): raise SystemExit("rule 2: %r is not in data/vocab_en_core.txt (common English words only)" % w)
    T, rec, m, L, shE, wE = _setup(a)
    if abs(m.width(w) - wE) > 24: raise SystemExit("rule 2: %r is too wide or too narrow for the plaque (width %d, allowed %d-%d)" % (w, m.width(w), wE - 24, wE + 24))
    P = _plaque(T, rec, w, m, L, shE, wE); Image.fromarray(P * 8).save(a.out)
    salt = a.salt or secrets.token_hex(8); h = hashlib.sha256((salt + ":" + w).encode()).hexdigest()
    png = hashlib.sha256(open(a.out, "rb").read()).hexdigest()
    log("wrote %s. PUBLISH: the image and this hash: %s   KEEP SECRET until the answer: word %r, salt %s" % (a.out, h, w, salt))
    log("(image file SHA-256 %s)" % png)


def decode(a):
    from .blind import decode_one
    _, rec, _, L, _, _ = _setup(a)
    P = np.asarray(Image.open(a.png).convert("L")).astype(np.float32) / 8.0
    a.ink = L; a.big_vocab = "data/vocab_big.txt"
    r = decode_one(P, rec, a)
    core = {x.strip().lower() for x in open("data/vocab_en_core.txt", encoding="utf-8")}
    real = [w for w in r["words"] if w.lower() in core]
    log("top strings: %s" % [w for w, _, _ in r["top"][:10]])
    log("ANSWER (best real English word): %r   (%d strings scored)" % (real[0] if real else None, r["n_scored"]))


def verify(a):
    w = a.word.strip(); w = w[:1].upper() + w[1:]
    T, rec, m, L, shE, wE = _setup(a)
    P = _plaque(T, rec, w, m, L, shE, wE); Q = np.asarray(Image.open(a.png).convert("L")) // 8
    same = bool((P == Q).all()); h = hashlib.sha256((a.salt + ":" + w).encode()).hexdigest()
    log("image regenerated from %r is %s the published one; hash of salt+word: %s" % (w, "IDENTICAL to" if same else "DIFFERENT from", h))


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("score", "make", "decode", "verify"):
        s = sub.add_parser(n); s.add_argument("--texture", default="texture.npy"); s.add_argument("--fonts-dir", default="fonts")
        s.add_argument("--recipes", default="results/stone_recipes_Adobe.json")
        if n == "score": s.add_argument("line1"); s.add_argument("line2", nargs="?"); s.add_argument("--font", default="AdobePalatino-BoldItalic.pfb")
        if n == "make": s.add_argument("--word", required=True); s.add_argument("--out", default="my_plaque.png"); s.add_argument("--salt")
        if n == "decode":
            s.add_argument("--png", required=True); s.add_argument("--K", type=int, default=60000); s.add_argument("--maxlen", type=int, default=10)
            s.add_argument("--wtol", type=int, default=24); s.add_argument("--keep", type=int, default=100); s.add_argument("--keep-words", type=int, default=20000)
        if n == "verify": s.add_argument("--png", required=True); s.add_argument("--word", required=True); s.add_argument("--salt", required=True)
    a = ap.parse_args(); {"score": score, "make": make, "decode": decode, "verify": verify}[a.cmd](a)


if __name__ == "__main__":
    main()
