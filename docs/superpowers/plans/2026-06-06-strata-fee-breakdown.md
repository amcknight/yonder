# Strata Fee Breakdown View (v1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the v1 single-year Strata Fee Breakdown — a sorted bar list of the building's operating-budget categories, each sized to the user's personal monthly share, with the Reserve contribution pinned on top — as a vertical slice on one real building's docs, no app UI.

**Architecture:** Mirror the Reserve Trajectory view's seams exactly: a forced-tool **extraction** call (`FeeExtract`), a **pure deterministic compute** function (`fee_breakdown`), a **`FeeBreakdown` JSON contract**, and the **existing throwaway HTML mock** rendered from real numbers via a `?data=` URL param. Unlike the reserve view this is *reporting, not forecasting* — no projection, no assumptions. v1 produces a single budget year; the v1.1 trend layer (delta caps, personal-dollar diffs, sparklines, total-fee-over-time) is **deferred** — its model fields exist (nullable, empty) and the mock omits the ornaments when the data is absent (graceful degradation, the reserve view's philosophy).

**Tech Stack:** Python 3.11+, Pydantic v2, `uv`, pytest. New package `src/yonder/fees/` (sibling to `src/yonder/outlook/`). HTML/SVG/vanilla-JS mock under `docs/mockups/`. Synthetic committed fixtures only — real strata docs stay gitignored.

---

## Design decisions (read before starting)

These resolve ambiguities in the spec so the tasks below are unambiguous.

- **`degraded` means "core bars cannot render"** (no operating budget at all) — the same hard-degrade semantics as the reserve view's blank chart. The spec's "graceful degradation for the one-year case" is honored a different way: the **trend layer is data-driven**. The mock shows caps/diffs/sparklines/total-trend only when the inputs are present (`prior_year_annual` on a row; ≥2 `total_fee_series` points). In v1 those inputs are always absent, so the ornaments simply don't render. A normal single-year breakdown is therefore **`degraded = False`** with bars present.
- **Reserve is pinned via a distinct top-level field** `FeeBreakdown.reserve` (not an in-list flag), because the mock renders it with different markup (green box, tap-through link). Its `building_annual` comes from the budget's "Reserve contribution" category line; its `personal_monthly` comes from the user's lot **CRF contribution directly** (not a share of spend).
- **Spend categories size to the operating fee:** `personal_monthly = (category_building_annual / total_spend_building_annual) × user_operating_monthly`. This makes the spend categories' personal dollars sum to the user's operating fee — an invariant we test.
- **Category mapping lives in extraction**, not a hardcoded account table: the model proposes `parent_category` per line item (open vocabulary, `"Other"` fallback). There is **no** `fees/categories.py` keyword classifier (deliberately unlike `outlook/categories.py`).
- **The pinned-reserve category name is the literal `"Reserve contribution"`**, exported as `RESERVE_CATEGORY` and named in the extraction prompt so the model uses it verbatim. Exact-match is acceptable for v1; mismatched casing/wording landing in spend is a known v1 limitation.

## File Structure

**Create:**
- `src/yonder/fees/__init__.py` — package marker.
- `src/yonder/fees/schema.py` — `FeeExtract`: the extraction tool-use schema (operating budget line items + per-lot fee schedule).
- `src/yonder/fees/model.py` — `FeeBreakdown`: the JSON contract the mock renders from.
- `src/yonder/fees/compute.py` — `fee_breakdown(extract, *, lot_id)`: the pure FeeExtract → FeeBreakdown mapping.
- `src/yonder/fees/extract.py` — the ONE intelligence call: AGM-package PDF/text → `FeeExtract`.
- `src/yonder/fees/sample.py` — `wexford_fee_sample()`: the synthetic committed `FeeBreakdown`.
- `docs/mockups/fee-breakdown.html` — the data-driven phone mock.
- `tests/test_fees_schema.py`, `tests/test_fees_model.py`, `tests/test_fees_compute.py`, `tests/test_fees_sample.py`, `tests/test_fees_fixture_contract.py`, `tests/test_fees_extract.py`, `tests/test_fees_extract_live.py`, `tests/test_fees_cli.py`.
- `fixtures/samples/fee_breakdown.sample.json` — committed synthetic fixture (generated, not hand-written).

**Modify:**
- `src/yonder/cli.py` — add `fees` and `fees-sample` subcommands.
- `fixtures/samples/generate_sample.py` — add a budget + fee-schedule page to the synthetic PDF.
- `CLAUDE.md` — document the two new dev commands.

---

## Task 1: `FeeExtract` extraction schema

**Files:**
- Create: `src/yonder/fees/__init__.py`
- Create: `src/yonder/fees/schema.py`
- Test: `tests/test_fees_schema.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_fees_schema.py`:

```python
import json

import pytest
from pydantic import ValidationError

from yonder.fees.schema import BudgetLineItem, FeeExtract, LotFee


def test_empty_extract_is_valid():
    e = FeeExtract()
    assert e.operating_budget == []
    assert e.fee_schedule == []
    assert e.building_name is None


def test_budget_line_item_requires_label_and_parent_category():
    with pytest.raises(ValidationError):
        BudgetLineItem(annual_amount=1000)  # no label, no parent_category


def test_lot_fee_requires_lot_id():
    with pytest.raises(ValidationError):
        LotFee(operating_monthly=521)  # no lot_id


def test_round_trips_through_plain_json():
    e = FeeExtract(
        building_name="The Spectrum",
        fiscal_year=2024,
        operating_budget=[
            BudgetLineItem(label="Insurance premium", parent_category="Insurance",
                           annual_amount=182000, fiscal_year=2024),
        ],
        fee_schedule=[
            LotFee(lot_id="1802", entitlement=82, operating_monthly=521, crf_monthly=78),
        ],
    )
    back = FeeExtract.model_validate(json.loads(e.model_dump_json()))
    assert back == e
    assert back.operating_budget[0].parent_category == "Insurance"
    assert back.fee_schedule[0].lot_id == "1802"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m uv run pytest tests/test_fees_schema.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'yonder.fees'`

- [ ] **Step 3: Write minimal implementation**

Create `src/yonder/fees/__init__.py` (empty file):

```python
```

Create `src/yonder/fees/schema.py`:

```python
"""FeeExtract — the fee-breakdown extraction tool-use schema the model fills from
an AGM package (the approved operating budget + the per-lot strata-fee schedule).

Distinct from StrataExtract and ReserveExtract: this is what the ONE intelligence
call returns for the Fee Breakdown view, and it maps cleanly onto the FeeBreakdown
contract. All monetary values are CAD dollars. All fields nullable except a budget
line's `label` and `parent_category` (the rollup needs both) and a lot's `lot_id`
(the personal-share lookup needs it). Absence is first-class: the model leaves a
field null rather than inventing.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class BudgetLineItem(BaseModel):
    label: str                          # the account name, e.g. "Water & sewer", "Insurance"
    parent_category: str                # the model's proposed rollup bucket, e.g. "Utilities"
    annual_amount: float | None = None  # budgeted annual dollars
    fiscal_year: int | None = None      # the budget year this line belongs to


class LotFee(BaseModel):
    lot_id: str                              # the strata-lot identifier, e.g. "1802"
    entitlement: int | None = None           # unit entitlement (share of common property)
    operating_monthly: float | None = None   # monthly operating-fund contribution, dollars
    crf_monthly: float | None = None         # monthly contingency-reserve-fund contribution, dollars


class FeeExtract(BaseModel):
    building_name: str | None = None
    fiscal_year: int | None = None                           # the budget's fiscal year
    operating_budget: list[BudgetLineItem] = Field(default_factory=list)
    fee_schedule: list[LotFee] = Field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m uv run pytest tests/test_fees_schema.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/yonder/fees/__init__.py src/yonder/fees/schema.py tests/test_fees_schema.py
git commit -m "feat(fees): add FeeExtract extraction schema"
```

---

## Task 2: `FeeBreakdown` JSON contract

**Files:**
- Create: `src/yonder/fees/model.py`
- Test: `tests/test_fees_model.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_fees_model.py`:

