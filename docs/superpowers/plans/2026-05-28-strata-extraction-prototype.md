# Strata-PDF Extraction Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Python harness that extracts structured facts from a single BC strata PDF using Claude, plus an eval harness that scores extractions against hand-labeled ground truth — no cloud, no UI.

**Architecture:** A CLI (`yonder extract <pdf>` / `yonder eval`) calls extraction logic in `strata.py`, which sends the PDF to Claude through a thin `client.py` seam (Anthropic API now, Bedrock later) using forced tool-use against a Pydantic-derived JSON schema, then validates with a repair-retry-once loop. `score.py` compares a `StrataExtract` against a partial-or-complete JSON label and reports raw counts + an itemized diff — never synthetic percentages.

**Tech Stack:** Python 3.11+, uv, Pydantic v2, anthropic SDK, pytest, reportlab (dev-only, fixture generation).

**Spec:** `docs/superpowers/specs/2026-05-28-strata-extraction-prototype-design.md`

---

## File Structure

| File | Responsibility |
|---|---|
| `pyproject.toml` | uv project, deps, `yonder` CLI entry point |
| `.gitignore` | ignore `fixtures/strata/`, `.env`, build artifacts |
| `.env.example` | documents `ANTHROPIC_API_KEY` |
| `src/yonder/__init__.py` | package marker |
| `src/yonder/extract/schema.py` | Pydantic models — the `StrataExtract` contract |
| `src/yonder/extract/client.py` | thin Claude wrapper (forced tool-use over a PDF) |
| `src/yonder/extract/strata.py` | prompt + extraction + validate/repair-retry loop |
| `src/yonder/eval/score.py` | label-vs-extract comparison + result types |
| `src/yonder/cli.py` | `extract` and `eval` commands, table rendering |
| `tests/test_schema.py` | schema validation / ratio parsing (no API) |
| `tests/test_score.py` | comparison logic (no API) |
| `tests/test_extract.py` | integration vs committed sample (skips w/o API key) |
| `fixtures/samples/generate_sample.py` | reproducible synthetic-PDF generator (dev) |
| `fixtures/samples/sample-strata-package.pdf` | committed synthetic doc |
| `fixtures/samples/expected.json` | committed complete label (`"complete": true`) |
| `fixtures/strata/` | gitignored — real docs + their `*.expected.json` |
| `CLAUDE.md`, `README.md` | project guide + quickstart |

---

## Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `src/yonder/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_smoke.py`

- [ ] **Step 1: Write the failing smoke test**

`tests/test_smoke.py`:
```python
def test_package_imports():
    import yonder

    assert yonder.__version__ == "0.0.1"
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[project]
name = "yonder"
version = "0.0.1"
description = "BC home-buying companion — strata document extraction prototype"
requires-python = ">=3.11"
dependencies = [
    "anthropic>=0.40",
    "pydantic>=2.7",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "reportlab>=4.0",
]

[project.scripts]
yonder = "yonder.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/yonder"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 3: Create `.gitignore`**

```gitignore
# Real strata docs and their labels — never commit (copyright + privacy)
fixtures/strata/

# Secrets
.env

# Python
__pycache__/
*.pyc
.venv/
dist/
build/
*.egg-info/
.pytest_cache/
```

- [ ] **Step 4: Create `.env.example`**

```dotenv
# Copy to .env and fill in. Used by yonder.extract.client.
ANTHROPIC_API_KEY=sk-ant-...
```

- [ ] **Step 5: Create package markers**

`src/yonder/__init__.py`:
```python
__version__ = "0.0.1"
```

`tests/__init__.py`:
```python
```

- [ ] **Step 6: Sync and run the smoke test**

Run:
```bash
uv sync --extra dev
uv run pytest tests/test_smoke.py -v
```
Expected: PASS (1 passed).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .gitignore .env.example src/yonder/__init__.py tests/__init__.py tests/test_smoke.py uv.lock
git commit -m "chore: scaffold uv project with smoke test"
```

---

## Task 2: Extraction schema

