# docs → json MVP (Depreciation Report → ReserveOutlook) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn one real depreciation-report PDF into a `ReserveOutlook` JSON the existing mock renders — via a single Opus extraction call plus deterministic assembly.

**Architecture:** A new reserve-focused tool-use schema (`ReserveExtract`) and extractor (`extract.py`) mirror the existing `extract/strata.py` (build tool from `model_json_schema()`, validate→repair-once→fail, behind the `client.py` Claude seam). A pure `assemble()` maps the extract → the frozen `ReserveOutlook` contract (real projection; placeholder unit; degraded history). A `yonder outlook` CLI wires it end-to-end, and the mock gains a `?data=` param so real (gitignored) output renders without edits. The real API call is manual/consented; everything deterministic is TDD'd with canned data.

**Tech Stack:** Python 3.11+, Pydantic v2, argparse, pytest (`pythonpath=src`), the Anthropic SDK behind `extract/client.py`. Spec: `docs/superpowers/specs/2026-06-04-docs-to-json-reserve-mvp-design.md`.

**Scope reminder:** depreciation report ONLY; one intelligence call; no classification, no multi-building, no Form B / financials / strata-plan, no PDF chunking, no OCR. The interactive projection math stays in the mock's JS. Real strata PDFs and derived JSON are gitignored (`fixtures/strata/`).

**Convention:** all monetary values are CAD dollars (the mock converts to $k). Run Python via `python -m uv run ...`.

---

### Task 1: `ReserveExtract` schema (the reserve tool-use model)

**Files:**
- Create: `src/yonder/outlook/schema.py`
- Test: `tests/test_reserve_extract_schema.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_reserve_extract_schema.py
import datetime
import json

from yonder.outlook.schema import ProjectedExpenditure, ReserveExtract


def test_empty_extract_is_valid():
    e = ReserveExtract()
    assert e.projected_expenditures == []
    assert e.current_crf_balance is None


def test_point_and_range_expenditures():
    point = ProjectedExpenditure(label="Roof", amount=180000, year=2028)
    rng = ProjectedExpenditure(label="Envelope", amount=1100000, start_year=2031, end_year=2033)
    assert point.year == 2028 and point.start_year is None
    assert rng.start_year == 2031 and rng.end_year == 2033


def test_parses_iso_dates_and_round_trips():
    e = ReserveExtract(
        building_name="The Spectrum",
        report_date="2022-05-01",
        current_crf_balance=350000,
        balance_as_of_date="2022-05-01",
        recommended_annual_contribution=90000,
        funding_model="full funding",
        projected_expenditures=[ProjectedExpenditure(label="Roof", amount=180000, year=2028)],
    )
    assert e.report_date == datetime.date(2022, 5, 1)
    back = ReserveExtract.model_validate(json.loads(e.model_dump_json()))
    assert back == e


def test_label_is_required_on_expenditure():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ProjectedExpenditure(amount=180000, year=2028)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m uv run pytest tests/test_reserve_extract_schema.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'yonder.outlook.schema'`

- [ ] **Step 3: Write the schema**

```python
# src/yonder/outlook/schema.py
"""ReserveExtract — the reserve-focused tool-use schema the model fills from a
depreciation report. Distinct from the general StrataExtract: this is what the
ONE intelligence call returns, and it maps cleanly onto the ReserveOutlook
contract. All monetary values are CAD dollars; all fields nullable except an
expenditure's label (a cost with no name is useless). Absence is first-class:
the model leaves a field null rather than inventing.
"""

from __future__ import annotations

import datetime

from pydantic import BaseModel, Field


class ProjectedExpenditure(BaseModel):
    label: str                                # the component, e.g. "Roof", "Envelope"
    amount: float | None = None               # projected cost, dollars
    year: int | None = None                   # a point expenditure
    start_year: int | None = None             # or a phased range
    end_year: int | None = None


class ReserveExtract(BaseModel):
    building_name: str | None = None
    report_date: datetime.date | None = None
    current_crf_balance: float | None = None      # opening CRF balance the forecast builds on
    balance_as_of_date: datetime.date | None = None
    recommended_annual_contribution: float | None = None
    funding_model: str | None = None              # free text, e.g. "full funding"
    interest_or_inflation_rate: float | None = None  # the assumption the report uses, if stated
    projected_expenditures: list[ProjectedExpenditure] = Field(default_factory=list)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m uv run pytest tests/test_reserve_extract_schema.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/yonder/outlook/schema.py tests/test_reserve_extract_schema.py
git commit -m "feat: add ReserveExtract reserve-focused tool-use schema"
```

