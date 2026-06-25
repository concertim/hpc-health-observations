#!/usr/bin/env python3
"""Generate a companion PDF of the HPC Health Observations guide.

Renders the print template (``pdf_template.html``) to A4 PDF with headless
Chromium via Playwright, drawing on the same CSV data as ``build.py`` so the
PDF and the website never drift apart.

Requirements: the ``playwright`` Python package and a Chromium browser.
Install once with::

    pip install playwright
    python -m playwright install chromium

(Chromium is already present where this guide was developed.)

Usage::

    python3 build_pdf.py            # writes docs/hpc-health-observations.pdf
"""

import datetime
import html
import sys
from pathlib import Path

import build  # reuse load_rows() / normalisation from the site builder

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "pdf_template.html"
OUT = HERE / "docs" / "hpc-health-observations.pdf"

TOPIC_ORDER = ["Vitals", "Security", "Performance"]


def topic_rank(t):
    i = TOPIC_ORDER.index(t) if t in TOPIC_ORDER else -1
    return i if i >= 0 else 99 + t


def topic_emoji(t):
    """Emoji prefix for a topic label (shared with the site via build.py)."""
    e = build.TOPIC_EMOJI.get(t, "")
    return e + " " if e else ""


def esc(s):
    return html.escape("" if s is None else str(s), quote=True)


def rich(s):
    """Escaped text with known cross-references lightly emphasised (no link)."""
    out = esc(s)
    ref = "(Appendix A: Concertim Hardware Troubleshooting Methodology)"
    return out.replace(ref, f'<em class="appendix">{ref}</em>')


def item_html(it):
    draft = '<span class="pill draft">Draft</span>' if it.get("draft") else ""
    notes = it.get("authoring_notes") or []
    note_html = ""
    if notes:
        note_html = (
            '<div class="authornotes"><strong>Authoring note:</strong><ul>'
            + "".join(f"<li>{esc(n)}</li>" for n in notes)
            + "</ul></div>"
        )
    intro = it["sow"]["intro"]
    intro_html = f'<p class="intro">{rich(intro)}</p>' if intro else ""
    steps = it["sow"]["steps"] or []
    if steps:
        steps_html = '<ol class="steps">' + "".join(
            f"<li>{rich(s)}</li>" for s in steps
        ) + "</ol>"
    else:
        steps_html = '<p class="muted">No steps documented yet.</p>'
    desc = it["description"]
    desc_html = f'<p class="desc">{rich(desc)}</p>' if desc else '<p class="muted">Not yet documented.</p>'
    impact = it["potential_service_impact"]
    impact_html = f"<p>{rich(impact)}</p>" if impact else '<p class="muted">Not yet documented.</p>'
    return f"""<article class="item">
  <h3 class="item-title">{esc(it['attention_area'])}</h3>
  <div class="meta"><span class="pill scope">{esc(it['scope'])}</span>{draft}</div>
  {desc_html}
  {note_html}
  <div class="block"><h4>Potential service impact</h4>{impact_html}</div>
  <div class="block"><h4>Where we'd start looking</h4>{intro_html}{steps_html}</div>
</article>"""


def build_doc():
    items, _flags = build.load_rows()
    topics = sorted({it["topic"] for it in items}, key=topic_rank)
    counts = {t: sum(1 for it in items if it["topic"] == t) for t in topics}
    topics_summary = ", ".join(f"{topic_emoji(t)}{t} ({counts[t]})" for t in topics)

    toc = "".join(
        f"<li><span>{topic_emoji(t)}{esc(t)}</span><span class=\"c\">{counts[t]}</span></li>"
        for t in topics
    )
    body = []
    for t in topics:
        body.append(
            f'<section class="topic"><h2 class="topic-title">{topic_emoji(t)}{esc(t)}'
            f'<span class="topic-count">{counts[t]} observation'
            f'{"" if counts[t] == 1 else "s"}</span></h2>'
        )
        for it in items:
            if it["topic"] == t:
                body.append(item_html(it))
        body.append("</section>")
    body_html = "\n".join(body)

    tpl = TEMPLATE.read_text(encoding="utf-8")
    generated = datetime.datetime.now(datetime.timezone.utc).strftime("%d %B %Y, %H:%M UTC")
    for token, val in {
        "__GENERATED__": generated,
        "__COUNT__": str(len(items)),
        "__TOPICS_SUMMARY__": topics_summary,
        "__TOC__": toc,
        "__BODY__": body_html,
    }.items():
        tpl = tpl.replace(token, val)
    return tpl, len(items), generated, counts


def render_pdf(tpl_html, generated):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("Playwright is required for PDF generation.\n"
                 "Install it with:  pip install playwright && python -m playwright install chromium")

    tmp = Path("/tmp/hpc_pdf_render.html")
    tmp.write_text(tpl_html, encoding="utf-8")

    footer = (
        '<div style="width:100%;font-size:8pt;color:#8a93a1;font-family:'
        "system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;padding:0 15mm;"
        'display:flex;justify-content:space-between;align-items:center">'
        f'<span style="color:#ff7401;font-weight:700">Generated {html.escape(generated, quote=False)}</span>'
        '<span style="color:#5b6472">HPC Health Observations · Concertim</span>'
        '<span>Page <span class="pageNumber"></span> / <span class="totalPages"></span></span>'
        '</div>'
    )
    header = (
        '<div style="width:100%;padding:0 15mm 1mm;font-family:'
        "system-ui,-apple-system,'Segoe UI',Roboto,sans-serif\">"
        '<div style="border-bottom:1px solid #ffd0a8;padding-bottom:1mm;font-size:8pt;color:#8a93a1">'
        "HPC Health Observations — Open Reference Guide</div></div>"
    )

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(tmp.as_uri(), wait_until="load")
        page.emulate_media(media="print")
        pdf = page.pdf(
            format="A4",
            print_background=True,
            display_header_footer=True,
            header_template=header,
            footer_template=footer,
            margin={"top": "20mm", "bottom": "18mm", "left": "15mm", "right": "15mm"},
        )
        browser.close()
    return pdf


def main():
    tpl_html, n, generated, counts = build_doc()
    pdf = render_pdf(tpl_html, generated)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(pdf)
    detail = ", ".join(f"{t} {c}" for t, c in counts.items())
    print(f"Wrote {OUT.relative_to(HERE)} ({len(pdf) // 1024} KB) — {n} items ({detail})")
    print(f"Generated {generated}")
    # Refresh the website so its About panel shows the "Download PDF" link now
    # that the PDF exists.
    build.main()


if __name__ == "__main__":
    main()