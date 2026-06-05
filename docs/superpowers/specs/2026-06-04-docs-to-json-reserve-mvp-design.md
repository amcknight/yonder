# Yonder — docs → json MVP: Depreciation Report → ReserveOutlook (Design)

*Date: 2026-06-04. Status: approved design, pre-implementation.*

Second half of the Reserve Trajectory slice. The first half
(`2026-06-04-reserve-trajectory-view-design.md` →
`2026-06-04-reserve-outlook-json-to-dashboard.md`, merged) froze the
`ReserveOutlook` JSON contract and made the mock render from it. This half
**produces** a real `ReserveOutlook` from an actual strata document. Companion:
`docs/brainstorm/doc-pipeline.md` (the cheap-first philosophy this refines).

## Goal

Prove the product's core unknown — **can Claude reliably pull a depreciation
report's 30-year financial forecast into structured facts?** — by turning
Spectrum 4's real `DepreciationReport (2).pdf` (76 pp, 6.1 MB) into a
`ReserveOutlook` JSON that renders in the existing mock. When this works, the
chart's entire right half (projected work, reserve trajectory, levy injections,
fee-slider what-if) is driven by **real building data**, not the synthetic
Wexford sample.

Non-goals: classification/routing automation, multi-building, Form B / financial
statements / strata plan extraction, balance history, per-unit fee from Form B,
PDF chunking for >100-page docs, OCR, the canonical Python projection function.
All deferred (see Scope).

## The keystone-minimal cut (decided)

**One document, one intelligence call.** The MVP extracts from the depreciation
report *only*. The report typically already states the current CRF balance,
recommended contribution, funding model, and the projected expenditure
schedule — enough to render the chart. Spectrum 4 has **no Form B**, so a
specific unit's fee/entitlement is unavailable; those become explicit
placeholders, and balance history is empty (the "actual" line honestly degrades
to just the *now* point).

## The load-bearing principle: the script ↔ intelligence frontier

The whole design hangs on one question — *what must be done by intelligence, and
what can be plain code?* The answer for this MVP:

| Step | Script / 🧠 Intelligence | How |
|---|---|---|
| 1. Select the doc | **Script** | The caller points `yonder outlook` at the report. (Model-based classification deferred — filenames are proven unreliable: `FS_Summary`, no Form B.) |
| 2. Prep the PDF | **Script** | 76 pp / 6.1 MB ≤ Anthropic's 100 pp / 32 MB cap → send the whole PDF as one document block (vision preserves table structure). Chunking deferred until a doc exceeds the cap. |
| 3. **Extract facts** | **🧠 Intelligence** | The *only* LLM call. Opus, forced tool-use into a reserve-focused schema. |
| 4. Assemble | **Script** | Map the extract → a `ReserveOutlook`; fill placeholders; flag degraded fields. |
| 5. Derive events | **Script** | Generate bottom-lane work events from `expenditures[]`. |
| 6. Emit JSON | **Script** | `model_dump_json` → gitignored per-user output. |
| 7. Render | **done** | the existing mock. |

**The boundary is two layers sliding in opposite directions — not one frontier.**

- **Mechanics → script, with more stages over time.** Orchestration work —
  routing, dedup, page-prep, assembly, validation, emit — is deterministic glue.
  The pipeline should grow *more* such stages over time, and each should be plain
  code wherever code suffices. Scripts get the structure; they do not read meaning.
- **Content → intelligence, on nearly everything.** Reading and reasoning about a
  document's *content* — understanding it well enough to report facts — should be
  done by an LLM for **almost every** document, once intelligence is cheap enough
  and the pipeline is trusted. The script layer never tries to "understand" a doc;
  it shuttles docs to/from the model and assembles the results.

These are not in tension: *slide toward scripting* for mechanics, *slide toward
the LLM* for content understanding. This MVP sits at the cheap end of both — a
thin script skeleton and a single content-reading call — but must not bake in
anything that blocks growth on either axis. Concretely, the per-doc intelligence
call is kept **generic** (one PDF → facts, like `extract/strata.py`), so expanding
to "read every doc" later is a *fan-out over docs* through more pipeline stages,
not a rewrite.

