# Yonder — Reserve Chart: Real-Data Hardening (Design)

*Date: 2026-06-05. Status: approved design, pre-implementation.*

Follows the docs→json MVP (`2026-06-04-docs-to-json-reserve-mvp-design.md`,
merged). The first real extraction (Spectrum 4: 47 components across 2022–2057)
exposed that the locked chart was tuned to the synthetic 6-event Wexford sample
and breaks on real reports. This hardens the chart to render *any* report
legibly. Design validated through live mockups (companion `realdata-v1…v4`).

## The problem (what real data broke)

A real depreciation report is a reserve study cataloguing **every** building
system (40–60 line items) over a **multi-decade** horizon. Rendered with the
synthetic-tuned chart, Spectrum 4 showed:

- **Event smear** — 47 long labels in two rows became an unreadable grey band.
- **Y-axis clipping** — fixed `$1.3M` cap; the real balance climbs to ~$3M+.
- **Slider touched the past** — fees changed pre-"now" balances.
- **No "now"** — no anchor separating elapsed work from future work.
- **Dead vertical space** — fixed SVG height left a gap above the verdict.

## Design (validated in mockups)

**1. Aggregate by year-bucket.** Collapse N components into one marker per year.
Spectrum's 47 → ~10 year-bubbles; the 18-item 2037 wave becomes one bubble. This
is the load-bearing move — it makes any report legible regardless of item count.

**2. The bubble lane.** Each year is a bubble whose **area encodes total spend**,
with the **item count inside**. Dollar labels are **greedily packed into rows** —
a label only drops to a lower row when it would collide, so spread-out years stay
on one line and only crowded clusters (Spectrum's 2022–25) stagger, with thin
connectors. Every bubble is labelled.

**3. Tap to expand, cost-first.** Tapping a bubble opens its components **ordered
by cost descending** (top 8 + "+N more"), so the $1M pipe job leads its year. Tap
again to close.

**4. Dynamic y-axis.** Snap min/max to a "nice" step computed from the data so
the axis fits the real range instead of clipping. **$0 is always a gridline**, and
becomes a **bold, bright line** whenever any series dips below it (the unfunded
ghost, or a slider-induced shortfall).

**5. The "now" split.** A vertical **now** line at *today*. The reserve line is
**cyan (actual/elapsed) before now**, **green (projected) after**. Past-work
bubbles render **hollow/dashed** (already due). The "if-unfunded" ghost is drawn
**future-only** (the past is settled).

**6. Fees move only the future.** The slider's contribution multiplier applies to
years **after now**; the past segment is frozen. (Fixes the "strata changes affect
before-now" bug.)

**7. Shrink-to-content height.** The SVG sizes to its content (no dead gap before
the verdict) and grows only when a bucket is expanded.

## Where it lives

This is **presentation logic**, so it belongs in the chart, not the data layer:

- Fold the design into the committed `docs/mockups/reserve-trajectory.html`,
  which already renders a `ReserveOutlook` (synthetic Wexford default; real via
  `?data=`). The bucketing, packing, dynamic axis, now-split, and expand
  interaction are JS in that file. It must render **both** the 6-event synthetic
  sample and a 47-event real outlook cleanly.
- **`assemble.py` stays as-is** — it still emits flat per-component
  `expenditures[]` and `events[]`; the chart aggregates them by year at render
  time. The one likely contract touch: the renderer needs to know where "now" is.
  Default to *today's* year in the browser; optionally let `ReserveOutlook`
  carry an explicit `as_of`/`now_year` (decide at plan time). The existing
  range→point collapse and event derivation in `assemble` can be **simplified or
  dropped**, since the chart now buckets components directly.

## Testing

The chart is JS in a throwaway-then-committed mock; verification is **in-browser**
(controller drives it via the local server + `?data=`), checking it renders both
the synthetic sample and the real Spectrum 4 outlook without smear or clipping. If
any aggregation moves into Python, TDD it there. No new API calls.

## Scope & deferred

**In scope:** the seven items above, against both synthetic and real data.

**Deferred (in priority order):**

1. **Horizontal pan/zoom** — the highest-value follow-up. A 35-year span squashes
   the near-term $0–2M detail under the far-future peak; reports always span
   decades, so the time axis must pan/zoom rather than fit-all. Pulled forward
   from the original deferred list.
2. **Phone-size verification** — bubbles/labels at ~8–9px must be checked on a real
   ~390px device; sizes may need a bump. (Phone-first per `project-yonder-platform`.)
3. **Minutes cross-reference for stale future-work** — an old report plans work for
   dates now in the past (Spectrum's 2022–25 items). Cross-reference the **minutes**
   to learn whether each was actually done. When unresolved, **surface it to the
   buyer as an active diligence question** ("the report planned $490k of
   balcony-membrane work in 2023 — was it done?"), prioritised by cost. This turns
   a data-staleness problem into a feature — an "open questions" surface — and is a
   new extraction/aggregation output, not just a chart change.

**Out of scope (separate concern):** the **cost mis-alignment** in the Spectrum
extraction (duplicate amounts across unrelated rows) is an extraction-accuracy
issue from the garbled text table — addressed by a sharper prompt or the
vision/PDF path, not by this chart work.

## What "done" looks like

1. `docs/mockups/reserve-trajectory.html` renders the **synthetic Wexford** sample
   (6 events) and a **real 47-item** outlook (`?data=`) — both legible: year-bucket
   bubbles, packed labels, tap-to-expand cost-first, dynamic axis with a always-on
   (bold-when-negative) $0 line, now-split cyan/green, future-only slider.
2. No dead vertical gap; height grows only on expand.
3. Browser-verified by the controller against both data sets.
4. Deferred items recorded (horizontal zoom next); the minutes-cross-ref idea
   captured as a future extraction feature.
