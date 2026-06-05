# Yonder — Reserve Trajectory View (Design)

*Date: 2026-06-04. Status: approved design, pre-implementation.*

Companion to `docs/brainstorm/v1-scope.md` (the Strata Health Visualizer is the
signature v1 feature), `docs/brainstorm/doc-pipeline.md` (the layer this motivates),
and the Prototype-1 spec `2026-05-28-strata-extraction-prototype-design.md` (the
extraction core this builds on). Reference mock: the iterated phone mockups under
`.superpowers/brainstorm/` (gitignored, throwaway), final = `reserve-v6.html`.

## What this is

The **Strata Health Visualizer** is the v1 signature feature — a set of *views* over
a building's strata documents. This spec scopes its **first and hero view: Reserve
Trajectory × Work** — the one that answers the question a strata buyer most wants
answered and can least answer themselves:

> **Will the reserve fund cover the work that's coming — or is a special levy
> coming, roughly when, and how much would it cost *my* unit?**

The view plots the contingency reserve fund (CRF) balance over time — **actual** past
balances flowing into a **projected** future — against the depreciation report's
**projected major expenditures**, and lets the user drag a **strata-fee what-if
slider** to see the fund go from doomed to solvent (and watch their own monthly fee
and levy risk move with it). It is, deliberately, the same view whether you're
*buying* a unit or you *own* one.

This is a **vertical slice**: prove the hero view end-to-end on one real building's
actual documents, before building the other candidate views (Appendix A) or any real
app UI.

## Goal

Turn the validated mockup into a real artifact computed from **Spectrum 4's actual
strata documents**. Concretely: extract the facts the chart needs, compute the
projection, emit a `ReserveOutlook` JSON, and render it in the existing throwaway
HTML mock. Success = the locked chart, drawn from real numbers, not invented ones.

The secondary goal — equally important — is that doing this **forces the first real
decisions in the under-designed document pipeline** (`doc-pipeline.md`). The chart is
the concrete thing that *demands* classification (find the depreciation report, Form
B, financials, minutes in a folder of 63 files) and aggregation (merge per-file facts
into one building-level outlook). We build those stages because this view needs them
— "one stage per demonstrated need," exactly as the pipeline doc prescribes.

Non-goals: a real app UI / React Native (the HTML mock is the *only* viewer); the
other Visualizer views (Appendix A); MLS or email data; OCR or heavy table parsing
(deferred-until-hit per Prototype 1); the dual-graph "monthly carry" experiment
(explored and parked — Appendix C); cross-building anything.

## Approach (chosen)

**Extract → compute → JSON → existing mock.** Four pieces:

1. **Schema extensions** — add the facts the chart needs to `StrataExtract`
   (depreciation-report projections, recommended contribution, balance history,
   unit fee, planned fee changes). The depreciation report is the keystone source.
2. **A pure computation layer** — `reserve_outlook(facts, assumptions) → ReserveOutlook`,
   a deterministic Python function that reproduces the model now living in the mock's
   JS (contributions, interest, expenditures, levy injection, planned increases, the
   what-if). This is the **TDD heart** of the slice — pure, testable, no LLM, no I/O.
3. **Pipeline: classify/route + aggregate** — turn Spectrum 4's *folder* into the
   per-building fact set the computation layer consumes. The two stages
   `doc-pipeline.md` already marks "New v1 work."
4. **Emit + render** — write `ReserveOutlook` as JSON; the existing mock reads it and
   draws the locked chart. The JSON is **per-user, ephemeral** (the one rule) — it is
   computed-and-displayed for this user, never pooled.

Rejected: building a real UI now (the mock proves the view for free, and Prototype 1's
"no UI" rule still holds — the mock is a measurement tool, not the product). Rejected:
building all five pipeline stages on spec (only classify + aggregate are demonstrated;
OCR/heavy-parse stay deferred-until-hit). Rejected: hard-coding model assumptions
(interest rate, fee-escalation default) as truth — they are **placeholder assumptions**
until grounded by the deferred deep-research pass.

## Build order & the JSON seam (chosen)

This slice splits at the `ReserveOutlook` **JSON contract**, and we build
**json → dashboard first, then docs → json**:

