"""Modern-font control: prepare every font of the Google Fonts repository for the recipe search.

Download https://github.com/google/fonts/archive/refs/heads/main.zip (~1.7 GB). Static .ttf files are copied as they are;
variable fonts ("Family[wght].ttf", "Family-Italic[wght].ttf") are cut into their named instances Regular / Italic /
Bold / Bold Italic with fontTools' instancer, so every family gets the same style range as the era fonts.
Output: <outdir>/GF-<name>.ttf + a list file (one font name per line). Then score like the era tournament (quick for
all, --stage fontcmp for the quick top 60, --stage full for the fontcmp top 8):
    python -m plaquedecode.modern_fonts main.zip fonts_gf GF_LIST.txt
    while read f; do python -m plaquedecode recipe --font fonts_gf/$f --stage quick --out results/modern_quick/$f.json; done < GF_LIST.txt
Result in this repository: results/modern_fonts_stone.json (4,583 styles; best after the full grid Libertinus Sans
Italic 905.3 vs Adobe Palatino Bold Italic 788.7).
"""
import io, os, re, sys, zipfile
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

KEEP = {"regular", "italic", "bold", "bold italic"}


def safe(s): return re.sub(r"[^A-Za-z0-9_.-]+", "", s)


def one(args):
    """prepare one archive member -> list of output font names (runs in a worker process)."""
    zpath, outdir, n = args; z = zipfile.ZipFile(zpath); out = []; base = os.path.basename(n)[:-4]
    try:
        if "[" in base:
            f = TTFont(io.BytesIO(z.read(n))); fam = base.split("[")[0]
            if "fvar" not in f: return out
            inst_names = {}
            for inst in f["fvar"].instances:
                nm = f["name"].getDebugName(inst.subfamilyNameID) or ""
                if nm.lower() in KEEP: inst_names[nm] = inst.coordinates
            for nm, coords in inst_names.items():
                dst = os.path.join(outdir, "GF-%s-%s.ttf" % (safe(fam), safe(nm)))
                if not os.path.exists(dst):
                    g = instancer.instantiateVariableFont(TTFont(io.BytesIO(z.read(n))), dict(coords), updateFontNames=False); g.save(dst)
                out.append(os.path.basename(dst))
        else:
            dst = os.path.join(outdir, "GF-%s.ttf" % safe(base))
            if not os.path.exists(dst): open(dst, "wb").write(z.read(n))
            out.append(os.path.basename(dst))
    except Exception as e:
        print("  skip", n, str(e)[:60], flush=True)
    return out


def main_parallel(zpath, outdir, listfile, workers=12):
    from multiprocessing import Pool
    z = zipfile.ZipFile(zpath); names = [n for n in z.namelist() if n.lower().endswith(".ttf") and re.search(r"/(ofl|apache|ufl)/", n)]
    print("ttf files in archive:", len(names), flush=True); out = []
    with Pool(workers) as pool:
        for k, r in enumerate(pool.imap_unordered(one, [(zpath, outdir, n) for n in names], chunksize=4)):
            out += r
            if k % 250 == 0: print("  %d/%d done, %d fonts" % (k, len(names), len(out)), flush=True)
    out = sorted(set(out)); open(listfile, "w").write("\n".join(out) + "\n")
    print("modern fonts ready: %d -> %s" % (len(out), listfile))


if __name__ == "__main__":
    main_parallel(*sys.argv[1:4])