**Files:**
- Create: `src/yonder/extract/__init__.py`
- Create: `src/yonder/extract/schema.py`
- Test: `tests/test_schema.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_schema.py`:
```python
import datetime

import pytest
from pydantic import ValidationError

from yonder.extract.schema import (
    DocType,
    ReserveTrend,
    SpecialLevy,
    StrataExtract,
    UnitEntitlement,
)


def test_empty_extract_is_valid():
    """Real docs are partial; an all-empty extract must validate."""
    extract = StrataExtract()
    assert extract.documents == []
    assert extract.special_levies == []
    assert extract.unit_entitlement is None


def test_unit_entitlement_from_ratio_string():
    ue = UnitEntitlement.from_ratio("18/2719")
    assert ue.numerator == 18
    assert ue.denominator == 2719


def test_unit_entitlement_from_ratio_tolerates_spaces():
    ue = UnitEntitlement.from_ratio("  18 / 2719 ")
    assert (ue.numerator, ue.denominator) == (18, 2719)


def test_unit_entitlement_from_ratio_rejects_garbage():
    with pytest.raises(ValueError):
        UnitEntitlement.from_ratio("not-a-ratio")


def test_special_levy_parses_iso_date():
    levy = SpecialLevy(amount=4200.0, date_approved="2023-11-15", purpose="roof")
    assert levy.date_approved == datetime.date(2023, 11, 15)


def test_doctype_defaults_to_other():
    extract = StrataExtract.model_validate({"documents": [{"issue_date": "2024-03-12"}]})
    assert extract.documents[0].type == DocType.OTHER


def test_reserve_trend_defaults_unknown():
    extract = StrataExtract.model_validate({"reserve_fund": {"balance": 100000.0}})
    assert extract.reserve_fund.trend == ReserveTrend.UNKNOWN


def test_unknown_doctype_rejected_so_model_must_use_other():
    with pytest.raises(ValidationError):
        StrataExtract.model_validate({"documents": [{"type": "tax_return"}]})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_schema.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'yonder.extract'`.

- [ ] **Step 3: Implement the schema**

`src/yonder/extract/__init__.py`:
```python
```

`src/yonder/extract/schema.py`:
```python
"""The StrataExtract contract — what a strata PDF becomes.

v0 seed, not frozen. All fields nullable (real docs are partial; absence is a
first-class state — never invent). Provenance + confidence attach at FACT
granularity: each list item and each top-level group, not every scalar.
Doc type is an open vocabulary: a typed core plus OTHER + free label, so an
unrecognized doc degrades gracefully instead of being force-fit.
"""

from __future__ import annotations

import datetime
from enum import Enum

from pydantic import BaseModel, Field


class DocType(str, Enum):
    AGM_MINUTES = "agm_minutes"
    SGM_MINUTES = "sgm_minutes"
    DEPRECIATION_REPORT = "depreciation_report"
    FINANCIAL_STATEMENT = "financial_statement"
    FORM_B = "form_b"
    BYLAWS = "bylaws"
    OTHER = "other"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReserveTrend(str, Enum):
    RISING = "rising"
    FLAT = "flat"
    DECLINING = "declining"
    UNKNOWN = "unknown"


class Provenance(BaseModel):
    page: int | None = None
    doc_id: str | None = Field(
        default=None, description="Sub-document id within a combined PDF, if any."
    )
    confidence: Confidence = Confidence.MEDIUM


class Building(BaseModel):
    name: str | None = None
    address: str | None = None
    provenance: Provenance | None = None


class UnitEntitlement(BaseModel):
    numerator: int | None = None
    denominator: int | None = None
    provenance: Provenance | None = None

    @classmethod
    def from_ratio(cls, ratio: str) -> "UnitEntitlement":
        parts = ratio.split("/")
        if len(parts) != 2:
            raise ValueError(f"Not a ratio: {ratio!r}")
        num, den = (p.strip() for p in parts)
        if not (num.isdigit() and den.isdigit()):
            raise ValueError(f"Not a ratio: {ratio!r}")
        return cls(numerator=int(num), denominator=int(den))


class FoundDocument(BaseModel):
    type: DocType = DocType.OTHER
    type_label: str | None = Field(
        default=None, description="Free-text label when type is OTHER."
    )
    issue_date: datetime.date | None = None
    period_covered: str | None = None
    provenance: Provenance | None = None


class Meeting(BaseModel):
    type: str | None = Field(default=None, description='"AGM" or "SGM".')
    date: datetime.date | None = None
    provenance: Provenance | None = None


class SpecialLevy(BaseModel):
    amount: float | None = None
    date_approved: datetime.date | None = None
    purpose: str | None = None
    provenance: Provenance | None = None


class Litigation(BaseModel):
    present: bool | None = None
    summary: str | None = None
    provenance: Provenance | None = None


class ReserveFund(BaseModel):
    balance: float | None = None
    as_of_date: datetime.date | None = None
    trend: ReserveTrend = ReserveTrend.UNKNOWN
    provenance: Provenance | None = None


class StrataExtract(BaseModel):
    building: Building = Field(default_factory=Building)
    unit_entitlement: UnitEntitlement | None = None
    documents: list[FoundDocument] = Field(default_factory=list)
    meetings: list[Meeting] = Field(default_factory=list)
    special_levies: list[SpecialLevy] = Field(default_factory=list)
    litigation: Litigation | None = None
    reserve_fund: ReserveFund | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_schema.py -v`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add src/yonder/extract/__init__.py src/yonder/extract/schema.py tests/test_schema.py