1. **json → dashboard (first).** Freeze the `ReserveOutlook` JSON shape; hand-author a
   realistic instance (reading Spectrum 4's depreciation report by hand); rewire the
   committed mock (`docs/mockups/reserve-trajectory.html`) to *consume that JSON*
   instead of its hardcoded JS constants. Outcome: a runnable end-to-end render of
   real-shaped data, and — more importantly — a **frozen contract** that becomes the
   concrete target for the extraction half.
2. **docs → json (second).** Build classify → aggregate → extract → `reserve_outlook`
   to *produce* that JSON from Spectrum 4's actual docs — building toward a known
   target instead of a moving one.

**Storage = JSON** for the prototype (per-user, ephemeral — the one rule). SQLite is
unnecessary for a single building's outlook; Postgres is the eventual cloud target
(architecture sketch), not this slice. Revisit only when querying across many
docs/buildings/users is real.

**Selective extraction, not all 63.** The reserve view needs only ~4–8 documents — the
latest depreciation report, Form B, recent financial statements, recent minutes — so
classify's job is to *select* those, not organize the whole folder. Spectrum 4's
subfolders already signal most of them; Claude-assisted classification is a fallback
for unlabeled files, not the primary cost. The extraction core itself already exists
(Prototype 1: `client.py` / `strata.py` / `schema.py`); the genuinely hard, risky part
is pulling the depreciation report's **30-year expenditure tables** — that risk lives
entirely in the docs→json half, which is exactly why we freeze the contract first.

## The view (locked design)

What the chart shows — validated across six mock iterations:

- **One shared time axis**, years along the **top**, with a **"now"** divider.
  Spans real history → multi-decade projection; needs horizontal **pan/zoom** for
  long spans (deferred interaction — Appendix B).
- **Actual balance line** (solid) from past financial statements, left of "now".
- **Projected balance line** (solid) right of "now", reacting to the slider.
- **"If unfunded" ghost** (dashed) showing where the balance *would* go with no levy —
  the honest contrast to reality.
- **Reserves never go negative.** When a projected expense outruns the fund, a
  **special levy injects cash** (green bar **up** from $0), labeled with the **per-unit
  cost** (via unit entitlement). Work pulls the line **down** (indigo bars); levies
  push it **up** (green) — a clean visual grammar. (Domain note: a BC strata can't
  spend money it doesn't have; it raises a ¾-vote special levy or, increasingly, a
  strata *loan* — the loan path is a future modeling option, Appendix B.)
- **Dated events** in a **two-row bottom lane** (so labels don't collide): work items,
  meetings, and **planned fee changes** from the minutes. A planned increase (e.g.
  "+10% Oct 2027") is a flag that **actually bends the projected line**, not just an
  annotation. Crowded events **collapse into a count badge** that expands on
  long-press into a fanned bubble overlapping content below.
- **The fee what-if slider** (−30% … +150%, with a zero mark) is the lever. Dragging
  it moves the projected line, the user's **monthly fee** ($486 → …), the **reserve
  contribution**, and the **total per-unit levy risk** — **Money Snapshot folded into
  the lever** rather than a separate panel. The on-brand default isn't a generic
  average; it's the depreciation report's own **recommended contribution schedule**,
  with qualitative signals from minutes ("council discussed 10% for 2027").

Y-axis is labeled in dollars ($1.0M / $500k / $0 / −$500k). Phone-first sizing
(~390px) per `project-yonder-platform` — chart text sized for mobile, not scaled-down
desktop.

## Computation layer

```
reserve_outlook(facts: ReserveFacts, assumptions: Assumptions, fee_delta: float)
    -> ReserveOutlook
```

A pure function. No LLM, no I/O — just arithmetic over the extracted facts. Year by
year from "now":

```
contribution(y) = base_annual_contribution * (1 + fee_delta) * planned_factor(y)
balance(y)      = balance(y-1) * (1 + interest) + contribution(y) - expenditure(y)
if balance(y) < 0:  levy(y) = -balance(y);  balance(y) = 0   # injection, floored at 0
```

`ReserveOutlook` carries: `actual[]` (year, balance), `projected[]` (year, balance),
`levies[]` (year, total, per_unit), `events[]` (year, type, label, row/cluster),
`expenditures[]` (year or range, amount, label), `assumptions` echoed back, and a
`degraded` flag + reason when inputs are missing (below). Per-unit levy =
`levy_total * (entitlement.numerator / entitlement.denominator)`.

`planned_factor(y)` applies the building's **known** scheduled increases (from
minutes) cumulatively; `fee_delta` is the user's *additional* what-if on top. Both the
"with levy" reality track and the "if unfunded" ghost are returned.

**TDD targets** (deterministic, CI-safe): contribution escalation, interest
compounding, levy injection and flooring-at-zero, per-unit math from entitlement,
planned-increase bending, the slider as a pure parameter, and the degraded path. This
is where correctness is proven; the mock is just a renderer of its output.

**Assumptions are explicit and labeled.** `interest`, the default fee-escalation, and
any horizon length live in `Assumptions` with sourced-vs-placeholder provenance, so
the chart never presents a guess as a fact. Real defaults await the deep-research pass.

## Schema extensions (`schema.py`)

Additive, all nullable, absence is first-class (Prototype-1 philosophy — "health
factors are additive; adding one is a localized change, not a refactor"). New facts
the chart needs:

| Field | Source doc | Notes |
|---|---|---|
| `unit.strata_fee` (monthly) | **Form B** | the lever's anchor |
| `unit.crf_contribution` (monthly) + operating/reserve split | **budget** | reserve portion of the fee |
| `crf_balance_history[]` (date, balance) | past **financial statements** | the actual line; usually only 1–3 yrs available |
| `projected_expenditures[]` (year or **range**, amount, component, label) | **depreciation report** | the work bars; ranges supported (e.g. envelope 2031–33) |
| `recommended_contribution` + `funding_model` | **depreciation report** | the data-grounded slider default |
| `planned_fee_changes[]` (effective_date, pct or amount, source) | **minutes / budget** | the line-bending events |

`special_levies[]`, `unit_entitlement`, `reserve_fund` already exist (Prototype 1).
The **depreciation report is the keystone** — four of these fields die without it,
which is exactly why the degraded path matters.

## Pipeline stages this forces

Spectrum 4 is a *folder* of 63 PDFs in nested subfolders, not one combined PDF. To
feed `reserve_outlook`, we build the two stages `doc-pipeline.md` marks "New v1 work":

- **Classify / route / dedup** — identify which files are the depreciation report,
  Form B, financial statements, and minutes (filename heuristics + first-page text,
  cheapest-that-works), with their dates; drop `(1)`/`ATTACH` near-duplicates. Spectrum
  4's `Depreciation report & Engineering report/` folder is a gift here (foldername is
  a strong signal); Cambie, with no obvious report, is the routing/degradation test.
- **Aggregate** — merge per-file `StrataExtract`s into one building-level `ReserveFacts`:
  latest depreciation report wins for projections, financials provide the balance
  history series, Form B provides the unit fee, minutes provide planned changes.
  Conflicts resolve by document recency; provenance survives the merge (so the future
  trust UI — "from the 2022 depreciation report, p.40" — still works).

Per the pipeline doc's discipline: **preserve + provenance** and **text-vs-scan triage**
are cheap and justified now; **OCR** and **heavy structural parsing** stay
deferred-until-hit. Originals stay immutable; derived artifacts are per-user/ephemeral.

## Data flow

```
Spectrum 4 folder (63 PDFs, gitignored)
        │  preserve + normalize (text-vs-scan triage)
        ▼
  classify / route / dedup ──►  per-file StrataExtract (extraction core, Prototype 1)
        │                              │
        └──────────► aggregate ◄───────┘
                          │   ReserveFacts (building-level)
                          ▼
              reserve_outlook(facts, assumptions, fee_delta)   ← pure, TDD'd
                          │   ReserveOutlook
                          ▼
                  emit JSON (per-user, ephemeral)
                          ▼
        existing HTML mock renders the locked chart on real numbers
```

## Graceful degradation

The right half of the chart rests entirely on the depreciation report, which can be
**absent** (waived by ¾ vote) or **stale** (3-yr cycle). When it's missing or out of
date:

- Render **present-state only** — current balance, this unit's fee, the actual history
  line — with a **loud "no current depreciation report — projection unavailable"**, and
  any work items found in *minutes* shown without a full projection.
- **Never fabricate** a projection. `ReserveOutlook.degraded` carries the reason; the
  chart shows the gap honestly.

**Cambie (no obvious depreciation report) is the explicit test case** for this path.

## Scope & sequencing

- **Build first:** schema extensions, `reserve_outlook` (TDD), classify + aggregate,
  JSON emit, render on **Spectrum 4**.
- **Then:** copy **Sterling** (has a report) and **Cambie** (no report → degradation
  test) from `~/Documents/Stratas` into `fixtures/strata/` (gitignored) and run them
  through. *Ask before copying the user's files.* (All three buildings — 97 PDFs — are
  the corpus `doc-pipeline.md` references.)
