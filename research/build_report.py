"""Render REPORT.md to a typeset PDF (markdown -> HTML -> WeasyPrint).

Handles the custom block classes used in REPORT.md (.plain / .math / .worked /
.takeaway / cards / callouts), builds a title page and an auto-numbered table of
contents with real page numbers, and aligns numeric table columns.
"""

import os
import re

import markdown
from weasyprint import HTML, CSS

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "REPORT.md")
DST = os.path.join(HERE, "AlgoJam3_Structural_Analysis.pdf")

raw = open(SRC, encoding="utf-8").read()

# md_in_html only descends into a raw HTML block when told to, so mark every
# wrapper div. Without this, **bold**, tables and paragraph breaks inside the
# .plain / .math / .worked / .takeaway boxes are emitted literally.
NO_MD = {"eq", "frac", "num", "den"}   # inline-maths markup, must pass through raw
raw = re.sub(r'<div class="([^"]+)">',
             lambda m: m.group(0) if m.group(1).split()[0] in NO_MD
             else f'<div class="{m.group(1)}" markdown="1">', raw)

body = markdown.markdown(
    raw,
    extensions=["tables", "fenced_code", "attr_list", "sane_lists", "md_in_html"],
)

# ---------------------------------------------------------------- table alignment
# A column is right-aligned only if every body cell in it is numeric, so mixed
# columns never look ragged. NB the fraction markup also uses .num, hence .numcell.
NUM = re.compile(r"^[<>±+~−\-]?\s*[\d.,]+(\s*(?:[–\-]|to)\s*"
                 r"[<>±+~−\-]?[\d.,]+)?\s*(?:%|d|x|×|OOS)?$")
BLANK = {"—", "ns", "", "-", "–"}


def cells(row):
    return re.findall(r"<(?:td|th)(?:[^>]*)>(.*?)</(?:td|th)>", row, flags=re.S)


def text_of(cell):
    return re.sub(r"<[^>]+>", "", cell).replace("$", "").replace(",", "").strip()


def is_num(cell):
    t = text_of(cell)
    return t in BLANK or bool(NUM.match(t))


def fix_table(m):
    table = m.group(0)
    rows = re.findall(r"<tr>.*?</tr>", table, flags=re.S)
    body_rows = [r for r in rows if "<td" in r]
    if not body_rows:
        return table
    ncol = max(len(cells(r)) for r in body_rows)
    numeric = []
    for i in range(ncol):
        vals = [cells(r)[i] for r in body_rows if len(cells(r)) > i]
        real = [v for v in vals if text_of(v) not in BLANK]
        numeric.append(bool(real) and all(is_num(v) for v in vals))

    def fix_row(rm):
        idx = [0]

        def cell(cm):
            tag, attrs, inner = cm.group(1), cm.group(2), cm.group(3)
            i = idx[0]
            idx[0] += 1
            if i < ncol and numeric[i]:
                return f"<{tag}{attrs} class='numcell'>{inner}</{tag}>"
            return cm.group(0)

        return re.sub(r"<(td|th)(.*?)>(.*?)</\1>", cell, rm.group(0), flags=re.S)

    return re.sub(r"<tr>.*?</tr>", fix_row, table, flags=re.S)


body = re.sub(r"<table>.*?</table>", fix_table, body, flags=re.S)

# ---------------------------------------------------------------- anchors + TOC
toc = []


def anchor(m):
    level, text = m.group(1), m.group(2)
    plain = re.sub(r"<[^>]+>", "", text)
    slug = "s" + str(len(toc))
    toc.append((level, plain, slug))
    return f'<h{level} id="{slug}">{text}</h{level}>'


body = re.sub(r"<h([23])>(.*?)</h\1>", anchor, body, flags=re.S)

toc_html = ['<div class="toc"><h2 class="toc-h">Contents</h2>']
for level, text, slug in toc:
    cls = "toc2" if level == "2" else "toc3"
    toc_html.append(
        f'<p class="{cls}"><a href="#{slug}">{text}</a></p>')
toc_html.append("</div>")
toc_html = "\n".join(toc_html)

