#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render a CHEATSHEET.md into a printable A4 reference card (PDF).

Only the markdown TABLES are carried over -- the prose in CHEATSHEET.md is
explanation, while the PDF is meant to be a dense card you keep next to the
keyboard.  Keeping CHEATSHEET.md as the single source of truth means the two
cannot drift apart.

    python3 shared/make_cheatsheet_pdf.py vim/CHEATSHEET.md vim/CHEATSHEET.pdf

Rendering goes through headless Chromium (Playwright) rather than reportlab,
because the content is Japanese and Chromium picks up Noto Sans CJK JP without
any font plumbing.
"""
import asyncio
import html
import re
import sys
from pathlib import Path


def parse(md_text):
    """Return [(heading, [rows]), ...] keeping only headings that own a table."""
    sections, heading, rows, in_table = [], None, [], False

    def flush():
        if heading and rows:
            sections.append((heading, list(rows)))

    for line in md_text.splitlines():
        h = re.match(r"^(#{2,3})\s+(.*)", line)
        if h:
            flush()
            heading, rows, in_table = h.group(2).strip(), [], False
            continue
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                in_table = True          # the |---|---| separator row
                continue
            rows.append(("head" if not in_table else "body", cells))
            continue
        if in_table and line.strip() == "":
            in_table = False
    flush()
    return sections


INLINE_CODE = re.compile(r"`([^`]+)`")
BOLD = re.compile(r"\*\*([^*]+)\*\*")


def inline(text):
    out = html.escape(text)
    out = INLINE_CODE.sub(lambda m: f"<kbd>{m.group(1)}</kbd>", out)
    out = BOLD.sub(lambda m: f"<b>{m.group(1)}</b>", out)
    return out


CSS = """
@page {{ size: A4 portrait; margin: 9mm 8mm 8mm 8mm; }}
* {{ box-sizing: border-box; }}
body {{
  font-family: "Noto Sans CJK JP", "Hiragino Sans", sans-serif;
  font-size: {fs}pt; line-height: 1.34; color: #14171a; margin: 0;
}}
h1 {{
  font-size: 1.75em; margin: 0 0 1.5mm 0; letter-spacing: .2px;
  column-span: all; border-bottom: 1.6pt solid #14171a; padding-bottom: 1.2mm;
}}
.sub {{
  column-span: all; font-size: .93em; color: #55606a;
  margin: 0 0 3mm 0; display: flex; justify-content: space-between; gap: 4mm;
}}
.cols {{ column-count: 2; column-gap: 5mm; column-fill: balance; }}
section {{ break-inside: avoid; margin: 0 0 3.2mm 0; }}
h2 {{
  font-size: 1.08em; margin: 0 0 1mm 0; padding: 0.7mm 1.6mm;
  background: #14171a; color: #fff; border-radius: 1.2pt; font-weight: 600;
}}
table {{ width: 100%; border-collapse: collapse; }}
td, th {{
  text-align: left; vertical-align: top; padding: 0.75mm 1.4mm;
  border-bottom: .4pt solid #dfe4e8;
}}
th {{ font-size: .86em; color: #6b7680; font-weight: 600; text-transform: uppercase; }}
tr:last-child td {{ border-bottom: none; }}
td:first-child {{ white-space: nowrap; width: 1%; }}
kbd {{
  font-family: "SF Mono", "DejaVu Sans Mono", monospace; font-size: .93em;
  background: #eef2f5; border: .4pt solid #cdd6dd; border-bottom-width: 1pt;
  border-radius: 2pt; padding: 0 1.1mm; white-space: nowrap; color: #0b3d5c;
}}
b {{ color: #b3261e; font-weight: 600; }}
"""


def build_html(title, subtitle, sections, font_pt):
    parts = [
        "<!doctype html><meta charset='utf-8'>",
        f"<style>{CSS.format(fs=font_pt)}</style>",
        f"<h1>{html.escape(title)}</h1>",
        f"<div class='sub'>{subtitle}</div>",
        "<div class='cols'>",
    ]
    for heading, rows in sections:
        parts.append(f"<section><h2>{inline(heading)}</h2><table>")
        for kind, cells in rows:
            tag = "th" if kind == "head" else "td"
            tds = "".join(f"<{tag}>{inline(c)}</{tag}>" for c in cells)
            parts.append(f"<tr>{tds}</tr>")
        parts.append("</table></section>")
    parts.append("</div>")
    return "\n".join(parts)


# Largest first: we keep the biggest type size that still fits on one page.
FONT_SIZES = [11.0, 10.5, 10.0, 9.5, 9.0, 8.6, 8.2, 7.8, 7.4, 7.0, 6.6, 6.2]


def page_count(path):
    from pypdf import PdfReader
    return len(PdfReader(str(path)).pages)


def normalize(path, title):
    """Strip the timestamps Chromium embeds so rebuilds are byte-identical.

    Without this every `make` produces a different file and git shows the PDFs
    as modified even when the cheat sheet did not change.
    """
    import subprocess
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(str(path))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.add_metadata({"/Title": title, "/Producer": "make_cheatsheet_pdf.py",
                         "/CreationDate": "D:20000101000000Z",
                         "/ModDate": "D:20000101000000Z"})
    with open(path, "wb") as fh:
        writer.write(fh)
    # qpdf derives /ID from the file contents instead of a random value
    subprocess.run(["qpdf", "--deterministic-id", "--replace-input", str(path)],
                   check=True)


async def render_autofit(title, subtitle, sections, out_path, max_pages=1):
    """Render at the largest font size that still fits within max_pages."""
    from playwright.async_api import async_playwright
    chosen = FONT_SIZES[-1]
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        for fs in FONT_SIZES:
            await page.set_content(build_html(title, subtitle, sections, fs),
                                   wait_until="networkidle")
            await page.pdf(path=str(out_path), format="A4", print_background=True,
                           margin={"top": "9mm", "bottom": "8mm",
                                   "left": "8mm", "right": "8mm"})
            if page_count(out_path) <= max_pages:
                chosen = fs
                break
        await browser.close()
    return chosen


def main():
    if len(sys.argv) < 3:
        sys.exit(f"usage: {sys.argv[0]} <CHEATSHEET.md> <out.pdf>")
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    md = src.read_text(encoding="utf-8")

    m = re.match(r"^#\s+(.*)", md.splitlines()[0])
    title = m.group(1).strip() if m else src.stem

    mode = "vim" if "vim" in str(src).lower() else "emacs"
    subtitle = ("<span>Karabiner-Elements / US (ANSI) layout / "
                "Caps Lock リーダー</span>"
                f"<span>{mode}-mode.json</span>")

    sections = parse(md)
    if not sections:
        sys.exit("no markdown tables found -- nothing to render")

    out.parent.mkdir(parents=True, exist_ok=True)
    fs = asyncio.run(render_autofit(title, subtitle, sections, out))
    normalize(out, title)

    rows = sum(len(r) for _, r in sections)
    print(f"{src} -> {out}  ({len(sections)} sections, {rows} rows, "
          f"{fs}pt, {page_count(out)} page, {out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