git commit -m "feat: add StrataExtract schema with nullable fact-level provenance"
```

---

## Task 3: Scoring logic

**Files:**
- Create: `src/yonder/eval/__init__.py`
- Create: `src/yonder/eval/score.py`
- Test: `tests/test_score.py`

Label format (decided here): a JSON object that is a partial `StrataExtract` plus a
top-level boolean `"complete"`. When `complete` is true, extracted facts not present
in the label are **hallucinations**; when false (the default for real docs), they are
**unlabeled-extra (unknown)** and never counted as hallucinations.

Prototype 1 scores three representative fields — `unit_entitlement` (ratio),
`reserve_fund.trend` (enum), and `special_levies` (list, matched by purpose) — and is
extended field-by-field as labels grow. This keeps scoring complete and honest without
over-building.

- [ ] **Step 1: Write the failing tests**

`tests/test_score.py`:
```python
from yonder.eval.score import ResultType, score_extract
from yonder.extract.schema import (
    ReserveFund,
    ReserveTrend,
    SpecialLevy,
    StrataExtract,
    UnitEntitlement,
)


def _result_for(results, field):
    return next(r for r in results if r.field == field)


def test_matching_ratio_scores_match():
    extract = StrataExtract(unit_entitlement=UnitEntitlement(numerator=18, denominator=2719))
    label = {"unit_entitlement": {"numerator": 18, "denominator": 2719}}
    results = score_extract(extract, label)
    assert _result_for(results, "unit_entitlement").type == ResultType.MATCH


def test_wrong_ratio_scores_wrong_value():
    extract = StrataExtract(unit_entitlement=UnitEntitlement(numerator=18, denominator=9999))
    label = {"unit_entitlement": {"numerator": 18, "denominator": 2719}}
    results = score_extract(extract, label)
    assert _result_for(results, "unit_entitlement").type == ResultType.WRONG


def test_missing_labeled_field_scores_missed():
    extract = StrataExtract()  # extracted nothing
    label = {"reserve_fund": {"trend": "declining"}}
    results = score_extract(extract, label)
    assert _result_for(results, "reserve_fund.trend").type == ResultType.MISSED


def test_trend_match():
    extract = StrataExtract(reserve_fund=ReserveFund(trend=ReserveTrend.DECLINING))
    label = {"reserve_fund": {"trend": "declining"}}
    results = score_extract(extract, label)
    assert _result_for(results, "reserve_fund.trend").type == ResultType.MATCH


def test_special_levies_matched_by_purpose():
    extract = StrataExtract(
        special_levies=[
            SpecialLevy(amount=4200.0, purpose="roof"),
            SpecialLevy(amount=850.0, purpose="elevator"),
        ]
    )
    label = {
        "special_levies": [
            {"amount": 4200.0, "purpose": "roof"},
            {"amount": 850.0, "purpose": "elevator"},
        ]
    }
    results = score_extract(extract, label)
    levy_results = [r for r in results if r.field.startswith("special_levies")]
    assert all(r.type == ResultType.MATCH for r in levy_results)
    assert len(levy_results) == 2


def test_missed_levy_is_flagged():
    extract = StrataExtract(special_levies=[SpecialLevy(amount=4200.0, purpose="roof")])
    label = {
        "special_levies": [
            {"amount": 4200.0, "purpose": "roof"},
            {"amount": 850.0, "purpose": "elevator"},
        ]
    }
    results = score_extract(extract, label)
    missed = [r for r in results if r.type == ResultType.MISSED]
    assert any("elevator" in (r.expected or "") for r in missed)


def test_extra_levy_partial_label_is_unlabeled_extra():
    extract = StrataExtract(
        special_levies=[
            SpecialLevy(amount=4200.0, purpose="roof"),
            SpecialLevy(amount=99.0, purpose="garden"),
        ]
    )
    label = {"complete": False, "special_levies": [{"amount": 4200.0, "purpose": "roof"}]}
    results = score_extract(extract, label)
    extras = [r for r in results if r.type == ResultType.UNLABELED_EXTRA]
    assert any("garden" in (r.got or "") for r in extras)