---

### Task 2: `extract.py` — reserve tool + extraction orchestration

**Files:**
- Create: `src/yonder/outlook/extract.py`
- Test: `tests/test_reserve_extract.py`

This mirrors `src/yonder/extract/strata.py` exactly in shape (read it for reference): a tool built from `model_json_schema()`, and a `validate → repair-retry-once → fail` loop behind the injected `client`. Tests use a fake client — **no API**.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_reserve_extract.py
import pytest
from pydantic import ValidationError

from yonder.outlook.extract import extract_reserve, reserve_tool, TOOL_NAME


class FakeClient:
    """Returns canned tool-input dicts in order; records each call's kwargs."""
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def extract_with_tool(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def test_reserve_tool_shape():
    t = reserve_tool()
    assert t["name"] == TOOL_NAME == "record_reserve_facts"
    assert "input_schema" in t and t["input_schema"]["type"] == "object"


def test_extract_reserve_returns_validated():
    fc = FakeClient([{
        "building_name": "X",
        "current_crf_balance": 350000,
        "projected_expenditures": [{"label": "Roof", "amount": 180000, "year": 2028}],
    }])
    res = extract_reserve(b"%PDF fake", client=fc)
    assert res.building_name == "X"
    assert res.projected_expenditures[0].label == "Roof"
    assert len(fc.calls) == 1


def test_extract_reserve_repairs_once_then_succeeds():
    bad = {"projected_expenditures": [{"amount": 180000}]}      # missing required label
    good = {"building_name": "Y", "projected_expenditures": []}
    fc = FakeClient([bad, good])
    res = extract_reserve(b"%PDF fake", client=fc)
    assert res.building_name == "Y"
    assert len(fc.calls) == 2
    assert fc.calls[1]["extra_note"]  # the repair note was sent on the retry


def test_extract_reserve_raises_if_both_attempts_invalid():
    bad = {"projected_expenditures": [{"amount": 180000}]}      # missing required label
    fc = FakeClient([bad, bad])
    with pytest.raises(ValidationError):
        extract_reserve(b"%PDF fake", client=fc)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m uv run pytest tests/test_reserve_extract.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'yonder.outlook.extract'`

- [ ] **Step 3: Write the extractor**

```python
# src/yonder/outlook/extract.py
"""The ONE intelligence call: a depreciation-report PDF -> ReserveExtract.

Mirrors extract/strata.py: build a forced tool from the Pydantic schema, send
the whole PDF through the client.py Claude seam, and validate ->
repair-retry-once -> fail loudly. This call is kept generic (one PDF -> facts)
so it can later be pointed at any document type, not just depreciation reports.
"""

from __future__ import annotations

from pydantic import ValidationError

from yonder.outlook.schema import ReserveExtract

TOOL_NAME = "record_reserve_facts"

SYSTEM_PROMPT = """You read a British Columbia strata DEPRECIATION REPORT (a \
30-year contingency-reserve-fund forecast) and extract the facts needed to chart \
the reserve fund's future. Rules:

- Extract ONLY what the report states. If a fact is not present, leave it null. \
Never invent or infer a number that is not written.
- `current_crf_balance` is the opening contingency-reserve-fund balance the \
forecast is built on (with `balance_as_of_date`).
- `recommended_annual_contribution` is the report's recommended annual CRF \
contribution. `funding_model` is the scenario name if given (e.g. "full \
funding"). `interest_or_inflation_rate` is the rate the model assumes, if stated.
- `projected_expenditures` is the financial forecast / expenditure schedule: one \
entry per major component (roof, envelope, elevators, plumbing, etc.) with its \
projected cost and the year it falls due. Use `year` for a single year, or \
`start_year`/`end_year` for phased work spanning years.

Call the record_reserve_facts tool with everything you found."""


def reserve_tool() -> dict:
    return {
        "name": TOOL_NAME,
        "description": "Record the reserve-fund facts extracted from the depreciation report.",
        "input_schema": ReserveExtract.model_json_schema(),
    }


def extract_reserve(pdf_bytes: bytes, *, client) -> ReserveExtract:
    """Extract a ReserveExtract from PDF bytes. Retries once with the validation
    error fed back to the model; raises ValidationError if the retry is also
    invalid."""
    tool = reserve_tool()
    extra_note: str | None = None
    last_error: ValidationError | None = None

    for _ in range(2):
        raw = client.extract_with_tool(
            pdf_bytes=pdf_bytes,
            system=SYSTEM_PROMPT,
            tool=tool,
            tool_name=TOOL_NAME,
            extra_note=extra_note,
        )
        try:
            return ReserveExtract.model_validate(raw)
        except ValidationError as exc:
            last_error = exc
            extra_note = (
                "Your previous tool call failed schema validation with these errors:\n"
                f"{exc}\n"
                "Return the record_reserve_facts tool call again, corrected. Use null "
                "for anything the report does not state; every expenditure needs a label."
            )

    assert last_error is not None
    raise last_error
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m uv run pytest tests/test_reserve_extract.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/yonder/outlook/extract.py tests/test_reserve_extract.py
git commit -m "feat: add reserve extraction (tool + validate/repair loop)"
```

---

### Task 3: `assemble.py` — `ReserveExtract` → `ReserveOutlook` (pure)

**Files:**
- Create: `src/yonder/outlook/assemble.py`
- Test: `tests/test_reserve_assemble.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_reserve_assemble.py
from yonder.outlook.assemble import PLACEHOLDER_UNIT, assemble
from yonder.outlook.model import ReserveOutlook
from yonder.outlook.schema import ProjectedExpenditure, ReserveExtract


def _full_extract():
    return ReserveExtract(
        building_name="The Spectrum",
        report_date="2022-05-01",
        current_crf_balance=350000,
        balance_as_of_date="2022-05-01",
        recommended_annual_contribution=90000,
        funding_model="full funding",
        projected_expenditures=[
            ProjectedExpenditure(label="Roof", amount=180000, year=2028),
            ProjectedExpenditure(label="Envelope", amount=1100000, start_year=2031, end_year=2033),
        ],
    )


def test_assemble_maps_real_fields():
    o = assemble(_full_extract())
    assert isinstance(o, ReserveOutlook)
    assert o.degraded is False
    assert o.start_balance == 350000
    assert o.building.name == "The Spectrum"
    assert o.assumptions.base_annual_contribution == 90000
    assert o.assumptions.sourced is True
    assert o.assumptions.interest_rate == 0.02  # placeholder when report states none


def test_assemble_collapses_expenditures_to_points_on_the_timeline():
    o = assemble(_full_extract())
    # ranges collapse to their start_year so the mock (single-range) stays correct
    years = sorted(e.year for e in o.expenditures)
    assert years == [2028, 2031]
    assert all(e.start_year is None for e in o.expenditures)


def test_assemble_derives_projection_window():
    o = assemble(_full_extract())
    assert o.assumptions.projection_start_year == 2022   # from balance_as_of_date
    assert o.assumptions.horizon_end_year == 2031        # latest expenditure


def test_assemble_derives_work_events_alternating_rows():
    o = assemble(_full_extract())
    assert [e.type for e in o.events] == ["work", "work"]
    assert [e.row for e in o.events] == [0, 1]
    assert o.events[0].label.startswith("Roof")
    assert "1.1M" in o.events[1].label


def test_assemble_uses_placeholder_unit():
    o = assemble(_full_extract())
    assert o.unit == PLACEHOLDER_UNIT
    assert "placeholder" in (o.building.source_note or "")


def test_assemble_degrades_when_no_balance_or_no_expenditures():
    no_bal = ReserveExtract(building_name="B", report_date="2022-01-01",
                            projected_expenditures=[ProjectedExpenditure(label="Roof", amount=1, year=2028)])
    o1 = assemble(no_bal)
    assert o1.degraded is True and "balance" in o1.degraded_reason

    no_exp = ReserveExtract(building_name="B", current_crf_balance=350000)
    o2 = assemble(no_exp)
    assert o2.degraded is True and "expenditure" in o2.degraded_reason
    assert o2.start_balance == 350000  # present-state still carried
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m uv run pytest tests/test_reserve_assemble.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'yonder.outlook.assemble'`

- [ ] **Step 3: Write the assembler**

```python
# src/yonder/outlook/assemble.py
"""Pure mapping: ReserveExtract -> ReserveOutlook (the frozen contract).

Real fields come from the depreciation report; the unit is a documented
placeholder (no Form B in the corpus); balance history is empty (only the
current balance is known) so the mock's "actual" line collapses to the now
point. If the report yields no balance or no datable expenditures, return a
`degraded` present-state outlook rather than a fabricated projection.
"""

from __future__ import annotations

from yonder.outlook.model import (
    Assumptions,
    BuildingMeta,
    Expenditure,
    ReserveOutlook,
    TimelineEvent,
    Unit,
)
from yonder.outlook.schema import ProjectedExpenditure, ReserveExtract

# No Form B in the corpus -> unit figures are illustrative. Mirrors the Wexford
# sample's values for visual continuity; clearly labelled placeholder.
PLACEHOLDER_UNIT = Unit(
    entitlement_numerator=18,
    entitlement_denominator=2719,
    strata_fee_monthly=486,
    reserve_portion_monthly=50,
)


def _year_of(e: ProjectedExpenditure) -> int | None:
    return e.year if e.year is not None else e.start_year


def _short_amt(amount: float | None) -> str:
    if amount is None:
        return ""
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:.1f}M"
    return f"${round(amount / 1000)}k"


