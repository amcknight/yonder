# Yonder — Prototype 1: Strata-PDF Extraction Harness (Design)

*Date: 2026-05-28. Status: approved design, pre-implementation.*

Companion to the three brainstorm docs (moving to `docs/brainstorm/`):
`ARCHITECTURE Sketch.md`, `bc-home-buying-feature-glossary.md`,
`bc-home-buying-data-playbook.md`.

## Goal

Prove the one thing the whole product rests on: **can a Claude-based agent
reliably pull structured facts out of real BC strata documents?** Everything
else in the architecture (SES inbound, queues, Bedrock, the app UI) is plumbing
that does not move this signal. So Prototype 1 builds *only* the extraction core
plus a way to measure its quality, and defers all cloud infrastructure.

Non-goals for Prototype 1: any AWS service, any UI, OAuth/email ingestion,
MLS/VOW data, agent-email fact extraction (deferred to a second pass).

## Approach (chosen)

**Local extraction harness, no cloud.** A Python CLI reads a born-digital strata
PDF, sends it to Claude as a document block, and returns a validated structured
facts object. A separate eval harness scores extracted facts against hand-labeled
ground truth and reports raw counts + an itemized match table (not synthetic
percentages). The Claude call sits behind a thin `client.py` seam so a later swap
to Bedrock touches one file.

Rejected for now: building on the target stack (Bedrock + Strands) from day one
— AWS/IAM friction and likely rework, for code whose shape we don't yet know.
Rejected: standing up SES inbound — pure plumbing, doesn't test extraction.

## Repo structure

```
yonder/
  CLAUDE.md
  README.md
  pyproject.toml             # uv-managed; deps: anthropic, pydantic, pytest (+ pypdf only if needed)
  .env.example               # ANTHROPIC_API_KEY=
  .gitignore                 # adds fixtures/strata/ and *.expected.json under it
  src/yonder/
    __init__.py
    extract/
      schema.py              # Pydantic models — the structured strata facts
      strata.py              # extraction logic: build prompt, call client, validate
      client.py              # thin Claude wrapper (Anthropic API now; Bedrock swap later)
    eval/
      score.py               # compare extracted vs ground-truth labels, per-field result
    cli.py                   # `yonder extract <pdf>`, `yonder eval`
  tests/
    test_schema.py
    test_score.py
    test_extract.py          # integration test against committed synthetic sample
  fixtures/
    samples/                 # COMMITTED synthetic/redacted doc + expected.json
    strata/                  # GITIGNORED — real docs and their *.expected.json labels
  docs/
    brainstorm/              # the 3 md files (moved from repo root)
    superpowers/specs/       # this doc
```

### Tech choices

- **Python + uv** — matches the architecture's Python-everywhere intent; uv is the toolchain.
- **`client.py` is the seam.** All Claude access flows through it. Anthropic API now;
  Bedrock later is a one-file change. No Strands SDK yet — a single extraction call
  does not need an agent framework.
- **PDF handling** — send the PDF straight to Claude as a document content block
  (born-digital PDFs read natively, no OCR). A light local text-extraction fallback
  is *not* built until a real doc demonstrates it's needed (YAGNI).
- **Structured output** — Claude is forced to fill the schema via tool-use, so output
  is always schema-valid or the call retries.

## Extraction schema (`schema.py`)

The contract: what a strata doc becomes. Driven by the glossary's Strata Health
Visualizer. All fields optional/nullable — real docs are partial, and absence is a
first-class state (a missing reserve-fund balance is `null`, never a hallucinated
number).

```
StrataExtract
├─ building          name, address (if present)
├─ unit_entitlement  cost-share ratio — numerator / denominator (e.g. 18 / 2719)
├─ documents[]       each: type (AGM minutes | SGM minutes | depreciation report |
│                    financial statement | Form B | bylaws | other), issue_date, period_covered
├─ meetings[]        AGM/SGM: date, type
├─ special_levies[]  amount, date_approved, purpose
├─ litigation        present (bool), summary (nullable)
├─ reserve_fund      balance (nullable), as_of_date (nullable), trend (rising|flat|declining|unknown)
└─ provenance        EVERY extracted fact carries: source (doc + page) and confidence
```

Two deliberate choices beyond the bare glossary:

- **Provenance + confidence on every fact.** Records where each value came from
  (doc + page) and the model's confidence. Pays off three ways: it's what the eval
  scores against, it's the future user-facing trust story ("found in AGM minutes,
  p.4"), and it lets low-confidence facts be flagged rather than asserted.
- **Everything nullable.** Absence is modeled explicitly; the schema never invents.

**Designed to grow — this is a v0 seed, not a frozen contract.** Health factors
*will* multiply and doc types *will* proliferate as we see real docs, so the schema
and prompt are built to absorb that cheaply:

- **Doc type is an open vocabulary, not a closed enum.** A small typed core
  (AGM/SGM minutes, depreciation report, financial statement, Form B, bylaws) plus
  a freeform `other` with a model-supplied label — so an unrecognized doc type
  *degrades gracefully* (still extracted, just labeled) instead of failing or being
  force-fit into the wrong bucket.