def test_extra_levy_complete_label_is_hallucination():
    extract = StrataExtract(
        special_levies=[
            SpecialLevy(amount=4200.0, purpose="roof"),
            SpecialLevy(amount=99.0, purpose="garden"),
        ]
    )
    label = {"complete": True, "special_levies": [{"amount": 4200.0, "purpose": "roof"}]}
    results = score_extract(extract, label)
    halluc = [r for r in results if r.type == ResultType.HALLUCINATION]
    assert any("garden" in (r.got or "") for r in halluc)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_score.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'yonder.eval'`.

- [ ] **Step 3: Implement the scorer**

`src/yonder/eval/__init__.py`:
```python
```

`src/yonder/eval/score.py`:
```python
"""Compare a StrataExtract against a hand-written JSON label.

Honest reporting: raw counts, denominators always visible, no synthetic
percentage. Hallucinations are counted ONLY when the label is complete
("complete": true); otherwise an extracted-but-unlabeled fact is unknown,
not a hallucination.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from yonder.extract.schema import StrataExtract


class ResultType(str, Enum):
    MATCH = "match"
    WRONG = "wrong-value"
    MISSED = "missed"
    UNLABELED_EXTRA = "unlabeled-extra"
    HALLUCINATION = "hallucination"


@dataclass
class FieldResult:
    field: str
    type: ResultType
    expected: str | None = None
    got: str | None = None
    low_confidence: bool = False


def _norm_purpose(purpose: str | None) -> str:
    return (purpose or "").strip().lower()


def _score_scalar(field: str, got, expected, results: list[FieldResult]) -> None:
    """expected is present in the label; decide match/wrong/missed."""
    if got is None:
        results.append(FieldResult(field, ResultType.MISSED, expected=str(expected)))
    elif str(got) == str(expected):
        results.append(FieldResult(field, ResultType.MATCH, expected=str(expected), got=str(got)))
    else:
        results.append(
            FieldResult(field, ResultType.WRONG, expected=str(expected), got=str(got))
        )


def _score_unit_entitlement(extract: StrataExtract, label: dict, results: list[FieldResult]) -> None:
    exp = label["unit_entitlement"]
    expected_ratio = f"{exp.get('numerator')}/{exp.get('denominator')}"
    ue = extract.unit_entitlement
    got_ratio = None if ue is None else f"{ue.numerator}/{ue.denominator}"
    _score_scalar("unit_entitlement", got_ratio, expected_ratio, results)


def _score_reserve_trend(extract: StrataExtract, label: dict, results: list[FieldResult]) -> None:
    expected = label["reserve_fund"].get("trend")
    rf = extract.reserve_fund
    got = None if rf is None or rf.trend is None else rf.trend.value
    _score_scalar("reserve_fund.trend", got, expected, results)


def _score_special_levies(extract: StrataExtract, label: dict, results: list[FieldResult]) -> None:
    expected_levies = label["special_levies"]
    got_by_purpose = {_norm_purpose(lv.purpose): lv for lv in extract.special_levies}
    matched_purposes = set()

    for exp in expected_levies:
        key = _norm_purpose(exp.get("purpose"))
        field = f"special_levies[{exp.get('purpose')}]"
        got = got_by_purpose.get(key)
        if got is None:
            results.append(
                FieldResult(field, ResultType.MISSED, expected=str(exp.get("purpose")))
            )
            continue
        matched_purposes.add(key)
        if exp.get("amount") is not None and got.amount != exp["amount"]:
            results.append(
                FieldResult(
                    field,
                    ResultType.WRONG,
                    expected=f"${exp['amount']}",
                    got=f"${got.amount}",
                )
            )
        else:
            results.append(FieldResult(field, ResultType.MATCH, expected=str(exp.get("purpose"))))

    # Extracted levies not in the label.
    complete = bool(label.get("complete", False))
    extra_type = ResultType.HALLUCINATION if complete else ResultType.UNLABELED_EXTRA
    for purpose_key, lv in got_by_purpose.items():
        if purpose_key not in matched_purposes:
            results.append(
                FieldResult(
                    f"special_levies[{lv.purpose}]",
                    extra_type,
                    got=str(lv.purpose),
                )
            )


def score_extract(extract: StrataExtract, label: dict) -> list[FieldResult]:
    """Return a flat list of per-field results. Only fields the label asserts
    are scored; nothing is invented."""
    results: list[FieldResult] = []
    if "unit_entitlement" in label:
        _score_unit_entitlement(extract, label, results)
    if "reserve_fund" in label and "trend" in label["reserve_fund"]:
        _score_reserve_trend(extract, label, results)
    if "special_levies" in label:
        _score_special_levies(extract, label, results)
    return results


def tally(results: list[FieldResult]) -> dict[ResultType, int]:
    counts = {t: 0 for t in ResultType}
    for r in results:
        counts[r.type] += 1
    return counts
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_score.py -v`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add src/yonder/eval/__init__.py src/yonder/eval/score.py tests/test_score.py
git commit -m "feat: add label-vs-extract scorer with complete/partial hallucination rule"
```

---

## Task 4: Claude client seam

**Files:**
- Create: `src/yonder/extract/client.py`
- Test: `tests/test_client.py`

The client is intentionally thin: it builds a forced tool-use request with the PDF as a
base64 document block and returns the tool input dict. It is the one file that changes
when we later swap to Bedrock. The unit test mocks the SDK so it runs without an API key.

- [ ] **Step 1: Write the failing test**

`tests/test_client.py`:
```python
from unittest.mock import MagicMock

from yonder.extract.client import ClaudeClient


def _fake_tool_response(tool_input):
    block = MagicMock()
    block.type = "tool_use"
    block.name = "record_strata_facts"
    block.input = tool_input
    message = MagicMock()
    message.content = [block]
    return message


def test_extract_with_tool_returns_tool_input():
    sdk = MagicMock()
    sdk.messages.create.return_value = _fake_tool_response({"building": {"name": "X"}})
    client = ClaudeClient(sdk=sdk, model="claude-opus-4-8")

    result = client.extract_with_tool(
        pdf_bytes=b"%PDF-1.4 fake",
        system="sys",
        tool={"name": "record_strata_facts", "input_schema": {"type": "object"}},
        tool_name="record_strata_facts",
    )

    assert result == {"building": {"name": "X"}}


def test_extract_with_tool_sends_pdf_document_block():
    sdk = MagicMock()
    sdk.messages.create.return_value = _fake_tool_response({})
    client = ClaudeClient(sdk=sdk, model="claude-opus-4-8")

    client.extract_with_tool(
        pdf_bytes=b"%PDF-1.4 fake",
        system="sys",
        tool={"name": "record_strata_facts", "input_schema": {"type": "object"}},
        tool_name="record_strata_facts",
    )

    kwargs = sdk.messages.create.call_args.kwargs
    blocks = kwargs["messages"][0]["content"]
    doc_block = next(b for b in blocks if b["type"] == "document")
    assert doc_block["source"]["media_type"] == "application/pdf"
    assert kwargs["tool_choice"] == {"type": "tool", "name": "record_strata_facts"}


def test_extra_note_appended_as_second_message():
    sdk = MagicMock()
    sdk.messages.create.return_value = _fake_tool_response({})
    client = ClaudeClient(sdk=sdk, model="claude-opus-4-8")

    client.extract_with_tool(
        pdf_bytes=b"%PDF-1.4 fake",
        system="sys",
        tool={"name": "record_strata_facts", "input_schema": {"type": "object"}},
        tool_name="record_strata_facts",
        extra_note="Your previous output failed validation: bad date.",
    )

    kwargs = sdk.messages.create.call_args.kwargs
    assert len(kwargs["messages"]) == 2
    assert "failed validation" in kwargs["messages"][1]["content"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'yonder.extract.client'`.

- [ ] **Step 3: Implement the client**

`src/yonder/extract/client.py`:
```python
"""Thin Claude seam. The ONE file to change when swapping to Bedrock.