```python
import json

from yonder.fees.model import (
    BuildingMeta,
    CategoryRow,
    FeeBreakdown,
    LineItem,
    RESERVE_CATEGORY,
    TotalFeePoint,
    UnitMeta,
)


def test_empty_breakdown_is_valid_and_not_degraded():
    """Absence is first-class: an all-empty breakdown must validate."""
    fb = FeeBreakdown()
    assert fb.categories == []
    assert fb.reserve is None
    assert fb.total_fee_series == []
    assert fb.degraded is False


def test_reserve_category_constant():
    assert RESERVE_CATEGORY == "Reserve contribution"


def test_category_row_carries_v11_prior_year_field_defaulting_none():
    row = CategoryRow(category="Utilities", building_annual=350000, personal_monthly=196)
    assert row.prior_year_annual is None       # v1.1 trend input; absent in v1
    assert row.line_items == []


def test_degraded_breakdown_carries_a_reason():
    fb = FeeBreakdown(degraded=True, degraded_reason="no operating budget line items found")
    assert fb.degraded is True
    assert "no operating budget" in fb.degraded_reason


def test_full_breakdown_round_trips_through_json():
    fb = FeeBreakdown(
        building=BuildingMeta(name="The Wexford", unit_label="#1802", fiscal_year=2024),
        unit=UnitMeta(lot_id="1802", operating_fee_monthly=521, reserve_fee_monthly=78,
                      total_fee_monthly=599),
        reserve=CategoryRow(category=RESERVE_CATEGORY, building_annual=139000, personal_monthly=78),
        categories=[
            CategoryRow(category="Utilities", building_annual=350000, personal_monthly=196,
                        line_items=[LineItem(label="Water & sewer", annual_amount=150000)]),
        ],
        total_fee_series=[TotalFeePoint(year=2024, monthly_fee=599)],
    )
    blob = fb.model_dump_json()
    assert FeeBreakdown.model_validate_json(blob) == fb
    assert FeeBreakdown.model_validate(json.loads(blob)) == fb
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m uv run pytest tests/test_fees_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'yonder.fees.model'`

- [ ] **Step 3: Write minimal implementation**

Create `src/yonder/fees/model.py`:

```python
"""The FeeBreakdown contract — the JSON seam the Fee Breakdown mock renders from.

Carries everything the chart needs to draw client-side: building + unit meta, the
pinned Reserve row, the sorted spend-category rows (each with its building annual,
the user's personal monthly share, line items for tap-to-expand, and a nullable
prior-year amount the v1.1 trend layer will fill), and the total-fee series. All
monetary values are CAD dollars. All fields nullable: real docs are partial, a
missing fee schedule yields building-total-only rows (no personal sizing), and a
missing operating budget yields a `degraded` breakdown rather than empty bars.

This is reporting, not forecasting (unlike ReserveOutlook): no assumptions, no
projection. v1 emits a single budget year; the trend-layer fields (prior_year on
rows, multi-point total_fee_series) stay empty until v1.1 multi-year extraction.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

RESERVE_CATEGORY = "Reserve contribution"  # the one pinned, "saved not spent" category


class BuildingMeta(BaseModel):
    name: str | None = None
    unit_label: str | None = None       # e.g. "#1802"
    fiscal_year: int | None = None      # the budget year shown
    source_note: str | None = None      # e.g. "AGM budget FY2024"


class UnitMeta(BaseModel):
    lot_id: str | None = None
    entitlement: int | None = None
    operating_fee_monthly: float | None = None  # user's monthly operating contribution
    reserve_fee_monthly: float | None = None     # user's monthly CRF contribution
    total_fee_monthly: float | None = None       # operating + reserve


class LineItem(BaseModel):
    label: str
    annual_amount: float | None = None           # building annual dollars


class CategoryRow(BaseModel):
    category: str                                # parent category, e.g. "Utilities"
    building_annual: float | None = None         # sum of line items, building dollars
    personal_monthly: float | None = None        # user's monthly share, dollars (None = no fee schedule)
    prior_year_annual: float | None = None       # v1.1 trend input; None in v1
    line_items: list[LineItem] = Field(default_factory=list)


class TotalFeePoint(BaseModel):
    year: int
    monthly_fee: float                           # total monthly fee that year


class FeeBreakdown(BaseModel):
    building: BuildingMeta = Field(default_factory=BuildingMeta)
    unit: UnitMeta = Field(default_factory=UnitMeta)
    reserve: CategoryRow | None = None           # the pinned Reserve row (top), if known
    categories: list[CategoryRow] = Field(default_factory=list)  # spend, sorted desc by building_annual
    total_fee_series: list[TotalFeePoint] = Field(default_factory=list)  # v1: <=1 point
    degraded: bool = False
    degraded_reason: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m uv run pytest tests/test_fees_model.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/yonder/fees/model.py tests/test_fees_model.py
git commit -m "feat(fees): add FeeBreakdown JSON contract"
```

---

## Task 3: `fee_breakdown` — rollup, sort, reserve pin (building totals only)

**Files:**
- Create: `src/yonder/fees/compute.py`
- Test: `tests/test_fees_compute.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_fees_compute.py`:

```python
import pytest

from yonder.fees.compute import fee_breakdown
from yonder.fees.model import FeeBreakdown, RESERVE_CATEGORY
from yonder.fees.schema import BudgetLineItem, FeeExtract, LotFee


def _budget_extract() -> FeeExtract:
    return FeeExtract(
        building_name="The Spectrum",
        fiscal_year=2024,
        operating_budget=[
            BudgetLineItem(label="Water & sewer", parent_category="Utilities",
                           annual_amount=200000, fiscal_year=2024),
            BudgetLineItem(label="Heat", parent_category="Utilities",
                           annual_amount=150000, fiscal_year=2024),
            BudgetLineItem(label="Insurance premium", parent_category="Insurance",
                           annual_amount=182000, fiscal_year=2024),
            BudgetLineItem(label="Transfer to CRF", parent_category="Reserve contribution",
                           annual_amount=139000, fiscal_year=2024),
        ],
    )


def test_returns_a_feebreakdown():
    assert isinstance(fee_breakdown(_budget_extract()), FeeBreakdown)


def test_rolls_line_items_into_parent_categories():
    fb = fee_breakdown(_budget_extract())
    util = next(c for c in fb.categories if c.category == "Utilities")
    assert util.building_annual == 350000
    assert {li.label for li in util.line_items} == {"Water & sewer", "Heat"}


def test_categories_sorted_descending_by_building_annual():
    fb = fee_breakdown(_budget_extract())
    annuals = [c.building_annual for c in fb.categories]
    assert annuals == sorted(annuals, reverse=True)
    assert fb.categories[0].category == "Utilities"  # 350k beats Insurance 182k


def test_reserve_pinned_separately_not_in_spend_list():
    fb = fee_breakdown(_budget_extract())
    assert fb.reserve is not None
    assert fb.reserve.category == RESERVE_CATEGORY
    assert fb.reserve.building_annual == 139000
    assert all(c.category != RESERVE_CATEGORY for c in fb.categories)


def test_building_meta_carries_name_and_fiscal_year_and_source_note():
    fb = fee_breakdown(_budget_extract())
    assert fb.building.name == "The Spectrum"
    assert fb.building.fiscal_year == 2024
    assert "FY2024" in fb.building.source_note


def test_building_totals_only_when_no_fee_schedule():
    fb = fee_breakdown(_budget_extract())
    assert all(c.personal_monthly is None for c in fb.categories)
    assert fb.unit.operating_fee_monthly is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m uv run pytest tests/test_fees_compute.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'yonder.fees.compute'`

- [ ] **Step 3: Write minimal implementation**

Create `src/yonder/fees/compute.py`:

