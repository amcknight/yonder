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

### 2. Bubble = dominant category

For each year:
1. Bucket that year's items into the ~5 systems.
2. **Sum dollars per system** (not per line item).
3. Fill the bubble with the color of the largest-dollar system.

Radius still encodes total spend; the count badge stays. So a year reads as
*when · how big · what flavor* with no interaction.

Summing per system before picking the dominant matters: in 2037, "Domestic
Water Pipes" is one $1M line, but envelope (membranes + walls + guardrails +
roof + doors) summed is larger — so 2037 should read as **envelope**, not
plumbing.

### 3. Expanded list = swatch dots

The tap-to-open per-year box lists each line item. Each item gets a small
colored dot to its left matching its system:

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

### 5. Data seam

Add an optional field to `Expenditure` ([src/yonder/outlook/model.py](../../../src/yonder/outlook/model.py)):

```python
category: str | None = None   # one of the ~5 system buckets; None -> classifier fallback
```

The renderer uses `category` when present, otherwise falls back to the keyword
classifier. So:

- **Today:** mockups carry no `category`; the renderer classifies by label. Works
  immediately.
- **Later:** the extractor can populate `category` directly with no renderer
  change.

The keyword classifier is the single source of truth for label → system mapping
and is shared by both the renderer fallback and (eventually) any
extractor-side defaulting.

## Explicitly out of scope (YAGNI)

- **Rim-arcs / donut bubbles** showing the full category blend on the bubble —
  die at small phone sizes. Revisit only if dominant-color-only feels too lossy
  on real data.
- **Icons / glyphs** per system — more design work than swatch dots; the dot +
  legend covers the need.
- **Swimlanes** and **stacked bars** — both discard the radius = magnitude read,
  which is the chart's strongest feature, and cost vertical space on a phone.

## Open questions (defer to implementation / review)

- Final hex values + whether the user wants any semantic leaning within the
  collision-safe space (decided after seeing them on real data).
- Tie-break rule when two systems are within a few % of each other for dominance
  (proposed: stable priority order Envelope > Mechanical > Plumbing&Fire >
  Electrical&Vertical > Amenities, so the read is deterministic).
- Whether the legend should hide systems absent from the current building's data
  (proposed: yes — only show colors that actually appear).
