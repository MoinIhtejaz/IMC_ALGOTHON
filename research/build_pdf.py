"""Render FINDINGS.md to a typeset PDF via markdown -> HTML -> WeasyPrint."""

import os
import re

import markdown
from weasyprint import HTML, CSS

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "FINDINGS.md")
DST = os.path.join(HERE, "AlgoJam3_Structural_Analysis.pdf")

raw = open(SRC, encoding="utf-8").read()

# Strip the H1 (it becomes the cover block) and pull the standfirst.
raw = re.sub(r"^# .*?\n", "", raw, count=1)
raw = raw.replace("⚠️ ", "")

body = markdown.markdown(
    raw,
    extensions=["tables", "fenced_code", "attr_list", "sane_lists"],
)

# Align whole COLUMNS, not individual cells: a column goes right-aligned only if
# every one of its body cells is numeric. Mixed columns stay flush left so the
# table never looks ragged.
NUM = re.compile(r"^[<>±+~\-]?\s*[\d.,]+(\s*(?:[–\-]|to)\s*[<>±+~\-]?[\d.,]+)?"
                 r"\s*(?:%|d|x|×|OOS)?$")
BLANK = {"—", "ns", "", "-"}


def cells(row):
    return re.findall(r"<(?:td|th)(?:[^>]*)>(.*?)</(?:td|th)>", row, flags=re.S)


def text_of(cell):
    return re.sub(r"<[^>]+>", "", cell).strip()


def is_num(cell):
    t = text_of(cell)
    return t in BLANK or bool(NUM.match(t))


def fix_table(m):
    table = m.group(0)
    rows = re.findall(r"<tr>.*?</tr>", table, flags=re.S)
    if not rows:
        return table
    body_rows = [r for r in rows if "<td" in r]
    if not body_rows:
        return table
    ncol = max(len(cells(r)) for r in body_rows)
    numeric_col = []
    for i in range(ncol):
        vals = [cells(r)[i] for r in body_rows if len(cells(r)) > i]
        real = [v for v in vals if text_of(v) not in BLANK]
        numeric_col.append(bool(real) and all(is_num(v) for v in vals))

    def fix_row(rm):
        row = rm.group(0)
        idx = [0]

        def cell(cm):
            tag, attrs, inner = cm.group(1), cm.group(2), cm.group(3)
            i = idx[0]
            idx[0] += 1
            if i < ncol and numeric_col[i]:
                return f"<{tag}{attrs} class='num'>{inner}</{tag}>"
            return cm.group(0)

        return re.sub(r"<(td|th)(.*?)>(.*?)</\1>", cell, row, flags=re.S)

    return re.sub(r"<tr>.*?</tr>", fix_row, table, flags=re.S)


body = re.sub(r"<table>.*?</table>", fix_table, body, flags=re.S)

# Verdict pills.
body = body.replace("<strong>USE</strong>", "<span class='use'>USE</span>")
for w in ("rejected", "reject"):
    body = re.sub(rf"<td class='num'>{w}</td>", f"<td><span class='no'>{w}</span></td>", body)
    body = re.sub(rf"<td>{w}</td>", f"<td><span class='no'>{w}</span></td>", body)

# Section 6's correction paragraph becomes a callout.
body = body.replace(
    "<p><strong>Correcting a trap I hit:</strong>",
    "<p class='warn'><strong>Correcting a trap I hit:</strong>")