```python
"""Pure mapping: FeeExtract -> FeeBreakdown (the JSON contract).

Deterministic reporting, not forecasting (unlike the reserve view's assemble):
roll the operating-budget line items into their parent categories, pin the Reserve
category on top, sort the spend categories by size, and (Task 4) size each to the
user's personal monthly share. With no operating budget the breakdown is
`degraded` (Task 5). No projection, no assumptions, never an invented number.
"""

from __future__ import annotations

from yonder.fees.model import (
    BuildingMeta,
    CategoryRow,
    FeeBreakdown,
    LineItem,
    RESERVE_CATEGORY,
    UnitMeta,
)
from yonder.fees.schema import FeeExtract


def _source_note(extract: FeeExtract) -> str:
    return f"AGM budget FY{extract.fiscal_year}" if extract.fiscal_year else "AGM operating budget"


def _rollup(extract: FeeExtract) -> dict[str, CategoryRow]:
    """Group budget line items by parent_category, summing amounts and collecting
    line items. Preserves first-seen order in the dict (irrelevant: spend is sorted)."""
    rows: dict[str, CategoryRow] = {}
    for li in extract.operating_budget:
        row = rows.get(li.parent_category)
        if row is None:
            row = CategoryRow(category=li.parent_category, building_annual=None, line_items=[])
            rows[li.parent_category] = row
        row.line_items.append(LineItem(label=li.label, annual_amount=li.annual_amount))
        if li.annual_amount is not None:
            row.building_annual = (row.building_annual or 0.0) + li.annual_amount
    return rows


def fee_breakdown(extract: FeeExtract, *, lot_id: str | None = None) -> FeeBreakdown:
    building = BuildingMeta(
        name=extract.building_name,
        fiscal_year=extract.fiscal_year,
        source_note=_source_note(extract),
    )
    rows = _rollup(extract)
    reserve_row = rows.pop(RESERVE_CATEGORY, None)
    spend = sorted(rows.values(), key=lambda r: r.building_annual or 0.0, reverse=True)

    return FeeBreakdown(
        building=building,
        unit=UnitMeta(),
        reserve=reserve_row,
        categories=spend,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m uv run pytest tests/test_fees_compute.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/yonder/fees/compute.py tests/test_fees_compute.py
git commit -m "feat(fees): roll budget into sorted categories with pinned reserve"
```

---

## Task 4: `fee_breakdown` — personal share from the fee schedule

**Files:**
- Modify: `src/yonder/fees/compute.py`
- Test: `tests/test_fees_compute.py` (append)

- [ ] **Step 1: Write the failing test (append to `tests/test_fees_compute.py`)**

```python
def _extract_with_schedule() -> FeeExtract:
    e = _budget_extract()
    e.fee_schedule = [
        LotFee(lot_id="1802", entitlement=82, operating_monthly=521, crf_monthly=78),
        LotFee(lot_id="0101", entitlement=70, operating_monthly=445, crf_monthly=66),
    ]
    return e


def test_unit_meta_and_total_fee_populated_from_lot():
    fb = fee_breakdown(_extract_with_schedule(), lot_id="1802")
    assert fb.unit.lot_id == "1802"
    assert fb.unit.entitlement == 82
    assert fb.unit.operating_fee_monthly == 521
    assert fb.unit.reserve_fee_monthly == 78
    assert fb.unit.total_fee_monthly == 599
    assert fb.building.unit_label == "#1802"


def test_spend_personals_sum_to_the_operating_fee():
    # personal = share * operating_fee, and the shares sum to 1.
    fb = fee_breakdown(_extract_with_schedule(), lot_id="1802")
    total = sum(c.personal_monthly for c in fb.categories)
    assert total == pytest.approx(521, abs=0.5)


def test_personal_share_proportional_to_building_annual():
    fb = fee_breakdown(_extract_with_schedule(), lot_id="1802")
    util = next(c for c in fb.categories if c.category == "Utilities")  # 350k
    spend_total = sum(c.building_annual for c in fb.categories)          # 350k + 182k = 532k
    assert util.personal_monthly == pytest.approx(350000 / spend_total * 521, abs=0.5)


def test_reserve_personal_uses_crf_not_a_share():
    fb = fee_breakdown(_extract_with_schedule(), lot_id="1802")
    assert fb.reserve.personal_monthly == 78  # the lot's CRF contribution, directly


def test_unknown_lot_falls_back_to_building_totals():
    fb = fee_breakdown(_extract_with_schedule(), lot_id="9999")
    assert fb.unit.operating_fee_monthly is None
    assert all(c.personal_monthly is None for c in fb.categories)
    assert fb.reserve.personal_monthly is None


def test_no_lot_id_given_falls_back_to_building_totals():
    fb = fee_breakdown(_extract_with_schedule())  # lot_id omitted
    assert fb.unit.operating_fee_monthly is None
    assert all(c.personal_monthly is None for c in fb.categories)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m uv run pytest tests/test_fees_compute.py -v`
Expected: FAIL — `test_unit_meta_and_total_fee_populated_from_lot` fails (unit fields are None; no `lot_id` handling yet)

- [ ] **Step 3: Write the implementation (replace the whole of `src/yonder/fees/compute.py`)**

```python
"""Pure mapping: FeeExtract -> FeeBreakdown (the JSON contract).

Deterministic reporting, not forecasting (unlike the reserve view's assemble):
roll the operating-budget line items into their parent categories, pin the Reserve
category on top, sort the spend categories by size, and size each to the user's
personal monthly share of the operating fee (Reserve uses the CRF contribution
directly). With no fee schedule (or the lot not found) the rows carry building
totals only. With no operating budget the breakdown is `degraded` (Task 5). No
projection, no assumptions, never an invented number.
"""

from __future__ import annotations

from yonder.fees.model import (
    BuildingMeta,
    CategoryRow,
    FeeBreakdown,
    LineItem,
    RESERVE_CATEGORY,
    UnitMeta,
)
from yonder.fees.schema import FeeExtract, LotFee


def _source_note(extract: FeeExtract) -> str:
    return f"AGM budget FY{extract.fiscal_year}" if extract.fiscal_year else "AGM operating budget"


def _sum_opt(a: float | None, b: float | None) -> float | None:
    if a is None and b is None:
        return None
    return (a or 0.0) + (b or 0.0)


def _rollup(extract: FeeExtract) -> dict[str, CategoryRow]:
    """Group budget line items by parent_category, summing amounts and collecting
    line items. Preserves first-seen order in the dict (irrelevant: spend is sorted)."""
    rows: dict[str, CategoryRow] = {}
    for li in extract.operating_budget:
        row = rows.get(li.parent_category)
        if row is None:
            row = CategoryRow(category=li.parent_category, building_annual=None, line_items=[])
            rows[li.parent_category] = row
        row.line_items.append(LineItem(label=li.label, annual_amount=li.annual_amount))
        if li.annual_amount is not None:
            row.building_annual = (row.building_annual or 0.0) + li.annual_amount
    return rows


def _find_lot(extract: FeeExtract, lot_id: str | None) -> LotFee | None:
    if lot_id is None:
        return None
    for lot in extract.fee_schedule:
        if lot.lot_id == lot_id:
            return lot
    return None


def fee_breakdown(extract: FeeExtract, *, lot_id: str | None = None) -> FeeBreakdown:
    building = BuildingMeta(
        name=extract.building_name,
        fiscal_year=extract.fiscal_year,
        source_note=_source_note(extract),
    )
    rows = _rollup(extract)
    reserve_row = rows.pop(RESERVE_CATEGORY, None)
    spend = sorted(rows.values(), key=lambda r: r.building_annual or 0.0, reverse=True)

    unit = UnitMeta()
    lot = _find_lot(extract, lot_id)
    if lot is not None:
        unit = UnitMeta(
            lot_id=lot.lot_id,
            entitlement=lot.entitlement,
            operating_fee_monthly=lot.operating_monthly,
            reserve_fee_monthly=lot.crf_monthly,
            total_fee_monthly=_sum_opt(lot.operating_monthly, lot.crf_monthly),
        )
        building.unit_label = f"#{lot.lot_id}"
        total_spend = sum(r.building_annual or 0.0 for r in spend)
        if lot.operating_monthly is not None and total_spend > 0:
            for r in spend:
                share = (r.building_annual or 0.0) / total_spend
                r.personal_monthly = round(share * lot.operating_monthly, 2)
        if lot.crf_monthly is not None:
            if reserve_row is None:
                reserve_row = CategoryRow(category=RESERVE_CATEGORY)
            reserve_row.personal_monthly = lot.crf_monthly

    return FeeBreakdown(
        building=building,
        unit=unit,
        reserve=reserve_row,
        categories=spend,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m uv run pytest tests/test_fees_compute.py -v`
