"""Blind test of the first-word decoder: does it find a word it was NOT told?

make   : draws N secret English words (data/vocab_en_core.txt, 4-10 letters, capitalised, width within --wtol of
         "Eternal" so "Star" still lands on its pixels) with the OS random generator, and builds one synthetic plaque
         per word: the real texture with the ink of the fitted "Eternal Star" replaced by the ink of "<word> Star"
         (same locked recipe, same ink level, line re-centred), so the real stone AND the real fit residual stay.
         The words go to <secret_dir>/secret.json; <dir>/sealed.json holds a SHA-256 of every salted word and of the
         whole secret file (publish/commit that hash BEFORE decoding).
decode : decodes every synthetic plaque exactly like firstword.py decodes the real one (vocabulary + blind
         letter-by-letter beam, width filter, exact rescoring); reads only <dir>/plaque_XX.npy, never the secret.
score  : opens the secret, checks the hashes, and reports the rank of every true word.
    PLAQUE_STONE=stone/stone_box.npy PLAQUE_STONE_VAR=stone/stone_box_var.npy \
    python -m plaquedecode.blind make   --recipes results/stone_recipes_Adobe.json --n 20 --dir blind --secret-dir blind_secret
    python -m plaquedecode.blind decode --recipes results/stone_recipes_Adobe.json --dir blind
    python -m plaquedecode.blind score  --dir blind --secret-dir blind_secret --out results/blind_firstword.json
The synthetic plaques contain the real texture (Nintendo data): they stay local (*.npy is git-ignored).
"""
import argparse, glob, hashlib, json, os, secrets, time
import numpy as np
import torch
from .__main__ import log, load_T, best_recipe
from .firstword import Model, beam, OFFP


def ink(m, word, shift):
    """gamma-applied coverage (H x 32) of '<word> Star' at a line shift."""
    idx, pen = m.encode([word]); lin = m.TT[idx, (pen + shift + OFFP).clamp(0, m.NP - 1)].sum(1)[0]
    return lin.clamp(0, 1) ** m.rec.gamma


def make(a, T, rec):
    m = Model(T, rec, a.fonts_dir); wE = m.width("Eternal")
    sc, sh = m.exact(["Eternal"]); shE = int(sh[0])
    aE = ink(m, "Eternal", shE).reshape(-1); Ma = m.l1.M @ aE; L = float((Ma @ m.l1.Mt) / (Ma @ Ma))
    pool = sorted({w.strip()[:1].upper() + w.strip()[1:] for w in open(a.vocab, encoding="utf-8")
                   if w.strip().isalpha() and w.strip().isascii() and 4 <= len(w.strip()) <= 10})
    pool = [w for w in pool if w != "Eternal" and abs(m.width(w) - wE) <= a.wtol]
    rng = secrets.SystemRandom(); words = rng.sample(pool, a.n)
    os.makedirs(a.dir, exist_ok=True); os.makedirs(a.secret_dir, exist_ok=True)
    R0, R1 = m.l1.R0, m.l1.R1; sealed, secret = [], []
    for k, w in enumerate(words):
        shW = shE + int(round((wE - m.width(w)) / 2))                            # the artist centres the line
        Ts = np.array(T, dtype=np.float32)
        band = torch.as_tensor(Ts[R0:R1], device=m.dev) - L * ink(m, "Eternal", shE) + L * ink(m, w, shW)
        Ts[R0:R1] = band.cpu().numpy(); np.save(os.path.join(a.dir, "plaque_%02d.npy" % k), Ts)
        salt = secrets.token_hex(16); secret.append(dict(k=k, word=w, salt=salt, shift=shW))
        sealed.append(dict(k=k, sha256=hashlib.sha256((salt + w).encode()).hexdigest()))
    sj = json.dumps(secret, indent=1); open(os.path.join(a.secret_dir, "secret.json"), "w").write(sj)
    meta = dict(n=a.n, pool=len(pool), vocab=os.path.basename(a.vocab), wtol=a.wtol, width_Eternal=wE, ink=L,
                secret_file_sha256=hashlib.sha256(sj.encode()).hexdigest(), plaques=sealed)
    json.dump(meta, open(os.path.join(a.dir, "sealed.json"), "w"), indent=1)
    log("made %d blind plaques from a pool of %d words; secret file SHA-256 %s" % (a.n, len(pool), meta["secret_file_sha256"]))