- **Defer:** the other five candidate views (Appendix A); a real app UI; the
  dual-graph monthly-carry view (Appendix C); pan/zoom, drag-to-reposition events,
  toggling hypothetical events on/off, landscape precision mode, strata-loan modeling
  (Appendix B); deep-research-grounded assumption defaults.

## Deferred UI-polish notes (from mock review)

Captured so they aren't rediscovered; **not** in scope for this slice:

- Event-label **collision handling** is still naive — labels overlap; needs real
  greedy row-packing / clustering by pixel distance.
- Dollar **readouts** want a distinct color and alignment with the panel title.
- The cluster bubble should **not reserve vertical space** when collapsed — if there's
  room it should already be expanded; if collapsed, opening overlaps content below
  (a popover), rather than pushing layout.

## Open questions for the plan pass

- **Intermediate store:** where do per-file `StrataExtract`s + normalized text live
  locally (sidecar files beside the gitignored original? a small local index)? (Open
  in `doc-pipeline.md` too.)
- **Classification method:** filename heuristics + first-page text vs. a cheap model
  pass — start cheapest.
- **Balance-history depth:** a single package usually yields only 1–3 yrs of actual
  balances; is that enough for a meaningful "actual" line, or do we ask for more years?
- **`reserve_outlook` location:** new `src/yonder/outlook/` module vs. under `extract/`?
- **JSON contract:** freeze the `ReserveOutlook` shape the mock consumes as the seam
  between compute and render.

