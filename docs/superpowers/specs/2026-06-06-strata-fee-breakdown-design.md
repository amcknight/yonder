# Yonder — Strata Fee Breakdown View (Design)

*Date: 2026-06-06. Status: approved design, pre-implementation.*

Companion to `docs/brainstorm/v1-scope.md` (the Strata Health Visualizer is the
signature v1 feature), `docs/brainstorm/doc-pipeline.md` (the extraction layer this
extends), and `2026-06-04-reserve-trajectory-view-design.md` (the sibling hero view
this links into). Reference mocks: the iterated phone mockups under
`.superpowers/brainstorm/` (gitignored, throwaway), final = `final.html`.

## What this is

The second view in the **Strata Health Visualizer** family. Where the Reserve
Trajectory view answers *"will the savings cover what's coming?"*, this view answers
the everyday companion question a buyer (or owner) asks and can't easily answer:

> **What is my strata fee actually buying — and is any part of it quietly climbing?**

A single phone screen: a sorted bar list of the building's annual operating expenses,
each bar scaled to **the user's own monthly share** of that category, with the
**Reserve contribution pinned on top** (the one "saved, not spent" row, linking
through to the Reserve Trajectory view). On-screen change signals — an in-bar delta
cap, a personal-dollar diff, a per-category sparkline, and a total-fee-over-time
header — are layered so that a reader **never needs to open a PDF to ask "is this a
blip or a trend?"**. That last property is the load-bearing design principle:
surface everything that matters, stay quiet about what doesn't, keep people out of
the source docs.

This is a **vertical slice**, same as the Reserve view: prove it on one real
building's actual documents before any app UI.

## Why bars, not a flow/Sankey (recorded decision)

The feature was explored at length as a fund-flow **Sankey/ribbon** chart (money in →
the strata → where it goes). It was **rejected**, and the reasoning matters enough to
record so we don't re-litigate it:

- **Single-year flow ribbons carry no information.** Every owner's dollar is fungible:
  it pools into one fund and pays everything pro-rata. A ribbon from "the penthouses"
  to "the strata" tells you nothing a bar doesn't — there is no real routing from a
  specific source to a specific sink. The convergence-into-one-node makes the ribbons
  decorative.
- **The two-fund split (Operating vs CRF) is a near-circular hop, and a Special-Levy
  fund is episodic** ($0 most years, six figures occasionally) — neither earns a
  structural tier in a steady annual view. Reserve is best shown as one *pinned
  destination*, not a fund that re-emits.
- **Ribbons only become honest across *time*** (an alluvial of each category over
  years). That richness is real but is captured more legibly here by per-category
  **sparklines + a delta cap**, without the cognitive cost of a flow diagram on a
  ~390px screen.

The flow exploration is preserved in the throwaway mocks; the bar design is the
product.

## The locked chart

Phone-first (~390px), rendered (for now) in the throwaway HTML mock — the **only**
viewer, exactly as in the Reserve view. Top to bottom:

1. **Total-fee-over-time header card.** The building's *total* monthly fee as a big
   number plus a sparkline and a plain-language trajectory (`$600/mo · ↗ +$40/mo over
   3 yrs`). This is the "am I on an escalator?" headline. It needs only one number per
   year, so it is the cheapest trend to source.
2. **Reserve contribution — pinned, boxed, set apart.** The single "saved" row, green,
   with a **tap-through to the Reserve Trajectory view**. Always on top regardless of
   size, because it is the most decision-relevant signal and the bridge to the sibling
   view. Labelled `Reserve contribution`; no "→ savings" caption.
3. **Spend categories — sorted by size, descending.** One bar each. Per bar:
   - bar width = the category's share, drawn to **the user's personal monthly dollars**
     (e.g. `$196/mo`), with the **building annual total printed inside the bar**
     (`$350k`); for bars too narrow to hold text, the total sits just after the bar in
     grey.
   - right cluster on the label line: a grey **personal-dollar diff** immediately left
     of the bold monthly figure — `+$6  $196/mo` — shown only when it moved.
   - an **in-bar delta cap**: a white seam at last year's mark when it grew, a dashed
     hollow box past the bar end when it shrank.
   - a small **sparkline**, coloured in the bar's colour **only when the category
     moved**, faint grey and flat when steady. Always present (fixed column) so rows
     stay aligned; colour itself is the "look here" signal.
4. **Tap a bar → its line items** (Utilities → water/sewer, heat, electricity, gas,
   garbage). Single-line categories (often Insurance) don't expand.

### Categories (open vocabulary)

Operating line items roll up into a small set of parent categories. v1 seed:
**Utilities, Repairs & maintenance, Insurance, Security & life-safety, Building
services, Administration**, plus **Reserve contribution** (pinned). Mapping is an
**open vocabulary with an `Other` fallback** (mirrors `DocType`): an unrecognized
account name lands in `Other` rather than being force-fit or dropped. The line-item →
category mapping is part of extraction (the model proposes a category per line item),
not a hardcoded account-number table — account schemes differ per management company
(Spectrum's `4050 Insurance` vs the Sterling's `5100 Insurance`).

### The personal share (the "sliver")

