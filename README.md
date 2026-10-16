# What does the Super Mario 64 courtyard plaque say?

**Short answer — most likely:**

> ***Eternal Star***
> ***We hope so***

…set in **Palatino Bold Italic**, most likely **Adobe's own 1990 PostScript Palatino** (Adobe Type Manager era), and **not** "L is real 2401".
With that font, a blind search over 17.7k English words returns exactly **"We hope so"** as its best string.

The plaque on the star statue in Peach's castle courtyard is a single 32×32 grey texture. Its two lines of text are
3–5 pixels tall, too small to *read*. This project doesn't try to read or upscale it. Instead it **simulates how a
1996 artist made it** and searches for the text that best explains the stored pixels:
1. Type the text in a period font, on a canvas of some size.
2. Resize to 32×32 with a standard filter.
3. Apply blur and gamma.
4. Lay it on the stone.

Millions of fonts, process settings and texts were scored on a GPU, and the method was calibrated on synthetic
plaques with known text.

![real plaque vs. model](report/figures/hero.png)

*Left: the real texture. Right: our best reconstruction: "Eternal Star / We hope so" in Adobe Palatino Bold Italic
(1990), typed on a 190×160 artwork, letters nudged by hand, shrunk to 32×32 (bilinear, light blur, gamma 1.4) on the
extracted stone. Inside the text the model is on average about 1 grey level (of 31) away from the plaque.*

📄 **Full report:** [`report/report.pdf`](report/report.pdf) (LaTeX source in `report/`)

## Key results