Builds a forced tool-use request with the PDF as a base64 document block and
returns the tool's input dict.
"""

from __future__ import annotations

import base64
import os


class ExtractionError(RuntimeError):
    """The model did not return the expected tool call."""


class ClaudeClient:
    def __init__(self, *, sdk=None, api_key: str | None = None, model: str = "claude-opus-4-8"):
        if sdk is None:
            from anthropic import Anthropic

            sdk = Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])
        self._sdk = sdk
        self.model = model

    def extract_with_tool(
        self,
        *,
        pdf_bytes: bytes,
        system: str,
        tool: dict,
        tool_name: str,
        extra_note: str | None = None,
        max_tokens: int = 8000,
    ) -> dict:
        b64 = base64.standard_b64encode(pdf_bytes).decode("ascii")
        first_content = [
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": b64,
                },
            },
            {"type": "text", "text": "Extract the strata facts from this document."},
        ]
        messages = [{"role": "user", "content": first_content}]
        if extra_note:
            messages.append({"role": "user", "content": extra_note})

        message = self._sdk.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            tools=[tool],
            tool_choice={"type": "tool", "name": tool_name},
            messages=messages,
        )
        for block in message.content:
            if getattr(block, "type", None) == "tool_use" and block.name == tool_name:
                return block.input
        raise ExtractionError(f"No '{tool_name}' tool_use block in response.")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_client.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/yonder/extract/client.py tests/test_client.py
git commit -m "feat: add thin Claude client seam with forced tool-use over PDF"
```

---

## Task 5: Extraction orchestration with repair-retry

**Files:**
- Create: `src/yonder/extract/strata.py`
- Test: `tests/test_strata.py`

`strata.py` owns the prompt, builds the tool schema from `StrataExtract`, and runs
**validate → repair-retry-once → fail loudly**. Unit-tested with a fake client (no API).

- [ ] **Step 1: Write the failing tests**

`tests/test_strata.py`:
```python
import pytest
from pydantic import ValidationError

from yonder.extract.schema import StrataExtract
from yonder.extract.strata import extract_strata, strata_tool


def test_strata_tool_has_object_schema():
    tool = strata_tool()
    assert tool["name"] == "record_strata_facts"
    assert tool["input_schema"]["type"] == "object"


class _FakeClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def extract_with_tool(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


def test_valid_first_response_returns_extract():
    client = _FakeClient([{"building": {"name": "Gardens at Yaletown"}}])
    extract = extract_strata(b"%PDF fake", client=client)
    assert isinstance(extract, StrataExtract)
    assert extract.building.name == "Gardens at Yaletown"
    assert len(client.calls) == 1


def test_invalid_then_valid_triggers_one_repair_retry():
    client = _FakeClient(
        [
            {"documents": [{"type": "tax_return"}]},  # invalid enum -> ValidationError
            {"building": {"name": "Recovered"}},      # repaired
        ]
    )
    extract = extract_strata(b"%PDF fake", client=client)
    assert extract.building.name == "Recovered"
    assert len(client.calls) == 2
    assert client.calls[1]["extra_note"] is not None


def test_invalid_twice_fails_loudly():
    client = _FakeClient(
        [
            {"documents": [{"type": "tax_return"}]},
            {"documents": [{"type": "still_bad"}]},
        ]
    )
    with pytest.raises(ValidationError):
        extract_strata(b"%PDF fake", client=client)
    assert len(client.calls) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_strata.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'yonder.extract.strata'`.

- [ ] **Step 3: Implement extraction**

`src/yonder/extract/strata.py`:
```python
"""Prompt + extraction orchestration: validate -> repair-retry-once -> fail loudly."""

from __future__ import annotations

from pydantic import ValidationError

from yonder.extract.schema import StrataExtract

TOOL_NAME = "record_strata_facts"

SYSTEM_PROMPT = """You read British Columbia strata documents and extract structured \
facts for a home-buyer's strata-health view. Rules:

