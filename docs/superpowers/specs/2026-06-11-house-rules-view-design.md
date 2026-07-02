# Yonder — House Rules View (Design)

*Date: 2026-06-11. Status: v1 mockup committed with synthetic data; pre-extraction.*

Sibling to `2026-06-04-reserve-trajectory-view-design.md` and
`2026-06-06-strata-fee-breakdown-design.md`. Where those answer the *money*
questions ("will the reserve cover what's coming?" and "what is my fee buying?"),
this view answers the *living* question a buyer can't easily answer from a stack
of bylaw and rule PDFs:

> **What can I — and can't I — do here?**

Pets, rentals (long + short-term), age limits, smoking, cannabis, balcony BBQs,
EV charging, move-ins, quiet hours, parking, amenities. Twelve rows on one phone
screen; each row a stance (Open / Limited / No), a one-line summary, and the
source bylaw or rule.

## What exists today

- **Mockup:** `docs/mockups/house-rules.html` — phone-frame list, fixture-driven
  (`fetch()` from a JSON sample), same dark visual language as the Reserve and
  Fee Breakdown mockups.
- **Fixture:** `fixtures/samples/house_rules.sample.json` — synthetic data for
  "The Wexford" (same building as the fee-breakdown sample, so the views feel
  like one building's panel).
- **Loads under** `python -m http.server` from the repo root, like the others.

## Locked layout (v1)

Top to bottom:

1. **Verdict line** — one-sentence buyer summary (`Pet-friendly with size limits ·
   no short-term rentals · no rental cap`). Plain English, no counts. It's the
   "what does this building feel like" headline.
2. **Twelve rule rows**, in buyer-priority order, not source order:
   pets → long-term rentals → short-term rentals → age → smoking → cannabis →
   BBQ → EV → moves → noise → parking → amenities. Each row:
   - **Icon chip**, coloured by stance.
   - **Label** + **stance pill** (Open / Limited / No; "none" rows show no pill).
   - **Summary** — one line, plain English ("Up to 2 pets per unit. Dogs ≤15 kg.").
   - **Source ref** — `Bylaw 4` vs `Rule 7.2`. The distinction matters: **bylaws are
     registered and slow to change; rules are set by council and can shift**. A
     serious buyer wants to know which is which.

## Why a list, not a chart

The other two Visualizer views are quantitative (money trajectories, fee
composition). Bylaws are categorical — "allowed / limited / prohibited" with a
short caveat. A chart would be invented complexity. The pill + colour gives the
at-a-glance signal a chart would; the summary gives the nuance a chart can't.

## The four stances

- **Open** (teal) — no restriction beyond ordinary courtesy.
- **Limited** (amber) — allowed with conditions worth knowing (size cap, hours,
  fees, council approval, etc.). Most rows land here for most buildings.
- **No** (red) — flat prohibition.
- **None** (slate, no pill) — no rule on file / not applicable (e.g. age
  restrictions in a non-55+ building). Distinct from "Open" so we don't fake a
  positive signal.

## Scope: v1 vs v1.1

**v1 (here) — the mockup + synthetic fixture.** Proves the visual and the schema
on a hand-authored sample. No extraction yet.

**v1.1 — bylaws-PDF → schema.** A single LLM call per building reads the bylaws
+ rules PDFs and emits a `HouseRules` object matching the v1 fixture shape. The
prompt enumerates the 12 buyer concerns and asks the model to classify each
against the four stances, with a short summary and a source citation (bylaw or
rule number). This fits the pipeline philosophy: *script the mechanics, use the
LLM to read nearly all of the document content, keep per-doc calls generic.*

**v1.2 (maybe) — tap-to-cite.** A row taps through to the bylaw excerpt that
produced it, for the buyer who wants to verify before believing.

## Schema

See `fixtures/samples/house_rules.sample.json` for the concrete shape. Top level:

```
{
  building: { name, source_note },
  verdict:  "one-line plain-English summary",
  rules: [
    { key, icon, label, stance, summary, source_ref },
    ...
  ]
}
```

`icon` is one of a fixed sprite set (`pets`, `longRental`, `shortRental`, `age`,
`smoking`, `cannabis`, `bbq`, `ev`, `moves`, `noise`, `parking`, `amenities`) —
extensible, but the v1 set covers the standard BC strata bylaw surface.
