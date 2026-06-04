# Yonder v1 — Strata-First Scope

*Working scope doc. Brainstorm altitude, not a spec. Companion to
`architecture-sketch.md`, `feature-glossary.md`, `data-playbook.md`. Expect
rearranging — this exists to give the spec pass a spine.*

## The cut (one line)

**v1 is a per-user strata-document app: the user supplies a building's strata
package, Yonder extracts it, and the Strata Health Visualizer + Doc Vault make
it legible — organized on a board of the buildings they're weighing.**

No MLS/VOW. No email inbox reading. No licensed data of any kind.

## Why this cut, in the project's own terms

This overrides the architecture sketch's stated v1 path (which led with
**email forwarding**, MLS as a parallel long-lead track). The strata-first cut
is stronger because:

- **It removes both long-lead-time dependencies at once.** The two things that
  gate the original v1 are paperwork with months of latency, not code:
  MLS/VOW board membership + compliance review ("the hard gate"), and Gmail
  restricted-scope verification + annual CASA (2–6 mo). v1 needs **neither** —
  nothing blocks on a signature.
- **It lives in the green zone.** The data playbook's safest row is
  *user-supplied uploaded docs → "yours to store & manipulate."* A package the
  buyer hands you is the cleanest input the product has. (One caveat below.)
- **The signature feature is also the most independent.** The Strata Health
  Visualizer runs on nothing but strata docs — zero MLS, zero email. Highest
  value and lowest dependency are the *same* feature. Exploit that.
- **Prototype 1 already is the engine.** One PDF → one `StrataExtract` with
  provenance is exactly the core v1 wraps. v1 is the product shell around the
  harness that just merged, not a new direction.

## The spine: the strata doc as a backfill engine, not a gate

The load-bearing design idea. **The strata package is the data-entry
mechanism.** Everything a user would otherwise type, the doc fills in for them —
this is "as little typing as possible, ruthlessly" made real. The onboarding
*is* the upload.

A board card therefore has a lifecycle:

```
  SEED state  (pre-doc)                 BACKFILLED state  (doc lands)
  ─────────────────────────            ──────────────────────────────
  ask for almost nothing       ──►     extraction floods in:
  (a name, maybe an address)            building, unit entitlement,
  a card to hang the upload on          reserve trend, meetings, levies,
  status: "watching"                    litigation, doc freshness →
                                        the Strata Health Visualizer lights up
```

- We **do not** make the user fill a form. The seed state asks for the minimum
  needed to create a card; the package backfills the rest.
- The board holds cards at **both** stages simultaneously — some seeded, some
  rich.
- This is the connective tissue between the pre-doc world and the extraction
  core, and it's what keeps the app non-empty before any document arrives.

## Feature triage

Glossary features mapped against a docs-only, green-only v1:

| Feature | v1? | Why |
|---|---|---|
| **Strata Health Visualizer** | ✅ core | 100% doc-powered; the signature |
| **Doc Vault** | ✅ core | Per-home doc store; where uploads land and get summarized |
| **Portfolio Board** | ✅ core | The board of buildings being evaluated; holds seed + backfilled cards |
| **Home Card (seed state)** | ✅ core | Minimal pre-doc card to attach a package to |
| **Home Card (listing snapshot)** | ❌ defer | VOW feed + enrichment dies without MLS |
| **Memory & Verdict** | ❌ v1.5 | Cheap and green, but a feature beyond core; the seed card borrows only its lightest affordance (a nickname), not full notes/photos/voice |
| **True-Cost** | ❌ v1.5 | BC tax rules are ours, not licensed — works on a hand-entered price; defer to keep v1 ruthless |
| **Diff** | ❌ defer | Needs listing fields ($/sqft, beds/baths) we won't have |
| **Deal Workspace** | ❌ defer | Heavy; note the *strata-review subject* is doc-powered — a later hook |
| **Gmail Intake** | ❌ out | The thing v1 explicitly removes |
| **Co-buyer / Summit / Pros Directory** | ❌ defer | End-of-journey or growth-loop, not core proof |

**v1 surface = Visualizer + Doc Vault + Board + seed-state card.** Companions
(Memory & Verdict, True-Cost) wait for v1.5, once extraction quality is proven.

## Intake: upload only

One surface in v1: **drag/drop one or more PDFs.** Zero new integration. In BC a
strata package typically reaches a buyer as a combined PDF (often hundreds of
pages) from an agent — upload covers that directly.

Sequenced fast-follows (explicitly **not** v1):

1. **Forward-an-email-with-attachments** → SES inbound catching attachments the
   user pushes. *Not* the Gmail-intake monster: no OAuth, no CASA, still
   user-supplied/green. The natural next surface.
2. **Folder link** (Drive / Dropbox) → each provider is its own connector + auth.
   Heaviest; latest.

## The guardrail to write into the spec

"Green" holds for **display to that user**. The hard rule still bites the moment
a building's extracted facts get reused for a *second* user looking at the *same
building* — the "never pool strata docs across users" line. A strata-doc product
feels constant pressure here (two buyers, one building, why re-extract?). v1
sidesteps it by staying strictly per-user; name it as a guardrail in the spec so
it isn't discovered later.

## Deliberately unplanned: the pre-doc paths & visuals

There is a large UX layer that is **not** extraction work: how a user enters
before they have a doc, how cards are seeded, empty/seed states, board
interactions, the seed→backfill transition animation/feel. This is the "million
paths and visuals" — important, but a separate design pass. v1 scope names it as
real and bounded; it does not try to design it here.

## What this binds us to

The strata-first cut narrows the audience to **strata buyers (apartments +
townhouses) in Greater Vancouver** — detached houses have no package to chase.
That's the right kind of narrow: the strata segment is large here, and it's
exactly where the document-drowning pain is most acute. We concentrate on the
sharpest version of the precise pain we solve, and grow outward from there.

## Relationship to the long-lead tracks

MLS/VOW board paperwork and Gmail CASA are **not** v1, but their lead times are
long. They can start in parallel as paperwork — they block nothing in v1, and
having them in flight keeps v2 (listing snapshot, inbox auto-fill) from starting
cold.

## Open questions for the spec pass

- **Seed state minimum:** what's the least we ask to create a card — a nickname
  only? nickname + address? Does a viewing photo seed it?
- **Multi-PDF per building:** a package often arrives as several files (Form B,
  depreciation report, minutes, bylaws) — in the real corpus, *always* a folder
  of 12–63 files, never one combined PDF. Prototype 1 is one-PDF-in; v1 needs to
  attach *several* docs to *one* card and merge. This is the first real
  extension beyond the harness, and the mechanism for it is the document cleanup
  pipeline — see `doc-pipeline.md` (preserve → normalize → classify/route →
  extract → aggregate).
- **Re-extraction & doc freshness:** when a newer doc arrives for a building
  already on the board, how does backfill update vs. append?
- **What surfaces before the doc:** which board/card visuals are worth building
  for the seed state vs. waiting for backfill.
