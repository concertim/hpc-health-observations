#!/usr/bin/env python3
"""Build the HPC Health Observations static guide from the CSV files.

Zero external dependencies — standard library only.

How it works
------------
1. Globs every ``OBSERVATIONS_AND_ACTIONS*.csv`` next to this script.
2. Derives a *topic* from the filename suffix (the bare file = "Vitals").
3. Normalises each row, dropping the (intentionally omitted) "Concertim
   Impact Rating" column — severity varies per customer/site/asset and is
   surfaced once in the page's About panel rather than per item.
4. Writes a single self-contained ``site/index.html`` with the data embedded
   inline (works from ``file://``, needs no server/fetch/CDN).

Add a new topic: drop a ``OBSERVATIONS_AND_ACTIONS_<TOPIC>.csv`` (same headers)
in this directory and re-run ``python3 build.py``.
Add an item: append a row to an existing CSV and re-run.
"""

import csv
import glob
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "template.html"
OUT = HERE / "docs" / "index.html"

# Authoring placeholder markers — when present we render the row as "Draft"
# and lift the offending line into an "Authoring note" callout rather than
# showing it as polished content.
AUTHOR_RE = re.compile(
    r"\b(SOME NOTE|TODO|FIXME|TBD|TBC|MAKE IT SPECIFIC|PLACEHOLDER)\b", re.I
)

# Map a filename suffix to a friendly topic label. The bare file (no suffix)
# is treated as the "Vitals" topic.
SUFFIX_TOPIC = {
    "": "Vitals",
    "SECURITY": "Security",
    "PERFORMANCE": "Performance",
    "VITALS": "Vitals",
}


def topic_for(path: Path) -> str:
    """Derive a friendly topic label from a CSV filename."""
    stem = path.stem  # e.g. OBSERVATIONS_AND_ACTIONS_SECURITY
    prefix = "OBSERVATIONS_AND_ACTIONS"
    suffix = stem[len(prefix):].lstrip("_").upper() if stem.startswith(prefix) else ""
    if suffix in SUFFIX_TOPIC:
        return SUFFIX_TOPIC[suffix]
    # Unknown suffix → title-case it so a new _RELIABILITY.csv "just works".
    pretty = suffix.replace("_", " ").strip().title() or "Misc"
    return pretty


def slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "item"


def split_notes(text: str):
    """Separate authoring-placeholder lines from real content.

    Returns (clean_text, notes) where notes is a list of stripped lines that
    matched an authoring marker.
    """
    notes = []
    kept = []
    for line in text.split("\n"):
        if AUTHOR_RE.search(line):
            nl = line.strip()
            if nl:
                notes.append(nl)
        else:
            kept.append(line)
    return "\n".join(kept), notes


def tidy(text: str) -> str:
    """Normalise whitespace: nbsp → space, collapse blank lines, trim."""
    text = (text or "").replace("\xa0", " ")
    lines = [ln.rstrip() for ln in text.split("\n")]
    # Drop leading/trailing blank lines, collapse internal runs to one.
    out = []
    blank_run = 0
    for ln in lines:
        if ln.strip() == "":
            blank_run += 1
            if blank_run <= 1:
                out.append("")
        else:
            blank_run = 0
            out.append(ln)
    while out and out[0] == "":
        out.pop(0)
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out)


def tidy_paragraph(text: str) -> str:
    """Like tidy() but joins lines into a single flowing paragraph."""
    t = tidy(text)
    return " ".join(ln.strip() for ln in t.split("\n") if ln.strip())


def parse_sow(raw: str):
    """Parse a Statement of Work cell into {intro, steps} plus authoring notes."""
    text, notes = split_notes(raw or "")
    text = tidy(text)
    intro = None
    steps = []
    body = [ln.strip() for ln in text.split("\n") if ln.strip()]
    i = 0
    leads = []
    while i < len(body) and not body[i].startswith("-"):
        leads.append(body[i])
        i += 1
    if leads:
        intro = " ".join(leads)
    for ln in body[i:]:
        if ln.startswith("- "):
            steps.append(ln[2:].strip())
        elif ln.startswith("-"):
            steps.append(ln[1:].strip())
        else:
            # Continuation line: attach to the previous step (or intro).
            if steps:
                steps[-1] = steps[-1] + " " + ln
            elif intro:
                intro = intro + " " + ln
            else:
                intro = ln
    return {"intro": intro, "steps": steps}, notes


