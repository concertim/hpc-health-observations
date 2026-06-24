# HPC Health Observations — Open Reference Guide

A small, static website that publishes Concertim's HPC health observations as an
**open reference** — describing *where we'd begin investigating* each observation,
shared so customers and peers can compare against their own practices. It is
deliberately **not** a prescriptive checklist of "things you must do".

The site is a single self-contained `index.html` (CSS, JS and data all inline):
no server, no fetch, no CDN, no JavaScript or CSS dependencies. It works from
`file://`, so you can open it directly or host the `docs/` folder anywhere.

A companion **PDF** can also be generated for customer information packets —
see [Companion PDF](#companion-pdf).

## Build

```
python3 build.py
```

Standard library only — nothing to install. Reads every
`OBSERVATIONS_AND_ACTIONS*.csv` next to the script and writes `docs/index.html`.

When the build finishes it prints a summary: the topics and item counts, plus any
**draft / incomplete rows** it flagged (see below).

## The data (single source of truth)

Each CSV uses the same six columns:

```
Concertim Impact Rating, Scope, Attention Area, Description, Potential Service Impact, Statement of Work
```

The CSVs are the only place you edit. The filename determines the **topic**:

| File | Topic |
|---|---|
| `OBSERVATIONS_AND_ACTIONS.csv` | Vitals (essential health indicators) |
| `OBSERVATIONS_AND_ACTIONS_SECURITY.csv` | Security |
| `OBSERVATIONS_AND_ACTIONS_PERFORMANCE.csv` | Performance |

An unknown suffix "just works" — `OBSERVATIONS_AND_ACTIONS_RELIABILITY.csv`
becomes a "Reliability" topic automatically.

### Adding an item

Append a row to the relevant CSV and re-run `python3 build.py`. That's it.

### Adding a topic

Create `OBSERVATIONS_AND_ACTIONS_<TOPIC>.csv` with the same six headers, drop it
in this directory, and re-run `python3 build.py`. A topic pill is generated
automatically (topics share the single Concertim-orange accent).

### Why there is no priority / severity on each item

The `Concertim Impact Rating` column is **intentionally dropped** from the
generated site. What's urgent depends entirely on the specific customer, site,
and the assets an observation touches — a "critical" filesystem fill on one
cluster may be routine headroom on another. Surfacing a fixed rating would imply
a ranking that doesn't hold across environments. That caveat is stated once, in
the site's **About** panel. Keep the column in the CSV if it's useful internally;
the build ignores it.

## Incomplete rows are shown, not hidden

The build does **not** invent missing content. If a row is missing any of its
description / potential service impact / statement of work, or contains an
authoring placeholder (`SOME NOTE`, `TODO`, `FIXME`, `TBD`, `TBC`,
`MAKE IT SPECIFIC`, `PLACEHOLDER`), it is:

- badged **Draft** and rendered in a muted style,
- shown with "Not yet documented" lines for the empty sections,
- and for placeholder lines, the placeholder text is lifted into an
  "Authoring note" callout rather than presented as the real description.

Flagged rows are listed on stdout at build time so you can clean them in the CSV
and re-run to drop the badges.

## Rebuilding the template

`build.py` injects the JSON data and a build date into `template.html`
(`__DATA__` / `__BUILD__` placeholders). All the HTML, CSS and JavaScript lives
in `template.html`, so you can restyle or change behaviour there without touching
Python — just re-run `python3 build.py`.

## Deploy

The generated `docs/index.html` is fully self-contained. Copy the `docs/`
folder to any static host (or open it directly). For GitHub Pages, serve from
the **`/docs`** folder — Pages' "deploy from a branch" mode only supports the
repo root or `/docs`, which is why the build writes to `docs/`. (To use a
custom domain, add a `docs/CNAME`.)

## Companion PDF

```
python3 build_pdf.py
```

Generates `docs/hpc-health-observations.pdf` — a print-ready A4 document for
shipping in a customer information packet. It reuses `build.py`'s data loader,
so the PDF and the website always draw from the same CSVs and never drift.

The PDF has:

- a **cover page** with the Concertim-orange accent, title, and a prominent
  **Generated** timestamp,
- an **About** section with the same non-prescriptive intent and the
  no-priority/severity caveat,
- a "what's inside" topic summary,
- each topic on its own page, with every observation as a card showing the
  description, potential service impact, and "where we'd start looking" steps
  (orange-numbered), **Draft** badges for incomplete rows, and authoring-note
  callouts where relevant,
- a footer on every page with the generated timestamp and `Page N / M`.

**Requirements:** the `playwright` Python package and a Chromium browser
(already present where this guide was developed). Elsewhere, install once:

```
pip install playwright
python -m playwright install chromium
```

The print styling lives in `pdf_template.html` (`__GENERATED__`, `__COUNT__`,
`__TOPICS_SUMMARY__`, `__TOC__`, `__BODY__` placeholders); edit it there and
re-run `python3 build_pdf.py`.

## Layout

- **Topic pills** (Vitals / Security / Performance / …) with counts.
- **Scope pills** that adapt to the selected topics (scopes differ per topic).
- **Free-text search** across every field.
- **Grid view** — expandable cards; each opens "Where we'd start looking" to
  reveal the potential service impact and our starting approach.
- **Walkthrough view** (`≡` button) — one item at a time, with `←` / `→`
  navigation and `Esc` to exit; deep-linkable via `#<topic>-<slug>` anchors.
- **Light / dark theme**, remembered across visits.
- **Print** — the whole guide prints with all disclosures expanded.