# Figures should not be split across a page break.
body = body.replace("<figure>", '<figure class="fig">')

CSS_TEXT = r"""
@page {
  size: A4; margin: 19mm 17mm 17mm 17mm;
  @bottom-center { content: counter(page);
    font-family: Carlito, sans-serif; font-size: 8pt; color: #8a8f98; }
  @top-right { content: "AlgoJam 3 — Round 1 structural analysis";
    font-family: Carlito, sans-serif; font-size: 7.2pt; color: #b0b5bc; }
}
@page :first { margin: 0; @top-right { content: ""; } @bottom-center { content: ""; } }
@page toc { @top-right { content: ""; } @bottom-center { content: ""; } }

body { font-family: Charter, Georgia, serif; font-size: 9.5pt; line-height: 1.52;
       color: #1c1f24; }
p { margin: 0 0 7pt 0; text-align: justify; hyphens: auto; }
strong { color: #0e1117; }
em { font-style: italic; }

/* ---------------------------------------------------------------- title page */
.title-page { page: cover; height: 297mm; padding: 46mm 22mm 20mm 22mm;
              box-sizing: border-box; page-break-after: always;
              border-top: 11mm solid #1f3d5c;
              display: flex; flex-direction: column; }
.title-page .spacer { flex: 1; }
.title-page .eyebrow { font-family: Carlito, sans-serif; font-size: 9pt;
   letter-spacing: 2.6pt; text-transform: uppercase; color: #6b7684; margin: 0 0 11mm 0; }
.title-page h1 { font-family: Carlito, sans-serif; font-size: 33pt; line-height: 1.13;
   font-weight: 700; letter-spacing: -0.7pt; color: #12151a; margin: 0 0 6mm 0; }
.title-page .lede { font-size: 12.5pt; line-height: 1.55; color: #3d444e;
   margin: 0; text-align: left; max-width: 132mm; }
.title-page .rule { border: 0; border-top: 1.6pt solid #1f3d5c; width: 40mm;
   margin: 0 0 8mm 0; }
.title-page .meta { font-family: Carlito, sans-serif; font-size: 9pt; color: #6b7684;
   line-height: 1.85; }
.title-page .meta b { color: #2c333c; font-weight: 700; }

/* ---------------------------------------------------------------- contents */
.toc { page: toc; page-break-after: always; }
.toc-h { font-family: Carlito, sans-serif; font-size: 17pt; font-weight: 700;
   border: 0; margin: 0 0 7mm 0; color: #12151a; }
.toc p { margin: 0; text-align: left; font-family: Carlito, sans-serif; }
.toc a { text-decoration: none; color: #1c1f24; }
.toc2 { font-size: 10pt; font-weight: 700; margin-top: 4.5mm !important; }
.toc2 a::after, .toc3 a::after {
  content: " " leader('.') " " target-counter(attr(href), page);
  color: #9aa1ab; font-weight: 400; }
.toc3 { font-size: 9pt; padding-left: 6mm; color: #444b55; }

/* ---------------------------------------------------------------- headings */
h2 { font-family: Carlito, sans-serif; font-size: 15pt; font-weight: 700;
     margin: 0 0 9pt 0; padding: 0 0 4pt 0; color: #12151a;
     border-bottom: 1.4pt solid #1f3d5c;
     page-break-before: always; page-break-after: avoid; }
h2:first-of-type { page-break-before: avoid; }
h3 { font-family: Carlito, sans-serif; font-size: 11.4pt; font-weight: 700;
     margin: 15pt 0 6pt 0; color: #1f3d5c; page-break-after: avoid; }
h4 { font-family: Carlito, sans-serif; font-size: 9.6pt; font-weight: 700;
     margin: 0 0 4pt 0; color: #12151a; }

/* ---------------------------------------------------------------- how-to box */
.howto { background: #f4f6f9; border: 0.6pt solid #d8dee6; border-radius: 3pt;
         padding: 10pt 13pt 4pt 13pt; margin: 0 0 14pt 0; page-break-inside: avoid; }
.legend p { margin: 0 0 5pt 0; font-size: 9pt; text-align: left; }

/* ---------------------------------------------------------------- layer chips */
.chip { font-family: Carlito, sans-serif; font-size: 6.9pt; font-weight: 700;
        letter-spacing: 0.5pt; text-transform: uppercase; padding: 1.6pt 5pt;
        border-radius: 2.5pt; margin-right: 5pt; white-space: nowrap; }
.chip-plain  { background: #dbe8f4; color: #1f4e79; }
.chip-math   { background: #e2e4e8; color: #3a4048; }
.chip-worked { background: #fbeed5; color: #8a5a10; }
.chip-take   { background: #d8ecdc; color: #1d5b2e; }

/* ---------------------------------------------------------------- layer boxes */
/* Prose boxes may split across pages — they are often long and forcing them
   whole leaves large gaps. Maths, worked examples and takeaways stay intact. */
.plain, .math, .worked, .takeaway { padding: 9pt 12pt; margin: 9pt 0 11pt 0;
        border-radius: 3pt; }
.math, .worked, .takeaway { page-break-inside: avoid; }
.plain    { background: #f2f7fc; border-left: 2.6pt solid #2f6ea5; }
.math     { background: #f7f8f9; border-left: 2.6pt solid #59616b; }
.worked   { background: #fdf8ee; border-left: 2.6pt solid #c8821a; }
.takeaway { background: #f1f8f3; border-left: 2.6pt solid #2f7d4f; }
.plain p:last-child, .math p:last-child, .worked p:last-child,
.takeaway p:last-child { margin-bottom: 0; }
.plain > .chip, .math > .chip, .worked > .chip, .takeaway > .chip { float: none; }

/* ---------------------------------------------------------------- equations */
.eq { font-family: Charter, Georgia, serif; font-size: 10.2pt; text-align: center;
      margin: 9pt 0; line-height: 1.9; color: #12151a; }
.eq, .eq p { text-align: center !important; }
.eq p { margin: 0; }
.eq i { font-style: italic; }
.eq b { color: #1f3d5c; }
.frac { display: inline-block; vertical-align: middle; text-align: center;
        margin: 0 3pt; }
.frac .num { display: block; padding: 0 4pt 1.2pt 4pt;
             border-bottom: 0.7pt solid #1c1f24; font-size: 8.9pt; }
.frac .den { display: block; padding: 1.2pt 4pt 0 4pt; font-size: 8.9pt; }
.where { background: #ffffff; border: 0.5pt solid #e0e3e7; border-radius: 2.5pt;
         padding: 6pt 10pt 1pt 10pt; margin: 7pt 0; }
.where p { margin: 0 0 4pt 0; font-size: 8.7pt; text-align: left; color: #3d444e; }

/* ---------------------------------------------------------------- callouts */
.warn-soft { background: #fdf3e6; border: 0.6pt solid #ecd3a8;
   border-left: 2.6pt solid #c8821a; border-radius: 3pt; padding: 9pt 12pt 3pt 12pt;
   margin: 10pt 0; page-break-inside: avoid; }
.warn-soft p { text-align: left; }
.tbl-note { font-size: 8.3pt; color: #5c636d; font-style: italic; margin: 7pt 0 -2pt 0;
   text-align: left; line-height: 1.45; }

/* ---------------------------------------------------------------- summary cards */
.summary-cards { margin: 11pt 0; }
.card { border: 0.6pt solid #dfe3e8; border-radius: 3pt; padding: 8pt 11pt 4pt 11pt;
        margin-bottom: 7pt; page-break-inside: avoid; border-left-width: 3pt;
        border-left-style: solid; }
.card-gold   { border-left-color: #b8860b; background: #fdfaf1; }
.card-silver { border-left-color: #6b7684; background: #f7f8fa; }
.card-bronze { border-left-color: #a0622d; background: #fbf6f2; }
.card-rank { font-family: Carlito, sans-serif; font-size: 6.8pt; font-weight: 700;
   letter-spacing: 1.1pt; text-transform: uppercase; color: #8a919b; margin: 0 0 2pt 0; }
.card h4 { font-size: 11pt; margin: 0 0 4pt 0; }
.card p { margin: 0 0 5pt 0; font-size: 9.1pt; }

.flags { background: #fcf4f4; border: 0.6pt solid #eccfcf; border-left: 2.6pt solid #b4453a;
   border-radius: 3pt; padding: 9pt 12pt 4pt 12pt; margin: 10pt 0;
   page-break-inside: avoid; }
.flags ol { margin: 0; padding-left: 15pt; }
.flags li { margin-bottom: 6pt; }

/* ---------------------------------------------------------------- tables */
table { border-collapse: collapse; width: 100%; margin: 9pt 0 12pt 0;
        font-family: Carlito, sans-serif; font-size: 8.2pt;
        page-break-inside: avoid; }
thead { background: #eaeef3; }
th { font-weight: 700; text-align: left; padding: 4.6pt 5pt; color: #22282f;
     border-bottom: 1pt solid #aeb6c0; }
td { padding: 3.7pt 5pt; border-bottom: 0.5pt solid #e6e9ed; vertical-align: top; }
tbody tr:nth-child(even) { background: #fafbfc; }
td.numcell, th.numcell { text-align: right; font-variant-numeric: tabular-nums; }
table strong { color: #0b3d6b; }
table em { color: #6b7684; }

/* ---------------------------------------------------------------- figures */
figure.fig { margin: 11pt 0 13pt 0; page-break-inside: avoid; }
figure.fig img { width: 100%; display: block; }
figcaption { font-size: 8.3pt; color: #4a515a; line-height: 1.45; margin-top: 4pt;
   padding-top: 4pt; border-top: 0.5pt solid #e0e3e7; text-align: left; }
figcaption strong { color: #1f3d5c; }

/* ---------------------------------------------------------------- misc */
blockquote { margin: 9pt 0; padding: 8pt 13pt; background: #eef4fa;
   border-left: 2.6pt solid #2f6ea5; page-break-inside: avoid; }
blockquote p { margin: 0; text-align: left; }
code { font-family: "DejaVu Sans Mono", monospace; font-size: 8.1pt;
   background: #eef0f3; padding: 0.7pt 2.5pt; border-radius: 2pt; color: #253044; }
pre { background: #f6f8fa; border: 0.5pt solid #dde1e7; border-left: 2.5pt solid #59616b;
   padding: 8pt 10pt; margin: 9pt 0; page-break-inside: avoid; }
pre code { background: none; padding: 0; font-size: 8.3pt; line-height: 1.5; }
ul, ol { margin: 0 0 8pt 0; padding-left: 15pt; }
li { margin-bottom: 3.5pt; text-align: justify; }
hr { border: none; border-top: 0.5pt solid #dde1e7; margin: 0; height: 0; }
"""