| question | answer | evidence |
|---|---|---|
| font | **Palatino Bold Italic** — best of all: Adobe's 1990 Type 1 original | best of ~530 era fonts and of every Palatino digitisation 1990–1999 (Adobe, Apple, URW, Linotype); wins an identical rigid process search against Times, New Century Schoolbook, Bookman, Georgia, Helvetica, Zapf Chancery, Courier… |
| in-game font? | **No** | SM64's own dialog font (extracted from the ROM, same process search) fits far worse than Palatino and ranks near the bottom |
| process | with Adobe's file: **192×160** artwork, **26 px** type, tracking +2, whole-pixel advances, **bilinear** resize, blur σ≈0.3 px, **gamma 1.4** | the free URW clone and the genuine Apple 1996 Palatino independently converge on 160×128, 23 px, tracking +1, blur 0.45, gamma 1.8 |
| plain stone (2nd pass) | same recipe, same words | the stone behind the text extracted (only 235 pixels inside two text boxes inpainted, the rest verbatim) and held fixed: the recipe search returns exactly the Adobe recipe again; "Star" #1 of 12,547 words; "L is real 2401" 2,031 vs "Eternal Star" 789 |
| every string (2nd pass) | the pixels force the shape, language picks the word | all 949,104 3–4-letter strings after "Eternal ": "Star" rank 14, everything ahead is "St/Sl + round + short letter" (Stoi, Stni, Stai, Stor…); line 2: "We" rank 8 of all 1–3-letter strings, "so" rank 4, "hope" rank 40 of 456,976 — each time only same-shape non-words ahead (`python -m plaquedecode.exhaustive`) |
| was Palatino available? | yes — exactly this Adobe file | IRIX 5.3 (SGI, 1995) ships no Palatino, but its doc viewer expects `/usr/lib/DPS/outline/base/Palatino-BoldItalic` and IRIX's `typeoncall` installs fonts from Adobe's PC *Type On Call* disc, whose Palatino Bold Italic metrics are byte-identical to the 1990 file used here |
| 470 era fonts (2nd pass) | Adobe 1990 Palatino still #1 | everything an artist could have had in 1993–96: IRIX 5.3 + Showcase, Illustrator 5.5 for IRIX (221 Adobe/ITC faces), Adobe 1990 Type 1 disc, CorelDRAW 6/7 (Bitstream), Office 4.3, Font Pack 2, KanjiTalk 7.5, System 7.5.3, Mac OS 9, Photoshop 3 ATM, FreeHand 5, Windows 3.1/95 JP: the 12 best distinct faces are all Palatino versions or close derivatives; best other design Schneidler Black Italic 926, IRIX Times BI 1,116 (`results/era_fonts_stone.json`) |
| line 1 | **Eternal Star** (capital or lower-case s undecided) | "Star" is rank 1 of 27,122 words with every setting frozen; rivals lose even with their own recipe search |
| line 2 | **We hope so** | same process, centred, same ink level; "hope" is rank 1 of 12,556 middle words. Fitting line 2's own typesetting on "hope" alone makes "We" and "so" the best real words on their own (held-out) pixels, and the unconstrained dictionary search then finds "We hope so" among its top 3 |
| inversion | supports it | running the fitted process backwards: the inverted plaque correlates 0.74 / 0.76 (row 1 / row 2) with inverted "Eternal Star / We hope so", vs 0.29 for "L is real 2401" and 0.30 for "A Secret star" |
| list-bias test | the sentence list does not invent the answer | planting 34 phrases that are NOT in the curated list and decoding them with the list: the list's best sentence lands inside the pixel-compatible window in only 5/34 (2/28 for text unrelated to "hope"; median gap 130 vs 0 on the real plaque) and never returns "We hope so"; all 8 in-list controls are recovered exactly (`results/listbias_adobe.json`, `python -m plaquedecode.listbias`) |
| designer steps (3rd pass) | hand kerning + a slightly narrower artwork are real; effects are not | both lines on one artwork, every step tested against noise-only fake plaques: hand kerning line 1 789 → 695, line 2 262 → 201 (fakes ≤ 66 / ≤ 11); artwork **190×160** instead of 192×160 another −41 (fakes 0); Screen/Normal blend, drop shadow, outline, sharpening, moving a line: no better than on noise; emboss borderline; "Lighten" blend ruled out (`python -m plaquedecode.designer`) |
| best version | Adobe Palatino BI (1990), 26 px / 19 px on a 190×160 artwork, hand-kerned, bilinear, blur 0.3, gamma 1.4 | mean error about 1 grey level (of 31) inside the text, 83 % of text pixels within 2 levels; the same 7 pixels stay wrong in every model (E top arm, S top, around the first t, r arm, W gap): bare stone on the plaque where every typeset version has faint ink. They are the pixels that would blur letters together (gaps: 7 of 22 clean) or blur stroke tips (4 of 8 clean), while bottom edges keep their grey (1 of 20): a legibility clean-up of the finished texture by hand |
| in Japanese? (interpretation) | yes, it reads like a Japanese memorial plaque | name + wish, like 「永遠の平和」 + 「を願って」: **Eternal Star** = 永遠の星, **We hope so** = そうであってほしい / そう願っています ("so" points back to the title like そう; "We" is the collective voice Japanese leaves implicit; "I/We hope so" is stock school English). The pixel look-alikes ("We hope or", "He hope so") make no sense as a Japanese wish. Best guess at the intent: 永遠の星――そうであってほしい, "an eternal star, and we hope it truly is" |
| "L is real 2401" | rejected | scored as claimed (whole phrase on row 1, no claim about row 2): row 1 fits about twice as badly as "Eternal Star" |

How much to trust it:
- **Strongly supported:** "Eternal", "Star", "hope".
- **Well supported:** "We".
- **Best-fitting, but by a smaller margin:** "so". It is the best real ending, ahead of "or", "us" and "he".

See the report for the calibration and its limits.

## Reproduce it

You need your **own** Super Mario 64 ROM (US, JP, EU, Shindou or iQue — the texture is identical in all of them). No
Nintendo data is included in this repository.

```bash
git clone https://github.com/supermochi64/sm64-plaque-decode && cd sm64-plaque-decode
pip install -r requirements.txt
python -m plaquedecode extract --rom "Super Mario 64 (USA).z64"        # -> texture.npy (stays local, git-ignored)
# fonts: put P052-BoldItalic.otf (free, URW base35) into fonts/  — see fonts/README.md
R=results/recipes_P052-BoldItalic.json
python -m plaquedecode recipe     --font P052-BoldItalic.otf --stage full   # designer-recipe search for line 1
python -m plaquedecode word2      --recipes $R                              # second word of line 1
python -m plaquedecode line2      --recipes $R --mode dp                    # unconstrained dictionary search, line 2
python -m plaquedecode line2      --recipes $R --mode combo --phrases curated
python -m plaquedecode candidates --recipes $R --line2 results/line2_dp_P052-BoldItalic.json
python -m plaquedecode hopefit    --recipes $R --line2 results/line2_dp_P052-BoldItalic.json --fonts2 P052-BoldItalic.otf
python -m plaquedecode simulate   --recipes $R --line2 results/line2_dp_P052-BoldItalic.json
python -m plaquedecode claims     --font P052-BoldItalic.otf --recipes $R
python -m plaquedecode figures    --out report/figures                     # figures + report/tables from results/
cd report && pdflatex main.tex && pdflatex main.tex
```