## The intelligence call (step 3)

- **Model:** `claude-opus-4-8` (the `client.py` default) — this is the hard
  reasoning case (a multi-page financial table read via vision). Generous
  `max_tokens` (the forecast has many rows).
- **Input:** the whole PDF as a base64 `document` block via the existing
  `ClaudeClient.extract_with_tool` seam. No trimming.
- **Output:** forced tool-use into a **reserve extraction schema** (new,
  focused — not the general `StrataExtract`):

  | Field | Meaning |
  |---|---|
  | `building_name` | strata/building name if stated |
  | `report_date` | the report's date |
  | `current_crf_balance` + `as_of_date` | opening CRF balance the forecast builds on |
  | `recommended_annual_contribution` | the report's recommended CRF contribution |
  | `funding_model` | e.g. "full funding", "current + inflation" (free text) |
  | `interest_or_inflation_rate` | the assumption the report uses, if stated |
  | `projected_expenditures[]` | each: `label`/component, `amount`, and `year` **or** `start_year`/`end_year` for phased work |

- **Prompt strategy:** "Extract the financial forecast / contingency-reserve
  expenditure schedule. For each major component give the year(s) and projected
  cost. Capture the recommended annual contribution and the funding model. Use
  the report's own opening balance. **Never invent** — leave a field null if the
  report doesn't state it. Phased/ranged work uses start/end years." Reuse
  `strata.py`'s **validate → repair-once → fail-loudly** loop (the SDK does not
  auto-repair Pydantic-invalid tool output; we do).
- **Cost & safety:** one 76-page PDF call is non-trivial in tokens and dollars,
  and the PDF is copyrighted/private. The call runs **only** on an explicit
  `yonder outlook` invocation, gated by `ANTHROPIC_API_KEY`, never in tests/CI,
  and only with the user's go-ahead. Derived output is per-user/ephemeral and
  gitignored. Originals are never committed (`fixtures/strata/` is gitignored).

## Deterministic assembly (steps 4–6)

`assemble(extract, *, unit=PLACEHOLDER) → ReserveOutlook` — pure, no I/O, TDD'd:

- **Real, from the report:** `start_balance` ← `current_crf_balance`;
  `expenditures` ← `projected_expenditures`; `assumptions.base_annual_contribution`
  ← `recommended_annual_contribution`; `assumptions.interest_rate` ← stated rate
  else placeholder `0.02`; `assumptions.sourced = True`;
  `building.{name, depreciation_report_date}`; `projection_start_year` ← year of
  `as_of_date`/report; `horizon_end_year` ← max expenditure year (fallback
  `projection_start + 30`); `history_start_year = projection_start_year`.
- **Placeholder (no Form B):** `unit.{entitlement_numerator/denominator,
  strata_fee_monthly, reserve_portion_monthly}` use documented placeholder
  constants; `source_note` says so. Per-unit levy math therefore renders but is
  illustrative until Form B lands.
- **Degraded:** `history = []` → the mock's "actual" line collapses to the *now*
  point (honest: only the current balance is known). `planned_fee_changes = []`
  for the MVP. If the report yields **no** projected expenditures or no balance,
  set `degraded = True` with a reason instead of rendering a fake projection.
- **Event derivation (script):** build `events[]` from `expenditures[]` — one
  `type:"work"` marker per item (label + amount), alternating rows to reduce
  collision. (Cluster/lane-packing polish stays deferred per the view spec.)

## Output & viewing

- `yonder outlook <pdf> [out]` writes the `ReserveOutlook` JSON. Default `out`:
  next to the source PDF (under the gitignored `fixtures/strata/`), so real
  building data is **never committed**.
- **Mock viewing without editing the mock:** add a tiny generic affordance — the
  mock reads an optional `?data=<relative-path>` query param and falls back to
  the committed Wexford sample when absent. Then:
  `http://localhost:8000/docs/mockups/reserve-trajectory.html?data=../../fixtures/strata/Spectrum%204/.../DepreciationReport%20(2).reserve_outlook.json`
  (served by `python -m http.server`; the gitignored JSON is still HTTP-served).
  This keeps the committed sample as the default and real data out of git.