Expected: PASS (12 passed)

- [ ] **Step 5: Commit**

```bash
git add src/yonder/fees/compute.py tests/test_fees_compute.py
git commit -m "feat(fees): size categories to the user's personal monthly share"
```

---

## Task 5: `fee_breakdown` — total-fee series + degraded path

**Files:**
- Modify: `src/yonder/fees/compute.py`
- Test: `tests/test_fees_compute.py` (append)

- [ ] **Step 1: Write the failing test (append to `tests/test_fees_compute.py`)**

```python
def test_total_fee_series_has_one_current_year_point_when_lot_known():
    fb = fee_breakdown(_extract_with_schedule(), lot_id="1802")
    assert len(fb.total_fee_series) == 1
    assert fb.total_fee_series[0].year == 2024
    assert fb.total_fee_series[0].monthly_fee == 599


def test_no_total_series_without_a_known_lot():
    fb = fee_breakdown(_budget_extract())
    assert fb.total_fee_series == []


def test_single_year_budget_is_not_hard_degraded():
    # v1 norm: one budget year renders bars; the trend layer simply has no data.
    fb = fee_breakdown(_budget_extract())
    assert fb.degraded is False
    assert fb.categories  # bars present
    assert all(c.prior_year_annual is None for c in fb.categories)  # no trend inputs in v1


def test_degrades_when_no_operating_budget():
    fb = fee_breakdown(FeeExtract(building_name="Empty", fiscal_year=2024))
    assert fb.degraded is True
    assert "no operating budget" in fb.degraded_reason
    assert fb.categories == []
    assert fb.reserve is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m uv run pytest tests/test_fees_compute.py -v`
Expected: FAIL — `test_total_fee_series_has_one_current_year_point_when_lot_known` fails (`total_fee_series` is `[]`)

- [ ] **Step 3: Write the implementation**

In `src/yonder/fees/compute.py`, update the imports to add `TotalFeePoint`:

```python
from yonder.fees.model import (
    BuildingMeta,
    CategoryRow,
    FeeBreakdown,
    LineItem,
    RESERVE_CATEGORY,
    TotalFeePoint,
    UnitMeta,
)
```

Then replace the final `return FeeBreakdown(...)` block of `fee_breakdown` with:

```python
    total_fee_series: list[TotalFeePoint] = []
    if unit.total_fee_monthly is not None and extract.fiscal_year is not None:
        total_fee_series = [
            TotalFeePoint(year=extract.fiscal_year, monthly_fee=unit.total_fee_monthly)
        ]

    fb = FeeBreakdown(
        building=building,
        unit=unit,
        reserve=reserve_row,
        categories=spend,
        total_fee_series=total_fee_series,
    )
    # Hard degrade only: nothing to draw. A single budget year is the v1 norm
    # (degraded stays False); the trend layer is absent by data, not by flag.
    if not spend and reserve_row is None:
        fb.degraded = True
        fb.degraded_reason = "no operating budget line items found"
    return fb
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m uv run pytest tests/test_fees_compute.py -v`
Expected: PASS (16 passed)

- [ ] **Step 5: Commit**

```bash
git add src/yonder/fees/compute.py tests/test_fees_compute.py
git commit -m "feat(fees): emit total-fee point and degrade when no budget"
```

---

## Task 6: Synthetic sample + committed fixture + fixture-contract guard

**Files:**
- Create: `src/yonder/fees/sample.py`
- Test: `tests/test_fees_sample.py`
- Test: `tests/test_fees_fixture_contract.py`
- Create (generated): `fixtures/samples/fee_breakdown.sample.json`

- [ ] **Step 1: Write the failing test**

Create `tests/test_fees_sample.py`:

```python
import json

from yonder.fees.model import FeeBreakdown, RESERVE_CATEGORY
from yonder.fees.sample import wexford_fee_sample


def test_sample_validates_and_has_expected_shape():
    fb = wexford_fee_sample()
    assert isinstance(fb, FeeBreakdown)
    assert fb.degraded is False
    assert fb.reserve is not None and fb.reserve.category == RESERVE_CATEGORY
    assert fb.unit.lot_id == "1802"
    assert len(fb.categories) == 6
    assert fb.categories[0].category == "Utilities"  # largest


def test_sample_categories_are_sorted_descending():
    annuals = [c.building_annual for c in wexford_fee_sample().categories]
    assert annuals == sorted(annuals, reverse=True)


def test_sample_spend_personals_sum_to_operating_fee():
    fb = wexford_fee_sample()
    total = sum(c.personal_monthly for c in fb.categories)
    assert abs(total - fb.unit.operating_fee_monthly) <= 1  # within rounding


def test_sample_has_a_multi_line_expandable_category():
    fb = wexford_fee_sample()
    assert any(len(c.line_items) > 1 for c in fb.categories)


def test_sample_round_trips_through_plain_json():
    fb = wexford_fee_sample()
    assert FeeBreakdown.model_validate(json.loads(fb.model_dump_json())) == fb
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m uv run pytest tests/test_fees_sample.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'yonder.fees.sample'`

- [ ] **Step 3: Write minimal implementation**

Create `src/yonder/fees/sample.py`:

```python
"""A synthetic-but-realistic FeeBreakdown ("The Wexford") — the committed sample
that drives the mock and tests. Mirrors the locked mockup's numbers so the
data-driven render is verifiably identical. NOT real building data.

Single budget year (v1): no prior_year amounts, a one-point total_fee_series, so
the mock shows bars without the trend layer.
"""

from __future__ import annotations

from yonder.fees.model import (
    BuildingMeta,
    CategoryRow,
    FeeBreakdown,
    LineItem,
    RESERVE_CATEGORY,
    TotalFeePoint,
    UnitMeta,
)


def wexford_fee_sample() -> FeeBreakdown:
    return FeeBreakdown(
        building=BuildingMeta(
            name="The Wexford", unit_label="#1802", fiscal_year=2024,
            source_note="AGM budget FY2024 · synthetic",
        ),
        unit=UnitMeta(
            lot_id="1802", entitlement=82,
            operating_fee_monthly=521, reserve_fee_monthly=78, total_fee_monthly=599,
        ),
        reserve=CategoryRow(category=RESERVE_CATEGORY, building_annual=139000, personal_monthly=78),
        categories=[
            CategoryRow(category="Utilities", building_annual=350000, personal_monthly=196,
                        line_items=[
                            LineItem(label="Water & sewer", annual_amount=150000),
                            LineItem(label="Heat", annual_amount=90000),
                            LineItem(label="Electricity", annual_amount=60000),
                            LineItem(label="Gas", annual_amount=30000),
                            LineItem(label="Garbage", annual_amount=20000),
                        ]),
            CategoryRow(category="Repairs & maintenance", building_annual=211000, personal_monthly=118,
                        line_items=[
                            LineItem(label="General repairs", annual_amount=130000),
                            LineItem(label="Landscaping", annual_amount=81000),
                        ]),
            CategoryRow(category="Insurance", building_annual=182000, personal_monthly=102,
                        line_items=[LineItem(label="Insurance premium", annual_amount=182000)]),
            CategoryRow(category="Security & life-safety", building_annual=119000, personal_monthly=67,
                        line_items=[
                            LineItem(label="Concierge", annual_amount=80000),
                            LineItem(label="Fire monitoring", annual_amount=39000),
                        ]),
            CategoryRow(category="Building services", building_annual=43000, personal_monthly=24,
                        line_items=[LineItem(label="Elevator maintenance", annual_amount=43000)]),
            CategoryRow(category="Administration", building_annual=25000, personal_monthly=14,
                        line_items=[LineItem(label="Management fees", annual_amount=25000)]),
        ],
        total_fee_series=[TotalFeePoint(year=2024, monthly_fee=599)],
    )
```

- [ ] **Step 4: Run sample test to verify it passes**