TITLE = """
<div class="title-page">
  <p class="eyebrow">UQ Fintech Society × IMC Trading · AlgoJam 3</p>
  <h1>What the Prices<br>Are Hiding</h1>
  <p class="lede">A structural analysis of nine instruments over one simulated
  year — testing each for mean reversion, momentum, volatility clustering,
  lead–lag relationships and cross-sectional reversal, and converting what
  survives into trading models.</p>
  <div class="spacer"></div>
  <hr class="rule">
  <p class="meta">
    <b>Data</b> &nbsp; Round 1 · 365 days · 9 instruments<br>
    <b>Methods</b> &nbsp; ADF · Hurst · ACF &amp; Ljung–Box · variance ratio ·
      ARCH-LM &amp; GARCH(1,1) · Granger · Engle–Granger · periodogram<br>
    <b>Validation</b> &nbsp; Split-half stability on every reported signal<br>
    <b>Written for</b> &nbsp; Readers with no prior finance or statistics background
  </p>
</div>
"""

DOC = (f'<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>'
       f'{TITLE}{toc_html}{body}</body></html>')

HTML(string=DOC, base_url=HERE).write_pdf(DST, stylesheets=[CSS(string=CSS_TEXT)])
print(f"wrote {DST} ({os.path.getsize(DST)/1024:.0f} KB)")