Each bar is sized to **the user's own dollars**, not the building's. Source: the
**per-lot strata-fee schedule** in the AGM package, which lists each lot's monthly fee
split into its **Operating** and **CRF** contributions by **unit entitlement**. The
user's lot gives their exact monthly fee; each category's personal figure is
`category_share × user_monthly_operating_fee` (Reserve uses the CRF contribution
directly). This is honest per-user, in-context computation — **never pooled** across
users (the one rule).

## Scope: v1 vs v1.1

A hard finding from pulling the real docs shapes the split:

> `pdftotext` reliably yields a **single year's** category budget, but **multi-year**
> budget tables scramble badly when flattened, and prior-year budgets are buried as
> attached schedules. Trustworthy multi-year numbers require the **LLM extraction**
> this feature builds — they cannot be shortcut with plain text parsing.

So the trend layer is gated on extraction, and we ship in two honest steps:

**v1 — single-year breakdown (unblocked, independently valuable).**
- Sorted bars + pinned Reserve, personal-dollar sizing, building totals, tap-to-line-items.
- Sourced from the **approved AGM operating budget** (what the fee is set to cover).
- No caps / diffs / sparklines / total-trend yet — they simply don't render with one
  year of data (graceful degradation, same philosophy as the Reserve view's
  `degraded` state).

**v1.1 — the trend layer (after multi-year extraction).**
- **Total-fee-over-time** first — cheapest (one number/year), highest signal.
- Per-category **delta caps, personal-dollar diffs, and sparklines** once category
  budgets are extracted across consecutive AGM years.
- **Budget-vs-actual overlay** (a stretch within v1.1): the financial statement
  carries both columns + variance, enabling a "where it went off-plan" read on the
  same chart.

## Approach (chosen): extract → compute → JSON → existing mock

Same shape as the Reserve view, reusing its seams:

1. **Schema extensions** to `StrataExtract` — add an **operating budget** (line items:
   account label, parent category, annual amount, fiscal year) and a **per-lot fee
   schedule** (lot id, entitlement, operating contribution, CRF contribution). v1.1
   adds the prior-year amounts (carried by extracting multiple AGM budgets and keying
   by category + year).
2. **A pure computation layer** — `fee_breakdown(facts, unit) → FeeBreakdown`, a
   deterministic Python function: roll line items into categories, compute the user's
   personal per-category dollars from their lot's fees, compute year-over-year deltas
   and the total-fee series when ≥2 years are present, flag movers (share moved
   > 1 point). No projection/assumptions — unlike the Reserve view this is reporting,
   not forecasting.
3. **A `FeeBreakdown` JSON contract** (a new `src/yonder/<view>/model.py`, sibling to
   `outlook/model.py`) — carries everything the chart needs to render client-side:
   building meta, unit meta, the category rows (label, category, building annual,
   personal monthly, prior-year, line items), the total-fee series, and `degraded` /
   `degraded_reason` for the one-year case.
4. **Render in the existing throwaway HTML mock**, populated from real numbers.

This forces the same pipeline stages the Reserve view needs (classify the AGM package
in a folder of many files; extract its budget + fee schedule), and adds the
**multi-year aggregation** stage — keying the same building's budgets across years —
which is new and which the trend layer demands.

## Honesty rails (the one rule)

- Everything is **computed and displayed in-context for the individual user**. The
  personal share is *their* lot in *their* building's docs. **No cross-user pooling**,
  no standalone dataset.
- Real strata docs stay in `fixtures/strata/` / `~/Documents/Stratas`, **gitignored**.
- Degrades gracefully: missing fee schedule → show building totals only, no personal
  sizing; one year of data → bars only, no trend layer; unrecognized line item →
  `Other`, never dropped or invented.

## Out of scope (parked, with rationale)

- **Owner bands by entitlement chunk** — grouping units that share an identical
  entitlement (genuine same-floor-plan cohorts, derivable from the fee schedule alone).
  Compelling and honest; a within-year *tap-in* detail, not v1 surface. Fast-follow.
- **Parallel "total housing cost" frame** — strata fee as one tributary beside
  mortgage / property tax / personal insurance. A buyer's-eye view; pulls in non-strata
  (public/personal) data. Later.
- **Sankey / fund-flow** — rejected (see "Why bars" above).
- App UI / React Native, MLS, email, cross-building anything.

## Testing

TDD, per the project workflow. Pure `fee_breakdown` computation is unit-tested against
hand-built fact fixtures (rollup correctness, personal-share math, delta/mover
flagging, the degraded one-year path). Extraction is validated against a real building
(Spectrum 4 has the cleanest single-year budget; the Sterling has the per-lot fee
schedule + the user's own lot 1802 for the personal share). Live extraction test skips
without an API key, mirroring the existing integration test.

## Appendix — visual decision trail

The design was reached through ~10 iterated mockups (gitignored). Key turns, recorded
so the *why* survives the throwaway HTML: flat single-year Sankey → "ribbons are
overkill" → spent/saved fork → "reserve→reserve is circular" → back to simple → the
convergence insight ("everything into one node makes ribbons decorative") → time-axis
alluvial → "losing the value thread" → **sorted bars with delta caps** → personal-dollar
sizing → trend layer (caps + diffs + sparklines + total-over-time) → real-data reality
check (multi-year needs the LLM) → **Reserve pinned on top**. Final = `final.html`.
