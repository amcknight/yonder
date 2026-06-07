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
