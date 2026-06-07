# Yonder

A BC (Greater Vancouver) home-buying companion app. The agent reads the messy
inputs a buyer would otherwise chase — strata docs, agent emails, listings — and
surfaces them as tappable cards. Working name: Yonder.

## The one rule (load-bearing)

**Compute & display in-context for the individual user -> green.
Accumulate a standalone, cross-user, reusable dataset or product -> red.**

## Hard rules

- Never pool email or strata docs across users into a shared dataset.
- Real strata docs live in `fixtures/strata/` and are **gitignored — never commit them** (copyright + privacy).
- MLS-derived enrichment, when it exists, stays ephemeral / per-user.

## Current scope: Prototype 1

Local strata-PDF extraction harness. **No AWS, no UI.** Goal: measure extraction
quality on real BC strata PDFs before any cloud or UI work. One PDF in -> one
`StrataExtract` out. Spec: `docs/superpowers/specs/2026-05-28-strata-extraction-prototype-design.md`.

## Stack & seam

Python + uv. Claude via the Anthropic API today, behind `src/yonder/extract/client.py`
— the one file to change when we graduate to Bedrock. No Strands SDK yet.

## Dev commands

- `uv sync --extra dev` — set up the environment
- `uv run yonder extract <pdf>` — extract facts from one PDF (needs `ANTHROPIC_API_KEY`)
- `uv run yonder eval fixtures/samples` — score labeled PDFs in a folder
- `uv run yonder fees <agm.pdf> --lot <lot-id>` — break one AGM package into a `FeeBreakdown` (needs `ANTHROPIC_API_KEY`)
- `uv run yonder fees-sample` — write the synthetic `FeeBreakdown` fixture
- `uv run pytest` — run tests (live integration test skips without a key)
- `uv run python fixtures/samples/generate_sample.py` — regenerate the synthetic fixture

## Where the thinking lives

- `docs/brainstorm/` — architecture sketch, feature glossary, data playbook
- `docs/superpowers/specs/` — the design spec
- `docs/superpowers/plans/` — this implementation plan

## Workflow

This project uses the superpowers workflow: brainstorm -> spec -> plan -> TDD
implementation. Write the failing test first; keep commits frequent.