def _source_note(extract: ReserveExtract) -> str:
    yr = extract.report_date.year if extract.report_date else "?"
    return f"deprec. report {yr} · unit figures placeholder"


def assemble(extract: ReserveExtract, *, unit: Unit = PLACEHOLDER_UNIT) -> ReserveOutlook:
    building = BuildingMeta(
        name=extract.building_name,
        depreciation_report_date=extract.report_date,
        source_note=_source_note(extract),
    )
    # Collapse every expenditure to a single timeline year (the mock renders only
    # one range band; collapsing keeps all expenditures correct in the projection).
    points = [
        Expenditure(label=e.label, amount=e.amount or 0.0, year=_year_of(e))
        for e in extract.projected_expenditures
        if _year_of(e) is not None
    ]

    if extract.current_crf_balance is None or not points:
        reasons = []
        if extract.current_crf_balance is None:
            reasons.append("no current CRF balance")
        if not points:
            reasons.append("no datable projected expenditures")
        return ReserveOutlook(
            building=building,
            unit=unit,
            start_balance=extract.current_crf_balance,
            degraded=True,
            degraded_reason="; ".join(reasons),
        )

    anchor = extract.balance_as_of_date or extract.report_date
    proj_start = anchor.year if anchor else min(p.year for p in points)
    horizon = max(p.year for p in points)
    if horizon <= proj_start:
        horizon = proj_start + 30

    assumptions = Assumptions(
        interest_rate=(
            extract.interest_or_inflation_rate
            if extract.interest_or_inflation_rate is not None
            else 0.02
        ),
        base_annual_contribution=extract.recommended_annual_contribution,
        history_start_year=proj_start,
        projection_start_year=proj_start,
        horizon_end_year=horizon,
        sourced=True,
    )
    events = [
        TimelineEvent(
            year=float(p.year),
            row=i % 2,
            type="work",
            label=f"{p.label} {_short_amt(p.amount)}".strip(),
        )
        for i, p in enumerate(points)
    ]
    return ReserveOutlook(
        building=building,
        unit=unit,
        assumptions=assumptions,
        start_balance=extract.current_crf_balance,
        history=[],
        expenditures=points,
        planned_fee_changes=[],
        events=events,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m uv run pytest tests/test_reserve_assemble.py -q`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/yonder/outlook/assemble.py tests/test_reserve_assemble.py
git commit -m "feat: assemble ReserveExtract into the ReserveOutlook contract"
```

---

### Task 4: `yonder outlook <pdf>` CLI

**Files:**
- Modify: `src/yonder/cli.py`
- Test: `tests/test_outlook_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_outlook_cli.py
from pathlib import Path

from yonder import cli
from yonder.outlook.model import ReserveOutlook
from yonder.outlook.schema import ProjectedExpenditure, ReserveExtract


def test_outlook_cli_writes_reserveoutlook(tmp_path, monkeypatch):
    canned = ReserveExtract(
        building_name="Test Tower",
        report_date="2022-05-01",
        current_crf_balance=350000,
        balance_as_of_date="2022-05-01",
        recommended_annual_contribution=90000,
        projected_expenditures=[ProjectedExpenditure(label="Roof", amount=180000, year=2028)],
    )
    # No API: stub the intelligence call and the client builder.
    monkeypatch.setattr(cli, "extract_reserve", lambda pdf_bytes, *, client: canned)
    monkeypatch.setattr(cli, "_build_client", lambda: object())

    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    out = tmp_path / "outlook.json"

    rc = cli.main(["outlook", str(pdf), str(out)])
    assert rc == 0

    o = ReserveOutlook.model_validate_json(out.read_text(encoding="utf-8"))
    assert o.start_balance == 350000
    assert o.assumptions.sourced is True
    assert o.building.name == "Test Tower"


def test_outlook_cli_default_out_path_next_to_pdf(tmp_path, monkeypatch):
    canned = ReserveExtract(current_crf_balance=1, projected_expenditures=[
        ProjectedExpenditure(label="Roof", amount=1, year=2030)])
    monkeypatch.setattr(cli, "extract_reserve", lambda pdf_bytes, *, client: canned)
    monkeypatch.setattr(cli, "_build_client", lambda: object())

    pdf = tmp_path / "MyReport.pdf"
    pdf.write_bytes(b"%PDF fake")
    rc = cli.main(["outlook", str(pdf)])
    assert rc == 0
    assert (tmp_path / "MyReport.reserve_outlook.json").exists()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m uv run pytest tests/test_outlook_cli.py -q`
Expected: FAIL — `AttributeError: module 'yonder.cli' has no attribute 'extract_reserve'` (or unknown command "outlook")

- [ ] **Step 3: Wire the CLI**

In `src/yonder/cli.py`, add these imports with the other `from yonder...` imports near the top:

```python
from yonder.outlook.assemble import assemble
from yonder.outlook.extract import extract_reserve
```

Add the command function after `cmd_eval`:

```python
def cmd_outlook(args: argparse.Namespace) -> int:
    pdf = Path(args.pdf)
    out = Path(args.out) if args.out else pdf.parent / f"{pdf.stem}.reserve_outlook.json"
    extract = extract_reserve(pdf.read_bytes(), client=_build_client())
    outlook = assemble(extract)
    out.write_text(outlook.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0
```

In `main`, register the subparser after the `eval` block and before `args = parser.parse_args(argv)`:

```python
    p_outlook = sub.add_parser(
        "outlook", help="Extract a depreciation-report PDF into a ReserveOutlook JSON."
    )
    p_outlook.add_argument("pdf")
    p_outlook.add_argument("out", nargs="?", default=None)
    p_outlook.set_defaults(func=cmd_outlook)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m uv run pytest tests/test_outlook_cli.py -q`
Expected: PASS (2 passed)

Also run the whole suite: `python -m uv run pytest -q` (no regressions).

- [ ] **Step 5: Commit**

```bash
git add src/yonder/cli.py tests/test_outlook_cli.py
git commit -m "feat: add 'yonder outlook' CLI (pdf -> ReserveOutlook json)"
```

---

### Task 5: mock `?data=` param (render real, gitignored output)

**Files:**
- Modify: `docs/mockups/reserve-trajectory.html`
- Modify: `docs/mockups/README.md`

The mock currently fetches the committed sample at a fixed path. Make it read an optional `?data=<relative-path>` query param, defaulting to the sample. This lets a gitignored real outlook be rendered (served over http) without editing the mock.

- [ ] **Step 1: Update the fetch in the mock**

In `docs/mockups/reserve-trajectory.html`, find this line inside the `<script>`:

```javascript
  fetch('../../fixtures/samples/reserve_outlook.sample.json')
```

Replace it (and keep the rest of the `.then(...).catch(...)` chain intact) with:

```javascript
  var _params = new URLSearchParams(location.search);
  var _dataUrl = _params.get('data') || '../../fixtures/samples/reserve_outlook.sample.json';
  fetch(_dataUrl)
```

Then update the `catch` message to reference the chosen file. Find:

```javascript
    .catch(function(e){ fail('Could not load reserve_outlook.sample.json. Serve the repo root over http (python -m http.server) and open this page via http://localhost:8000/docs/mockups/reserve-trajectory.html  ['+e.message+']'); });
```

Replace with:

```javascript
    .catch(function(e){ fail('Could not load '+_dataUrl+'. Serve the repo root over http (python -m http.server) and open via http://localhost:8000/docs/mockups/reserve-trajectory.html  ['+e.message+']'); });
```

- [ ] **Step 2: Document the param in the README**

In `docs/mockups/README.md`, append this section at the end:

```markdown

## Rendering real extracted data

`yonder outlook <report.pdf>` writes a `*.reserve_outlook.json` next to the PDF
(under the gitignored `fixtures/strata/`). Point the mock at it with the `?data=`
query param (path is relative to this HTML file), e.g.:

```
http://localhost:8000/docs/mockups/reserve-trajectory.html?data=../../fixtures/strata/<building>/<report>.reserve_outlook.json
```

With no `?data=`, the committed synthetic Wexford sample is shown. Real building
data stays gitignored; the http server still serves it locally.
```

- [ ] **Step 3: Verify the default still renders (manual / controller)**

Run (leave running): `python -m http.server 8000` from the repo root.
Open `http://localhost:8000/docs/mockups/reserve-trajectory.html` (no param) → the Wexford chart renders exactly as before (header "The Wexford · #304", levy verdict at +0%). Then confirm `?data=../../fixtures/samples/reserve_outlook.sample.json` renders identically (proves the param path).

- [ ] **Step 4: Commit**

```bash
git add docs/mockups/reserve-trajectory.html docs/mockups/README.md
git commit -m "feat: mock reads ?data= param to render real gitignored outlooks"
```

---

## Self-Review

**Spec coverage** (against `2026-06-04-docs-to-json-reserve-mvp-design.md`):
- "Reserve extraction schema (focused, not StrataExtract)" → Task 1. ✓
- "The one intelligence call: Opus, whole PDF, forced tool-use, validate→repair→fail" → Task 2 (`extract.py` mirrors `strata.py`; model is `claude-opus-4-8`, the `client.py` default). ✓
- "Deterministic assembly: real fields, placeholder unit, degraded history, event derivation, year derivation" → Task 3. ✓
- "`yonder outlook <pdf>` CLI; default out next to the (gitignored) PDF" → Task 4. ✓
- "Mock `?data=` param; committed sample is default" → Task 5. ✓
- "Script ↔ intelligence frontier; per-doc call kept generic" → `extract_reserve(pdf_bytes, *, client)` is doc-type-agnostic in shape; only the prompt is report-specific. ✓
- "Testing: deterministic parts TDD'd with canned data, no API; real call manual/gated" → Tasks 1–4 use fakes/canned/monkeypatch; the real call only runs via `yonder outlook` with a key. ✓
- "Key handling via `.env` + `--env-file`" → documented in spec; the manual run uses `python -m uv run --env-file .env yonder outlook ...` (no code needed; `client.py` reads `os.environ`). ✓
- "Collapse ranges to points (mock single-range limitation)" → Task 3 `assemble` + its test. ✓

**Placeholder scan:** no TBD/TODO; every code step is complete; the only manual step (Task 5 Step 3) has explicit pass criteria and is controller-verifiable in a browser.

**Type consistency:** `ReserveExtract`/`ProjectedExpenditure` field names are identical across Task 1 (definition), Task 2 (fake-client dicts), Task 3 (`assemble` reads them), and Task 4 (canned CLI fixture). `assemble()` emits only fields defined on `ReserveOutlook` (Task-1-of-the-prior-plan model): `building`, `unit`, `assumptions`, `start_balance`, `history`, `expenditures`, `planned_fee_changes`, `events`, `degraded`, `degraded_reason`. CLI symbol names (`extract_reserve`, `assemble`, `_build_client`) match the monkeypatch targets in the test. Tool name `record_reserve_facts` is consistent between `extract.py` and its test.

**Note on the real run (post-implementation, separate from these tasks):** once the code is in, the depreciation-report extraction is exercised manually with the user's consent:
`python -m uv run --env-file .env yonder outlook "fixtures/strata/Spectrum 4/Spectrum 4-Strata Docs_updated Apr 25,2025/Depreciation report & Engineering report/DepreciationReport (2).pdf"`
then view via the mock's `?data=`. Its output quality is read by eye and used to iterate the prompt/schema — not asserted in CI.
