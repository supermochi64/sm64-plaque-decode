# Fonts

No fonts are distributed with this repository. Put font files in this folder (or pass `--fonts-dir`).

| file name expected | what | where to get it | needed for |
|---|---|---|---|
| `P052-BoldItalic.otf` | URW P052 Bold Italic — free, metric-compatible clone of Palatino Bold Italic (URW base35) | <https://github.com/ArtifexSoftware/urw-base35-fonts> (AGPL + font exception); also shipped by Ghostscript (`gsfonts`) | **everything** — reproduces the main result |
| `PalatinoBoldItalic.ttf` | Apple System 7.5.3 (1996) Palatino Bold Italic, converted to TrueType | your own copy of Mac OS 7.5.3 (commercial, Linotype/Apple — not redistributable) | the "genuine 1996 font" columns |
| `AdobePalatino-BoldItalic.pfb` | Adobe Type 1 Palatino Bold Italic 001.005 (1990), e.g. from an *Adobe Type Basics* disc | your own licensed copy (commercial — not redistributable) | the best-fitting font (report section "The artist's font file") |
| other URW base35 faces (`NimbusRoman-*`, `C059-*`, `URWBookman-*`, `NimbusSans-*`, `URWGothic-*`, `Z003-*`, `NimbusMonoPS-*`) | free clones of Times, New Century Schoolbook, Bookman, Helvetica, Avant Garde, Zapf Chancery, Courier | same URW repository | font-family comparison |

Any other font can be tested with `python -m plaquedecode recipe --font <file> --stage fontcmp`.
