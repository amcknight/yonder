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