CSS_TEXT = """
@page {
  size: A4; margin: 20mm 16mm 18mm 16mm;
  @bottom-center {
    content: counter(page) " / " counter(pages);
    font-family: Carlito, sans-serif; font-size: 8pt; color: #8a8f98;
  }
  @top-right {
    content: "AlgoJam 3 — Round 1 structural analysis";
    font-family: Carlito, sans-serif; font-size: 7.5pt; color: #a8adb5;
  }
}
@page :first { @top-right { content: ""; } }

body { font-family: Charter, Georgia, serif; font-size: 9.4pt; line-height: 1.5;
       color: #1c1f24; }

.cover { border-bottom: 2.5pt solid #1c1f24; padding-bottom: 10pt; margin-bottom: 16pt; }
.cover h1 { font-family: Carlito, sans-serif; font-size: 23pt; font-weight: 700;
            margin: 0 0 3pt 0; letter-spacing: -0.4pt; color: #12151a; }
.cover .sub { font-family: Carlito, sans-serif; font-size: 10.5pt; color: #6b7280; margin: 0; }

h2 { font-family: Carlito, sans-serif; font-size: 13pt; font-weight: 700;
     margin: 20pt 0 7pt 0; padding-bottom: 3pt; color: #12151a;
     border-bottom: 0.7pt solid #d6dae0; page-break-after: avoid; }
h3 { font-family: Carlito, sans-serif; font-size: 10.5pt; font-weight: 700;
     margin: 13pt 0 4pt 0; color: #2c313a; page-break-after: avoid; }
p { margin: 0 0 7pt 0; text-align: justify; hyphens: auto; }

table { border-collapse: collapse; width: 100%; margin: 8pt 0 12pt 0;
        font-family: Carlito, sans-serif; font-size: 8.1pt;
        page-break-inside: avoid; }
thead { background: #eef1f5; }
th { font-weight: 700; text-align: left; padding: 4.5pt 5pt; color: #2c313a;
     border-bottom: 1pt solid #b9bfc8; }
td { padding: 3.6pt 5pt; border-bottom: 0.5pt solid #e6e9ed; vertical-align: top; }
tbody tr:nth-child(even) { background: #fafbfc; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
table strong { color: #0b3d6b; }

code { font-family: "DejaVu Sans Mono", monospace; font-size: 8.2pt;
       background: #f2f4f7; padding: 0.7pt 2.5pt; border-radius: 2pt; color: #253044; }
pre { background: #f6f8fa; border: 0.5pt solid #dde1e7; border-left: 2.5pt solid #4a6f96;
      padding: 8pt 10pt; margin: 8pt 0; page-break-inside: avoid; }
pre code { background: none; padding: 0; font-size: 8.4pt; line-height: 1.45; }

blockquote { margin: 9pt 0; padding: 8pt 12pt; background: #eef4fa;
             border-left: 2.5pt solid #2f6ea5; page-break-inside: avoid; }
blockquote p { margin: 0; text-align: left; }

p.warn { background: #fdf4e7; border-left: 2.5pt solid #c8821a; padding: 8pt 12pt;
         margin: 9pt 0; text-align: left; }

ul, ol { margin: 0 0 8pt 0; padding-left: 15pt; }
li { margin-bottom: 3.5pt; text-align: justify; }

.use { background: #d9ecd9; color: #1d5b1d; font-weight: 700; font-size: 7.3pt;
       padding: 1pt 4pt; border-radius: 2.5pt; letter-spacing: 0.3pt; }
.no  { background: #f1e0e0; color: #8a2a2a; font-weight: 700; font-size: 7.3pt;
       padding: 1pt 4pt; border-radius: 2.5pt; letter-spacing: 0.3pt; }

hr { border: none; border-top: 0.5pt solid #dde1e7; margin: 15pt 0; }
strong { color: #12151a; }
"""

HTML_DOC = f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>
<div class="cover">
  <h1>AlgoJam 3 — Round 1 Structural Analysis</h1>
  <p class="sub">Stationarity · autocorrelation · volatility persistence · lead-lag ·
     cross-sectional reversion — with split-half validation</p>
</div>
{body}
</body></html>"""

HTML(string=HTML_DOC).write_pdf(DST, stylesheets=[CSS(string=CSS_TEXT)])
print(f"wrote {DST} ({os.path.getsize(DST)/1024:.0f} KB)")
