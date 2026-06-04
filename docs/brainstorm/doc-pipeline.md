# Yonder — Document Cleanup Pipeline (design note)

*Brainstorm altitude. Companion to `v1-scope.md`. Captures the shape of the
normalize/route/aggregate layer that sits between raw uploaded files and the
extraction intelligence. Not a spec — and deliberately under-built until real
runs say otherwise.*

## Why a pipeline at all — the reframe

The instinct "clean the PDFs up before inspecting them with intelligence" is
right, but **not for the reason you'd expect.** Claude already reads these PDFs
natively — born-digital *and* scanned (it sees scans as images). So the
pipeline's job is **not** "make the document legible to the model." Its job is
the three problems the real corpus exposed (3 buildings, 97 PDFs in
`fixtures/strata/`):

1. **Cost control.** A real "Form B" turned out to be a 105-page, 6.9 MB bundle.
   Sent raw as page-images that's expensive and may exceed context. Cheap
   normalization (use an existing text layer; OCR only a true scan) can cut
   tokens by 10×+.
2. **Routing & dedup.** Buildings arrive as folders of 12–63 files with names
   like `5171_BCS2611_2024_09_SCM _ Nov27 - ATTACH.pdf` and literal `(1)`
   duplicates. Knowing *which doc this is* (AGM / SGM / depreciation / Form B),
   its date, and that it's a duplicate — **before** extraction — is
   classification, a different job than fact-pulling.
3. **Aggregation.** A building = a *folder* of many PDFs (the core finding in
   `v1-scope.md`). A pipeline that turns each file into a consistent intermediate
   is exactly what feeds building-level backfill. **This pipeline is the
   seed→backfill mechanism, made concrete.**

## The layered flow

```
  preserve            normalize              classify / route / dedup
  (originals,    →    (text-vs-scan     →    (doc_type, date, building,
   immutable)         triage; pull            drop duplicates)
                      embedded text)                  │
                                                      ▼
                          aggregate           ◄──   extract
                     (merge per-file              (StrataExtract
                      facts → building card)       per file)
```

Per-file intermediate the middle stages produce, roughly:
`{ original_path, hash, doc_type, date, text_or_pages, source }`.

## Cheap-first, OCR-last

The order things get reached for, cheapest first:

- **Check for an existing text layer before ever reaching for OCR.** Many BC
  strata scans are already OCR'd by the management company or doc service (the
  Sterling Form B has 760 font refs despite 22 images — it almost certainly has a
  text layer). Pull that text cheaply (pypdf / pdfplumber) when present.
- **OCR only a genuine scan with no text layer** — deferred until a real doc
  actually has none. (This honours the Prototype-1 spec's YAGNI deferral of OCR;
  it just adds the trigger condition.)
- **Heavy structural parsing** (table extraction, financial-statement layout)
  stays deferred until a real extraction demonstrably fails without it.

## Guardrails (non-negotiable)

- **Originals are immutable + WORM.** This is the architecture sketch's S3 Object
  Lock and the legal source-of-truth. The pipeline only ever *adds* derived
  artifacts beside the original — it never mutates or replaces it.
- **Derived artifacts are per-user and ephemeral** (the one rule). Normalized
  text, OCR output, classifications — none of it pools into a cross-user asset.
- **Provenance survives the transform.** Every derived artifact carries a
  reference back to its original file + page, so the eventual trust-UI ("found in
  AGM minutes p.4") still works after normalization.

## Sequencing discipline — don't build all five stages on spec

The Prototype-1 spec deferred this layer for a good reason ("built only when a
real doc demonstrates it's needed"). Real docs now *do* demonstrate it — but
unevenly. Triage what to build when:

| Stage | Status | Why |
|---|---|---|
| Preserve + provenance | **Justified now** | Source-of-truth + legal posture; cheap |
| Text-vs-scan triage + embedded-text pull | **Justified now** | Directly controls cost; evidence already shows huge bundles |
| Classify / route / dedup | **New v1 work** | The folder→building shape isn't optional; it's the actual input |
| Aggregate (folder → card) | **New v1 work** | Same — the product unit is the building |
| OCR | **Deferred-until-hit** | Model reads scans already; only needed when no text layer exists |
| Heavy structural parsing | **Deferred-until-hit** | Only if a real extraction fails without it |

## The first real run does double duty

The first live `yonder extract` on a real PDF is no longer just a plumbing test.
It is also the **measurement that picks which pipeline stage to build first**:
does raw-PDF-to-Claude fail on *cost* (→ build normalize first)? on the *combined
bundles* (→ build classify/split first)? Observed failure selects the next stage,
instead of guessing. Build the pipeline reactively, one stage per demonstrated
need.

## Open questions for the spec pass

- **Intermediate store:** where do normalized text + per-file metadata live
  locally in the prototype (sidecar files next to the gitignored original? a
  small local index)?
- **Doc classification method:** filename heuristics + first-page text, or a
  cheap model pass? Start with the cheapest that works.
- **Dedup key:** content hash, or `(building, doc_type, date)`? The `(1)` /
  `ATTACH` variants suggest near-duplicates that a pure hash won't catch.
- **Where extraction reads from:** the normalized text, the raw PDF, or both
  depending on text-vs-scan? The triage stage decides per file.