Run: `python -m uv run pytest tests/test_fees_sample.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Generate the committed fixture**

Run:

```bash
python -m uv run python -c "from pathlib import Path; from yonder.fees.sample import wexford_fee_sample; Path('fixtures/samples/fee_breakdown.sample.json').write_text(wexford_fee_sample().model_dump_json(indent=2) + '\n', encoding='utf-8'); print('wrote fixture')"
```

Expected: prints `wrote fixture`; `fixtures/samples/fee_breakdown.sample.json` now exists.

- [ ] **Step 6: Write the fixture-contract test**

Create `tests/test_fees_fixture_contract.py`:

```python
"""Guards the JSON<->mock seam: the committed fixture must carry every field the
mock (docs/mockups/fee-breakdown.html) derives its render from."""

import json
from pathlib import Path

FIXTURE = Path("fixtures/samples/fee_breakdown.sample.json")


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_fixture_exists_and_parses():
    assert FIXTURE.exists(), "run: yonder fees-sample"
    _load()


def test_building_and_unit_meta_present():
    fb = _load()
    assert fb["building"]["name"]
    assert fb["building"]["unit_label"]
    u = fb["unit"]
    assert u["operating_fee_monthly"] and u["reserve_fee_monthly"] and u["total_fee_monthly"]


def test_reserve_row_present_with_building_and_personal():
    r = _load()["reserve"]
    assert r is not None
    assert r["category"] == "Reserve contribution"
    assert r["building_annual"] is not None and r["personal_monthly"] is not None


def test_categories_sorted_with_building_personal_and_line_items():
    cats = _load()["categories"]
    assert cats
    annuals = [c["building_annual"] for c in cats]
    assert annuals == sorted(annuals, reverse=True)
    for c in cats:
        assert c["building_annual"] is not None
        assert c["personal_monthly"] is not None
        assert "line_items" in c
    assert any(len(c["line_items"]) > 1 for c in cats), "need an expandable category for the tap demo"


def test_total_fee_series_has_a_point():
    series = _load()["total_fee_series"]
    assert series and series[-1]["monthly_fee"] is not None
```

- [ ] **Step 7: Run all fees tests to verify they pass**

Run: `python -m uv run pytest tests/test_fees_sample.py tests/test_fees_fixture_contract.py -v`
Expected: PASS (10 passed)

- [ ] **Step 8: Commit**

```bash
git add src/yonder/fees/sample.py tests/test_fees_sample.py tests/test_fees_fixture_contract.py fixtures/samples/fee_breakdown.sample.json
git commit -m "feat(fees): add synthetic FeeBreakdown sample + committed fixture"
```

---

## Task 7: The extraction intelligence call (`FeeExtract` from PDF/text)

**Files:**
- Create: `src/yonder/fees/extract.py`
- Test: `tests/test_fees_extract.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_fees_extract.py`:

```python
import pytest
from pydantic import ValidationError

from yonder.fees.extract import (
    TOOL_NAME,
    extract_fees,
    extract_fees_from_text,
    fees_tool,
)


class FakeClient:
    """Returns canned tool-input dicts in order; records each call's kwargs."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def extract_with_tool(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def test_fees_tool_shape():
    t = fees_tool()
    assert t["name"] == TOOL_NAME == "record_fee_facts"
    assert "input_schema" in t and t["input_schema"]["type"] == "object"


def test_extract_fees_returns_validated():
    fc = FakeClient([{
        "building_name": "X",
        "fiscal_year": 2024,
        "operating_budget": [
            {"label": "Insurance", "parent_category": "Insurance", "annual_amount": 182000},
        ],
        "fee_schedule": [{"lot_id": "1802", "operating_monthly": 521, "crf_monthly": 78}],
    }])
    res = extract_fees(b"%PDF fake", client=fc)
    assert res.building_name == "X"
    assert res.operating_budget[0].parent_category == "Insurance"
    assert res.fee_schedule[0].lot_id == "1802"
    assert len(fc.calls) == 1


def test_extract_fees_repairs_once_then_succeeds():
    bad = {"operating_budget": [{"annual_amount": 1}]}  # missing label + parent_category
    good = {"building_name": "Y", "operating_budget": []}
    fc = FakeClient([bad, good])
    res = extract_fees(b"%PDF fake", client=fc)
    assert res.building_name == "Y"
    assert len(fc.calls) == 2
    assert fc.calls[0]["extra_note"] is None
    assert fc.calls[1]["extra_note"]


def test_extract_fees_raises_if_both_attempts_invalid():
    bad = {"operating_budget": [{"annual_amount": 1}]}
    fc = FakeClient([bad, bad])
    with pytest.raises(ValidationError):
        extract_fees(b"%PDF fake", client=fc)


def test_extract_fees_from_text_passes_text_not_pdf():
    fc = FakeClient([{"building_name": "Z", "operating_budget": []}])
    res = extract_fees_from_text("some parsed budget text", client=fc)
    assert res.building_name == "Z"
    assert fc.calls[0]["text"] == "some parsed budget text"
    assert "pdf_bytes" not in fc.calls[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m uv run pytest tests/test_fees_extract.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'yonder.fees.extract'`

- [ ] **Step 3: Write minimal implementation**

Create `src/yonder/fees/extract.py`:

```python
"""The ONE intelligence call: an AGM-package PDF -> FeeExtract.

Mirrors outlook/extract.py: build a forced tool from the Pydantic schema, send the
PDF (or already-parsed text) through the client.py Claude seam, and validate ->
repair-retry-once -> fail loudly. Only the system prompt is fee-specific.
"""

from __future__ import annotations

from pydantic import ValidationError

from yonder.fees.schema import FeeExtract

TOOL_NAME = "record_fee_facts"

SYSTEM_PROMPT = """You read a British Columbia strata AGM package and extract the \
two facts needed to break down a unit's strata fee. Rules:

- Extract ONLY what the documents state. If a fact is not present, leave it null. \
Never invent or infer a number that is not written.
- `operating_budget` is the APPROVED ANNUAL OPERATING BUDGET: one entry per line \
item, with its account `label`, its budgeted `annual_amount`, and the `fiscal_year` \
the budget is for. For EACH line item also assign a `parent_category` — a short \
rollup bucket. Prefer this vocabulary: "Utilities", "Repairs & maintenance", \
"Insurance", "Security & life-safety", "Building services", "Administration". The \
annual contribution to the contingency reserve fund (a "transfer to CRF" / \
"reserve contribution" line) MUST use the exact parent_category "Reserve \
contribution". If a line fits none of these, use "Other" — never force-fit and \
never drop it.
- `fee_schedule` is the PER-LOT STRATA-FEE SCHEDULE: one entry per strata lot, \
with its `lot_id`, its unit `entitlement`, and its monthly fee split into the \
`operating_monthly` (operating fund) and `crf_monthly` (contingency reserve fund) \
contributions.
- `fiscal_year` (top level) is the budget's fiscal year.