## Module structure

```
src/yonder/outlook/
  model.py        # ReserveOutlook contract (exists)
  sample.py       # Wexford synthetic sample (exists)
  schema.py       # NEW: ReserveExtract — the reserve-focused tool-use model
  extract.py      # NEW: build tool spec + call client.py + validate/repair → ReserveExtract
  assemble.py     # NEW: pure ReserveExtract (+ placeholders) → ReserveOutlook
cli.py            # NEW subcommand: `yonder outlook <pdf> [out]`
```

`extract/client.py` stays the single Claude seam (Bedrock swap = one file). The
new `extract.py` mirrors `extract/strata.py`'s shape so the two per-doc
extractors stay consistent and the call is reusable for other doc types later.

## Testing

- **Deterministic, CI-safe (no API):** `ReserveExtract` schema validation; the
  tool-spec builder; `assemble()` mapping (real fields, placeholders, degraded
  paths, year derivation); event derivation; JSON emit. These use a **canned
  `ReserveExtract` fixture** (hand-written, mimicking a real report's facts) —
  the assembly is fully provable without a single API call.
- **The real extraction is a local run, not a gate:** `yonder outlook` against
  the real PDF, gated by `ANTHROPIC_API_KEY`, run manually with user consent.
  Its quality is read by eye / the eval harness, never asserted in CI (LLM output
  isn't deterministic, and the doc can't be committed). Mirrors Prototype-1's
  split: deterministic tests guard the code; local runs measure the model.

## Key handling

`ANTHROPIC_API_KEY` lives in a gitignored `.env` at the repo root (already
ignored; `.env.example` is the template). The project has no auto-loader, so runs
use `python -m uv run --env-file .env yonder outlook ...`. The plan may add
`python-dotenv` + `load_dotenv()` so `.env` "just works"; until then, `--env-file`
is the mechanism. The key is never printed and never committed.

## Scope & sequencing

- **Build:** `ReserveExtract` schema, `extract.py` (the one intelligence call),
  `assemble.py`, the `yonder outlook` CLI, the mock's `?data=` param, tests.
- **Then (manual):** run `yonder outlook` on Spectrum 4's report (with consent),
  eyeball the rendered chart, iterate the prompt/schema against what the real
  report yields.
- **Defer:** model-based classification; multi-building (Sterling's flat
  structure, Cambie's no-report degradation); Form B / financials / strata-plan
  extraction (real per-unit fee, real balance history, real planned changes);
  PDF chunking for >100-page docs; OCR; the canonical Python projection function;
  pooling/cross-user anything (the one rule).

## Open questions for the plan pass

- **`ReserveExtract` vs extending `StrataExtract`:** the MVP uses a focused new
  schema to keep the report extraction clean; revisit unifying later.
- **Provenance granularity:** carry page refs per expenditure now, or defer? Lean
  defer for the MVP (one doc), but the schema should leave room.
- **Placeholder unit values:** reuse Wexford's (18/2719, $486/$50) for visual
  continuity, or obviously-fake sentinels? Lean Wexford-like for a realistic look,
  clearly labelled placeholder in `source_note`.
- **Repair-loop reuse:** extract `strata.py`'s validate/repair into a shared
  helper, or copy the small loop into `extract.py`? Decide at plan time.

## What "done" looks like

1. `ReserveExtract` schema + tool-spec builder, unit-tested.
2. `assemble()` fully unit-tested against a canned extract (real-field mapping,
   placeholders, degraded paths, event derivation) — no API.
3. `yonder outlook <pdf>` wired through `client.py`, emitting a valid
   `ReserveOutlook` JSON (validated by the existing model + contract-guard).
4. The mock renders a real Spectrum-4 outlook via `?data=` — projected work,
   trajectory, levy, and slider all from the depreciation report.
5. `pytest` green (deterministic only); real docs + derived JSON gitignored;
   the API call gated and run only with consent.

The outcome we're buying: the first real proof that the hardest extraction in the
product — the depreciation report's forecast — turns into a live dashboard.