def decode_one(T, rec, a):
    m = Model(T, rec, a.fonts_dir); wE = m.width("Eternal")                   # same width window as the real decode
    vocab = {w.strip() for w in open(a.big_vocab, encoding="utf-8") if w.strip()}
    vocab = {v for w in vocab for v in (w, w[:1].upper() + w[1:]) if v.isalpha() and v.isascii() and 2 <= len(v) <= 14}
    L_ink = a.ink                                                               # plaque ink level, not secret (beam pruning only;
                                                                                # the exact rescoring fits the ink freely)
    cands = set(vocab); beamset = set()
    for sh in (-12, -6, 0, 6, 12):
        b = beam(m, L_ink, sh, a.K, a.maxlen); cands.update(b); beamset.update(b)
    fit = sorted(w for w in cands if abs(m.width(w) - wE) <= a.wtol)
    sc, _ = m.exact(fit); order = np.argsort(sc)
    return dict(n_scored=len(fit), top=[(fit[i], round(float(sc[i]), 2), fit[i] in beamset) for i in order[:a.keep]],
                words=[fit[i] for i in order[:a.keep_words]])


def decode(a, rec):
    a.ink = json.load(open(os.path.join(a.dir, "sealed.json")))["ink"]
    for f in sorted(glob.glob(os.path.join(a.dir, "plaque_*.npy"))):
        out = f[:-4] + "_decoded.json"
        if os.path.exists(out): continue
        t0 = time.time(); r = decode_one(np.load(f), rec, a); json.dump(r, open(out, "w"))
        log("%s: top %s  (%d scored, %.0f s)" % (os.path.basename(f), [w for w, _, _ in r["top"][:5]], r["n_scored"], time.time() - t0))


def score(a):
    meta = json.load(open(os.path.join(a.dir, "sealed.json"))); sj = open(os.path.join(a.secret_dir, "secret.json")).read()
    assert hashlib.sha256(sj.encode()).hexdigest() == meta["secret_file_sha256"], "secret file was changed"
    vocab = {w.strip() for w in open(a.vocab, encoding="utf-8") if w.strip()}
    vocab |= {w[:1].upper() + w[1:] for w in vocab}
    rows = []
    for s, p in zip(json.loads(sj), meta["plaques"]):
        assert hashlib.sha256((s["salt"] + s["word"]).encode()).hexdigest() == p["sha256"]
        d = json.load(open(os.path.join(a.dir, "plaque_%02d_decoded.json" % s["k"])))
        order = d["words"]; real = [w for w in order if w in vocab]
        rows.append(dict(k=s["k"], word=s["word"], rank=order.index(s["word"]) + 1 if s["word"] in order else None,
                         rank_among_real_words=real.index(s["word"]) + 1 if s["word"] in real else None,
                         rank_Eternal=order.index("Eternal") + 1 if "Eternal" in order else None,   # leak check: real residual
                         n_scored=d["n_scored"], top5=[w for w, _, _ in d["top"][:5]], best_real_word=real[0] if real else None))
        log("%2d %-12s rank %-6s among real words %-4s  top: %s" % (s["k"], s["word"], rows[-1]["rank"], rows[-1]["rank_among_real_words"], rows[-1]["top5"]))
    n = len(rows); r1 = sum(r["rank"] == 1 for r in rows); w1 = sum(r["rank_among_real_words"] == 1 for r in rows)
    t10 = sum(r["rank"] is not None and r["rank"] <= 10 for r in rows)
    summ = dict(n=n, true_word_rank1=r1, true_word_top10=t10, true_word_best_real_word=w1, secret_file_sha256=meta["secret_file_sha256"],
                note="Blind first-word test: secret capitalised English words (data/vocab_en_core.txt) planted as '<word> Star' into the real "
                     "texture (real stone + real fit residual kept), decoded with the unchanged firstword pipeline. rank = among all scored "
                     "strings (vocabulary + blind beam); rank_among_real_words = among strings in the core English vocabulary.", rows=rows)
    json.dump(summ, open(a.out, "w"), indent=1)
    summ["Eternal_in_top10"] = sum(r["rank_Eternal"] is not None and r["rank_Eternal"] <= 10 for r in rows)
    json.dump(summ, open(a.out, "w"), indent=1)
    log("BLIND: true word #1 overall %d/%d, top 10 %d/%d, best real word %d/%d" % (r1, n, t10, n, w1, n))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["make", "decode", "score"])
    ap.add_argument("--texture", default="texture.npy"); ap.add_argument("--fonts-dir", default="fonts_cmp")
    ap.add_argument("--recipes"); ap.add_argument("--dir", default="blind"); ap.add_argument("--secret-dir", default="blind_secret")
    ap.add_argument("--n", type=int, default=20); ap.add_argument("--vocab", default="data/vocab_en_core.txt")
    ap.add_argument("--big-vocab", default="data/vocab_big.txt"); ap.add_argument("--wtol", type=int, default=24)
    ap.add_argument("--K", type=int, default=40000); ap.add_argument("--maxlen", type=int, default=10)
    ap.add_argument("--keep", type=int, default=100); ap.add_argument("--keep-words", type=int, default=20000)
    ap.add_argument("--out", default="results/blind_firstword.json")
    a = ap.parse_args()
    if a.cmd == "score": return score(a)
    rec = best_recipe(a.recipes)
    if a.cmd == "make": make(a, load_T(a.texture), rec)
    else: decode(a, rec)


if __name__ == "__main__":
    main()
