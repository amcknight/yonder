# Yonder — strata extraction prototype

Extracts structured facts from BC strata PDFs using Claude, and scores the
extractions against hand-labeled ground truth. Local only — no cloud, no UI.

## Setup

```bash
uv sync --extra dev
cp .env.example .env   # then add your ANTHROPIC_API_KEY
```

## Use

```bash
uv run yonder extract fixtures/samples/sample-strata-package.pdf
uv run yonder eval fixtures/samples
uv run pytest
```

## Fixtures

- `fixtures/samples/` — a synthetic, committed strata package (safe to share).
- `fixtures/strata/` — **gitignored.** Put your real PDFs and their
  `*.expected.json` labels here; they never leave your machine.

See `CLAUDE.md` for project rules and `docs/` for the design.
