"""press/README.md -> press_report.tex (same text; small Markdown subset).  Build with tectonic/xelatex (xeCJK +
NotoSerifJP-Regular.otf next to the .tex for the Japanese words).    python press/make_pdf.py"""
import os, re
HERE = os.path.dirname(os.path.abspath(__file__))
BASE = "https://github.com/supermochi64/sm64-plaque-decode/blob/main/"
PRE = r"""\documentclass[11pt,a4paper]{article}
\usepackage[margin=2cm]{geometry}
\usepackage{graphicx,booktabs,xcolor,array,hyperref,enumitem,longtable}
\usepackage{xeCJK}\setCJKmainfont[Path=./]{NotoSerifJP-Regular.otf}
\hypersetup{colorlinks=true,urlcolor=blue!60!black,linkcolor=black,pdftitle={Super Mario 64's unreadable plaque, decoded},pdfauthor={mochi64}}
\setlength{\parindent}{0pt}\setlength{\parskip}{6pt}\setlist{itemsep=2pt,topsep=2pt}\pagestyle{empty}
\begin{document}
"""


def inline(t):
    t = t.replace("\\", r"\textbackslash{}")
    for a, b in (("&", r"\&"), ("%", r"\%"), ("#", r"\#"), ("_", r"\_"), ("$", r"\$")):
        t = t.replace(a, b)
    def link(m):
        u = m.group(2).replace(r"\_", "_")
        if not u.startswith("http"):                                              # relative repo links -> absolute GitHub URLs
            import posixpath; path, _, frag = u.partition(r"\#"); u = BASE + posixpath.normpath("press/" + path) + (r"\#" + frag if frag else "")
        return r"\href{%s}{%s}" % (u, m.group(1))
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, t)
    t = re.sub(r"`([^`]+)`", r"\\texttt{\1}", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", t); t = re.sub(r"\*(.+?)\*", r"\\emph{\1}", t)
    t = re.sub(r'"([^"]*)"', r"``\1''", t)
    t = t.replace("~", r"\textasciitilde{}").replace("×", r"$\times$").replace("·", r"\textperiodcentered{}")
    t = t.replace("●", r"$\bullet$").replace("○", r"$\circ$").replace("→", r"$\rightarrow$")
    return t


def main():
    md = open(os.path.join(HERE, "README.md"), encoding="utf-8").read().splitlines(); out = [PRE]; i = 0; para = []
    def flush():
        if para: out.append(inline(" ".join(para)) + "\n"); para.clear()
    while i < len(md):
        ln = md[i]
        if ln.startswith("📄") or not ln.strip():
            flush(); i += 1; continue
        if ln.startswith("# "):
            flush(); out.append(r"{\LARGE\bfseries %s\par}" % inline(ln[2:]) + "\n"); i += 1; continue
        if ln.startswith("## "):
            flush(); out.append(r"\section*{%s}" % inline(ln[3:]) + "\n"); i += 1; continue
        m = re.match(r"!\[[^\]]*\]\(([^)]+)\)", ln)
        if m:
            flush(); out.append(r"\begin{center}\includegraphics[width=0.92\linewidth]{%s}\end{center}" % m.group(1) + "\n"); i += 1; continue
        if ln.startswith("- "):
            flush(); out.append(r"\begin{itemize}")
            while i < len(md) and md[i].startswith(("- ", "  ")):
                item = md[i][2:]; i += 1
                while i < len(md) and md[i].startswith("  ") and not md[i].startswith("- "): item += " " + md[i].strip(); i += 1
                out.append(r"\item " + inline(item))
            out.append(r"\end{itemize}"); continue
        if ln.startswith("|"):
            flush(); rows = []
            while i < len(md) and md[i].startswith("|"): rows.append([c.strip() for c in md[i].strip("|").split("|")]); i += 1
            rows = [r for r in rows if not all(set(c) <= set("-: ") for c in r)]; n = len(rows[0])
            spec = {2: r"p{4.6cm}p{11.4cm}", 3: r"p{2.2cm}p{3.2cm}p{10.4cm}"}.get(n, "l" * n)
            out.append(r"\begin{longtable}{%s}\toprule" % spec)
            for k, r in enumerate(rows):
                out.append(" & ".join(inline(c) for c in r) + r"\\" + (r"\midrule" if k == 0 and any(rows[0]) else ""))
            out.append(r"\bottomrule\end{longtable}"); continue
        para.append(ln.strip()); i += 1
    flush(); out.append(r"\end{document}")
    open(os.path.join(HERE, "press_report.tex"), "w", encoding="utf-8").write("\n".join(out))


if __name__ == "__main__":
    main()
