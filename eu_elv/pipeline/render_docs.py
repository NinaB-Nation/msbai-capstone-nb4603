"""Render the ELV analysis markdown to PDF via headless Chromium.

The uploaded PDF was produced by Chromium (metadata: Creator Chromium,
Producer Skia/PDF), so this uses the same engine. Markdown is the single
source: the .md files in the repo are converted here rather than the content
being maintained twice, which is the only way the two stay in agreement.

Header and footer come from Playwright's templates because Chrome ignores
CSS @page margin boxes.
"""
import asyncio
import re
import sys

import markdown
from playwright.async_api import async_playwright

DOCS = "/home/user/msbai-capstone-nb4603/eu_elv/docs"

CSS = """
* { box-sizing: border-box; }
body {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 10.2pt; line-height: 1.55; color: #1a1a1a; margin: 0;
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
h1 {
  font-size: 23pt; line-height: 1.2; margin: 0 0 10px; letter-spacing: -0.2px;
}
h1 + p { color: #555; font-size: 10.4pt; margin: 0 0 18px; }
h2 {
  font-size: 14.5pt; margin: 25px 0 9px; line-height: 1.25;
  padding-bottom: 5px; border-bottom: 1px solid #ddd9d0;
  page-break-after: avoid; break-after: avoid;
}
h3 {
  font-size: 11.6pt; margin: 17px 0 7px; line-height: 1.3;
  page-break-after: avoid; break-after: avoid;
}
p { margin: 0 0 9px; orphans: 2; widows: 2; }
ul, ol { margin: 0 0 9px; padding-left: 20px; }
li { margin-bottom: 4px; }
code {
  font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 0.86em;
  background: #f1efe9; padding: 1px 4px; border-radius: 3px;
}
pre {
  background: #f7f5f0; border: 1px solid #e2ded4; border-radius: 4px;
  padding: 9px 11px; font-size: 8.8pt; line-height: 1.45;
  white-space: pre-wrap; margin: 0 0 10px;
  page-break-inside: avoid; break-inside: avoid;
}
pre code { background: none; padding: 0; }
table {
  border-collapse: collapse; width: 100%; margin: 8px 0 13px;
  font-size: 9.1pt; page-break-inside: avoid; break-inside: avoid;
}
th {
  text-align: left; background: #f4f2ec; font-weight: 600;
  border-bottom: 1.5px solid #cdc7ba; padding: 6px 8px; vertical-align: top;
}
td { border-bottom: 1px solid #e8e5dd; padding: 5px 8px; vertical-align: top; }
tr:last-child td { border-bottom: none; }
blockquote {
  background: #f7f5f0; border-left: 3px solid #b8b0a0;
  padding: 10px 13px; margin: 12px 0; page-break-inside: avoid;
  break-inside: avoid;
}
blockquote p:last-child { margin-bottom: 0; }
hr { border: none; border-top: 1px solid #e5e1d8; margin: 20px 0; }
"""

HEADER = ('<div style="font-size:7.5pt;color:#9a9a9a;width:100%;'
          'padding:0 16mm;"></div>')


def footer(title):
    return (
        '<div style="font-family:Helvetica,Arial,sans-serif;font-size:7.5pt;'
        'color:#8a8a8a;width:100%;padding:4px 16mm 0;'
        'border-top:0.5px solid #ddd;display:flex;'
        'justify-content:space-between;">'
        f'<span>{title}</span>'
        '<span>Page <span class="pageNumber"></span> of '
        '<span class="totalPages"></span></span></div>'
    )


def build_html(md_path, title):
    text = open(md_path).read()
    # The rule right under the title block is decoration in markdown and
    # redundant once h2 carries a rule, so drop the leading one only.
    body = markdown.markdown(
        text, extensions=["tables", "fenced_code", "sane_lists"])
    # Numeric-looking cells read better right-aligned in a printed table.
    body = re.sub(r"<td>([\d,.]+%?)</td>",
                  r'<td style="text-align:right;white-space:nowrap">\1</td>',
                  body)
    return (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>{title}</title><style>{CSS}</style></head>"
            f"<body>{body}</body></html>")


async def render(md_path, pdf_path, title):
    html = build_html(md_path, title)
    async with async_playwright() as pw:
        # The installed playwright pins a newer chromium build than the one
        # present, so point it at the binary that is actually here rather
        # than downloading one.
        browser = await pw.chromium.launch(
            executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
        pg = await browser.new_page()
        await pg.set_content(html, wait_until="load")
        await pg.pdf(
            path=pdf_path, format="A4", print_background=True,
            display_header_footer=True,
            header_template=HEADER, footer_template=footer(title),
            margin={"top": "14mm", "bottom": "16mm",
                    "left": "16mm", "right": "16mm"},
        )
        await browser.close()
    print(f"  wrote {pdf_path}")


async def main():
    await render(f"{DOCS}/belgium_material_value.md",
                 f"{DOCS}/Belgium_ELV_Material_Value_Analysis.pdf",
                 "Belgium ELV Material Value Analysis")
    await render(f"{DOCS}/netherlands_figures_review.md",
                 f"{DOCS}/Netherlands_Comparator_Figures_Review.pdf",
                 "Netherlands Comparator Figures: Review")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