- Extract ONLY what the document states. If a fact is not present, leave it null. \
Never guess or infer a number that is not written.
- A single PDF may be a combined package of several sub-documents (years of AGM \
minutes, a depreciation report, Form B). Populate `documents` with each sub-document \
you identify.
- For every fact, set provenance.page to the page it came from, and provenance.confidence \
to high/medium/low based on how explicit the source is.
- If a document type is not in the known list, use type "other" and put a short label \
in type_label.
- Cost-share / unit-entitlement is a ratio like 18/2719 (this unit / total).

Call the record_strata_facts tool with everything you found."""


def strata_tool() -> dict:
    return {
        "name": TOOL_NAME,
        "description": "Record the structured strata facts extracted from the document.",
        "input_schema": StrataExtract.model_json_schema(),
    }


def extract_strata(pdf_bytes: bytes, *, client) -> StrataExtract:
    """Extract a StrataExtract from PDF bytes. Retries once with the validation
    error fed back to the model; raises ValidationError if the second try is
    also invalid."""
    tool = strata_tool()
    extra_note: str | None = None
    last_error: ValidationError | None = None

    for attempt in range(2):
        raw = client.extract_with_tool(
            pdf_bytes=pdf_bytes,
            system=SYSTEM_PROMPT,
            tool=tool,
            tool_name=TOOL_NAME,
            extra_note=extra_note,
        )
        try:
            return StrataExtract.model_validate(raw)
        except ValidationError as exc:
            last_error = exc
            extra_note = (
                "Your previous tool call failed schema validation with these errors:\n"
                f"{exc}\n"
                "Return the record_strata_facts tool call again, corrected. Use null for "
                "anything you are unsure of, and only the allowed enum values."
            )

    assert last_error is not None
    raise last_error
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_strata.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/yonder/extract/strata.py tests/test_strata.py
git commit -m "feat: add strata extraction with validate/repair-retry-once loop"
```

---

## Task 6: Synthetic fixture (committed sample)

**Files:**
- Create: `fixtures/samples/generate_sample.py`
- Create: `fixtures/samples/sample-strata-package.pdf` (generated)
- Create: `fixtures/samples/expected.json`

The synthetic PDF is a fictional combined package whose label is **complete** — the only
fixture where hallucinations are counted. The generator is committed so the PDF is
reproducible.

- [ ] **Step 1: Write the generator**

`fixtures/samples/generate_sample.py`:
```python
"""Generate the committed synthetic strata package. Reproducible; no real data.

