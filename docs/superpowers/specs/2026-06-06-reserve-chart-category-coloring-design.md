# Reserve chart — category coloring design

**Date:** 2026-06-06
**Status:** Approved (brainstorm), pending implementation plan
**Scope:** Reserve-trajectory chart (mockups today; renderer + `ReserveOutlook`
schema). Phone-first (~390px).

## Problem

The reserve-trajectory chart shows each year's major work as a bubble in a
bottom lane: position = *when*, radius = *how much*, a count badge = *how many
items*. What it cannot show is **what kind** of spending is coming. A buyer
scanning the timeline can see "a big year hits in 2037" but not "2037 is a wall
of envelope and plumbing work" without tapping the bubble open.

**Goal:** let a buyer scan the timeline and read *what kind of spending is
coming when* — at a glance, no tap required.

## Constraints

- **Phone-first (~390px).** Bubbles are small (radius ~4.5–16px). Anything that
  relies on sub-8px detail (pie/donut wedges) is unreadable and out of scope.
- **Palette collision.** The chart's lines already own the obvious colors:
  cyan = actual, green = projected / levy, amber = unfunded, indigo = work.
  The category palette must avoid cyan / green / amber so it never fights the
  lines. (This rules out the intuitive "piping green" and "pool blue".)
- **~5 buckets.** Five distinct hues survive a phone screen and colorblind
  viewers; 8+ turns to mud. The exact taxonomy can settle as real labels are
  seen — five is the target, not a hard cap.

## Design

### 1. Taxonomy + palette

Raw expenditure labels (~30 distinct in real data) collapse into ~5 systems by
keyword match. Starting set — refine as real labels accumulate:

| System | Catches (keywords) | Color |
|---|---|---|
| Envelope | roof, wall, window, membrane, sealant, guardrail, balcony, door, paint coating | violet |
| Mechanical | HVAC, boiler, hot water, expansion/reheat tank, cooling tower, heat exchanger, pump | orange (not amber) |
| Plumbing & Fire | pipe, sprinkler, fire, drainage, sump, water main | rose / magenta |
| Electrical & Vertical | elevator, generator, power, lighting, electrical, distribution | teal (not cyan) |
| Amenities & Site | lobby, hallway, common, playground, landscaping/soft/hardscape, water feature, mailbox, signage | slate-gray |

Exact hex values are tuned during implementation against the dark slate
background (`#0f172a`); the user will sanity-check how they feel on real data.
Slate-gray intentionally reads as "misc / cosmetic" — the de-emphasized bucket.

### 2. Marker color — dominant, optionally a donut

For each year, bucket that year's items into the ~5 systems and **sum dollars
per system** (not per line item). Then color the marker:

- **Baseline (solid dominant):** fill the bubble with the largest-dollar
  system's color.
- **Optional (multicolor donut):** for years whose spend genuinely spans
  multiple systems, render the marker as a donut split into 2–3 wedges by
  dollar share. Only the **big** years (e.g. 2037) have the pixels to carry
  this on a phone; **small** years fall back to the solid dominant fill. This
  was first cut as YAGNI but is back **in scope for the preview** to evaluate —
  the user will judge whether the blend read is worth the busier marker.

Radius still encodes total spend; the count badge stays. So a year reads as
*when · how big · what flavor* with no interaction.

Summing per system before picking the dominant matters: in 2037, "Domestic
Water Pipes" is one $1M line, but envelope (membranes + walls + guardrails +
roof + doors) summed is larger — so 2037 should read as **envelope**, not
plumbing.

### 3. Expanded list = swatch dots (priority)

This is the **must-have** of the feature. The tap-to-open per-year box lists
each line item; each item gets a small colored dot to its left matching its
system:

```
● Domestic Water Pipes            $1.0M
● Balcony Guardrails              $316k
● Elevator Modernization         $196k
```

This is where the blend that the single bubble color hides becomes visible — a
two-flavored year shows two dot colors here even though the bubble shows one.

### 4. Legend

A second small legend row beneath the existing line legend maps the 5 colors →
system names. Required because swatch dots are not self-explanatory. Keep it
compact (single wrapping row, small type) to respect phone width.

### 5. The classifier (now) + data seam (deferred)

The label → system mapping is the durable, fussable core ("is a water feature an
amenity or plumbing?"), so it is built **now** in tested Python:

```python
def categorize(label: str) -> str   # -> one of the ~5 system bucket names
```

backed by an ordered keyword table. The preview sketch mirrors the *same* small
keyword table in JS (the only duplicated bit; small and stable).

**Deferred to the "make it real" round** (after the user likes the colors): an
optional `category: str | None = None` field on `Expenditure`
([src/yonder/outlook/model.py](../../../src/yonder/outlook/model.py)), so the
renderer can prefer an extractor-supplied category and fall back to `categorize`.
Not built in this round.

## Two-round delivery

- **Round 1 — quick color preview (this plan):** Python `categorize` classifier
  (TDD) + a visual preview that colors the bubble sketch on real Spectrum 4 data:
  dominant/donut markers, swatch-dot expanded list, category legend. Goal: let
  the user see how the colors feel without touching the hardened chart.
- **Round 2 — make it real (later, separate plan):** fold the per-year-bubble +
  coloring into the canonical JSON-driven chart, add the `category` schema field
  + extractor wiring. Only after Round 1 colors are approved.

## Explicitly out of scope (YAGNI)

- **Icons / glyphs** per system — more design work than swatch dots; the dot +
  legend covers the need.
- **Swimlanes** and **stacked bars** — both discard the radius = magnitude read,
  which is the chart's strongest feature, and cost vertical space on a phone.
- **Schema `category` field + extractor wiring** — deferred to Round 2 (above).

## Open questions (defer to implementation / review)

- Final hex values + whether the user wants any semantic leaning within the
  collision-safe space (decided after seeing them on real data).
- Tie-break rule when two systems are within a few % of each other for dominance
  (proposed: stable priority order Envelope > Mechanical > Plumbing&Fire >
  Electrical&Vertical > Amenities, so the read is deterministic).
- Whether the legend should hide systems absent from the current building's data
  (proposed: yes — only show colors that actually appear).