Second pass against the plain stone (fonts: put your own `AdobePalatino-BoldItalic.pfb` into `fonts/` or use P052):

```bash
python -m plaquedecode stone                                               # -> stone/stone_box.npy (stays local)
export PLAQUE_STONE=stone/stone_box.npy PLAQUE_STONE_VAR=stone/stone_box_var.npy PLAQUE_L2_RATIO=1.10
python -m plaquedecode recipe --font AdobePalatino-BoldItalic.pfb --stage full --out results/stone_recipes_Adobe.json
python -m plaquedecode word2  --recipes results/stone_recipes_Adobe.json
python -m plaquedecode.exhaustive --recipes results/stone_recipes_Adobe.json --hopefit results/stone_hopefit_Adobe.json \
       --line2 results/stone_line2_dp_Adobe.json --out results/stone_exhaustive_Adobe.json
python -m plaquedecode recipe --font SomeFont.ttf --stage quick             # cheap triage (~6 s per font on a CPU)
python -m plaquedecode.nudge --recipes results/stone_recipes_Adobe.json --top 2000 --out results/stone_nudge_Adobe.json
python -m plaquedecode.nudge --both --recipes results/stone_recipes_Adobe.json --hopefit results/stone_hopefit_Adobe.json \
       --line2 results/stone_line2_dp_hopefit_Adobe.json --out results/stone_nudge_both_Adobe.json      # hand kerning, both lines
python -m plaquedecode.designer [--scale] --recipes results/stone_recipes_Adobe.json --hopefit results/stone_hopefit_Adobe.json \
       --line2 results/stone_line2_dp_hopefit_Adobe.json --out results/stone_designer_Adobe.json        # designer steps vs noise
```

- A CUDA GPU makes the searches take minutes. The CPU works too (`PLAQUE_DEV=cpu`); for the recipe search it is as
  fast as a GPU that is shared with other work.
- All result files behind the report are in `results/`, so the figures and tables can be regenerated without a GPU.
- To test a reading of your own:

```bash
echo "Your reading here" > mine.txt
python -m plaquedecode line2 --recipes results/recipes_P052-BoldItalic.json --mode combo --phrases mine.txt --p2 16,17,18
# with line 2's own typesetting calibrated on "hope":
python -m plaquedecode line2 --recipes results/recipes_P052-BoldItalic.json --hopefit results/hopefit_PalatinoBoldItalic.json \
       --mode combo --phrases mine.txt --p2 17,18,19
```

## Repository layout

| path | content |
|---|---|
| `plaquedecode/` | the maintained pipeline: ROM extraction, forward model, recipe search, word/line decoders, simulation, claims, figures |
| `results/` | JSON results used in the report |
| `report/` | LaTeX source, figures, tables, PDF |
| `data/vocab_en_core.txt` | 17.7k-word English vocabulary (SCOWL/Hunspell-derived) |
| `data/vocab_big.txt` | 268k strings for the exhaustive checks (core + top-120k word frequencies with case variants, names, romaji, Latin, German, archaic, contractions, numbers 0–9999); word frequencies from wordfreq (CC BY-SA 4.0) |
| `fonts/` | put fonts here (none distributed) |

## Legal

- Super Mario 64 is © Nintendo. This repository contains no ROM data, no texture and no Nintendo assets; the texture is
  extracted from your own copy at run time.
- The report reproduces the 32×32 texture in its figures for the purpose of commentary and analysis. The extracted
  stone (`stone/`) is texture-derived and stays local like `texture.npy`.
- No fonts are distributed. The era fonts were tested from archived period media; only their names and scores are
  published.
- Fonts are not distributed.
- The code is MIT-licensed (see `LICENSE`).