Run: uv run python fixtures/samples/generate_sample.py
"""

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

OUT = Path(__file__).parent / "sample-strata-package.pdf"

PAGES = [
    [
        "STRATA PLAN BCS9999 - GARDENS AT YALETOWN",
        "Combined Document Package (SYNTHETIC - NOT A REAL BUILDING)",
        "",
        "Unit 304 - Strata Lot 18",
        "Unit Entitlement: 18 / 2719",
    ],
    [
        "ANNUAL GENERAL MEETING - MINUTES",
        "Date: March 12, 2024",
        "",
        "1. The reserve (contingency) fund balance as of Dec 31, 2023",
        "   was $412,000. The fund has been DECLINING over three years.",
        "2. A special levy of $4,200 per unit was approved on",
        "   November 15, 2023 for roof replacement.",
    ],
    [
        "SPECIAL GENERAL MEETING - MINUTES",
        "Date: February 2, 2024",
        "",
        "A special levy of $850 per unit was approved on",
        "February 2, 2024 for elevator modernization.",
        "",
        "No litigation is currently pending against the strata corporation.",
    ],
]


def main() -> None:
    c = canvas.Canvas(str(OUT), pagesize=letter)
    for page in PAGES:
        text = c.beginText(72, 720)
        text.setFont("Helvetica", 12)
        for line in page:
            text.textLine(line)
        c.drawText(text)
        c.showPage()
    c.save()
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Generate the PDF**

Run:
```bash
uv run python fixtures/samples/generate_sample.py
```
Expected: `Wrote .../sample-strata-package.pdf`, and the file exists.

- [ ] **Step 3: Write the complete label**

`fixtures/samples/expected.json`:
```json
{
  "complete": true,
  "unit_entitlement": { "numerator": 18, "denominator": 2719 },
  "reserve_fund": { "trend": "declining" },
  "special_levies": [
    { "amount": 4200.0, "purpose": "roof" },
    { "amount": 850.0, "purpose": "elevator" }
  ]
}
```

- [ ] **Step 4: Commit**

```bash
git add fixtures/samples/generate_sample.py fixtures/samples/sample-strata-package.pdf fixtures/samples/expected.json
git commit -m "test: add synthetic strata package fixture with complete label"
```

---

## Task 7: CLI

**Files:**
- Create: `src/yonder/cli.py`
- Test: `tests/test_cli.py`

`yonder extract <pdf> [--json]` prints the extract; `yonder eval <dir>` scores every
`*.pdf` that has a sibling label and prints the itemized table + raw counts. Rendering
logic (`render_report`) is unit-tested directly; the commands wire it to the client.

- [ ] **Step 1: Write the failing test (rendering only — no API)**

`tests/test_cli.py`:
```python
from yonder.cli import render_report
from yonder.eval.score import FieldResult, ResultType


def test_render_report_shows_denominators_and_counts():
    results = [
        FieldResult("unit_entitlement", ResultType.MATCH, expected="18/2719", got="18/2719"),
        FieldResult("special_levies[elevator]", ResultType.MISSED, expected="elevator"),
        FieldResult("special_levies[roof]", ResultType.MATCH, expected="roof"),
    ]
    out = render_report("sample-strata-package", results, complete=True)
    assert "sample-strata-package" in out
    assert "label: complete" in out
    assert "match: 2" in out
    assert "missed: 1" in out
    # No synthetic percentage anywhere.
    assert "%" not in out


def test_render_report_marks_partial_label():
    out = render_report("real-doc", [], complete=False)
    assert "label: partial" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'yonder.cli'`.

- [ ] **Step 3: Implement the CLI**

`src/yonder/cli.py`:
```python
"""yonder CLI: `extract` one PDF, `eval` a folder of labeled PDFs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from yonder.eval.score import FieldResult, ResultType, score_extract, tally
from yonder.extract.client import ClaudeClient
from yonder.extract.schema import StrataExtract
from yonder.extract.strata import extract_strata

_SYMBOL = {
    ResultType.MATCH: "OK ",
    ResultType.WRONG: "XX ",
    ResultType.MISSED: "-- ",
    ResultType.UNLABELED_EXTRA: "?? ",
    ResultType.HALLUCINATION: "!! ",
}


def render_report(doc_name: str, results: list[FieldResult], *, complete: bool) -> str:
    lines = [f"doc: {doc_name}  (label: {'complete' if complete else 'partial'})"]
    for r in results:
        detail = ""
        if r.type == ResultType.WRONG:
            detail = f"  got {r.got!r}, expected {r.expected!r}"
        elif r.expected:
            detail = f"  {r.expected}"
        elif r.got:
            detail = f"  {r.got}"
        lines.append(f"  {_SYMBOL[r.type]}{r.field}{detail}")
    counts = tally(results)
    summary = "  ".join(f"{t.value}: {counts[t]}" for t in ResultType if counts[t])
    lines.append(f"  counts -> {summary or 'none'}")
    if not complete:
        lines.append("  (label partial: extras are unknown, NOT counted as hallucinations)")
    return "\n".join(lines)


def _build_client() -> ClaudeClient:
    return ClaudeClient()