Call the record_fee_facts tool with everything you found."""


def fees_tool() -> dict:
    return {
        "name": TOOL_NAME,
        "description": "Record the operating budget and per-lot fee schedule from the AGM package.",
        "input_schema": FeeExtract.model_json_schema(),
    }


def _run(client, **source) -> FeeExtract:
    """Shared validate -> repair-retry-once -> fail loop. `source` is exactly one
    of pdf_bytes=... or text=..., forwarded to client.extract_with_tool."""
    tool = fees_tool()
    extra_note: str | None = None
    last_error: ValidationError | None = None

    for _ in range(2):
        raw = client.extract_with_tool(
            system=SYSTEM_PROMPT,
            tool=tool,
            tool_name=TOOL_NAME,
            extra_note=extra_note,
            **source,
        )
        try:
            return FeeExtract.model_validate(raw)
        except ValidationError as exc:
            last_error = exc
            extra_note = (
                "Your previous tool call failed schema validation with these errors:\n"
                f"{exc}\n"
                "Return the record_fee_facts tool call again, corrected. Use null for "
                "anything the documents do not state; every budget line needs a label and "
                "a parent_category, and every lot needs a lot_id."
            )

    assert last_error is not None
    raise last_error


def extract_fees(pdf_bytes: bytes, *, client) -> FeeExtract:
    """Extract a FeeExtract from an AGM-package PDF (text + page images)."""
    return _run(client, pdf_bytes=pdf_bytes)


def extract_fees_from_text(text: str, *, client) -> FeeExtract:
    """Extract a FeeExtract from already-parsed text (cheaper: no page images)."""
    return _run(client, text=text)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m uv run pytest tests/test_fees_extract.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/yonder/fees/extract.py tests/test_fees_extract.py
git commit -m "feat(fees): add the FeeExtract intelligence call"
```

---

## Task 8: Extend the synthetic PDF + live extraction test

This gives the live extraction test committed synthetic data so it never needs a real (gitignored) doc. The live test skips without `ANTHROPIC_API_KEY`, mirroring `tests/test_extract.py`.

**Files:**
- Modify: `fixtures/samples/generate_sample.py`
- Regenerate: `fixtures/samples/sample-strata-package.pdf`
- Test: `tests/test_fees_extract_live.py`

- [ ] **Step 1: Add a budget + fee-schedule page to the generator**

In `fixtures/samples/generate_sample.py`, append two new page lists to the `PAGES` list (insert before the closing `]` of `PAGES`, after the SGM page):

```python
    [
        "ANNUAL OPERATING BUDGET - FISCAL YEAR 2024",
        "(SYNTHETIC - NOT A REAL BUILDING)",
        "",
        "Water & Sewer .................. $150,000   (Utilities)",
        "Heat / Natural Gas ............. $120,000   (Utilities)",
        "Electricity .................... $ 60,000   (Utilities)",
        "Building Insurance ............. $182,000   (Insurance)",
        "General Repairs & Maintenance .. $130,000   (Repairs & maintenance)",
        "Concierge / Security ........... $ 80,000   (Security & life-safety)",
        "Management Fees ................ $ 25,000   (Administration)",
        "Transfer to Contingency Reserve  $139,000   (Reserve contribution)",
    ],
    [
        "SCHEDULE OF MONTHLY STRATA FEES BY LOT - 2024",
        "(SYNTHETIC - NOT A REAL BUILDING)",
        "",
        "Lot   Entitlement   Operating/mo   CRF/mo",
        "0101      70           $445          $66",
        "0304      82           $521          $78",
        "1802      82           $521          $78",
    ],
```

- [ ] **Step 2: Regenerate the committed PDF**

Run: `python -m uv run python fixtures/samples/generate_sample.py`
Expected: prints `Wrote .../sample-strata-package.pdf`

- [ ] **Step 3: Verify the existing reserve/strata live tests still describe the same doc**

Run: `python -m uv run pytest tests/test_extract.py -v`
Expected: SKIPPED (no `ANTHROPIC_API_KEY`) — confirms the file still imports and the skip marker fires. (If a key IS set, it should still PASS: the new pages don't remove the entitlement 18/2719, the special levies, or the documents the existing assertions check.)

- [ ] **Step 4: Write the live extraction test**

Create `tests/test_fees_extract_live.py`:

```python
import os
from pathlib import Path

import pytest

from yonder.extract.client import ClaudeClient
from yonder.fees.extract import extract_fees
from yonder.fees.schema import FeeExtract

SAMPLE = Path("fixtures/samples/sample-strata-package.pdf")

pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="needs ANTHROPIC_API_KEY (live extraction)",
)


def test_sample_fees_extract_has_budget_and_schedule():
    e = extract_fees(SAMPLE.read_bytes(), client=ClaudeClient())
    assert isinstance(e, FeeExtract)
    # The synthetic budget page clearly contains these.
    assert len(e.operating_budget) >= 5
    assert all(li.parent_category for li in e.operating_budget)
    assert any(li.parent_category == "Reserve contribution" for li in e.operating_budget)
    # The synthetic fee schedule lists lot 1802.
    assert any(lot.lot_id == "1802" for lot in e.fee_schedule)
```

- [ ] **Step 5: Run the live test (skips without a key)**

Run: `python -m uv run pytest tests/test_fees_extract_live.py -v`
Expected: SKIPPED (1 skipped) when no key is set.

- [ ] **Step 6: Commit**

```bash
git add fixtures/samples/generate_sample.py fixtures/samples/sample-strata-package.pdf tests/test_fees_extract_live.py
git commit -m "feat(fees): extend synthetic PDF with budget + fee schedule; live test"
```

---

## Task 9: CLI wiring (`fees` and `fees-sample`)

**Files:**
- Modify: `src/yonder/cli.py`
- Test: `tests/test_fees_cli.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_fees_cli.py`:

```python
import json
from pathlib import Path

from yonder import cli
from yonder.fees.model import FeeBreakdown
from yonder.fees.sample import wexford_fee_sample
from yonder.fees.schema import BudgetLineItem, FeeExtract, LotFee


def _canned_extract() -> FeeExtract:
    return FeeExtract(
        building_name="Test Tower",
        fiscal_year=2024,
        operating_budget=[
            BudgetLineItem(label="Insurance", parent_category="Insurance", annual_amount=182000),
            BudgetLineItem(label="Transfer to CRF", parent_category="Reserve contribution",
                           annual_amount=139000),
        ],
        fee_schedule=[LotFee(lot_id="1802", operating_monthly=521, crf_monthly=78)],
    )


def test_fees_cli_writes_feebreakdown(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "extract_fees", lambda pdf_bytes, *, client: _canned_extract())
    monkeypatch.setattr(cli, "_build_client", lambda: object())

    pdf = tmp_path / "agm.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    out = tmp_path / "fb.json"

    rc = cli.main(["fees", str(pdf), "--lot", "1802", str(out)])
    assert rc == 0

    fb = FeeBreakdown.model_validate_json(out.read_text(encoding="utf-8"))
    assert fb.building.name == "Test Tower"
    assert fb.unit.lot_id == "1802"
    assert fb.reserve.personal_monthly == 78


def test_fees_cli_default_out_path_next_to_pdf(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "extract_fees", lambda pdf_bytes, *, client: _canned_extract())
    monkeypatch.setattr(cli, "_build_client", lambda: object())

    pdf = tmp_path / "MyAgm.pdf"
    pdf.write_bytes(b"%PDF fake")
    rc = cli.main(["fees", str(pdf)])
    assert rc == 0
    assert (tmp_path / "MyAgm.fee_breakdown.json").exists()


def test_fees_cli_txt_source_uses_text_extractor(tmp_path, monkeypatch):
    seen = {}

    def fake_from_text(text, *, client):
        seen["text"] = text
        return _canned_extract()

    monkeypatch.setattr(cli, "extract_fees_from_text", fake_from_text)
    monkeypatch.setattr(cli, "extract_fees", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("PDF extractor must not be called for a .txt source")))
    monkeypatch.setattr(cli, "_build_client", lambda: object())

    txt = tmp_path / "budget.txt"
    txt.write_text("INSURANCE 182000; CRF 139000", encoding="utf-8")
    out = tmp_path / "o.json"

    rc = cli.main(["fees", str(txt), "--lot", "1802", str(out)])
    assert rc == 0
    assert seen["text"].startswith("INSURANCE")


def test_fees_sample_cli_writes_valid_json(tmp_path):
    out = tmp_path / "sample.json"
    rc = cli.main(["fees-sample", str(out)])
    assert rc == 0
    loaded = FeeBreakdown.model_validate_json(out.read_text(encoding="utf-8"))
    assert loaded == wexford_fee_sample()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m uv run pytest tests/test_fees_cli.py -v`
Expected: FAIL — `argument command: invalid choice: 'fees'` (the subcommands don't exist yet)

- [ ] **Step 3: Write the implementation**

In `src/yonder/cli.py`, add to the imports near the top (after the existing `from yonder.outlook...` imports):

```python
from yonder.fees.compute import fee_breakdown
from yonder.fees.extract import extract_fees, extract_fees_from_text
from yonder.fees.sample import wexford_fee_sample
```

Add these two command functions after `cmd_outlook_sample`:

```python
def cmd_fees(args: argparse.Namespace) -> int:
    src = Path(args.pdf)
    out = Path(args.out) if args.out else src.parent / f"{src.stem}.fee_breakdown.json"
    client = _build_client()
    if src.suffix.lower() == ".txt":
        extract = extract_fees_from_text(
            src.read_text(encoding="utf-8", errors="replace"), client=client
        )
    else:
        extract = extract_fees(src.read_bytes(), client=client)
    breakdown = fee_breakdown(extract, lot_id=args.lot)
    out.write_text(breakdown.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


def cmd_fees_sample(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(wexford_fee_sample().model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0
```

In `main`, register the two subparsers (after the `p_outlook` block, before `args = parser.parse_args(argv)`):

```python
    p_fees = sub.add_parser(
        "fees",
        help="Extract an AGM package (.pdf or already-parsed .txt) into a FeeBreakdown JSON.",
    )
    p_fees.add_argument("pdf", help="path to the AGM package .pdf, or a .txt of its parsed text")
    p_fees.add_argument("--lot", default=None, help="the user's strata-lot id, for personal sizing")
    p_fees.add_argument("out", nargs="?", default=None)
    p_fees.set_defaults(func=cmd_fees)

    p_fees_sample = sub.add_parser(
        "fees-sample", help="Write the synthetic FeeBreakdown sample JSON."
    )
    p_fees_sample.add_argument(
        "out", nargs="?", default="fixtures/samples/fee_breakdown.sample.json"
    )
    p_fees_sample.set_defaults(func=cmd_fees_sample)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m uv run pytest tests/test_fees_cli.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Verify `fees-sample` reproduces the committed fixture byte-for-byte**

Run: `python -m uv run yonder fees-sample fixtures/samples/fee_breakdown.sample.json`
Then: `git diff --stat fixtures/samples/fee_breakdown.sample.json`
Expected: prints `wrote fixtures/...`; `git diff` shows **no change** (the Task 6 fixture already matches the CLI output).

- [ ] **Step 6: Commit**

```bash
git add src/yonder/cli.py tests/test_fees_cli.py
git commit -m "feat(fees): add fees and fees-sample CLI subcommands"
```

---

## Task 10: The data-driven HTML mock

**Files:**
- Create: `docs/mockups/fee-breakdown.html`

This mirrors `docs/mockups/reserve-trajectory.html`: load JSON from a `?data=` URL param (default = the committed fixture), render client-side, fail with a serve-over-http hint. The Reserve row taps through to `reserve-trajectory.html`. The trend layer (caps/diffs/sparklines/total-trend) renders **only** when its inputs are present — absent in v1, so v1 shows bars only.

- [ ] **Step 1: Create the mock**

Create `docs/mockups/fee-breakdown.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fee Breakdown v1 — sorted bars, reserve pinned</title>
<style>
  body{margin:0;background:#e2e8f0;color:#0f172a;font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;padding:24px 12px;display:flex;flex-direction:column;align-items:center}
  .cap{color:#475569;font-size:.85rem;margin:0 0 14px;max-width:430px;text-align:center;line-height:1.4}
  .phone{width:390px;max-width:100%;background:#0f172a;border-radius:34px;padding:14px 14px 22px;box-shadow:0 14px 44px rgba(0,0,0,.4);color:#e2e8f0;border:6px solid #1e293b}
  .notch{height:16px;display:flex;justify-content:center;align-items:center;margin-bottom:4px}
  .notch div{width:90px;height:5px;border-radius:3px;background:#334155}
  .head{display:flex;justify-content:space-between;align-items:baseline;margin:2px 4px 8px}
  .bname{font-weight:600;font-size:1rem}
  .stale{font-size:.66rem;color:#94a3b8;text-align:right;max-width:140px}
  svg a{cursor:pointer}
</style>
</head>
<body>
  <p class="cap">v1 single-year breakdown: spend categories sorted by size, each bar scaled to <b>your</b> monthly share; the building annual sits inside the bar. <b>Reserve</b> is pinned on top and taps through to the Reserve Trajectory view. Tap a multi-line category to expand its line items.</p>
  <div class="phone">
    <div class="notch"><div></div></div>
    <div class="head">
      <div class="bname">&mdash;</div>
      <div class="stale"></div>
    </div>
    <svg id="chart" viewBox="0 0 340 400" style="width:100%;height:auto;display:block"></svg>
  </div>
  <p class="cap" style="margin-top:14px">Trend ornaments (delta caps, +/- diffs, sparklines, total-fee trend) appear only with multi-year data &mdash; deferred to v1.1.</p>

<script>
(function(){
  var NS='http://www.w3.org/2000/svg', D=String.fromCharCode(36);
  // distinct bar colours, cycled by sort order
  var COLORS=['#3b82f6','#f97316','#ef4444','#eab308','#14b8a6','#a855f7','#0ea5e9','#ec4899'];

  function money(v){
    if(v==null) return '';
    var a=Math.abs(v);
    if(a>=1e6) return D+(v/1e6).toFixed(1)+'M';
    if(a>=1000) return D+Math.round(v/1000)+'k';
    return D+Math.round(v);
  }
  function el(tag,at,txt){var e=document.createElementNS(NS,tag);for(var k in at)e.setAttribute(k,at[k]);if(txt!=null)e.textContent=txt;return e;}

  var DATA=null, expanded={};
  function toggle(i){ expanded[i]=!expanded[i]; render(DATA); }

  function render(fb){
    var b=fb.building||{}, u=fb.unit||{}, svg=document.getElementById('chart');
    document.querySelector('.bname').textContent=(b.name||'—')+(b.unit_label?(' · '+b.unit_label):'');
    document.querySelector('.stale').textContent=b.source_note||'';
    svg.innerHTML='';

    var W=340, BARMAX=247, y=6;

    // hard-degrade: no bars to draw
    if(fb.degraded && (!fb.categories||!fb.categories.length) && !fb.reserve){
      svg.setAttribute('viewBox','0 0 340 90');
      svg.appendChild(el('text',{x:W/2,y:50,'text-anchor':'middle','font-size':11,fill:'#f59e0b'},
        '⚠ '+(fb.degraded_reason||'breakdown unavailable')));
      return;
    }

    // ---- total-fee header ----
    var series=fb.total_fee_series||[], latest=series.length?series[series.length-1]:null;
    var headNum = latest?latest.monthly_fee:(u.total_fee_monthly!=null?u.total_fee_monthly:null);
    svg.appendChild(el('rect',{x:6,y:y,width:328,height:54,rx:6,fill:'#11161f'}));
    svg.appendChild(el('text',{x:16,y:y+18,'font-size':9,'font-weight':600,fill:'#9aa0a6'},'TOTAL FEE / MONTH'));
    svg.appendChild(el('text',{x:16,y:y+41,'font-size':20,'font-weight':700,fill:'#fff'}, headNum!=null?money(headNum):'—'));
    if(series.length>=2){  // v1.1 trend layer: only with multiple years
      var first=series[0], delta=latest.monthly_fee-first.monthly_fee, span=latest.year-first.year;
      svg.appendChild(el('text',{x:88,y:y+41,'font-size':8.5,'font-weight':600,fill:'#8b93a0'},
        (delta>=0?'↗ +':'↘ -')+D+Math.abs(Math.round(delta))+'/mo over '+span+' yrs'));
      var lo=Math.min.apply(null,series.map(function(p){return p.monthly_fee;}));
      var hi=Math.max.apply(null,series.map(function(p){return p.monthly_fee;}));
      var rng=(hi-lo)||1;
      var pts=series.map(function(p,i){
        var px=210+i*(120/(series.length-1));
        var py=(y+48)-((p.monthly_fee-lo)/rng)*22;
        return px+','+py;
      });
      svg.appendChild(el('polyline',{points:pts.join(' '),fill:'none',stroke:'#fff','stroke-width':1.5}));
    }
    y+=62;

    // largest building_annual sets the bar scale (reserve included, for one shared scale)
    var maxAnnual=0;
    function consider(c){ if(c && (c.building_annual||0)>maxAnnual) maxAnnual=c.building_annual||0; }
    (fb.categories||[]).forEach(consider); consider(fb.reserve);
    function barW(c){ return maxAnnual ? Math.max(16,(c.building_annual||0)/maxAnnual*BARMAX) : 80; }

    // in-bar total if wide enough, else grey total just after the bar
    function drawTotal(g,c,w,barY){
      if(c.building_annual==null) return;
      if(w>=44) g.appendChild(el('text',{x:14,y:barY+10,'font-size':8.5,'font-weight':700,fill:'#fff'},money(c.building_annual)));
      else g.appendChild(el('text',{x:w+14,y:barY+10,'font-size':8.5,'font-weight':600,fill:'#7c8493'},money(c.building_annual)));
    }

    // ---- pinned reserve ----
    if(fb.reserve){
      var r=fb.reserve, rw=barW(r);
      svg.appendChild(el('rect',{x:6,y:y,width:328,height:40,rx:6,fill:'#0e1a17',stroke:'#15463c'}));
      svg.appendChild(el('text',{x:10,y:y+16,'font-size':10.5,'font-weight':600,fill:'#5eead4'},'Reserve contribution'));
      if(r.personal_monthly!=null)
        svg.appendChild(el('text',{x:332,y:y+16,'font-size':11,'font-weight':700,fill:'#fff','text-anchor':'end'},money(r.personal_monthly)+'/mo'));
      svg.appendChild(el('rect',{x:10,y:y+22,width:rw,height:13,rx:2,fill:'#22c55e'}));
      if(r.building_annual!=null)
        svg.appendChild(el('text',{x:16,y:y+32,'font-size':8.5,'font-weight':700,fill:'#fff'},money(r.building_annual)));
      var link=el('a',{href:'reserve-trajectory.html'});
      link.appendChild(el('text',{x:Math.min(rw+22,236),y:y+32,'font-size':8,'font-weight':600,fill:'#5eead4'},'tap → reserve trajectory ↗'));
      svg.appendChild(link);
      y+=48;
    }

    // section divider
    svg.appendChild(el('line',{x1:6,y1:y,x2:334,y2:y,stroke:'#1f2937'}));
    svg.appendChild(el('text',{x:8,y:y-4,'font-size':7.5,'font-weight':600,fill:'#5b6573'},'SAVED ↑'));
    svg.appendChild(el('text',{x:8,y:y+14,'font-size':7.5,'font-weight':600,fill:'#5b6573'},'SPENT ↓'));
    y+=22;

    // ---- spend rows (sorted desc by the contract) ----
    (fb.categories||[]).forEach(function(c,i){
      var color=COLORS[i%COLORS.length], w=barW(c), labelY=y+16, barY=y+22;
      svg.appendChild(el('text',{x:10,y:labelY,'font-size':10.5,'font-weight':600,fill:'#e8eaed'},c.category));
      if(c.personal_monthly!=null)
        svg.appendChild(el('text',{x:332,y:labelY,'font-size':11,'font-weight':700,fill:'#fff','text-anchor':'end'},money(c.personal_monthly)+'/mo'));
      // v1.1: a grey personal-dollar diff would render at x~284 when prior_year_annual is set.

      var multi=(c.line_items&&c.line_items.length>1);
      var g=el('g', multi?{style:'cursor:pointer'}:{});
      g.appendChild(el('rect',{x:10,y:barY,width:w,height:14,rx:2,fill:color}));
      drawTotal(g,c,w,barY);
      if(multi){
        g.appendChild(el('text',{x:332,y:barY+11,'font-size':8,fill:'#7c8493','text-anchor':'end'},expanded[i]?'▲':'▼'));
        (function(idx){ g.addEventListener('click',function(){ toggle(idx); }); })(i);
      }
      svg.appendChild(g);
      y+=38;

      if(multi && expanded[i]){
        c.line_items.forEach(function(it){
          svg.appendChild(el('text',{x:20,y:y,'font-size':8.5,fill:'#8b93a0'},
            '• '+it.label+(it.annual_amount!=null?('   '+money(it.annual_amount)):'')));
          y+=13;
        });
        y+=4;
      }
    });

    svg.setAttribute('viewBox','0 0 340 '+(y+8));
  }

  function fail(msg){
    var svg=document.getElementById('chart'); svg.innerHTML='';
    svg.appendChild(el('text',{x:8,y:24,'font-size':9,fill:'#f59e0b'},msg));
  }
  var _params=new URLSearchParams(location.search);
  var _dataUrl=_params.get('data')||'../../fixtures/samples/fee_breakdown.sample.json';
  fetch(_dataUrl)
    .then(function(r){ if(!r.ok) throw new Error('HTTP '+r.status); return r.json(); })
    .then(function(fb){ DATA=fb; render(fb); })
    .catch(function(e){ fail('Could not load '+_dataUrl+'. Serve the repo root over http (python -m http.server) and open http://localhost:8000/docs/mockups/fee-breakdown.html  ['+e.message+']'); });
})();
</script>
</body>
</html>
```

- [ ] **Step 2: Verify the mock renders the committed fixture**

The mock uses `fetch`, so it must be served over http (file:// fails CORS). On Windows, launch the server in the background and foreground-friendly (see global Windows guidance):

Run (background): `python -m http.server 8000`
Then open: `http://localhost:8000/docs/mockups/fee-breakdown.html`

Expected (visual): building header "The Wexford · #1802"; a TOTAL FEE / MONTH card showing `$599` with **no** sparkline/trend caption; a green pinned "Reserve contribution" row reading `$78/mo`, `$139k`, and a "tap → reserve trajectory ↗" link; six spend bars sorted Utilities ($196/mo, $350k) → … → Administration ($14/mo, $25k); tapping "Utilities" expands its five line items. Clicking the reserve link navigates to the reserve-trajectory mock.

Stop the server when done.

- [ ] **Step 3: Commit**

```bash
git add docs/mockups/fee-breakdown.html
git commit -m "feat(fees): data-driven Fee Breakdown mock (sorted bars, pinned reserve)"
```

---

## Task 11: Document the new dev commands

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add the two commands under "Dev commands"**

In `CLAUDE.md`, in the `## Dev commands` list, add these two bullets after the `uv run yonder eval ...` line:

```markdown
- `uv run yonder fees <agm.pdf> --lot <lot-id>` — break one AGM package into a `FeeBreakdown` (needs `ANTHROPIC_API_KEY`)
- `uv run yonder fees-sample` — write the synthetic `FeeBreakdown` fixture
```

- [ ] **Step 2: Run the full suite to confirm nothing regressed**

Run: `python -m uv run pytest -q`
Expected: PASS — all prior tests plus the new fees tests pass; the two live tests (`test_extract.py`, `test_fees_extract_live.py`) show as SKIPPED without a key.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document yonder fees and fees-sample commands"
```

---

## Self-review (coverage against the spec)

- **Sorted per-category bars sized to personal share** → Tasks 3–4 (`fee_breakdown` rollup, sort, personal share), rendered in Task 10.
- **Reserve pinned on top, boxed, tap-through** → `FeeBreakdown.reserve` (Task 2), CRF-direct personal sizing (Task 4), green boxed row + `reserve-trajectory.html` link (Task 10).
- **Building annual printed inside the bar; total after the bar when narrow** → Task 10 `drawTotal`.
- **Tap a bar → line items; single-line categories don't expand** → `line_items` (Task 2), multi-item gate in Task 10.
- **Personal share from the per-lot fee schedule; Reserve uses CRF directly** → Task 4.
- **Open-vocabulary category mapping with `Other` fallback, decided in extraction** → Task 1 schema + Task 7 prompt (no hardcoded table).
- **extract → compute → FeeBreakdown JSON → existing HTML mock slice** → Tasks 7 → 3–5 → 2 → 10, wired by the CLI in Task 9.
- **TDD, failing test first, frequent commits** → every task.
- **Honesty rails / graceful degradation** → no fee schedule ⇒ building totals only (Task 4); no budget ⇒ `degraded` (Task 5); single year ⇒ bars only, trend ornaments absent by data (Tasks 5 + 10); synthetic committed fixtures, real docs gitignored (Tasks 6, 8).
- **v1.1 deferred** → trend fields (`prior_year_annual`, multi-point `total_fee_series`) exist but stay empty; delta/mover/trend computation and ornaments are NOT built; the mock omits them when inputs are absent.

**Deferred to v1.1 (explicitly out of this plan):** multi-year aggregation (keying budgets across AGM years), delta caps, personal-dollar diffs, per-category sparklines, total-fee-over-time trend, mover flagging (`share moved > 1 point`), budget-vs-actual overlay. Out of scope entirely: owner bands, total-housing-cost frame, Sankey, app UI / MLS / email.