## What "done" looks like

1. `StrataExtract` carries the new fields; schema unit tests pass.
2. `reserve_outlook` is fully unit-tested (contributions, interest, levy injection,
   per-unit math, planned increases, what-if, degraded path) — deterministic, CI-safe.
3. Classify + aggregate turn the **Spectrum 4 folder** into one `ReserveFacts`.
4. A `ReserveOutlook` JSON is produced from Spectrum 4's real docs and the existing
   mock renders the locked chart from it — real numbers, with provenance intact.
5. The **degraded path** is demonstrated (Cambie, or Spectrum 4 with the report
   withheld) — present-state only, no fabricated projection.
6. `pytest` green; real docs gitignored; assumptions labeled placeholder-vs-sourced.

The outcome we're buying: the signature view, proven on one real building, with the
two pipeline stages it forced now standing — the foundation the rest of the Strata
Health Visualizer grows from.

---

## Appendix A — the candidate view set (deferred)

Six views surfaced in brainstorming; each could anchor the dashboard. Reserve
Trajectory (this spec) is the hero; the rest are future slices:

- **Building Timeline** — meetings, reports, levies, planned work on one pan/zoom axis
  with a loud freshness mark. (User's #2 pick.)
- **Doc Freshness & Gaps** — what's present / stale / missing vs. a full package;
  diligence backbone, largely *derivable* from what extraction did/didn't find.
- **Money Snapshot** — folded into this view's slider; could also stand alone.
- **Health Verdict** — one synthesized at-a-glance read with the factors that drove it.
- **Risk & Restrictions** — insurance/deductible, defects flagged in reports, pet/age/
  short-term-rental rules.

## Appendix B — deferred interactions & modeling

Horizontal pan/zoom for multi-decade spans; drag-to-reposition ranged/uncertain
events; toggle hypothetical events on/off; landscape precision mode; **strata-loan**
funding as an alternative to lump-sum levies (spreads cost over years).

## Appendix C — parked experiment: dual-graph monthly carry

A second stacked graph (strata + property tax + insurance + levy, optional mortgage
layer) sharing the slider, showing the **smooth-vs-lumpy** tradeoff (pay more now in
fees vs. a levy spike later). Compelling but judged too dense for phone v1. Parked,
not discarded.

## Appendix D — full strata-doc info inventory

Everything a normal BC package (Form B/F, depreciation report, financials, minutes,
bylaws, insurance summary) can yield that's worth surfacing — captured for future
views. ✓ already extracted · ~ partial · ✗ new:

- **Money/fees:** unit strata fee ✗ · operating/reserve split ✗ · CRF contribution ✗ ·
  this-unit levy owed ✗ · arrears ✗ · fee-increase trend ✗ · parking/storage ✗
- **Reserve/capital:** CRF balance+date ✓ · trend ✓ · funded ratio vs. recommended ✗ ·
  projected 30-yr expenditures ✗ · funding model ✗ · depreciation-report age ~
- **Governance/ops:** council seated? ✗ · self- vs. professionally-managed ✗ · AGM on
  time/quorum ~ · recurring unresolved issues in minutes ✗ · approved-but-not-done work
  ✗ · bylaw/rule changes ✗
- **Risk/legal/insurance:** litigation ✓ · insured?/policy date ✗ · water-damage & other
  deductibles ✗ · defects flagged in engineering reports ✗ · envelope/rainscreen +
  remediation history ✗ · hazards (asbestos, oil tank) ✗
- **Restrictions/fit:** pet ✗ · age (55+) ✗ · short-term-rental ✗ · rental-disclosure ✗ ·
  move-in/other fees ✗ · owner-occupancy / investor density ~
- **Building context:** units/floors ✗ · year built / construction era ✗ · amenities ✗ ·
  commercial/mixed-use component ✗
- **Doc meta:** present-vs-expected checklist ✗ · per-doc freshness ✓ · low-confidence
  flags ✓