def load_rows():
    files = sorted(glob.glob(str(HERE / "OBSERVATIONS_AND_ACTIONS*.csv")))
    if not files:
        sys.exit("No OBSERVATIONS_AND_ACTIONS*.csv files found next to build.py.")
    items = []
    flags = []  # (topic, attention_area, reason) for draft/flagged rows
    seen_slugs = {}
    for fp in files:
        path = Path(fp)
        topic = topic_for(path)
        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None:
                continue
            for row in reader:
                attention = tidy_paragraph(row.get("Attention Area", ""))
                scope = tidy_paragraph(row.get("Scope", ""))
                desc_raw = row.get("Description", "") or ""
                impact_raw = row.get("Potential Service Impact", "") or ""
                sow_raw = row.get("Statement of Work", "") or ""

                desc, desc_notes = split_notes(desc_raw)
                desc = tidy_paragraph(desc)
                impact, impact_notes = split_notes(impact_raw)
                impact = tidy_paragraph(impact)
                sow, sow_notes = parse_sow(sow_raw)

                authoring_notes = []
                for n in desc_notes + impact_notes + sow_notes:
                    if n and n not in authoring_notes:
                        authoring_notes.append(n)

                has_sow = bool(sow["intro"]) or bool(sow["steps"])
                empty_core = not desc or not impact or not has_sow
                draft = empty_core or bool(authoring_notes)

                if draft:
                    reasons = []
                    if not desc:
                        reasons.append("missing description")
                    if not impact:
                        reasons.append("missing service-impact")
                    if not has_sow:
                        reasons.append("missing statement of work")
                    if authoring_notes:
                        reasons.append("authoring placeholder")
                    flags.append((topic, attention or "(untitled)",
                                  "; ".join(reasons)))

                base = slugify(attention) or "item"
                tslug = slugify(topic)
                slug = f"{tslug}-{base}"
                # Guarantee uniqueness within a topic.
                if slug in seen_slugs:
                    seen_slugs[slug] += 1
                    slug = f"{tslug}-{base}-{seen_slugs[f'{tslug}-{base}']}"
                else:
                    seen_slugs[slug] = 1

                items.append({
                    "topic": topic,
                    "topic_slug": tslug,
                    "id": slug,
                    "scope": scope,
                    "attention_area": attention,
                    "description": desc,
                    "potential_service_impact": impact,
                    "sow": sow,
                    "authoring_notes": authoring_notes,
                    "draft": draft,
                })
    return items, flags


PDF_NAME = "hpc-health-observations.pdf"


def pdf_link_html():
    """About-panel download link, shown only when the companion PDF is present."""
    pdf_path = OUT.parent / PDF_NAME
    if not pdf_path.exists():
        return ""
    size_kb = max(1, pdf_path.stat().st_size // 1024)
    return (
        '<p class="pdfline">Prefer a printable copy for offline use? '
        f'<a class="dlink" href="{PDF_NAME}" download '
        f'aria-label="Download the companion PDF ({size_kb} KB)">'
        'Download the companion PDF <span aria-hidden="true">↓</span></a></p>'
    )


def main():
    items, flags = load_rows()
    html = TEMPLATE.read_text(encoding="utf-8")
    # Embed the data. We use JSON-serialised text in place of a sentinel token.
    # A JSON string value could only contain "__DATA__" if a CSV cell literally
    # did — none do — so a plain substitution is safe here.
    html = html.replace("__DATA__", json.dumps(items, ensure_ascii=False, indent=0))
    html = html.replace("__BUILD__", _build_stamp())
    html = html.replace("__PDF_LINK__", pdf_link_html())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")

    # --- report -----------------------------------------------------------
    topics = {}
    for it in items:
        topics[it["topic"]] = topics.get(it["topic"], 0) + 1
    print(f"Built {OUT.relative_to(HERE)} — {len(items)} items across "
          f"{len(topics)} topic(s):")
    for t, n in topics.items():
        print(f"  • {t}: {n}")
    drafted = [it for it in items if it["draft"]]
    if drafted:
        print(f"\n{len(drafted)} draft/incomplete row(s) rendered with a Draft badge:")
        for topic, name, reason in flags:
            print(f"  • [{topic}] {name!r} — {reason}")
        print("Clean these in the CSV and re-run to drop the badges.")
    else:
        print("\nNo draft/incomplete rows detected.")


def _build_stamp():
    # Build timestamp — keep stable-ish; build runs on demand so this is fine.
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


if __name__ == "__main__":
    main()