- **Health factors are additive.** The fields above are the starting set; adding a
  new factor should be a localized schema + prompt change, not a refactor. Avoid
  coupling the extractor to any one factor's shape.
- The eval harness must tolerate this: scoring only checks fields a label asserts,
  so new schema fields don't break existing labels/regression tests.

Scope note: Prototype 1's schema covers **Strata Health Visualizer facts only**.
Agent-email facts (viewing times, subject-removal dates, price changes) are a
deferred second pass.

## Validation layer

This is what makes Prototype 1 a *proof*, not a demo.

### Fixtures (legal-safe)

- `fixtures/strata/` — real PDFs. **Gitignored, never committed.** (Playbook:
  strata docs carry copyright + privacy risk; reusing one buyer's docs is a hazard.)
- `fixtures/samples/` — **one synthetic strata doc** (fictional building, plausible
  AGM minutes + financials), committed, with a hand-written `expected.json` beside
  it. This is what CI and fresh clones run against.
- Real-doc labels (`*.expected.json` under `fixtures/strata/`) describe real
  buildings, so they are also gitignored.

### Eval harness (`eval/score.py` + `yonder eval`)

- User hand-labels expected facts for a handful of real docs in small
  `*.expected.json` files (local only).
- `yonder eval` runs extraction over the labeled set and reports **raw counts +
  an itemized match table** — no synthetic aggregate percentage.

Reporting principle (resolved during design): percentages over a handful of docs
are misleading — one miss swings everything, and a percentage pretends to be a
rate it isn't. Instead:

- `score.py` emits a structured per-field result, each typed as one of:
  **match | wrong-value | missed | hallucinated** (plus a low-confidence-but-correct
  flag).
- The CLI renders an itemized diff table with **raw counts and the denominator
  always visible** (e.g. "special_levies: 2 expected · 2 found · 0 extra").
- **No aggregate percentage** until the labeled set is large enough (dozens of docs)
  that one miss doesn't dominate. The value early is reading the *failure modes*,
  not a headline number.
- Comparison is field-typed: dates normalized, money tolerant of formatting,
  ratios exact.

Example render:

```
doc: gardens-at-yaletown-2024
  cost_share_ratio   ✓ 18/2719
  AGM date           ✓ 2024-03-12
  special_levies     2 expected · 2 found · 0 extra
    ✓ $4,200  2023-11  roof
    ✗ MISSED  $850   2024-02  elevator
  reserve_fund.trend ✗ got "flat", expected "declining"
  hallucinations     0
```

### User-facing confidence is a separate concern

When facts later surface in the app, confidence is **per-fact, tied to provenance**
("found in AGM minutes p.4" vs "not stated"), bucketed high/med/low or shown-vs-
flagged — never a made-up accuracy number and never free text. The eval harness's
internals are *not* reused as the user-facing confidence; they are different things.
Noted now to prevent that conflation later.

## Testing (TDD)

- **Unit tests, deterministic, CI-safe (no API calls):**
  - `test_schema.py` — model validation, nullability, ratio parsing.
  - `test_score.py` — the comparison logic (match/wrong/missed/hallucinated typing,
    date/money normalization, denominators).
- **Integration test against the committed synthetic sample** (`test_extract.py`):
  asserts *structure* — correct doc types found, dates parse, no crash — not exact
  LLM wording, so it stays stable. May be marked to skip without an API key.
- **Real-doc eval is a local report (`yonder eval`), not a CI gate** — LLM output
  isn't deterministic enough to gate a build on, and the docs can't be committed.

Split: deterministic tests guard the code; the local eval measures the model.

## CLAUDE.md (to be written)

Standing project guide containing:

- **What Yonder is** — one paragraph + working-name note.
- **The one rule** (verbatim from the playbook): compute & display in-context for
  the individual user → green; accumulate a standalone, cross-user, reusable dataset
  → red. Load-bearing, near the top.
- **Legal guardrails as hard rules** — never pool email or strata docs across users;
  real strata docs are gitignored and never committed; MLS-derived enrichment stays
  ephemeral/per-user.
- **Current scope** — "Prototype 1: local strata-PDF extraction harness. No AWS, no
  UI. Goal: measure extraction quality on real docs."
- **Stack & the `client.py` seam** — Anthropic API now, Bedrock later, one file.
- **Dev commands** — `uv sync`, `yonder extract <pdf>`, `yonder eval`, `pytest`.
- **Where the thinking lives** — links to the three brainstorm docs and this spec.
- **Superpowers workflow pointer** — TDD + brainstorming-first carry across sessions.

## What "done" looks like for Prototype 1

1. `uv sync` sets up the environment from a clean clone.
2. `yonder extract <pdf>` on the committed synthetic sample returns a valid
   `StrataExtract` with provenance + confidence.
3. `yonder eval` over a local labeled set prints the itemized count-based report.
4. `pytest` passes (schema + score unit tests; integration test against the sample).
5. CLAUDE.md and README in place; brainstorm docs relocated; real-doc fixtures
   gitignored.

The outcome we're buying: a measured, honest read on extraction quality against
real BC strata PDFs — the green light (or the list of what to fix) before any
cloud or UI work begins.