def cmd_extract(args: argparse.Namespace) -> int:
    pdf_bytes = Path(args.pdf).read_bytes()
    extract = extract_strata(pdf_bytes, client=_build_client())
    print(json.dumps(extract.model_dump(mode="json"), indent=2))
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    folder = Path(args.folder)
    pdfs = sorted(folder.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs in {folder}", file=sys.stderr)
        return 1
    client = _build_client()
    for pdf in pdfs:
        label_path = pdf.with_suffix(".expected.json")
        if not label_path.exists():
            # Convention: the sample uses expected.json (single sample per folder).
            alt = pdf.parent / "expected.json"
            label_path = alt if alt.exists() else label_path
        if not label_path.exists():
            print(f"skip {pdf.name}: no label", file=sys.stderr)
            continue
        label = json.loads(label_path.read_text())
        extract = extract_strata(pdf.read_bytes(), client=client)
        results = score_extract(extract, label)
        print(render_report(pdf.stem, results, complete=bool(label.get("complete", False))))
        print()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="yonder")
    sub = parser.add_subparsers(dest="command", required=True)

    p_extract = sub.add_parser("extract", help="Extract facts from one strata PDF.")
    p_extract.add_argument("pdf")
    p_extract.set_defaults(func=cmd_extract)

    p_eval = sub.add_parser("eval", help="Score labeled PDFs in a folder.")
    p_eval.add_argument("folder")
    p_eval.set_defaults(func=cmd_eval)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/yonder/cli.py tests/test_cli.py
git commit -m "feat: add extract and eval CLI commands with honest count-based report"
```

---

## Task 8: Integration test against the sample (skips without API key)

**Files:**
- Create: `tests/test_extract.py`

Asserts structure, not exact LLM wording, so it stays stable. Skips when
`ANTHROPIC_API_KEY` is absent so CI/clones without a key still go green.

- [ ] **Step 1: Write the integration test**

`tests/test_extract.py`:
```python
import os
from pathlib import Path

import pytest

from yonder.extract.client import ClaudeClient
from yonder.extract.schema import StrataExtract
from yonder.extract.strata import extract_strata

SAMPLE = Path("fixtures/samples/sample-strata-package.pdf")

pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="needs ANTHROPIC_API_KEY (live extraction)",
)


def test_sample_extracts_valid_structure():
    extract = extract_strata(SAMPLE.read_bytes(), client=ClaudeClient())
    assert isinstance(extract, StrataExtract)
    # Structural expectations — the synthetic doc clearly contains these.
    assert extract.unit_entitlement is not None
    assert extract.unit_entitlement.denominator == 2719
    assert len(extract.special_levies) >= 1
    assert len(extract.documents) >= 1
```

- [ ] **Step 2: Run it (skips without a key)**

Run: `uv run pytest tests/test_extract.py -v`
Expected (no key): SKIPPED. With a key set: PASS.

- [ ] **Step 3: Run the full suite**

Run: `uv run pytest -v`
Expected: all unit tests PASS; integration test SKIPPED (or PASS with a key).

- [ ] **Step 4: Commit**

```bash
git add tests/test_extract.py
git commit -m "test: add live integration test against synthetic sample (skips without key)"
```

---

## Task 9: Docs and housekeeping

**Files:**
- Create: `CLAUDE.md`
- Create: `README.md`
- Move: the three brainstorm docs to `docs/brainstorm/`

- [ ] **Step 1: Move the brainstorm docs**

The three docs are currently **untracked** (never committed), so use plain `mv`,
not `git mv`. They get added to git in this task's final commit. Run (bash):
```bash
mkdir -p docs/brainstorm
mv "ARCHITECTURE Sketch.md" docs/brainstorm/architecture-sketch.md
mv bc-home-buying-feature-glossary.md docs/brainstorm/feature-glossary.md
mv bc-home-buying-data-playbook.md docs/brainstorm/data-playbook.md
```

- [ ] **Step 2: Write `CLAUDE.md`**

```markdown
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
- `uv run pytest` — run tests (live integration test skips without a key)
- `uv run python fixtures/samples/generate_sample.py` — regenerate the synthetic fixture

## Where the thinking lives

- `docs/brainstorm/` — architecture sketch, feature glossary, data playbook
- `docs/superpowers/specs/` — the design spec
- `docs/superpowers/plans/` — this implementation plan

## Workflow

This project uses the superpowers workflow: brainstorm -> spec -> plan -> TDD
implementation. Write the failing test first; keep commits frequent.
```

- [ ] **Step 3: Write `README.md`**

```markdown
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
```

- [ ] **Step 4: Verify the suite still passes after the move**

Run: `uv run pytest -v`
Expected: unchanged — all PASS / integration SKIPPED.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md README.md docs/brainstorm/
git commit -m "docs: add CLAUDE.md, README, and relocate brainstorm docs"
```

---

## Definition of done

- `uv sync --extra dev` works from a clean clone.
- `uv run pytest` is green (unit tests pass; live integration test skips without a key).
- `uv run yonder extract fixtures/samples/sample-strata-package.pdf` returns a valid `StrataExtract` (with a key).
- `uv run yonder eval fixtures/samples` prints the itemized, count-based report — no percentages.
- `CLAUDE.md`, `README.md` in place; brainstorm docs relocated; `fixtures/strata/` gitignored.
